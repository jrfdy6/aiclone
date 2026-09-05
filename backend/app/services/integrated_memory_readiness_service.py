from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json
from app.utils.ai_clone_clock import as_utc, utc_now


CONSOLIDATION_SCHEMA_VERSION = "integrated_memory_consolidation/v2"
READINESS_SCHEMA_VERSION = "integrated_memory_readiness/v2"
STRUCTURED_MEMORY_SCHEMA_VERSION = "structured_memory_entry/v1"
DURABILITY_POLICY_VERSION = "dream_durable_event_policy/v3"
POLICY_TRANSITION_BACKFILL_SCHEMA_VERSION = (
    "dream_durable_event_policy_transition_backfill/v1"
)
POLICY_TRANSITION_BACKFILL_LIMIT = 1000
EXACT_CONSOLIDATION_MEMORY_ENTRY_LIMIT = 1000
_V3_NEW_DURABLE_EVENT_TYPES = frozenset(
    {
        "decision.created",
        "workspace.action_completed",
        "workspace.action_failed",
        "owner.day_action_updated",
    }
)

# Canonical names match the normalized ledger writers. Compatibility aliases
# remain readable so a controlled migration does not strand earlier events.
_EVENT_LANES = {
    "content.publication_confirmed": "factual_continuity",
    "learning.publication_confirmed": "factual_continuity",
    "publication.confirmed": "factual_continuity",
    "decision.resolved": "operational_continuity",
    "decision.created": "operational_continuity",
    "decision.transitioned": "operational_continuity",
    "persona.promoted": "factual_continuity",
    "persona.reversed": "factual_continuity",
    "persona.candidate_recorded": "identity_candidate",
    "persona.candidate_created": "identity_candidate",
    "backup.restore_verified": "operational_continuity",
    "backup.verified": "operational_continuity",
    "backup.failed": "operational_continuity",
    "workspace.concluded": "operational_continuity",
    "workspace.action_completed": "operational_continuity",
    "workspace.action_failed": "operational_continuity",
    "owner.day_action_updated": "operational_continuity",
    "ops.concluded": "operational_continuity",
    "ops.reconcluded": "operational_continuity",
    "owner.feedback_recorded": "reversible_pattern",
    "learning.owner_feedback": "reversible_pattern",
}
DURABLE_EVENT_TYPES = frozenset(_EVENT_LANES)
RECALL_PROBE_QUERIES = (
    "SOURCE_OF_TRUTH owner authority",
    "integrated content opportunity canonical post",
    "Dream Cycle memory consolidation readiness",
)


class DurabilityPolicyTransitionBackfillLimitExceeded(ValueError):
    def __init__(
        self,
        *,
        candidate_limit: int,
        candidate_count_lower_bound: int,
        from_policy_version: str,
        attempted_at: str,
    ) -> None:
        super().__init__(
            "durability policy transition backfill exceeds the bounded candidate "
            "limit; consolidation failed closed before any consolidation or "
            "structured-memory write"
        )
        self.receipt = {
            "schema_version": POLICY_TRANSITION_BACKFILL_SCHEMA_VERSION,
            "status": "blocked_candidate_limit",
            "from_policy_version": from_policy_version,
            "to_policy_version": DURABILITY_POLICY_VERSION,
            "eligible_event_types": sorted(_V3_NEW_DURABLE_EVENT_TYPES),
            "candidate_limit": candidate_limit,
            "candidate_count": None,
            "candidate_count_lower_bound": candidate_count_lower_bound,
            "admitted_event_count": 0,
            "admitted_event_ids": [],
            "event_ids_truncated": False,
            "candidate_scan_truncated": True,
            "attempted_at": attempted_at,
            "semantic_occurrence_time_preserved": True,
            "failure_behavior": "fail_closed_before_write_if_candidate_limit_exceeded",
        }


class ExactConsolidationMemoryEntryLimitExceeded(ValueError):
    """Fail closed before an exact Dream handoff silently drops admitted facts."""

    def __init__(
        self,
        *,
        consolidation_id: str,
        entry_limit: int,
        entry_count_lower_bound: int,
    ) -> None:
        super().__init__(
            "exact Dream consolidation exceeds the bounded structured-memory "
            "handoff limit; downstream Dream synthesis must not truncate it"
        )
        self.consolidation_id = consolidation_id
        self.entry_limit = entry_limit
        self.entry_count_lower_bound = entry_count_lower_bound


def _sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(dict(value)).encode("utf-8")).hexdigest()


