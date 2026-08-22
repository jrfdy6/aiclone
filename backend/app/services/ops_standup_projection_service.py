from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from app.services.integrated_content_projection_service import _decision_summary
from app.services.integrated_system_store import IntegratedSystemStore


PROJECTION_SCHEMA = "ops_standup_summary_conclusion/v1"
SNAPSHOT_TYPE = "ops_standup_summary_conclusion"
WORKSPACE_KEY = "shared_ops"
MAX_ITEMS = 100
MAX_BYTES = 256 * 1024


class OpsStandupProjectionError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return text


def _bounded_items(value: Any, *, evidence: bool = False) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            raw = {"summary": str(raw)}
        item: dict[str, Any] = {}
        for key, cell in raw.items():
            key = str(key)
            if key in {"local_path", "absolute_path", "payload", "private_notes", "raw_body", "transcript"}:
                continue
            if evidence and key in {"url", "href", "source_url"}:
                safe = _safe_url(cell)
                if safe:
                    item[key] = safe
            elif isinstance(cell, bool):
                item[key] = cell
            elif isinstance(cell, (int, float)):
                item[key] = cell
            elif cell is None:
                item[key] = None
            else:
                item[key] = " ".join(str(cell).split())[:1000]
        result.append(item)
        if len(result) >= MAX_ITEMS:
            break
    return result


def _bounded_mapping(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if not isinstance(value, dict) or depth > 2:
        return {}
    result: dict[str, Any] = {}
    for raw_key, cell in list(value.items())[:MAX_ITEMS]:
        key = str(raw_key)[:120]
        if key in {"local_path", "absolute_path", "payload", "private_notes", "raw_body", "transcript"}:
            continue
        if isinstance(cell, bool) or isinstance(cell, (int, float)) or cell is None:
            result[key] = cell
        elif isinstance(cell, str):
            result[key] = " ".join(cell.split())[:1000]
        elif isinstance(cell, dict):
            result[key] = _bounded_mapping(cell, depth=depth + 1)
        elif isinstance(cell, list):
            result[key] = [" ".join(str(item).split())[:300] for item in cell[:20] if not isinstance(item, (dict, list))]
    return result


def build_ops_standup_projection(*, store: IntegratedSystemStore | None = None) -> dict[str, Any]:
    store = store or IntegratedSystemStore()
    store.migrate()
    with store.connection() as connection:
        row = connection.execute(
            "SELECT * FROM ops_conclusions ORDER BY created_at DESC,ops_conclusion_id DESC LIMIT 1"
        ).fetchone()
        decision_rows = connection.execute(
            "SELECT * FROM decision_records ORDER BY updated_at DESC,decision_id LIMIT ?",
            (MAX_ITEMS,),
        ).fetchall()
        canonical_decisions = []
        for decision in decision_rows:
            links = [
                dict(item)
                for item in connection.execute(
                    "SELECT surface,external_ref FROM decision_links WHERE decision_id=? ORDER BY surface,external_ref",
                    (decision["decision_id"],),
                )
            ]
            canonical_decisions.append(_decision_summary(decision, links))
    if not row:
        return unavailable_ops_standup_projection(
            "ops_conclusion_not_generated",
            state="empty",
            canonical_decisions=canonical_decisions,
        )
    payload = json.loads(row["payload_json"])
    projected = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _now_iso(),
        "state": "degraded" if payload.get("status") == "degraded" else "ready",
        "reason_codes": ["ops_cycle_degraded"] if payload.get("status") == "degraded" else [],
        "ops_conclusion_id": row["ops_conclusion_id"],
        "portfolio_cycle_id": payload.get("portfolio_cycle_id"),
        "cycle_date": payload.get("cycle_date"),
        "status": payload.get("status"),
        "workspace_updates": _bounded_items(payload.get("workspace_updates")),
        "ai_clone_process_updates": _bounded_mapping(payload.get("ai_clone_process_updates")),
        "endpoint_and_subsystem_health": _bounded_mapping(payload.get("endpoint_and_subsystem_health")),
        "work_underway": _bounded_items(payload.get("work_underway")),
        "completed_work": _bounded_items(payload.get("completed_work")),
        "blockers": _bounded_items(payload.get("blockers")),
        "urgent_escalations": _bounded_items(payload.get("urgent_escalations")),
        "workspace_decisions": _bounded_items(payload.get("workspace_decisions")),
        "ops_decisions": _bounded_items(payload.get("ops_decisions")),
        "owner_calls": _bounded_items(payload.get("owner_calls")),
        "canonical_decisions": canonical_decisions,
        "degraded_system_warnings": [" ".join(str(item).split())[:1000] for item in payload.get("degraded_system_warnings", [])[:MAX_ITEMS]],
        "supporting_evidence_links": _bounded_items(payload.get("supporting_evidence_links"), evidence=True),
        "recommended_next_actions": [" ".join(str(item).split())[:1000] for item in payload.get("recommended_next_actions", [])[:MAX_ITEMS]],
        "data_policy": {
            "canonical_authority": "mac_local_sql",
            "railway_role": "authenticated_bounded_ops_projection",
            "private_bodies_included": False,
        },
    }
    return validate_ops_standup_projection(projected)


