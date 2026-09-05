from __future__ import annotations

import json
import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.models.owner_day import OWNER_DAY_STATUSES
from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json
from app.services.open_brain_db import database_configured, get_pool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_mapping(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_mapping(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validated_briefing(value: Any) -> dict[str, Any]:
    required = {
        "plain_language_title", "what_it_means", "why_now", "workspace_goal",
        "recommended_next_action", "classification", "current_evidence",
        "unknowns", "decision_options",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise ValueError("a complete owner-day briefing is required")
    if not isinstance(value.get("current_evidence"), list) or not value["current_evidence"]:
        raise ValueError("owner-day briefing requires current evidence")
    return value


def _public_row(row: Any) -> dict[str, Any]:
    result = dict(row)
    for key, value in list(result.items()):
        if isinstance(value, (datetime, date_type)):
            result[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            result[key] = str(value)
    return result


class OwnerDayService:
    """Use durable Open Brain Postgres in production and the canonical local ledger locally."""

    def __init__(self, store: IntegratedSystemStore | None = None) -> None:
        self.store = store
        self._postgres = store is None and database_configured()
        if not self._postgres:
            self.store = store or IntegratedSystemStore()
            self.store.migrate()

    def upsert_session(self, *, owner_calendar_date: str, overview: dict[str, Any]) -> dict[str, Any]:
        date = str(owner_calendar_date or "").strip()
        if len(date) != 10:
            raise ValueError("owner_calendar_date must be YYYY-MM-DD")
        session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:owner-day:{date}"))
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT overview FROM owner_day_sessions WHERE owner_calendar_date=%s FOR UPDATE", (date,))
                existing = cur.fetchone()
                merged = _merge_mapping(dict(existing["overview"]) if existing else {}, overview)
                cur.execute(
                    """INSERT INTO owner_day_sessions(session_id,owner_calendar_date,status,overview)
                    VALUES(%s,%s,'open',%s) ON CONFLICT(owner_calendar_date) DO UPDATE
                    SET overview=excluded.overview,updated_at=NOW() RETURNING *""",
                    (session_id, date, Jsonb(merged)),
                )
                return self._session(cur.fetchone())
        now = _now()
        assert self.store is not None
        with self.store.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute("SELECT overview_json FROM owner_day_sessions WHERE owner_calendar_date=?", (date,)).fetchone()
            prior = json.loads(existing["overview_json"]) if existing else {}
            overview_json = _canonical_json(_merge_mapping(prior, overview))
            c.execute(
                "INSERT INTO owner_day_sessions(session_id,owner_calendar_date,status,overview_json,created_at,updated_at) VALUES(?,?,'open',?,?,?) ON CONFLICT(owner_calendar_date) DO UPDATE SET overview_json=excluded.overview_json,updated_at=excluded.updated_at",
                (session_id, date, overview_json, now, now),
            )
            row = c.execute("SELECT * FROM owner_day_sessions WHERE owner_calendar_date=?", (date,)).fetchone()
            c.execute("COMMIT")
        return self._session(row)

    def get_session(self, owner_calendar_date: str) -> dict[str, Any] | None:
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM owner_day_sessions WHERE owner_calendar_date=%s", (owner_calendar_date,))
                row = cur.fetchone()
        else:
            assert self.store is not None
            with self.store.connection() as c:
                row = c.execute("SELECT * FROM owner_day_sessions WHERE owner_calendar_date=?", (owner_calendar_date,)).fetchone()
        return self._session(row) if row else None

    def add_action(self, **values: Any) -> dict[str, Any]:
        if values["action_id"].strip() == "" or values["workspace_key"].strip() == "":
            raise ValueError("action_id and workspace_key are required")
        briefing = _validated_briefing(values.get("briefing"))
        action_id = values["action_id"].strip()
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """INSERT INTO owner_day_actions(action_id,session_id,workspace_key,title,description,source,briefing,status,next_step)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,'Open / Not reviewed',%s)
                    ON CONFLICT(action_id) DO NOTHING""",
                    (action_id, values["session_id"], values["workspace_key"].strip(), values["title"][:300], values["description"][:2000], Jsonb(values["source"]), Jsonb(briefing), values.get("next_step")),
                )
                cur.execute("SELECT * FROM owner_day_actions WHERE action_id=%s", (action_id,))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("owner-day action persistence failed")
                if str(row["session_id"]) != values["session_id"] or row["source"] != values["source"]:
                    raise ValueError("owner-day action idempotency conflict")
                return self._action(row)
        now = _now()
        source_json = _canonical_json(values["source"])
        assert self.store is not None
        with self.store.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute(
                "INSERT INTO owner_day_actions(action_id,session_id,workspace_key,title,description,source_json,status,next_step,outcome_json,created_at,updated_at,briefing_json) VALUES(?,?,?,?,?,?,'Open / Not reviewed',?,NULL,?,?,?) ON CONFLICT(action_id) DO NOTHING",
                (action_id, values["session_id"], values["workspace_key"].strip(), values["title"][:300], values["description"][:2000], source_json, values.get("next_step"), now, now, _canonical_json(briefing)),
            )
            row = c.execute("SELECT * FROM owner_day_actions WHERE action_id=?", (action_id,)).fetchone()
            if not row:
                raise RuntimeError("owner-day action persistence failed")
            if row["session_id"] != values["session_id"] or row["source_json"] != source_json:
                raise ValueError("owner-day action idempotency conflict")
            c.execute("COMMIT")
        return self._action(row)

    def update_briefing(self, action_id: str, briefing: dict[str, Any]) -> dict[str, Any]:
        briefing = _validated_briefing(briefing)
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute("UPDATE owner_day_actions SET briefing=%s,updated_at=NOW() WHERE action_id=%s RETURNING *", (Jsonb(briefing), action_id))
                row = cur.fetchone()
                if not row:
                    raise KeyError("unknown owner-day action")
                return self._action(row)
        assert self.store is not None
        with self.store.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT action_id FROM owner_day_actions WHERE action_id=?", (action_id,)).fetchone()
            if not row:
                raise KeyError("unknown owner-day action")
            c.execute("UPDATE owner_day_actions SET briefing_json=?,updated_at=? WHERE action_id=?", (_canonical_json(briefing), _now(), action_id))
            updated = c.execute("SELECT * FROM owner_day_actions WHERE action_id=?", (action_id,)).fetchone()
            c.execute("COMMIT")
        return self._action(updated)

    def update_action(self, action_id: str, *, status: str, next_step: str | None, outcome: dict[str, Any] | None, idempotency_key: str) -> dict[str, Any]:
        if status not in OWNER_DAY_STATUSES:
            raise ValueError("unknown owner-day status")
        if status == "Completed":
            required = {"what_happened", "involved", "result", "evidence_basis"}
            if not outcome or not required.issubset(outcome) or outcome.get("evidence_basis") not in {"provider_verified", "system_verified", "owner_attested"}:
                raise ValueError("Completed requires a bounded outcome and evidence_basis")
        event_key = str(idempotency_key or "").strip()
        if not event_key or len(event_key) > 200:
            raise ValueError("idempotency_key is required")
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM owner_day_actions WHERE action_id=%s FOR UPDATE", (action_id,))
                row = cur.fetchone()
                if not row:
                    raise KeyError("unknown owner-day action")
                payload = self._event_payload(row, status, next_step, outcome)
                cur.execute("SELECT payload FROM owner_day_events WHERE idempotency_key=%s", (event_key,))
                existing = cur.fetchone()
                if existing:
                    prior = existing["payload"]
                    if prior.get("action_id") != action_id or prior.get("status") != status:
                        raise ValueError("owner-day transition idempotency conflict")
                    return self._action(row)
                provenance = {"source": "start-my-day", "source_action_id": action_id, "prior_status": row["status"]}
                cur.execute("UPDATE owner_day_actions SET status=%s,next_step=%s,outcome=%s,updated_at=NOW() WHERE action_id=%s RETURNING *", (status, next_step, Jsonb(outcome) if outcome else None, action_id))
                updated = cur.fetchone()
                cur.execute("INSERT INTO owner_day_events(event_id,action_id,event_type,payload,provenance,idempotency_key) VALUES(%s,%s,'owner.day_action_updated',%s,%s,%s)", (event_id, action_id, Jsonb(payload), Jsonb(provenance), event_key))
                return self._action(updated)
        assert self.store is not None
        with self.store.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM owner_day_actions WHERE action_id=?", (action_id,)).fetchone()
            if not row:
                raise KeyError("unknown owner-day action")
            payload = self._event_payload(row, status, next_step, outcome)
            existing = c.execute("SELECT payload_json FROM system_events WHERE idempotency_key=?", (event_key,)).fetchone()
            if existing:
                prior = json.loads(existing["payload_json"])
                if prior.get("action_id") != action_id or prior.get("status") != status:
                    raise ValueError("owner-day transition idempotency conflict")
                c.execute("COMMIT")
                return self._action(row)
            now = _now()
            c.execute("UPDATE owner_day_actions SET status=?,next_step=?,outcome_json=?,updated_at=? WHERE action_id=?", (status, next_step, _canonical_json(outcome) if outcome else None, now, action_id))
            c.execute(
                "INSERT INTO system_events(event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key) VALUES(?,?,?,?,?,'owner_day',?,?,'[]',?)",
                (event_id, "owner.day_action_updated", "owner_day_action", action_id, now, _canonical_json(payload), _canonical_json({"source": "start-my-day", "source_action_id": action_id, "prior_status": row["status"]}), event_key),
            )
            updated = c.execute("SELECT * FROM owner_day_actions WHERE action_id=?", (action_id,)).fetchone()
            c.execute("COMMIT")
        return self._action(updated)

    def list_actions(self, session_id: str) -> list[dict[str, Any]]:
        ordering = "CASE WHEN status='Open / Not reviewed' THEN 0 ELSE 1 END, updated_at, action_id"
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute(f"SELECT * FROM owner_day_actions WHERE session_id=%s ORDER BY {ordering}", (session_id,))
                rows = cur.fetchall()
        else:
            assert self.store is not None
            with self.store.connection() as c:
                rows = c.execute(f"SELECT * FROM owner_day_actions WHERE session_id=? ORDER BY {ordering}", (session_id,)).fetchall()
        return [self._action(row) for row in rows]

    def list_events(self, limit: int = 500) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        if self._postgres:
            with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM owner_day_events ORDER BY occurred_at DESC,event_id DESC LIMIT %s", (bounded,))
                return [self._event(row) for row in reversed(cur.fetchall())]
        assert self.store is not None
        with self.store.connection() as c:
            rows = c.execute("SELECT * FROM system_events WHERE event_type='owner.day_action_updated' ORDER BY occurred_at DESC,event_id DESC LIMIT ?", (bounded,)).fetchall()
        return [self._event(row) for row in reversed(rows)]

    @staticmethod
    def _event_payload(row: Any, status: str, next_step: str | None, outcome: dict[str, Any] | None) -> dict[str, Any]:
        source = dict(row)
        briefing = source.get("briefing")
        if briefing is None and source.get("briefing_json"):
            briefing = json.loads(source["briefing_json"])
        return {"action_id": source["action_id"], "session_id": str(source["session_id"]), "workspace_key": source["workspace_key"], "status": status, "next_step": next_step, "outcome": outcome, "briefing": briefing}

    @staticmethod
    def _session(row: Any) -> dict[str, Any]:
        result = _public_row(row)
        if "overview_json" in result:
            result["overview"] = json.loads(result.pop("overview_json"))
        return result

    @staticmethod
    def _action(row: Any) -> dict[str, Any]:
        result = _public_row(row)
        if "source_json" in result:
            result["source"] = json.loads(result.pop("source_json"))
        if "briefing_json" in result:
            raw = result.pop("briefing_json")
            result["briefing"] = json.loads(raw) if raw else None
        if "outcome_json" in result:
            raw = result.pop("outcome_json")
            result["outcome"] = json.loads(raw) if raw else None
        return result

    @staticmethod
    def _event(row: Any) -> dict[str, Any]:
        result = _public_row(row)
        if "payload_json" in result:
            result["payload"] = json.loads(result.pop("payload_json"))
            result["provenance"] = json.loads(result.pop("provenance_json"))
            result["action_id"] = result.get("aggregate_id")
        return result