def _parse_json_object(value: str, *, field: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return parsed


def _parse_json_list(value: str, *, field: str) -> list[Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"{field} must contain a JSON list")
    return parsed


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _event_cursor(value: Any) -> dict[str, Any]:
    """Read the bounded ledger cursor while retaining compatibility with older rows."""

    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _ledger_rowid_for_cursor(connection: Any, cursor: Mapping[str, Any]) -> int:
    """Resolve a cursor through the immutable event identity, not event time.

    `occurred_at` is semantic time and may legitimately predate the cycle that
    receives an event.  The event id is the stable append-only ledger identity;
    SQLite's rowid is used only as the local ordering cursor resolved from that
    identity.  New cursors also retain the rowid as a bounded diagnostic and as
    compatibility fallback for an empty legacy cursor.
    """

    for key in ("ledger_event_id", "event_id"):
        event_id = str(cursor.get(key) or "").strip()
        if not event_id:
            continue
        row = connection.execute(
            "SELECT rowid AS ledger_rowid FROM system_events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if row:
            return int(row["ledger_rowid"])
        if key == "ledger_event_id":
            raise ValueError("memory consolidation ledger cursor references a missing event")
    raw_rowid = cursor.get("ledger_rowid")
    if isinstance(raw_rowid, int) and not isinstance(raw_rowid, bool) and raw_rowid >= 0:
        return raw_rowid
    return 0


def _memory_lane(event_type: str, payload: Mapping[str, Any]) -> str | None:
    lane = _EVENT_LANES.get(event_type)
    if lane is None:
        return None
    if event_type == "decision.transitioned" and payload.get("to") not in {
        "open",
        "resolved",
        "blocked",
        "canceled",
        "superseded",
    }:
        return None
    if event_type == "backup.verified" and payload.get("status") not in {"complete", "verified"}:
        return None
    if event_type == "backup.failed" and payload.get("status") not in {None, "failed", "degraded"}:
        return None
    return lane


def _receipt_hash_is_current(payload: Mapping[str, Any]) -> bool:
    supplied = str(payload.get("receipt_payload_sha256") or "").strip()
    if len(supplied) != 64:
        return False
    unhashed = dict(payload)
    unhashed.pop("receipt_payload_sha256", None)
    return _sha256_json(unhashed) == supplied


def _transition_backfill_receipt_is_current(payload: Mapping[str, Any]) -> bool:
    backfill = payload.get("durability_policy_transition_backfill")
    if not isinstance(backfill, Mapping):
        return False
    return bool(
        backfill.get("schema_version") == POLICY_TRANSITION_BACKFILL_SCHEMA_VERSION
        and backfill.get("to_policy_version") == DURABILITY_POLICY_VERSION
        and backfill.get("status") in {"complete", "not_required"}
        and backfill.get("candidate_scan_truncated") is False
    )


def _ready_receipt_matches_current_consolidation(
    connection: Any,
    row: Mapping[str, Any],
    *,
    cycle_id: str,
) -> bool:
    """Reject a stale ready shortcut after a consolidation policy repair.

    Readiness is meaningful only for the exact current consolidation payload.
    A status string alone cannot promote newly rebuilt/pending entries or bind a
    same-cycle v2 receipt to a repaired v3 durability policy.
    """

    if str(row.get("status") or "") != "ready":
        return False
    try:
        readiness = _parse_json_object(
            row.get("recall_probe_json"), field="readiness_receipts.recall_probe_json"
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    consolidation_id = str(row.get("consolidation_id") or "").strip()
    if (
        readiness.get("schema_version") != READINESS_SCHEMA_VERSION
        or str(readiness.get("cycle_id") or "") != cycle_id
        or str(readiness.get("status") or "") != "ready"
        or str(readiness.get("consolidation_id") or "") != consolidation_id
        or str(readiness.get("trusted_consolidation_id") or "") != consolidation_id
        or not _receipt_hash_is_current(readiness)
        or not consolidation_id
    ):
        return False
    consolidation = connection.execute(
        "SELECT * FROM memory_consolidations WHERE consolidation_id=?",
        (consolidation_id,),
    ).fetchone()
    if not consolidation or consolidation["status"] != "complete":
        return False
    try:
        consolidation_receipt = _parse_json_object(
            consolidation["receipt_json"], field="memory_consolidations.receipt_json"
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    readiness_consolidation = (
        readiness.get("consolidation")
        if isinstance(readiness.get("consolidation"), Mapping)
        else {}
    )
    if (
        consolidation_receipt.get("schema_version") != CONSOLIDATION_SCHEMA_VERSION
        or consolidation_receipt.get("durability_policy_version") != DURABILITY_POLICY_VERSION
        or not _transition_backfill_receipt_is_current(consolidation_receipt)
        or str(consolidation_receipt.get("cycle_id") or "") != cycle_id
        or not _receipt_hash_is_current(consolidation_receipt)
        or readiness_consolidation.get("schema_version") != CONSOLIDATION_SCHEMA_VERSION
        or readiness_consolidation.get("receipt_payload_sha256")
        != consolidation_receipt.get("receipt_payload_sha256")
    ):
        return False
    stored_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM structured_memory_entries WHERE consolidation_id=?",
            (consolidation_id,),
        ).fetchone()[0]
    )
    pending_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM structured_memory_entries "
            "WHERE consolidation_id=? AND verification_status='pending'",
            (consolidation_id,),
        ).fetchone()[0]
    )
    return bool(
        pending_count == 0
        and stored_count == int(consolidation_receipt.get("memory_entry_count") or 0)
    )


