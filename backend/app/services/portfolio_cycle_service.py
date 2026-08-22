from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


ACTIVE_WORKSPACE_STATUSES = frozenset({"live", "standing_up"})
CONCLUSION_KINDS = frozenset({"conclusion", "healthy_no_change"})
PROVENANCE_KINDS = frozenset({"independent_agent", "deterministic_policy", "synthesized_lens"})


class PortfolioCycleConflict(ValueError):
    pass


def active_portfolio_workspaces(registry_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> list[str]:
    return sorted(
        {
            str(entry.get("key") or "").strip()
            for entry in registry_entries
            if entry.get("portfolio_visible") is True
            and str(entry.get("status") or "").strip() in ACTIVE_WORKSPACE_STATUSES
            and str(entry.get("key") or "").strip()
        }
    )


class PortfolioCycleService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def start_cycle(
        self,
        *,
        portfolio_cycle_id: str,
        cycle_date: date,
        expected_workspaces: list[str],
        readiness_id: str,
        morning_brief_ref: str | None = None,
    ) -> dict[str, Any]:
        self.store.migrate()
        expected = sorted({item.strip() for item in expected_workspaces if item.strip()})
        if not expected:
            raise ValueError("portfolio cycle requires at least one active workspace")
        now = _utcnow()
        idempotency_key = f"portfolio-cycle:{portfolio_cycle_id}"
        metadata = {
            "expected_workspaces": expected,
            "readiness_id": readiness_id,
            "morning_brief_ref": morning_brief_ref,
        }
        with self.store.connection() as connection:
            readiness = connection.execute("SELECT * FROM readiness_receipts WHERE readiness_id=?", (readiness_id,)).fetchone()
            if not readiness:
                raise ValueError("portfolio cycle requires a persisted memory readiness receipt")
            initial_status = "waiting" if readiness["status"] == "ready" else "degraded"
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO portfolio_cycles(
                        portfolio_cycle_id,cycle_date,status,expected_workspace_count,created_at,idempotency_key,metadata_json
                    ) VALUES (?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (portfolio_cycle_id, cycle_date.isoformat(), initial_status, len(expected), now, idempotency_key, _canonical_json(metadata)),
                )
                row = connection.execute("SELECT * FROM portfolio_cycles WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if not row or json.loads(row["metadata_json"]).get("expected_workspaces") != expected:
                    raise PortfolioCycleConflict("portfolio cycle idempotency conflict")
                self._append_event(
                    connection,
                    event_type="portfolio_cycle.started",
                    aggregate_type="portfolio_cycle",
                    aggregate_id=portfolio_cycle_id,
                    payload={"status": initial_status, "expected_workspace_count": len(expected)},
                    provenance={"readiness_id": readiness_id},
                    idempotency_key=f"portfolio-cycle-started:{portfolio_cycle_id}",
                )
                connection.execute("COMMIT")
                return dict(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def record_workspace_conclusion(
        self,
        *,
        portfolio_cycle_id: str,
        workspace_key: str,
        conclusion_kind: str,
        provenance_kind: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if conclusion_kind not in CONCLUSION_KINDS:
            raise ValueError("invalid workspace conclusion kind")
        if provenance_kind not in PROVENANCE_KINDS:
            raise ValueError("invalid workspace conclusion provenance")
        workspace_key = workspace_key.strip()
        now = _utcnow()
        with self.store.connection() as connection:
            cycle = connection.execute("SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()
            if not cycle:
                raise ValueError("unknown portfolio cycle")
            expected = json.loads(cycle["metadata_json"]).get("expected_workspaces") or []
            if workspace_key not in expected:
                raise ValueError("workspace is not active in this portfolio cycle")
            conclusion_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:workspace-conclusion:{idempotency_key}"))
            normalized_payload = self._normalize_conclusion_payload(payload)
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO workspace_conclusions(
                        conclusion_id,portfolio_cycle_id,workspace_key,conclusion_kind,provenance_kind,
                        payload_json,created_at,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        conclusion_id,
                        portfolio_cycle_id,
                        workspace_key,
                        conclusion_kind,
                        provenance_kind,
                        _canonical_json(normalized_payload),
                        now,
                        idempotency_key,
                    ),
                )
                row = connection.execute("SELECT * FROM workspace_conclusions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if not row or row["portfolio_cycle_id"] != portfolio_cycle_id or row["workspace_key"] != workspace_key:
                    raise PortfolioCycleConflict("workspace conclusion idempotency conflict")
                self._append_event(
                    connection,
                    event_type="workspace.concluded",
                    aggregate_type="workspace_conclusion",
                    aggregate_id=row["conclusion_id"],
                    payload={"portfolio_cycle_id": portfolio_cycle_id, "workspace_key": workspace_key, "conclusion_kind": conclusion_kind},
                    provenance={"provenance_kind": provenance_kind},
                    idempotency_key=f"workspace-concluded:{idempotency_key}",
                )
                count = connection.execute("SELECT COUNT(*) FROM workspace_conclusions WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()[0]
                new_status = "ready" if count == cycle["expected_workspace_count"] and cycle["status"] != "degraded" else cycle["status"]
                connection.execute("UPDATE portfolio_cycles SET status=? WHERE portfolio_cycle_id=?", (new_status, portfolio_cycle_id))
                connection.execute("COMMIT")
                return dict(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def conclude_ops(
        self,
        *,
        portfolio_cycle_id: str,
        system_health: Mapping[str, Any],
        ops_decisions: list[Mapping[str, Any]] | None = None,
        owner_calls: list[Mapping[str, Any]] | None = None,
        recommended_next_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.store.connection() as connection:
            cycle = connection.execute("SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()
            if not cycle:
                raise ValueError("unknown portfolio cycle")
            existing = connection.execute("SELECT * FROM ops_conclusions WHERE portfolio_cycle_id=?", (portfolio_cycle_id,)).fetchone()
            if existing and existing["status"] == "complete":
                return self._ops_response(dict(existing))
            metadata = json.loads(cycle["metadata_json"])
            expected = metadata.get("expected_workspaces") or []
            rows = connection.execute("SELECT * FROM workspace_conclusions WHERE portfolio_cycle_id=? ORDER BY workspace_key", (portfolio_cycle_id,)).fetchall()
            by_workspace = {row["workspace_key"]: row for row in rows}
            missing = sorted(set(expected) - set(by_workspace))
            readiness = connection.execute("SELECT * FROM readiness_receipts WHERE readiness_id=?", (metadata.get("readiness_id"),)).fetchone()
            readiness_payload = json.loads(readiness["recall_probe_json"]) if readiness else {}
            degraded_warnings: list[str] = []
            if readiness_payload.get("status") != "ready":
                degraded_warnings.append(
                    f"Memory readiness is degraded at {readiness_payload.get('failed_component') or 'unknown component'}; using last verified memory from {readiness_payload.get('last_verified_memory_at') or 'unknown time'}."
                )
            if missing:
                degraded_warnings.append(f"Missing workspace conclusions: {', '.join(missing)}.")
            unhealthy = sorted(
                key
                for key, value in system_health.items()
                if str(value).strip().lower() in {"failed", "degraded", "not_verified", "unhealthy"}
                or str(value).strip().lower().startswith("failed:")
            )
            if unhealthy:
                degraded_warnings.append(f"Unhealthy or unverified subsystems: {', '.join(unhealthy)}.")
            workspace_updates = []
            blockers: list[dict[str, Any]] = []
            urgent: list[dict[str, Any]] = []
            workspace_decisions: list[dict[str, Any]] = []
            underway: list[dict[str, Any]] = []
            completed: list[dict[str, Any]] = []
            evidence_links: list[dict[str, Any]] = []
            for key in expected:
                row = by_workspace.get(key)
                if not row:
                    workspace_updates.append({"workspace_key": key, "state": "missing", "summary": "No conclusion receipt received."})
                    continue
                payload = json.loads(row["payload_json"])
                workspace_updates.append({"workspace_key": key, "state": row["conclusion_kind"], "summary": payload["summary"], "provenance_kind": row["provenance_kind"]})
                blockers.extend({"workspace_key": key, **item} for item in payload["blockers"])
                urgent.extend({"workspace_key": key, **item} for item in payload["urgent_escalations"])
                workspace_decisions.extend({"workspace_key": key, **item} for item in payload["decisions"])
                underway.extend({"workspace_key": key, **item} for item in payload["work_underway"])
                completed.extend({"workspace_key": key, **item} for item in payload["completed_work"])
                evidence_links.extend({"workspace_key": key, **item} for item in payload["evidence_links"])
            status = "degraded" if degraded_warnings else "complete"
            final_payload = {
                "schema_version": "ops_standup_summary_conclusion/v1",
                "portfolio_cycle_id": portfolio_cycle_id,
                "cycle_date": cycle["cycle_date"],
                "status": status,
                "workspace_updates": workspace_updates,
                "ai_clone_process_updates": {
                    "memory_readiness": readiness_payload,
                    "morning_brief_ref": metadata.get("morning_brief_ref"),
                },
                "endpoint_and_subsystem_health": dict(system_health),
                "work_underway": underway,
                "completed_work": completed,
                "blockers": blockers,
                "urgent_escalations": urgent,
                "workspace_decisions": workspace_decisions,
                "ops_decisions": [dict(item) for item in ops_decisions or []],
                "owner_calls": [dict(item) for item in owner_calls or []],
                "degraded_system_warnings": degraded_warnings,
                "supporting_evidence_links": evidence_links,
                "recommended_next_actions": [item.strip() for item in recommended_next_actions or [] if item.strip()],
            }
            ops_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:ops-conclusion:{portfolio_cycle_id}"))
            now = _utcnow()
            final_payload_json = _canonical_json(final_payload)
            if existing and existing["status"] == status and existing["payload_json"] == final_payload_json:
                return self._ops_response(dict(existing))
            connection.execute("BEGIN IMMEDIATE")
            try:
                if existing:
                    connection.execute(
                        """UPDATE ops_conclusions SET payload_json=?,status=?,created_at=?
                        WHERE ops_conclusion_id=? AND status!='complete'""",
                        (final_payload_json, status, now, existing["ops_conclusion_id"]),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0] != 1:
                        raise PortfolioCycleConflict("Ops conclusion changed before repair")
                    ops_id = existing["ops_conclusion_id"]
                else:
                    connection.execute(
                        """INSERT INTO ops_conclusions(
                            ops_conclusion_id,portfolio_cycle_id,payload_json,status,created_at,idempotency_key
                        ) VALUES (?,?,?,?,?,?)""",
                        (ops_id, portfolio_cycle_id, final_payload_json, status, now, f"ops-conclusion:{portfolio_cycle_id}"),
                    )
                attempt_number = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM ops_conclusion_attempts WHERE ops_conclusion_id=?", (ops_id,)
                    ).fetchone()[0]
                ) + 1
                attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:ops-attempt:{ops_id}:{attempt_number}"))
                connection.execute(
                    """INSERT INTO ops_conclusion_attempts(
                        attempt_id,ops_conclusion_id,attempt_number,payload_json,status,created_at
                    ) VALUES (?,?,?,?,?,?)""",
                    (attempt_id, ops_id, attempt_number, final_payload_json, status, now),
                )
                connection.execute(
                    "UPDATE portfolio_cycles SET status=?,completed_at=? WHERE portfolio_cycle_id=?",
                    (status, now, portfolio_cycle_id),
                )
                self._append_event(
                    connection,
                    event_type="ops.concluded" if attempt_number == 1 else "ops.reconcluded",
                    aggregate_type="ops_conclusion",
                    aggregate_id=ops_id,
                    payload={"portfolio_cycle_id": portfolio_cycle_id, "status": status, "missing_workspaces": missing, "attempt_number": attempt_number},
                    provenance={"workspace_conclusion_ids": [row["conclusion_id"] for row in rows]},
                    idempotency_key=f"ops-concluded:{portfolio_cycle_id}:attempt:{attempt_number}",
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return self._ops_response(
                dict(connection.execute("SELECT * FROM ops_conclusions WHERE ops_conclusion_id=?", (ops_id,)).fetchone())
            )

    @staticmethod
    def _normalize_conclusion_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        summary = " ".join(str(payload.get("summary") or "").split()).strip()
        if not summary:
            raise ValueError("workspace conclusion summary is required")
        normalized = {"summary": summary[:1000]}
        for key in ("work_underway", "completed_work", "blockers", "urgent_escalations", "decisions", "evidence_links", "recommended_next_actions"):
            raw_items = payload.get(key) or []
            if not isinstance(raw_items, list):
                raise ValueError(f"{key} must be a list")
            items = []
            for raw in raw_items[:100]:
                if isinstance(raw, dict):
                    item = {str(k): v for k, v in raw.items() if isinstance(v, (str, int, float, bool)) or v is None}
                else:
                    item = {"summary": " ".join(str(raw).split())[:500]}
                route = str(item.get("route") or "").strip().lower()
                if route in {"", "uncertain"}:
                    item["route"] = "ops"
                items.append(item)
            normalized[key] = items
        return normalized

    @staticmethod
    def _append_event(
        connection: Any,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        provenance: Mapping[str, Any],
        idempotency_key: str,
    ) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,
                provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,'portfolio_cycle',?,?, '[]',?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (event_id, event_type, aggregate_type, aggregate_id, _utcnow(), _canonical_json(dict(payload)), _canonical_json(dict(provenance)), idempotency_key),
        )

    @staticmethod
    def _ops_response(row: dict[str, Any]) -> dict[str, Any]:
        return {**json.loads(row["payload_json"]), "ops_conclusion_id": row["ops_conclusion_id"], "created_at": row["created_at"]}