def validate_ops_standup_projection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != PROJECTION_SCHEMA:
        raise OpsStandupProjectionError("invalid Ops projection schema")
    allowed = {
        "schema_version", "generated_at", "state", "reason_codes", "ops_conclusion_id", "portfolio_cycle_id",
        "cycle_date", "status", "workspace_updates", "ai_clone_process_updates", "endpoint_and_subsystem_health",
        "work_underway", "completed_work", "blockers", "urgent_escalations", "workspace_decisions", "ops_decisions",
        "owner_calls", "canonical_decisions", "degraded_system_warnings", "supporting_evidence_links", "recommended_next_actions", "data_policy",
    }
    if set(payload) - allowed or payload.get("state") not in {"ready", "empty", "degraded", "error"}:
        raise OpsStandupProjectionError("invalid Ops projection envelope")
    try:
        generated_at = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpsStandupProjectionError("invalid generated_at") from exc
    if generated_at.tzinfo is None:
        raise OpsStandupProjectionError("generated_at must be timezone aware")
    for key in ("workspace_updates", "work_underway", "completed_work", "blockers", "urgent_escalations", "workspace_decisions", "ops_decisions", "owner_calls", "supporting_evidence_links"):
        if not isinstance(payload.get(key), list) or len(payload[key]) > MAX_ITEMS:
            raise OpsStandupProjectionError(f"invalid {key}")
    canonical_decisions = payload.get("canonical_decisions")
    if not isinstance(canonical_decisions, list) or len(canonical_decisions) > MAX_ITEMS:
        raise OpsStandupProjectionError("invalid canonical_decisions")
    decision_fields = {
        "decision_id", "decision_type", "status", "title", "state_version", "interaction_mode",
        "route", "resolution", "session_ref", "updated_at", "links",
    }
    if any(
        not isinstance(item, dict)
        or set(item) != decision_fields
        or item.get("status") not in {"open", "in_session", "resolved", "superseded", "canceled", "blocked"}
        or item.get("interaction_mode") not in {"simple", "complex"}
        or item.get("route") not in {"ops", "workspace", "content", "feezie-os"}
        or not isinstance(item.get("state_version"), int)
        or not isinstance(item.get("links"), list)
        for item in canonical_decisions
    ):
        raise OpsStandupProjectionError("invalid canonical decision projection")
    expected_policy = {"canonical_authority": "mac_local_sql", "railway_role": "authenticated_bounded_ops_projection", "private_bodies_included": False}
    if payload.get("data_policy") != expected_policy:
        raise OpsStandupProjectionError("invalid Ops data policy")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_BYTES or any(token in serialized for token in ("/Users/", "file://", "transcript", "private_notes")):
        raise OpsStandupProjectionError("Ops projection contains private or oversized material")
    return payload


def unavailable_ops_standup_projection(
    reason: str,
    *,
    state: str = "degraded",
    canonical_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_SCHEMA, "generated_at": _now_iso(), "state": state, "reason_codes": [reason],
        "ops_conclusion_id": None, "portfolio_cycle_id": None, "cycle_date": None, "status": state,
        "workspace_updates": [], "ai_clone_process_updates": {}, "endpoint_and_subsystem_health": {},
        "work_underway": [], "completed_work": [], "blockers": [], "urgent_escalations": [],
        "workspace_decisions": [], "ops_decisions": [], "owner_calls": [],
        "canonical_decisions": list(canonical_decisions or [])[:MAX_ITEMS], "degraded_system_warnings": [],
        "supporting_evidence_links": [], "recommended_next_actions": [],
        "data_policy": {"canonical_authority": "mac_local_sql", "railway_role": "authenticated_bounded_ops_projection", "private_bodies_included": False},
    }