class IntegratedMemoryReadinessService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def consolidate(self, *, cycle_id: str, now: datetime | None = None) -> dict[str, Any]:
        now = as_utc(now) if now is not None else utc_now()
        self.store.migrate()
        now_text = now.isoformat()
        requested_window_end = now_text
        idempotency_key = f"dream-cycle:{cycle_id}"
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM memory_consolidations WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            existing_receipt: dict[str, Any] = {}
            transition_source_receipt: dict[str, Any] = {}
            if existing:
                existing_receipt = _parse_json_object(existing["receipt_json"], field="receipt_json")
                stored_entries = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM structured_memory_entries WHERE consolidation_id=?",
                        (existing["consolidation_id"],),
                    ).fetchone()[0]
                )
                if (
                    existing["status"] == "complete"
                    and existing_receipt.get("schema_version") == CONSOLIDATION_SCHEMA_VERSION
                    and existing_receipt.get("durability_policy_version")
                    == DURABILITY_POLICY_VERSION
                    and _transition_backfill_receipt_is_current(existing_receipt)
                    and stored_entries == int(existing_receipt.get("memory_entry_count") or 0)
                ):
                    return dict(existing)
                window_start = existing["window_start"]
                window_end = existing["window_end"]
                consolidation_id = existing["consolidation_id"]
                source_cursor_value = existing["source_event_cursor"]
                transition_source_receipt = existing_receipt
            else:
                prior = connection.execute(
                    """SELECT window_end,source_event_cursor,receipt_json FROM memory_consolidations
                    WHERE status IN ('complete','degraded') ORDER BY window_end DESC LIMIT 1"""
                ).fetchone()
                window_start = prior["window_end"] if prior else (now - timedelta(hours=24)).isoformat()
                window_end = requested_window_end
                consolidation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:dream:{cycle_id}"))
                source_cursor_value = prior["source_event_cursor"] if prior else None
                if prior:
                    transition_source_receipt = _parse_json_object(
                        prior["receipt_json"], field="memory_consolidations.receipt_json"
                    )

            prior_cursor = _event_cursor(source_cursor_value)
            prior_ledger_rowid = _ledger_rowid_for_cursor(connection, prior_cursor)
            scanned_rows = connection.execute(
                """SELECT e.rowid AS ledger_rowid,e.event_id,e.event_type,e.aggregate_type,
                    e.aggregate_id,e.occurred_at,e.actor_type,e.actor_id,e.payload_json,
                    e.provenance_json,e.artifact_refs_json,e.schema_version,
                    memory.consolidation_id AS admitted_consolidation_id
                FROM system_events AS e
                LEFT JOIN structured_memory_entries AS memory ON memory.source_event_id=e.event_id
                WHERE e.occurred_at<=? AND (e.occurred_at>? OR e.rowid>?)
                ORDER BY e.occurred_at,e.event_id""",
                (window_end, window_start, prior_ledger_rowid),
            ).fetchall()
            # A semantic window can overlap a previously admitted event after a
            # repair or clock correction. The immutable source-event link is
            # the duplicate authority, so only unadmitted events (or entries
            # already owned by this exact consolidation repair) are processed.
            rows = [
                row
                for row in scanned_rows
                if row["admitted_consolidation_id"] in {None, consolidation_id}
            ]
            normal_unadmitted_row_count = len(rows)
            transition_backfill_required = bool(
                transition_source_receipt
                and not _transition_backfill_receipt_is_current(transition_source_receipt)
            )
            transition_rows: list[Any] = []
            if transition_backfill_required and prior_ledger_rowid > 0:
                event_types = sorted(_V3_NEW_DURABLE_EVENT_TYPES)
                placeholders = ",".join("?" for _ in event_types)
                bounded_limit = int(POLICY_TRANSITION_BACKFILL_LIMIT)
                if bounded_limit < 1:
                    raise ValueError("durability policy transition backfill limit must be positive")
                transition_rows = list(
                    connection.execute(
                        f"""SELECT e.rowid AS ledger_rowid,e.event_id,e.event_type,e.aggregate_type,
                            e.aggregate_id,e.occurred_at,e.actor_type,e.actor_id,e.payload_json,
                            e.provenance_json,e.artifact_refs_json,e.schema_version,
                            memory.consolidation_id AS admitted_consolidation_id
                        FROM system_events AS e
                        LEFT JOIN structured_memory_entries AS memory
                            ON memory.source_event_id=e.event_id
                        WHERE e.event_type IN ({placeholders})
                            AND e.occurred_at<=?
                            AND e.rowid<=?
                            AND memory.source_event_id IS NULL
                        ORDER BY e.rowid
                        LIMIT ?""",
                        (*event_types, window_start, prior_ledger_rowid, bounded_limit + 1),
                    ).fetchall()
                )
                if len(transition_rows) > bounded_limit:
                    raise DurabilityPolicyTransitionBackfillLimitExceeded(
                        candidate_limit=bounded_limit,
                        candidate_count_lower_bound=len(transition_rows),
                        from_policy_version=str(
                            transition_source_receipt.get("durability_policy_version")
                            or "unversioned"
                        ),
                        attempted_at=now_text,
                    )
            transition_event_ids = {row["event_id"] for row in transition_rows}
            scanned_event_ids = {row["event_id"] for row in rows}
            rows.extend(row for row in transition_rows if row["event_id"] not in scanned_event_ids)
            rows.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
            late_cursor_rows = [
                row
                for row in rows
                if int(row["ledger_rowid"]) > prior_ledger_rowid
                and row["occurred_at"] <= window_start
            ]
            type_counts = Counter(row["event_type"] for row in rows)
            durable: list[dict[str, Any]] = []
            ignored_count = 0
            ignored_reason_counts: Counter[str] = Counter()
            for row in rows:
                payload = _parse_json_object(row["payload_json"], field="system_events.payload_json")
                lane = _memory_lane(row["event_type"], payload)
                if lane is None:
                    ignored_count += 1
                    reason = (
                        "conditional_rule_not_satisfied"
                        if row["event_type"] in DURABLE_EVENT_TYPES
                        else "not_durable"
                    )
                    ignored_reason_counts[reason] += 1
                    continue
                original_provenance = _parse_json_object(
                    row["provenance_json"], field="system_events.provenance_json"
                )
                artifact_refs = _parse_json_list(
                    row["artifact_refs_json"], field="system_events.artifact_refs_json"
                )
                event_document = {
                    "schema_version": int(row["schema_version"]),
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "aggregate_type": row["aggregate_type"],
                    "aggregate_id": row["aggregate_id"],
                    "occurred_at": row["occurred_at"],
                    "actor_type": row["actor_type"],
                    "actor_id": row["actor_id"],
                    "payload": payload,
                    "provenance": original_provenance,
                    "artifact_refs": artifact_refs,
                }
                source_event_sha256 = _sha256_json(event_document)
                fact = {
                    "schema_version": "structured_memory_fact/v1",
                    "source_event_type": row["event_type"],
                    "subject": {
                        "type": row["aggregate_type"],
                        "id": row["aggregate_id"],
                    },
                    "occurred_at": row["occurred_at"],
                    "payload": payload,
                }
                provenance = {
                    "schema_version": "structured_memory_provenance/v1",
                    "source_event_id": row["event_id"],
                    "source_event_sha256": source_event_sha256,
                    "source_event_schema_version": int(row["schema_version"]),
                    "source_event_type": row["event_type"],
                    "actor": {"type": row["actor_type"], "id": row["actor_id"]},
                    "original": original_provenance,
                    "artifact_refs": artifact_refs,
                }
                if row["event_id"] in transition_event_ids:
                    provenance["admission"] = {
                        "schema_version": POLICY_TRANSITION_BACKFILL_SCHEMA_VERSION,
                        "reason": "durability_policy_transition",
                        "from_policy_version": str(
                            transition_source_receipt.get("durability_policy_version")
                            or "unversioned"
                        ),
                        "to_policy_version": DURABILITY_POLICY_VERSION,
                        "occurred_at_preserved": row["occurred_at"],
                        "admitted_at": now_text,
                    }
                durable.append(
                    {
                        "source_event_id": row["event_id"],
                        "source_event_sha256": source_event_sha256,
                        "memory_entry_id": str(
                            uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:memory-entry:{row['event_id']}")
                        ),
                        "memory_lane": lane,
                        "subject_type": row["aggregate_type"],
                        "subject_id": row["aggregate_id"],
                        "fact_json": _canonical_json(fact),
                        "provenance_json": _canonical_json(provenance),
                        "created_at": row["occurred_at"],
                    }
                )

            lane_counts = Counter(item["memory_lane"] for item in durable)
            late_cursor_event_ids = {row["event_id"] for row in late_cursor_rows}
            late_admitted_event_ids = [
                item["source_event_id"]
                for item in durable
                if item["source_event_id"] in late_cursor_event_ids
            ]
            transition_admitted_event_ids = [
                item["source_event_id"]
                for item in durable
                if item["source_event_id"] in transition_event_ids
            ]
            scanned_highwater = max(
                scanned_rows,
                key=lambda row: int(row["ledger_rowid"]),
                default=None,
            )
            if scanned_highwater is not None and int(scanned_highwater["ledger_rowid"]) > prior_ledger_rowid:
                ledger_event_id = scanned_highwater["event_id"]
                ledger_rowid = int(scanned_highwater["ledger_rowid"])
            else:
                ledger_event_id = str(
                    prior_cursor.get("ledger_event_id") or prior_cursor.get("event_id") or ""
                ).strip() or None
                ledger_rowid = prior_ledger_rowid
            cursor = {
                "event_id": rows[-1]["event_id"] if rows else prior_cursor.get("event_id"),
                "occurred_at": rows[-1]["occurred_at"] if rows else window_end,
                "ledger_event_id": ledger_event_id,
                "ledger_rowid": ledger_rowid,
            }
            receipt = {
                "schema_version": CONSOLIDATION_SCHEMA_VERSION,
                "structured_memory_schema_version": STRUCTURED_MEMORY_SCHEMA_VERSION,
                "durability_policy_version": DURABILITY_POLICY_VERSION,
                "cycle_id": cycle_id,
                "window_start": window_start,
                "window_end": window_end,
                "source_event_cursor": cursor,
                "event_count": len(rows),
                "ledger_scan_count": len(scanned_rows),
                "already_admitted_event_count": (
                    len(scanned_rows) - normal_unadmitted_row_count
                ),
                "late_cursor_event_count": len(late_cursor_rows),
                "late_appended_event_count": len(late_admitted_event_ids),
                "late_appended_event_ids": late_admitted_event_ids[:200],
                "durability_policy_transition_backfill": {
                    "schema_version": POLICY_TRANSITION_BACKFILL_SCHEMA_VERSION,
                    "status": "complete" if transition_backfill_required else "not_required",
                    "from_policy_version": (
                        str(
                            transition_source_receipt.get("durability_policy_version")
                            or "unversioned"
                        )
                        if transition_backfill_required
                        else None
                    ),
                    "to_policy_version": DURABILITY_POLICY_VERSION,
                    "eligible_event_types": sorted(_V3_NEW_DURABLE_EVENT_TYPES),
                    "candidate_limit": POLICY_TRANSITION_BACKFILL_LIMIT,
                    "candidate_count": len(transition_rows),
                    "admitted_event_count": len(transition_admitted_event_ids),
                    "admitted_event_ids": transition_admitted_event_ids[:200],
                    "event_ids_truncated": len(transition_admitted_event_ids) > 200,
                    "candidate_scan_truncated": False,
                    "admitted_at": now_text if transition_backfill_required else None,
                    "semantic_occurrence_time_preserved": True,
                    "failure_behavior": "fail_closed_before_write_if_candidate_limit_exceeded",
                },
                "event_type_counts": dict(sorted(type_counts.items())),
                "durable_event_count": len(durable),
                "durable_event_ids": [item["source_event_id"] for item in durable[:200]],
                "durable_event_hashes": [item["source_event_sha256"] for item in durable[:200]],
                "memory_entry_count": len(durable),
                "memory_entry_ids": [item["memory_entry_id"] for item in durable[:200]],
                "memory_lane_counts": dict(sorted(lane_counts.items())),
                "receipt_lists_truncated": len(durable) > 200,
                "ignored_event_count": ignored_count,
                "ignored_reason_counts": dict(sorted(ignored_reason_counts.items())),
                "policy": {
                    "source_processing_performed": False,
                    "content_generation_performed": False,
                    "standup_generation_performed": False,
                    "identity_claims_auto_promoted": False,
                    "identity_candidates_recorded_without_promotion": lane_counts["identity_candidate"],
                    "entries_pending_until_readiness_verified": len(durable),
                },
            }
            receipt_sha256 = _sha256_json(receipt)
            receipt["receipt_payload_sha256"] = receipt_sha256
            connection.execute("BEGIN IMMEDIATE")
            try:
                if existing:
                    connection.execute(
                        """UPDATE memory_consolidations SET window_start=?,window_end=?,source_event_cursor=?,
                        receipt_json=?,status='complete',created_at=? WHERE consolidation_id=?""",
                        (
                            window_start,
                            window_end,
                            _canonical_json(cursor),
                            _canonical_json(receipt),
                            now_text,
                            consolidation_id,
                        ),
                    )
                else:
                    connection.execute(
                        """INSERT INTO memory_consolidations(
                            consolidation_id,window_start,window_end,source_event_cursor,
                            receipt_json,status,created_at,idempotency_key
                        ) VALUES (?,?,?,?,?,'complete',?,?)""",
                        (
                            consolidation_id,
                            window_start,
                            window_end,
                            _canonical_json(cursor),
                            _canonical_json(receipt),
                            now_text,
                            idempotency_key,
                        ),
                    )
                for item in durable:
                    connection.execute(
                        """INSERT INTO structured_memory_entries(
                            memory_entry_id,consolidation_id,source_event_id,source_event_sha256,memory_lane,
                            subject_type,subject_id,fact_json,provenance_json,durability_policy,
                            verification_status,created_at,schema_version
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,'pending',?,1)
                        ON CONFLICT(source_event_id) DO NOTHING""",
                        (
                            item["memory_entry_id"],
                            consolidation_id,
                            item["source_event_id"],
                            item["source_event_sha256"],
                            item["memory_lane"],
                            item["subject_type"],
                            item["subject_id"],
                            item["fact_json"],
                            item["provenance_json"],
                            DURABILITY_POLICY_VERSION,
                            item["created_at"],
                        ),
                    )
                    stored = connection.execute(
                        "SELECT * FROM structured_memory_entries WHERE source_event_id=?",
                        (item["source_event_id"],),
                    ).fetchone()
                    if (
                        not stored
                        or stored["consolidation_id"] != consolidation_id
                        or stored["source_event_sha256"] != item["source_event_sha256"]
                        or stored["memory_lane"] != item["memory_lane"]
                        or stored["fact_json"] != item["fact_json"]
                        or stored["provenance_json"] != item["provenance_json"]
                    ):
                        raise ValueError("structured memory source-event idempotency conflict")
                self._append_event(
                    connection,
                    event_type="memory.consolidated",
                    aggregate_type="memory_consolidation",
                    aggregate_id=consolidation_id,
                    payload={
                        "schema_version": CONSOLIDATION_SCHEMA_VERSION,
                        "cycle_id": cycle_id,
                        "durable_event_count": len(durable),
                        "memory_entry_count": len(durable),
                        "receipt_payload_sha256": receipt_sha256,
                        "status": "complete",
                    },
                    provenance={"durability_policy_version": DURABILITY_POLICY_VERSION},
                    idempotency_key=f"memory-consolidated:{cycle_id}:v2",
                    occurred_at=now_text,
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return dict(
                connection.execute(
                    "SELECT * FROM memory_consolidations WHERE consolidation_id=?", (consolidation_id,)
                ).fetchone()
            )

    def run_readiness(
        self,
        *,
        cycle_id: str,
        retrieval_refresh: Callable[[], dict[str, Any]],
        recall_search: Callable[[str], list[dict[str, Any]]],
        now: datetime | None = None,
        force_recheck: bool = False,
    ) -> dict[str, Any]:
        now = as_utc(now) if now is not None else utc_now()
        self.store.migrate()
        idempotency_key = f"memory-readiness:{cycle_id}"
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM readiness_receipts WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if (
                existing
                and not force_recheck
                and _ready_receipt_matches_current_consolidation(
                    connection, dict(existing), cycle_id=cycle_id
                )
            ):
                return self._readiness_response(dict(existing))

        failed_component: str | None = None
        failure_reason: str | None = None
        consolidation: dict[str, Any] | None = None
        consolidation_receipt: dict[str, Any] = {}
        consolidation_error_class: str | None = None
        consolidation_failure_receipt: dict[str, Any] | None = None
        refresh_result: dict[str, Any] = {
            "schema_version": None,
            "status": "not_run",
            "contract_valid": False,
            "files": None,
            "last_sync_at": None,
            "error_class": None,
            "reason": "dependency_not_run",
        }
        probe_results: list[dict[str, Any]] = []
        try:
            consolidation = self.consolidate(cycle_id=cycle_id, now=now)
            consolidation_receipt = _parse_json_object(
                consolidation["receipt_json"], field="memory_consolidations.receipt_json"
            )
            if consolidation["status"] != "complete":
                failed_component = "dream_cycle"
                failure_reason = "consolidation_not_complete"
        except Exception as exc:
            failed_component = "dream_cycle"
            failure_reason = "consolidation_exception"
            consolidation_error_class = type(exc).__name__
            candidate_receipt = getattr(exc, "receipt", None)
            if isinstance(candidate_receipt, Mapping):
                consolidation_failure_receipt = dict(candidate_receipt)

        if failed_component is None:
            try:
                raw_refresh = retrieval_refresh()
                refresh_result = self._validate_retrieval_refresh(
                    raw_refresh,
                    minimum_sync_at=_aware_datetime(consolidation["window_end"]),
                )
                if not refresh_result["contract_valid"]:
                    failed_component = "retrieval_refresh"
                    failure_reason = str(refresh_result.get("reason") or "invalid_refresh_receipt")
            except Exception as exc:
                failed_component = "retrieval_refresh"
                failure_reason = "refresh_exception"
                refresh_result = {
                    "schema_version": None,
                    "status": "failed",
                    "contract_valid": False,
                    "files": None,
                    "last_sync_at": None,
                    "error_class": type(exc).__name__,
                    "reason": failure_reason,
                }

        if failed_component is None:
            for query in RECALL_PROBE_QUERIES:
                try:
                    matches = recall_search(query)
                    if not isinstance(matches, list):
                        raise TypeError("recall result must be a list")
                    usable_matches = [item for item in matches if isinstance(item, dict) and item]
                    contract_valid = len(usable_matches) == len(matches)
                except Exception as exc:
                    failed_component = "recall_probes"
                    failure_reason = "probe_exception"
                    probe_results.append(
                        {
                            "query": query,
                            "status": "failed",
                            "contract_valid": False,
                            "error_class": type(exc).__name__,
                            "match_count": 0,
                            "reason": failure_reason,
                        }
                    )
                    break
                passed = contract_valid and bool(usable_matches)
                result = {
                    "query": query,
                    "status": "pass" if passed else "failed",
                    "contract_valid": contract_valid,
                    "match_count": len(usable_matches),
                    "reason": None if passed else ("no_matches" if contract_valid else "invalid_probe_receipt"),
                }
                probe_results.append(result)
                if not passed:
                    failed_component = "recall_probes"
                    failure_reason = str(result["reason"])
                    break

        status = "ready" if failed_component is None else "degraded"
        now_text = now.isoformat()
        readiness_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:readiness:{cycle_id}"))
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = connection.execute(
                    "SELECT * FROM readiness_receipts WHERE idempotency_key=?", (idempotency_key,)
                ).fetchone()
                if (
                    current
                    and not force_recheck
                    and _ready_receipt_matches_current_consolidation(
                        connection, dict(current), cycle_id=cycle_id
                    )
                ):
                    connection.execute("COMMIT")
                    return self._readiness_response(dict(current))
                prior_status = current["status"] if current else None
                prior_ready = (
                    current
                    if current and current["status"] == "ready"
                    else connection.execute(
                        """SELECT readiness_id,consolidation_id,last_verified_memory_at
                        FROM readiness_receipts WHERE status='ready' AND readiness_id<>?
                        ORDER BY created_at DESC LIMIT 1""",
                        (readiness_id,),
                    ).fetchone()
                )
                last_verified = (
                    now_text
                    if status == "ready"
                    else (prior_ready["last_verified_memory_at"] if prior_ready else None)
                )
                trusted_consolidation_id = (
                    consolidation["consolidation_id"]
                    if status == "ready" and consolidation
                    else (prior_ready["consolidation_id"] if prior_ready else None)
                )
                attempt_number = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM readiness_attempts WHERE readiness_id=?", (readiness_id,)
                    ).fetchone()[0]
                ) + 1
                if status == "ready" and consolidation:
                    connection.execute(
                        """UPDATE structured_memory_entries SET verification_status='verified',verified_at=?
                        WHERE verification_status='pending' AND consolidation_id IN (
                            SELECT consolidation_id FROM memory_consolidations
                            WHERE status='complete' AND window_end<=?
                        )""",
                        (now_text, consolidation["window_end"]),
                    )
                current_entry_counts = {"pending": 0, "verified": 0, "rejected": 0}
                if consolidation:
                    for row in connection.execute(
                        """SELECT verification_status,COUNT(*) AS count FROM structured_memory_entries
                        WHERE consolidation_id=? GROUP BY verification_status""",
                        (consolidation["consolidation_id"],),
                    ):
                        current_entry_counts[row["verification_status"]] = int(row["count"])
                total_verified_entries = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM structured_memory_entries WHERE verification_status='verified'"
                    ).fetchone()[0]
                )
                use_last_verified = status != "ready" and last_verified is not None
                receipt_payload = {
                    "schema_version": READINESS_SCHEMA_VERSION,
                    "cycle_id": cycle_id,
                    "attempt_number": attempt_number,
                    "supersedes_status": prior_status,
                    "status": status,
                    "consolidation_id": consolidation["consolidation_id"] if consolidation else None,
                    "consolidation": {
                        "schema_version": consolidation_receipt.get("schema_version"),
                        "status": consolidation["status"] if consolidation else "failed",
                        "memory_entry_count": consolidation_receipt.get("memory_entry_count", 0),
                        "receipt_payload_sha256": consolidation_receipt.get("receipt_payload_sha256"),
                        "error_class": consolidation_error_class,
                        "durability_policy_transition_backfill": (
                            consolidation_receipt.get(
                                "durability_policy_transition_backfill"
                            )
                            or consolidation_failure_receipt
                        ),
                    },
                    "retrieval_refresh": refresh_result,
                    "recall_probes": probe_results,
                    "retrieval_readiness": {
                        "dependency_order_verified": status == "ready",
                        "refresh_contract_valid": refresh_result.get("contract_valid") is True,
                        "required_probe_count": len(RECALL_PROBE_QUERIES),
                        "passed_probe_count": sum(item.get("status") == "pass" for item in probe_results),
                        "structured_memory_entry_counts": current_entry_counts,
                        "total_verified_structured_memory_entries": total_verified_entries,
                        "ready": status == "ready",
                    },
                    "failed_component": failed_component,
                    "failure_reason": failure_reason,
                    "last_verified_memory_at": last_verified,
                    "trusted_consolidation_id": trusted_consolidation_id,
                    "degraded_policy": {
                        "use_last_verified_memory": use_last_verified,
                        "verified_memory_available": status == "ready" or last_verified is not None,
                        "trusted_consolidation_id": trusted_consolidation_id,
                        "pending_memory_entries_excluded": status != "ready",
                        "fresh_persona_promotion_allowed": status == "ready",
                        "unsupported_new_source_claims_allowed": False,
                        "standups_may_continue_visibly_degraded": True,
                    },
                }
                receipt_payload_sha256 = _sha256_json(receipt_payload)
                receipt_payload["receipt_payload_sha256"] = receipt_payload_sha256
                if current:
                    connection.execute(
                        """UPDATE readiness_receipts SET consolidation_id=?,retrieval_refreshed_at=?,
                        recall_probe_json=?,last_verified_memory_at=?,failed_component=?,status=?,created_at=?
                        WHERE readiness_id=?""",
                        (
                            consolidation["consolidation_id"] if consolidation else None,
                            refresh_result.get("last_sync_at")
                            if refresh_result.get("contract_valid") is True
                            else None,
                            _canonical_json(receipt_payload),
                            last_verified,
                            failed_component,
                            status,
                            now_text,
                            readiness_id,
                        ),
                    )
                else:
                    connection.execute(
                        """INSERT INTO readiness_receipts(
                            readiness_id,consolidation_id,retrieval_refreshed_at,
                            recall_probe_json,last_verified_memory_at,
                            failed_component,status,created_at,idempotency_key
                        ) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            readiness_id,
                            consolidation["consolidation_id"] if consolidation else None,
                            refresh_result.get("last_sync_at")
                            if refresh_result.get("contract_valid") is True
                            else None,
                            _canonical_json(receipt_payload),
                            last_verified,
                            failed_component,
                            status,
                            now_text,
                            idempotency_key,
                        ),
                    )
                attempt_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"ai-clone:readiness-attempt:{readiness_id}:{attempt_number}",
                    )
                )
                connection.execute(
                    """INSERT INTO readiness_attempts(
                        attempt_id,readiness_id,attempt_number,receipt_json,status,created_at
                    ) VALUES (?,?,?,?,?,?)""",
                    (
                        attempt_id,
                        readiness_id,
                        attempt_number,
                        _canonical_json(receipt_payload),
                        status,
                        now_text,
                    ),
                )
                self._append_event(
                    connection,
                    event_type="memory.readiness_evaluated",
                    aggregate_type="memory_readiness",
                    aggregate_id=readiness_id,
                    payload={
                        "schema_version": READINESS_SCHEMA_VERSION,
                        "cycle_id": cycle_id,
                        "attempt_number": attempt_number,
                        "status": status,
                        "failed_component": failed_component,
                        "receipt_payload_sha256": receipt_payload_sha256,
                    },
                    provenance={
                        "consolidation_id": consolidation["consolidation_id"] if consolidation else None,
                        "supersedes_status": prior_status,
                    },
                    idempotency_key=f"memory-readiness-event:{cycle_id}:attempt:{attempt_number}",
                    occurred_at=now_text,
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            row = dict(
                connection.execute(
                    "SELECT * FROM readiness_receipts WHERE readiness_id=?", (readiness_id,)
                ).fetchone()
            )
        return self._readiness_response(row)

    def list_retrievable_memory_entries(
        self,
        *,
        lanes: list[str] | tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return only entries covered by a successful readiness receipt."""

        self.store.migrate()
        allowed_lanes = frozenset(_EVENT_LANES.values())
        selected_lanes = sorted({str(item).strip() for item in lanes or [] if str(item).strip()})
        if any(item not in allowed_lanes for item in selected_lanes):
            raise ValueError("unsupported structured memory lane")
        query = """SELECT * FROM structured_memory_entries
            WHERE verification_status='verified'"""
        parameters: list[Any] = []
        if selected_lanes:
            query += f" AND memory_lane IN ({','.join('?' for _ in selected_lanes)})"
            parameters.extend(selected_lanes)
        query += " ORDER BY created_at DESC,memory_entry_id DESC LIMIT ?"
        parameters.append(max(1, min(int(limit), 1000)))
        with self.store.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["fact"] = _parse_json_object(item.pop("fact_json"), field="fact_json")
            item["provenance"] = _parse_json_object(
                item.pop("provenance_json"), field="provenance_json"
            )
            result.append(item)
        return result

    def list_consolidation_memory_entries(
        self,
        *,
        consolidation_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return the exact completed Dream consolidation before readiness promotion.

        This read exists for the ordered Dream -> bounded FEEZIE context ->
        retrieval/readiness chain. It cannot select arbitrary pending entries:
        every returned row must belong to the named complete consolidation.
        """

        consolidation_id = str(consolidation_id or "").strip()
        if not consolidation_id:
            raise ValueError("consolidation_id is required")
        self.store.migrate()
        with self.store.connection() as connection:
            consolidation = connection.execute(
                "SELECT status FROM memory_consolidations WHERE consolidation_id=?",
                (consolidation_id,),
            ).fetchone()
            if not consolidation or consolidation["status"] != "complete":
                return []
            bounded_limit = max(
                1,
                min(int(limit), EXACT_CONSOLIDATION_MEMORY_ENTRY_LIMIT),
            )
            scan_limit = (
                bounded_limit + 1
                if bounded_limit == EXACT_CONSOLIDATION_MEMORY_ENTRY_LIMIT
                else bounded_limit
            )
            rows = connection.execute(
                """SELECT * FROM structured_memory_entries
                WHERE consolidation_id=?
                ORDER BY created_at DESC,memory_entry_id DESC LIMIT ?""",
                (consolidation_id, scan_limit),
            ).fetchall()
        if len(rows) > bounded_limit:
            raise ExactConsolidationMemoryEntryLimitExceeded(
                consolidation_id=consolidation_id,
                entry_limit=bounded_limit,
                entry_count_lower_bound=len(rows),
            )
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["fact"] = _parse_json_object(item.pop("fact_json"), field="fact_json")
            item["provenance"] = _parse_json_object(
                item.pop("provenance_json"), field="provenance_json"
            )
            result.append(item)
        return result

    @staticmethod
    def _validate_retrieval_refresh(
        value: Any,
        *,
        minimum_sync_at: datetime | None,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {
                "schema_version": None,
                "status": "failed",
                "contract_valid": False,
                "files": None,
                "last_sync_at": None,
                "error_class": "InvalidRefreshReceipt",
                "reason": "refresh_receipt_not_object",
            }
        schema_version = value.get("schema_version")
        files = value.get("files")
        sync_at = _aware_datetime(value.get("last_sync_at"))
        reason: str | None = None
        if value.get("status") != "ok":
            reason = "refresh_reported_not_ok"
        elif not isinstance(schema_version, str) or not schema_version.startswith("codex_memory_index/"):
            reason = "refresh_schema_unverified"
        elif isinstance(files, bool) or not isinstance(files, int) or files <= 0:
            reason = "refresh_index_empty_or_unreported"
        elif sync_at is None:
            reason = "refresh_timestamp_invalid"
        elif minimum_sync_at is None or sync_at < minimum_sync_at:
            reason = "refresh_precedes_consolidation"
        return {
            "schema_version": schema_version if isinstance(schema_version, str) else None,
            "status": "ok" if reason is None else "failed",
            "reported_status": value.get("status"),
            "contract_valid": reason is None,
            "files": files if isinstance(files, int) and not isinstance(files, bool) else None,
            "last_sync_at": value.get("last_sync_at") if sync_at else None,
            "private_state_files": value.get("private_state_files"),
            "project_files": value.get("project_files"),
            "error_class": value.get("error_class"),
            "reason": reason,
        }

    @staticmethod
    def _append_event(
        connection: Any,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        provenance: dict[str, Any],
        idempotency_key: str,
        occurred_at: str,
    ) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,
                provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,'dream_cycle',?,?, '[]',?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                occurred_at,
                _canonical_json(payload),
                _canonical_json(provenance),
                idempotency_key,
            ),
        )

    @staticmethod
    def _readiness_response(row: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(row["recall_probe_json"])
        return {**payload, "readiness_id": row["readiness_id"], "created_at": row["created_at"]}
