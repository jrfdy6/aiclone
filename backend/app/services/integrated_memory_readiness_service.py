from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json


CONSOLIDATION_SCHEMA_VERSION = "integrated_memory_consolidation/v2"
READINESS_SCHEMA_VERSION = "integrated_memory_readiness/v2"
STRUCTURED_MEMORY_SCHEMA_VERSION = "structured_memory_entry/v1"
DURABILITY_POLICY_VERSION = "dream_durable_event_policy/v2"

# Canonical names match the normalized ledger writers. Compatibility aliases
# remain readable so a controlled migration does not strand earlier events.
_EVENT_LANES = {
    "content.publication_confirmed": "factual_continuity",
    "learning.publication_confirmed": "factual_continuity",
    "publication.confirmed": "factual_continuity",
    "decision.resolved": "operational_continuity",
    "decision.transitioned": "operational_continuity",
    "persona.promoted": "factual_continuity",
    "persona.reversed": "factual_continuity",
    "persona.candidate_recorded": "identity_candidate",
    "persona.candidate_created": "identity_candidate",
    "backup.restore_verified": "operational_continuity",
    "backup.verified": "operational_continuity",
    "backup.failed": "operational_continuity",
    "workspace.concluded": "operational_continuity",
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


def _memory_lane(event_type: str, payload: Mapping[str, Any]) -> str | None:
    lane = _EVENT_LANES.get(event_type)
    if lane is None:
        return None
    if event_type == "decision.transitioned" and payload.get("to") != "resolved":
        return None
    if event_type == "backup.verified" and payload.get("status") not in {"complete", "verified"}:
        return None
    if event_type == "backup.failed" and payload.get("status") not in {None, "failed", "degraded"}:
        return None
    return lane


class IntegratedMemoryReadinessService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def consolidate(self, *, cycle_id: str, now: datetime | None = None) -> dict[str, Any]:
        self.store.migrate()
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        requested_window_end = now.isoformat()
        idempotency_key = f"dream-cycle:{cycle_id}"
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM memory_consolidations WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
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
                    and stored_entries == int(existing_receipt.get("memory_entry_count") or 0)
                ):
                    return dict(existing)
                window_start = existing["window_start"]
                window_end = existing["window_end"]
                consolidation_id = existing["consolidation_id"]
            else:
                prior = connection.execute(
                    """SELECT window_end,source_event_cursor FROM memory_consolidations
                    WHERE status IN ('complete','degraded') ORDER BY window_end DESC LIMIT 1"""
                ).fetchone()
                window_start = prior["window_end"] if prior else (now - timedelta(hours=24)).isoformat()
                window_end = requested_window_end
                consolidation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:dream:{cycle_id}"))

            rows = connection.execute(
                """SELECT event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,actor_id,
                    payload_json,provenance_json,artifact_refs_json,schema_version
                FROM system_events WHERE occurred_at>? AND occurred_at<=?
                ORDER BY occurred_at,event_id""",
                (window_start, window_end),
            ).fetchall()
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
            cursor = {
                "event_id": rows[-1]["event_id"] if rows else None,
                "occurred_at": rows[-1]["occurred_at"] if rows else window_end,
            }
            receipt = {
                "schema_version": CONSOLIDATION_SCHEMA_VERSION,
                "structured_memory_schema_version": STRUCTURED_MEMORY_SCHEMA_VERSION,
                "durability_policy_version": DURABILITY_POLICY_VERSION,
                "cycle_id": cycle_id,
                "window_start": window_start,
                "window_end": window_end,
                "event_count": len(rows),
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
            now_text = now.isoformat()
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
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.store.migrate()
        idempotency_key = f"memory-readiness:{cycle_id}"
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM readiness_receipts WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if existing and existing["status"] == "ready" and not force_recheck:
                return self._readiness_response(dict(existing))

        failed_component: str | None = None
        failure_reason: str | None = None
        consolidation: dict[str, Any] | None = None
        consolidation_receipt: dict[str, Any] = {}
        consolidation_error_class: str | None = None
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
                if current and current["status"] == "ready" and not force_recheck:
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
            rows = connection.execute(
                """SELECT * FROM structured_memory_entries
                WHERE consolidation_id=?
                ORDER BY created_at DESC,memory_entry_id DESC LIMIT ?""",
                (consolidation_id, max(1, min(int(limit), 1000))),
            ).fetchall()
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
