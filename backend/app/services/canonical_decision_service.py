from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


ALLOWED_TRANSITIONS = {
    "open": {"in_session", "resolved", "canceled", "blocked", "superseded"},
    "in_session": {"open", "resolved", "canceled", "blocked", "superseded"},
    "blocked": {"open", "in_session", "resolved", "canceled", "superseded"},
    "resolved": set(), "canceled": set(), "superseded": set(),
}
TERMINAL_STATUSES = frozenset({"resolved", "canceled", "superseded"})
SESSION_SURFACE = "decision_session"
KNOWN_ROUTES = frozenset(
    {
        "ops",
        "workspace",
        "content",
        "feezie-os",
        "fusion-os",
        "easyoutfitapp",
        "ai-swag-store",
        "agc",
        "work-life-tools",
    }
)


class DecisionConflict(ValueError):
    pass


class CanonicalDecisionService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store
        self.store.migrate()

    @staticmethod
    def _normalized_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        route = " ".join(str(normalized.get("route") or "").split()).strip().lower()
        normalized["route"] = route if route in KNOWN_ROUTES else "ops"
        mode = " ".join(str(normalized.get("interaction_mode") or normalized.get("complexity") or "simple").split()).strip().lower()
        normalized["interaction_mode"] = "complex" if mode == "complex" else "simple"
        normalized.pop("complexity", None)
        return normalized

    def create(self, *, decision_type: str, title: str, payload: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        title = " ".join(title.split()).strip()
        if not title:
            raise ValueError("decision title is required")
        if len(title) > 300:
            raise ValueError("decision title exceeds 300 characters")
        decision_type = " ".join(decision_type.split()).strip()
        if not decision_type:
            raise ValueError("decision type is required")
        if len(decision_type) > 120:
            raise ValueError("decision type exceeds 120 characters")
        idempotency_key = " ".join(str(idempotency_key or "").split()).strip()
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("bounded decision idempotency key is required")
        payload_json = _canonical_json(self._normalized_payload(payload))
        decision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:decision:{idempotency_key}"))
        now = _utcnow()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO decision_records(decision_id,decision_type,status,title,payload_json,state_version,created_at,updated_at,idempotency_key) VALUES (?,?, 'open',?,?,1,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING",
                    (decision_id, decision_type, title[:300], payload_json, now, now, idempotency_key),
                )
                row = connection.execute("SELECT * FROM decision_records WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if (
                    not row
                    or row["title"] != title[:300]
                    or row["decision_type"] != decision_type
                    or row["payload_json"] != payload_json
                ):
                    raise DecisionConflict("decision idempotency conflict")
                self._event(
                    connection,
                    row["decision_id"],
                    "decision.created",
                    {"status": "open", "state_version": 1, "decision_type": decision_type},
                    f"decision-created:{idempotency_key}",
                )
                connection.execute("COMMIT")
                return self._response(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def link_surface(self, *, decision_id: str, surface: str, external_ref: str) -> dict[str, Any]:
        surface = " ".join(surface.split()).strip()
        external_ref = " ".join(external_ref.split()).strip()
        if not surface or not external_ref:
            raise ValueError("decision surface and external reference are required")
        if len(surface) > 100 or len(external_ref) > 300:
            raise ValueError("decision surface links must be bounded")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if not connection.execute("SELECT 1 FROM decision_records WHERE decision_id=?", (decision_id,)).fetchone():
                    raise KeyError("unknown decision")
                connection.execute(
                    "INSERT INTO decision_links(decision_id,surface,external_ref) VALUES (?,?,?) ON CONFLICT DO NOTHING",
                    (decision_id, surface, external_ref),
                )
                self._event(
                    connection,
                    decision_id,
                    "decision.surface_linked",
                    {"surface": surface, "external_ref": external_ref},
                    f"decision-link:{decision_id}:{surface}:{external_ref}",
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return self.get(decision_id)

    def begin_session(self, *, decision_id: str, expected_version: int) -> dict[str, Any]:
        """Open exactly one shared session for a complex decision.

        The status transition, shared-session link, and lifecycle events commit
        together. Replays with the original version return the existing session.
        """

        if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 1:
            raise ValueError("expected_version must be a positive integer")
        session_ref = f"session:{decision_id}"
        event_key = f"decision-transition:{decision_id}:{expected_version + 1}"
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT * FROM decision_records WHERE decision_id=?",
                    (decision_id,),
                ).fetchone()
                if not row:
                    raise KeyError("unknown decision")
                payload = json.loads(row["payload_json"])
                if payload.get("interaction_mode") != "complex":
                    raise DecisionConflict("simple decisions are resolved inline")
                session_exists = connection.execute(
                    "SELECT 1 FROM decision_links WHERE decision_id=? AND surface=? AND external_ref=?",
                    (decision_id, SESSION_SURFACE, session_ref),
                ).fetchone()
                if row["state_version"] != expected_version:
                    if (
                        row["state_version"] == expected_version + 1
                        and row["status"] == "in_session"
                        and session_exists
                        and connection.execute(
                            "SELECT 1 FROM system_events WHERE idempotency_key=?",
                            (event_key,),
                        ).fetchone()
                    ):
                        connection.execute("COMMIT")
                        return self._response_with_links(connection, row)
                    raise DecisionConflict("stale decision version")
                if "in_session" not in ALLOWED_TRANSITIONS.get(row["status"], set()):
                    raise DecisionConflict(f"invalid decision transition {row['status']} -> in_session")
                now = _utcnow()
                cursor = connection.execute(
                    "UPDATE decision_records SET status='in_session',state_version=state_version+1,updated_at=?,resolved_at=NULL WHERE decision_id=? AND state_version=?",
                    (now, decision_id, expected_version),
                )
                if cursor.rowcount != 1:
                    raise DecisionConflict("decision changed before mutation")
                connection.execute(
                    "INSERT INTO decision_links(decision_id,surface,external_ref) VALUES (?,?,?) ON CONFLICT DO NOTHING",
                    (decision_id, SESSION_SURFACE, session_ref),
                )
                self._event(
                    connection,
                    decision_id,
                    "decision.transitioned",
                    {"from": row["status"], "to": "in_session", "state_version": expected_version + 1, "resolution_recorded": False},
                    event_key,
                )
                self._event(
                    connection,
                    decision_id,
                    "decision.session_opened",
                    {"session_ref": session_ref, "state_version": expected_version + 1},
                    f"decision-session:{decision_id}",
                )
                updated = connection.execute(
                    "SELECT * FROM decision_records WHERE decision_id=?",
                    (decision_id,),
                ).fetchone()
                response = self._response_with_links(connection, updated)
                connection.execute("COMMIT")
                return response
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def transition(self, *, decision_id: str, expected_version: int, new_status: str, resolution: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 1:
            raise ValueError("expected_version must be a positive integer")
        new_status = " ".join(str(new_status or "").split()).strip().lower()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute("SELECT * FROM decision_records WHERE decision_id=?", (decision_id,)).fetchone()
                if not row:
                    raise KeyError("unknown decision")
                if row["state_version"] != expected_version:
                    current_payload = json.loads(row["payload_json"])
                    replay_resolution = current_payload.get("resolution")
                    expected_resolution = dict(resolution) if resolution else None
                    event_key = f"decision-transition:{decision_id}:{expected_version + 1}"
                    if (
                        row["state_version"] == expected_version + 1
                        and row["status"] == new_status
                        and replay_resolution == expected_resolution
                        and connection.execute(
                            "SELECT 1 FROM system_events WHERE idempotency_key=?",
                            (event_key,),
                        ).fetchone()
                    ):
                        connection.execute("COMMIT")
                        return self._response(row)
                    raise DecisionConflict("stale decision version")
                if new_status == "in_session":
                    raise DecisionConflict("decision sessions must be opened through begin_session")
                if new_status not in ALLOWED_TRANSITIONS.get(row["status"], set()):
                    raise DecisionConflict(f"invalid decision transition {row['status']} -> {new_status}")
                current_payload = json.loads(row["payload_json"])
                if (
                    new_status == "resolved"
                    and current_payload.get("interaction_mode") == "complex"
                    and row["status"] != "in_session"
                ):
                    raise DecisionConflict("complex decisions require the shared session before resolution")
                if new_status == "resolved" and not resolution:
                    raise DecisionConflict("resolved decisions require a canonical resolution")
                if new_status != "resolved" and resolution:
                    raise DecisionConflict("resolution payload is valid only for a resolved decision")
                payload = current_payload
                if resolution:
                    payload["resolution"] = dict(resolution)
                now = _utcnow()
                resolved_at = now if new_status in TERMINAL_STATUSES else None
                cursor = connection.execute(
                    "UPDATE decision_records SET status=?,payload_json=?,state_version=state_version+1,updated_at=?,resolved_at=? WHERE decision_id=? AND state_version=?",
                    (new_status, _canonical_json(payload), now, resolved_at, decision_id, expected_version),
                )
                if cursor.rowcount != 1:
                    raise DecisionConflict("decision changed before mutation")
                self._event(
                    connection,
                    decision_id,
                    "decision.transitioned",
                    {
                        "from": row["status"],
                        "to": new_status,
                        "state_version": expected_version + 1,
                        "resolution_recorded": bool(resolution),
                        "decision_type": row["decision_type"],
                        "title": row["title"],
                        "route": str(payload.get("route") or "ops"),
                        **(
                            {"resolution": self._bounded_resolution(resolution)}
                            if resolution
                            else {}
                        ),
                    },
                    f"decision-transition:{decision_id}:{expected_version + 1}",
                )
                updated = connection.execute("SELECT * FROM decision_records WHERE decision_id=?", (decision_id,)).fetchone()
                connection.execute("COMMIT")
                return self._response(updated)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def get(self, decision_id: str) -> dict[str, Any]:
        with self.store.connection() as connection:
            row = connection.execute("SELECT * FROM decision_records WHERE decision_id=?", (decision_id,)).fetchone()
            if not row:
                raise KeyError("unknown decision")
            return self._response_with_links(connection, row)

    def list(self, *, include_terminal: bool = True, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(500, int(limit)))
        where = "" if include_terminal else "WHERE status NOT IN ('resolved','canceled','superseded')"
        with self.store.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM decision_records {where} ORDER BY updated_at DESC,decision_id LIMIT ?",
                (bounded_limit,),
            ).fetchall()
            return [self._response_with_links(connection, row) for row in rows]

    @classmethod
    def _response_with_links(cls, connection: Any, row: Any) -> dict[str, Any]:
        links = connection.execute(
            "SELECT surface,external_ref FROM decision_links WHERE decision_id=? ORDER BY surface,external_ref",
            (row["decision_id"],),
        ).fetchall()
        response = cls._response(row)
        response["links"] = [dict(item) for item in links]
        return response

    @staticmethod
    def _response(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        result.pop("idempotency_key", None)
        return result

    @staticmethod
    def _bounded_resolution(resolution: Mapping[str, Any]) -> dict[str, str]:
        """Keep the exact owner choice available to Dream without copying arbitrary payloads."""

        choice = " ".join(str(resolution.get("choice") or "").split()).strip()
        return {"choice": choice[:1000]} if choice else {}

    @staticmethod
    def _event(connection: Any, decision_id: str, event_type: str, payload: Mapping[str, Any], idempotency_key: str) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))
        connection.execute(
            "INSERT INTO system_events(event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key) VALUES (?,?, 'decision',?,?,'decision_service',?,?,'[]',?) ON CONFLICT(idempotency_key) DO NOTHING",
            (
                event_id,
                event_type,
                decision_id,
                _utcnow(),
                _canonical_json(dict(payload)),
                _canonical_json({"authority": "canonical_decision_service/v1"}),
                idempotency_key,
            ),
        )
