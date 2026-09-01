from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Iterable, Mapping
import uuid


HEALTHY_AUTOMATION_STATES = ("success", "succeeded", "done", "completed", "healthy", "ok")
HISTORICAL_DETAIL_REQUIRED_AUTOMATION_IDS = ("standup_participant_report",)
TERMINAL_JOB_STATES = ("completed", "failed", "canceled", "cancelled")
TERMINAL_STANDUP_STATES = ("completed", "closed")
RETENTION_LOCK_ID = 724_296_443
ROW_RECEIPT_TABLE = "railway_retention_row_receipts"
KNOWN_MIGRATION_GATES = frozenset(
    {
        "large_payload_local_migration",
        "standup_local_migration",
        "bounded_projection_migration",
        "automation_local_ledger_mirror",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_gates(values: Iterable[str] | None) -> tuple[str, ...]:
    gates = tuple(sorted({str(value or "").strip() for value in (values or ()) if str(value or "").strip()}))
    unknown = sorted(set(gates) - KNOWN_MIGRATION_GATES)
    if unknown:
        raise ValueError(f"unknown retention migration gate(s): {', '.join(unknown)}")
    return gates


_LOCAL_PROOF_BINDING_FIELDS = frozenset({"source_table", "rule_name", "row_identity", "source_row_sha256"})


def _normalize_receipt_proofs(
    values: Mapping[str, Mapping[str, str]] | None,
) -> tuple[dict[str, str], ...]:
    if values is None:
        return ()
    if not isinstance(values, Mapping):
        raise ValueError("verified local migration receipts must be exact receipt-to-row bindings")
    proofs: list[dict[str, str]] = []
    for receipt, raw_binding in values.items():
        receipt_sha256 = str(receipt or "").strip()
        if not isinstance(raw_binding, Mapping) or set(raw_binding) != _LOCAL_PROOF_BINDING_FIELDS:
            raise ValueError("verified local migration receipt bindings must use the closed v2 contract")
        binding = {field: str(raw_binding.get(field) or "").strip() for field in _LOCAL_PROOF_BINDING_FIELDS}
        if (
            re.fullmatch(r"[0-9a-f]{64}", receipt_sha256) is None
            or re.fullmatch(r"[0-9a-f]{64}", binding["source_row_sha256"]) is None
            or not binding["source_table"]
            or not binding["rule_name"]
            or not binding["row_identity"]
        ):
            raise ValueError("verified local migration receipt binding is invalid")
        proofs.append({"receipt_sha256": receipt_sha256, **binding})
    return tuple(sorted(proofs, key=lambda item: item["receipt_sha256"]))


def _normalize_automation_proofs(values: Mapping[str, str] | None) -> tuple[dict[str, str], ...]:
    if values is None:
        return ()
    if not isinstance(values, Mapping):
        raise ValueError("verified local automation rows must be exact ID-to-source-hash bindings")
    proofs = [
        {"row_identity": str(identity or "").strip(), "source_row_sha256": str(source or "").strip()}
        for identity, source in values.items()
    ]
    if any(
        not item["row_identity"]
        or re.fullmatch(r"[0-9a-f]{64}", item["source_row_sha256"]) is None
        for item in proofs
    ):
        raise ValueError("verified local automation row binding is invalid")
    return tuple(sorted(proofs, key=lambda item: item["row_identity"]))


def _normalized_utc_timestamp(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _migration_source_sha256(table_name: str, source: Any) -> str:
    """Hash the exact archived source while omitting only its cyclic receipt pointer."""

    if not isinstance(source, dict):
        raise ValueError("retention source must be an object")
    if table_name == "automation_runs":
        metadata = dict(source.get("metadata") or {})
        metadata.pop("locally_recorded_at", None)
        subject = {
            "id": str(source.get("id") or ""),
            "automation_id": str(source.get("automation_id") or ""),
            "automation_name": str(source.get("automation_name") or ""),
            "source": str(source.get("source") or "local_launchd_registry"),
            "runtime": source.get("runtime"),
            "status": str(source.get("status") or "unknown"),
            "delivered": source.get("delivered"),
            "delivery_channel": source.get("delivery_channel"),
            "delivery_target": source.get("delivery_target"),
            "run_at": _normalized_utc_timestamp(source.get("run_at")),
            "finished_at": _normalized_utc_timestamp(source.get("finished_at")),
            "duration_ms": source.get("duration_ms"),
            "error": source.get("error"),
            "owner_agent": source.get("owner_agent"),
            "session_target": source.get("session_target"),
            "scope": str(source.get("scope") or "shared_ops"),
            "workspace_key": source.get("workspace_key"),
            "action_required": bool(source.get("action_required")),
            "metadata": metadata,
        }
    elif table_name == "local_codex_jobs":
        subject = dict(source)
        row = dict(subject.get("row") or {})
        row.pop("retention_local_receipt_sha256", None)
        subject["row"] = row
    elif table_name == "standups":
        subject = dict(source)
        subject.pop("retention_local_receipt_sha256", None)
    elif table_name == "workspace_snapshots":
        subject = dict(source)
        metadata = dict(subject.get("metadata") or {})
        metadata.pop("local_archive_receipt_sha256", None)
        subject["metadata"] = metadata
    else:
        return _sha256(source)
    return _sha256(subject)


@dataclass(frozen=True)
class RetentionRule:
    name: str
    table_name: str
    candidate_sql: str
    params: tuple[Any, ...]
    mutation_kind: str
    migration_gate: str | None = None
    blocked_sql: str | None = None
    blocked_params: tuple[Any, ...] = ()
    blocked_reason: str | None = None
    target_contract_version: str | None = None
    local_proof_kind: str | None = None


def retention_rules(
    *,
    recent_days: int = 30,
    large_days: int = 7,
    audit_days: int = 365,
    as_of: datetime | None = None,
) -> tuple[RetentionRule, ...]:
    if not (7 <= recent_days <= 90 and 1 <= large_days <= 30 and 180 <= audit_days <= 730):
        raise ValueError("retention bounds are outside the approved policy envelope")
    fixed_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    recent_cutoff = fixed_as_of - timedelta(days=recent_days)
    large_cutoff = fixed_as_of - timedelta(days=large_days)
    audit_cutoff = fixed_as_of - timedelta(days=audit_days)
    automation_predicate = (
        "COALESCE(action_required,FALSE)=FALSE "
        "AND NOT (COALESCE(automation_id,'')=ANY(%s)) "
        "AND LOWER(COALESCE(status,''))=ANY(%s) "
        "AND COALESCE(finished_at,run_at,created_at)<%s"
    )
    automation_blocked = (
        "COALESCE(action_required,FALSE)=FALSE "
        "AND ((COALESCE(automation_id,'')=ANY(%s) "
        "AND COALESCE(finished_at,run_at,created_at)<%s) "
        "OR (NOT (LOWER(COALESCE(status,''))=ANY(%s)) "
        "AND COALESCE(finished_at,run_at,created_at)<%s))"
    )
    job_payload_bytes = """(
        pg_column_size(t.request_payload)+pg_column_size(t.context_packet)+
        pg_column_size(COALESCE(t.result_payload,'{}'::jsonb))+pg_column_size(t.artifacts)+
        COALESCE((SELECT SUM(pg_column_size(a)) FROM local_codex_job_artifacts a WHERE a.job_id=t.id),0)
    )"""
    job_source = """jsonb_build_object(
        'row',to_jsonb(t),
        'child_artifacts',COALESCE((
            SELECT jsonb_agg(to_jsonb(a) ORDER BY a.artifact_id)
            FROM local_codex_job_artifacts a WHERE a.job_id=t.id
        ),'[]'::jsonb)
    )"""
    # No current snapshot_type has a versioned bounded projector plus API/frontend
    # consumer acceptance. Keep every oversized row visible as blocked until one
    # exists; a generic hash-only stub would break active reader contracts.
    snapshot_eligible = "FALSE"
    snapshot_blocked = (
        "pg_column_size(t.payload)>262144"
    )
    job_last_mutation = """GREATEST(
        t.completed_at,
        t.created_at,
        COALESCE(t.updated_at,'-infinity'::timestamptz),
        COALESCE((SELECT MAX(a.updated_at) FROM local_codex_job_artifacts a WHERE a.job_id=t.id),'-infinity'::timestamptz)
    )"""
    job_broad_candidate = (
        "LOWER(COALESCE(t.status,''))=ANY(%s) "
        "AND COALESCE(t.completed_at,t.failed_at,t.canceled_at,t.created_at)<%s "
        f"AND {job_payload_bytes}>2048"
    )
    job_eligible = (
        f"LOWER(COALESCE(t.status,''))='completed' AND t.completed_at IS NOT NULL "
        f"AND {job_last_mutation}<%s "
        f"AND {job_payload_bytes}>2048"
    )
    job_blocked = f"{job_broad_candidate} AND NOT ({job_eligible})"
    standup_last_mutation = """GREATEST(
        t.created_at,
        COALESCE(t.updated_at,t.created_at)
    )"""
    return (
        RetentionRule(
            "automation_non_action_detail",
            "automation_runs",
            f"""SELECT t.id::text,pg_column_size(t),to_jsonb(t)
            FROM automation_runs t WHERE {automation_predicate} ORDER BY t.id::text""",
            (
                list(HISTORICAL_DETAIL_REQUIRED_AUTOMATION_IDS),
                list(HEALTHY_AUTOMATION_STATES),
                recent_cutoff,
            ),
            "delete_with_daily_aggregate",
            migration_gate="automation_local_ledger_mirror",
            blocked_sql=f"""SELECT t.id::text,pg_column_size(t),to_jsonb(t)
            FROM automation_runs t WHERE {automation_blocked} ORDER BY t.id::text""",
            blocked_params=(
                list(HISTORICAL_DETAIL_REQUIRED_AUTOMATION_IDS),
                recent_cutoff,
                list(HEALTHY_AUTOMATION_STATES),
                audit_cutoff,
            ),
            blocked_reason=(
                "historical_verification_detail_required_or_"
                "failed_or_nonhealthy_automation_run_lacks_resolution_proof"
            ),
            target_contract_version="automation_run_daily_receipt/v1",
            local_proof_kind="automation_run",
        ),
        RetentionRule(
            "completed_large_job_payloads",
            "local_codex_jobs",
            f"""SELECT t.id::text,{job_payload_bytes},{job_source}
            FROM local_codex_jobs t
            WHERE {job_eligible}
            ORDER BY t.id::text""",
            (large_cutoff,),
            "compact_job_payload_and_delete_artifacts",
            "large_payload_local_migration",
            f"""SELECT t.id::text,{job_payload_bytes},{job_source}
            FROM local_codex_jobs t WHERE {job_blocked} ORDER BY t.id::text""",
            (list(TERMINAL_JOB_STATES), large_cutoff, large_cutoff),
            (
                "terminal_job_is_not_completed_or_changed_within_window; "
                "failed/canceled or owner-unresolved jobs remain remote"
            ),
            target_contract_version="railway_retained_job_receipt/v1",
        ),
        RetentionRule(
            "standup_payload_compaction",
            "standups",
            """SELECT t.id::text,pg_column_size(t.payload),to_jsonb(t)
            FROM standups t WHERE FALSE ORDER BY t.id::text""",
            (),
            "compact_standup_payload",
            "standup_local_migration",
            f"""SELECT t.id::text,pg_column_size(t.payload),to_jsonb(t)
            FROM standups t WHERE LOWER(COALESCE(t.status,''))=ANY(%s)
              AND {standup_last_mutation}<%s
              AND t.created_at>=%s AND pg_column_size(t.payload)>2048
              ORDER BY t.id::text""",
            (list(TERMINAL_STANDUP_STATES), recent_cutoff, audit_cutoff),
            (
                "standup_payload_compaction_blocked_no_complete_active_consumer_contract; "
                "local archive proof does not authorize remote mutation"
            ),
            target_contract_version="railway_retained_standup_receipt/v1",
        ),
        RetentionRule(
            "standup_rows_after_audit_window",
            "standups",
            """SELECT t.id::text,pg_column_size(t),to_jsonb(t)
            FROM standups t WHERE FALSE ORDER BY t.id::text""",
            (),
            "delete",
            "standup_local_migration",
            f"""SELECT t.id::text,pg_column_size(t),to_jsonb(t)
            FROM standups t WHERE LOWER(COALESCE(t.status,''))=ANY(%s)
              AND {standup_last_mutation}<%s
              AND t.created_at<%s
              ORDER BY t.id::text""",
            (list(TERMINAL_STANDUP_STATES), audit_cutoff, audit_cutoff),
            (
                "standup_row_deletion_blocked_no_complete_historical_consumer_contract; "
                "local archive proof does not authorize remote mutation"
            ),
            target_contract_version="railway_retained_standup_receipt/v1",
        ),
        RetentionRule(
            "workspace_snapshot_payload_compaction",
            "workspace_snapshots",
            f"""SELECT t.id::text,pg_column_size(t.payload),to_jsonb(t)
            FROM workspace_snapshots t WHERE {snapshot_eligible} ORDER BY t.id::text""",
            (),
            "compact_workspace_snapshot_payload",
            "bounded_projection_migration",
            f"""SELECT t.id::text,pg_column_size(t.payload),to_jsonb(t)
            FROM workspace_snapshots t WHERE {snapshot_blocked} ORDER BY t.id::text""",
            (),
            (
                "workspace_snapshot_compaction_blocked_no_versioned_per_type_projector_or_consumer_acceptance; "
                "active/unknown catch-all snapshots remain remote"
            ),
            "railway_retained_workspace_snapshot_receipt/v1",
        ),
    )


def _rule_contract(rules: Iterable[RetentionRule], *, as_of: datetime) -> dict[str, Any]:
    return {
        "schema_version": "railway_retention_rules/v3",
        "as_of": as_of.astimezone(timezone.utc).isoformat(),
        "rules": [
            {
                "name": rule.name,
                "table_name": rule.table_name,
                "params": list(rule.params),
                "mutation_kind": rule.mutation_kind,
                "migration_gate": rule.migration_gate,
                "candidate_sql_sha256": hashlib.sha256(rule.candidate_sql.encode("utf-8")).hexdigest(),
                "blocked_sql_sha256": (
                    hashlib.sha256(rule.blocked_sql.encode("utf-8")).hexdigest() if rule.blocked_sql else None
                ),
                "target_contract_version": rule.target_contract_version,
                "local_proof_kind": rule.local_proof_kind,
            }
            for rule in rules
        ],
    }


def _candidate_rows(
    cursor: Any,
    rule: RetentionRule,
    *,
    blocked: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = rule.blocked_sql if blocked else rule.candidate_sql
    params = rule.blocked_params if blocked else rule.params
    if not query:
        return []
    if limit is not None:
        bounded_limit = max(1, min(int(limit), 5_000))
        bounded_offset = max(0, int(offset))
        query = (
            "SELECT * FROM (" + query + ") AS retention_archive_candidates "
            "ORDER BY 1 LIMIT %s OFFSET %s"
        )
        params = (*params, bounded_limit, bounded_offset)
    cursor.execute(query, params)
    rows = []
    for row in cursor.fetchall() or []:
        source = row[2]
        if isinstance(source, str):
            source = json.loads(source)
        # A signed participant report is the evidence that lets the historical
        # standup verifier reconstruct real attendance. A daily count cannot
        # substitute for its signed metadata, so keep it out of the mutation
        # set even if a future SQL edit accidentally widens the candidate query.
        if (
            rule.table_name == "automation_runs"
            and not blocked
            and str((source or {}).get("automation_id") or "")
            in HISTORICAL_DETAIL_REQUIRED_AUTOMATION_IDS
        ):
            continue
        if rule.table_name == "local_codex_jobs":
            source_row = dict((source or {}).get("row") or {})
            local_receipt = str(source_row.get("retention_local_receipt_sha256") or "")
        elif rule.table_name == "standups":
            local_receipt = str((source or {}).get("retention_local_receipt_sha256") or "")
        elif rule.table_name == "workspace_snapshots":
            local_receipt = str(dict((source or {}).get("metadata") or {}).get("local_archive_receipt_sha256") or "")
        else:
            local_receipt = ""
        rows.append(
            {
                "identity": str(row[0]),
                "bytes": int(row[1] or 0),
                "source": source,
                "source_sha256": _sha256(source),
                "migration_source_sha256": _migration_source_sha256(rule.table_name, source),
                "local_migration_receipt_sha256": (
                    local_receipt if re.fullmatch(r"[0-9a-f]{64}", local_receipt) else None
                ),
            }
        )
    return rows


def _candidate_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = [
        {
            "identity": row["identity"],
            "bytes": row["bytes"],
            "source_sha256": row["source_sha256"],
            "migration_source_sha256": row["migration_source_sha256"],
            "local_migration_receipt_sha256": row["local_migration_receipt_sha256"],
        }
        for row in rows
    ]
    return {
        "rows": len(rows),
        "bytes": sum(item["bytes"] for item in rows),
        "manifest_sha256": _sha256(manifest),
    }


def _preview(
    cursor: Any,
    rules: Iterable[RetentionRule],
    *,
    enabled_migration_gates: tuple[str, ...],
    verified_local_migration_proofs: tuple[dict[str, str], ...],
    verified_local_automation_proofs: tuple[dict[str, str], ...],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    source_by_rule: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        candidates = _candidate_rows(cursor, rule)
        blocked = _candidate_rows(cursor, rule, blocked=True)
        unverified_local: list[dict[str, Any]] = []
        unverified_reason: str | None = None
        if rule.local_proof_kind == "automation_run":
            verified_automation = {
                item["row_identity"]: item["source_row_sha256"]
                for item in verified_local_automation_proofs
            }
            eligible_local: list[dict[str, Any]] = []
            for item in candidates:
                target = (
                    eligible_local
                    if verified_automation.get(item["identity"]) == item["migration_source_sha256"]
                    else unverified_local
                )
                target.append(item)
            candidates = eligible_local
            blocked.extend(unverified_local)
            unverified_reason = "local_automation_ledger_row_not_verified"
        elif rule.migration_gate:
            verified = {item["receipt_sha256"]: item for item in verified_local_migration_proofs}
            verified_by_binding: dict[tuple[str, str, str, str], str] = {}
            for proof in verified_local_migration_proofs:
                key = (
                    proof["source_table"],
                    proof["rule_name"],
                    proof["row_identity"],
                    proof["source_row_sha256"],
                )
                current = verified_by_binding.get(key)
                receipt_sha256 = proof["receipt_sha256"]
                if current is None or receipt_sha256 < current:
                    verified_by_binding[key] = receipt_sha256
            eligible_local = []
            for item in candidates:
                pointer = str(item.get("local_migration_receipt_sha256") or "")
                binding = verified.get(pointer)
                if binding is None:
                    matched_receipt = verified_by_binding.get(
                        (rule.table_name, rule.name, item["identity"], item["migration_source_sha256"])
                    )
                    if matched_receipt:
                        binding = verified[matched_receipt]
                        item["local_migration_receipt_sha256"] = matched_receipt
                if not binding or (
                    binding["source_table"] != rule.table_name
                    or binding["rule_name"] != rule.name
                    or binding["row_identity"] != item["identity"]
                    or binding["source_row_sha256"] != item["migration_source_sha256"]
                ):
                    unverified_local.append(item)
                else:
                    eligible_local.append(item)
            candidates = eligible_local
            blocked.extend(unverified_local)
            unverified_reason = "local_migration_receipt_not_verified"
        source_by_rule[rule.name] = candidates
        candidate_summary = _candidate_summary(candidates)
        blocked_summary = _candidate_summary(blocked)
        gate_enabled = rule.migration_gate is None or rule.migration_gate in enabled_migration_gates
        if candidates and not gate_enabled:
            mutation_status = "blocked"
            mutation_blocker = f"migration_gate_not_enabled:{rule.migration_gate}"
        elif candidates:
            mutation_status = "ready_with_blocked_rows" if blocked else "ready"
            mutation_blocker = (
                unverified_reason
                if unverified_local
                else rule.blocked_reason if blocked else None
            )
        elif blocked:
            mutation_status = "blocked"
            mutation_blocker = unverified_reason if unverified_local else rule.blocked_reason
        else:
            mutation_status = "not_applicable"
            mutation_blocker = None
        results.append(
            {
                "rule": rule.name,
                "table_name": rule.table_name,
                "candidate_rows": candidate_summary["rows"],
                "candidate_bytes": candidate_summary["bytes"],
                "candidate_manifest_sha256": candidate_summary["manifest_sha256"],
                "blocked_rows": blocked_summary["rows"],
                "blocked_bytes": blocked_summary["bytes"],
                "blocked_manifest_sha256": blocked_summary["manifest_sha256"],
                "applied": False,
                "affected_rows": 0,
                "migration_gate": rule.migration_gate,
                "migration_gate_enabled": gate_enabled,
                "mutation_kind": rule.mutation_kind,
                "mutation_status": mutation_status,
                **({"blocked_reason": mutation_blocker} if mutation_blocker else {}),
            }
        )
    return results, source_by_rule


def _database_metrics(cursor: Any) -> dict[str, Any]:
    source_relations = {
        "automation_runs",
        "standups",
        "workspace_snapshots",
        "local_codex_jobs",
        "local_codex_job_artifacts",
    }
    retention_relations = {
        "automation_run_daily_receipts",
        "railway_retention_receipts",
        "railway_retention_rule_receipts",
        "railway_retention_row_receipts",
    }
    tracked_relations = sorted(source_relations | retention_relations)
    cursor.execute("SELECT pg_database_size(current_database())")
    database_bytes = int(cursor.fetchone()[0] or 0)
    cursor.execute(
        """SELECT relname,pg_relation_size(relid),pg_table_size(relid),
        pg_indexes_size(relid),pg_total_relation_size(relid),
        COALESCE(n_live_tup,0),COALESCE(n_dead_tup,0)
        FROM pg_stat_user_tables WHERE relname=ANY(%s) ORDER BY relname""",
        (tracked_relations,),
    )
    relation_metrics = {
        str(row[0]): {
            "heap_bytes": int(row[1] or 0),
            "table_including_toast_bytes": int(row[2] or 0),
            "index_bytes": int(row[3] or 0),
            "total_bytes": int(row[4] or 0),
            "estimated_live_rows": int(row[5] or 0),
            "estimated_dead_rows": int(row[6] or 0),
        }
        for row in (cursor.fetchall() or [])
    }
    relation_bytes = {
        name: int(metrics["total_bytes"])
        for name, metrics in relation_metrics.items()
    }
    return {
        "database_bytes": database_bytes,
        "relation_bytes": relation_bytes,
        "relation_metrics": relation_metrics,
        "tracked_source_relation_bytes": sum(
            relation_bytes.get(name, 0) for name in source_relations
        ),
        "tracked_retention_overhead_bytes": sum(
            relation_bytes.get(name, 0) for name in retention_relations
        ),
        "tracked_relation_bytes": sum(relation_bytes.values()),
        "row_counts_are_estimates": True,
        "dead_tuples_may_require_normal_autovacuum": True,
        "physical_reclamation_claimed": False,
    }


def _write_automation_aggregates(cursor: Any, *, receipt_id: str, rows: list[dict[str, Any]]) -> int:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in rows:
        row = dict(candidate["source"] or {})
        timestamp = _normalized_utc_timestamp(
            row.get("finished_at") or row.get("run_at") or row.get("created_at")
        )
        bucket_date = str(timestamp)[:10]
        key = (
            bucket_date,
            row.get("automation_id"),
            row.get("automation_name"),
            str(row.get("status") or "unknown").lower(),
            row.get("workspace_key"),
            row.get("source"),
            row.get("runtime"),
        )
        groups[key].append(candidate)
    aggregate_rows: list[tuple[Any, ...]] = []
    for key, members in groups.items():
        bucket_date, automation_id, automation_name, status, workspace_key, source, runtime = key
        identifiers = [item["identity"] for item in members]
        dimension_key = _sha256(list(key))
        identifiers_sha = _sha256(identifiers)
        source_rows = [dict(item["source"] or {}) for item in members]
        timestamps = sorted(
            timestamp
            for timestamp in (
                _normalized_utc_timestamp(
                    item.get("finished_at") or item.get("run_at") or item.get("created_at")
                )
                for item in source_rows
            )
            if timestamp is not None
        )
        aggregate_rows.append(
            (
                receipt_id,
                dimension_key,
                bucket_date,
                automation_id,
                automation_name,
                status,
                workspace_key,
                source,
                runtime,
                len(members),
                sum(1 for item in source_rows if item.get("delivered") is True),
                sum(max(0, int(item.get("duration_ms") or 0)) for item in source_rows),
                timestamps[0] if timestamps else None,
                timestamps[-1] if timestamps else None,
                _canonical_json(identifiers),
                identifiers_sha,
            )
        )
    if aggregate_rows:
        cursor.executemany(
            """INSERT INTO automation_run_daily_receipts(
                retention_receipt_id,dimension_key,bucket_date,automation_id,automation_name,
                normalized_status,workspace_key,source,runtime,run_count,delivered_count,
                total_duration_ms,first_run_at,last_run_at,source_row_ids,source_row_ids_sha256
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            aggregate_rows,
        )
        if int(cursor.rowcount or 0) != len(aggregate_rows):
            raise RuntimeError("automation aggregate affected-row mismatch; transaction aborted")
    return len(groups)


def _row_snapshot(cursor: Any, *, table_name: str, identity: str) -> Any | None:
    if table_name == "local_codex_jobs":
        cursor.execute(
            """SELECT jsonb_build_object(
                'row',to_jsonb(t),
                'child_artifacts',COALESCE((
                    SELECT jsonb_agg(to_jsonb(a) ORDER BY a.artifact_id)
                    FROM local_codex_job_artifacts a WHERE a.job_id=t.id
                ),'[]'::jsonb)
            ) FROM local_codex_jobs t WHERE t.id::text=%s""",
            (identity,),
        )
    elif table_name in {"standups", "workspace_snapshots", "automation_runs"}:
        cursor.execute(f"SELECT to_jsonb(t) FROM {table_name} t WHERE t.id::text=%s", (identity,))
    else:  # pragma: no cover - rules are a closed internal contract
        raise ValueError("unsupported retention table")
    row = cursor.fetchone()
    return row[0] if row else None


def _table_schema_sha256(cursor: Any, table_name: str) -> str:
    cursor.execute(
        """SELECT table_name,ordinal_position,column_name,data_type,udt_name,is_nullable
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=ANY(%s) ORDER BY table_name,ordinal_position""",
        ([table_name, "local_codex_job_artifacts"] if table_name == "local_codex_jobs" else [table_name],),
    )
    return _sha256([list(row) for row in (cursor.fetchall() or [])])


def _write_row_receipt(
    cursor: Any,
    *,
    receipt_id: str,
    rule: RetentionRule,
    candidate: dict[str, Any],
    target_sha256: str | None,
) -> None:
    if rule.migration_gate and candidate.get("local_migration_receipt_sha256") is None:
        raise RuntimeError("retention candidate lacks its verified local migration receipt")
    cursor.execute(
        """INSERT INTO railway_retention_row_receipts(
            retention_receipt_id,rule_name,table_name,row_identity,mutation_kind,
            source_row_sha256,target_row_sha256,source_schema_sha256,source_bytes,
            local_migration_receipt_sha256
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (retention_receipt_id,rule_name,row_identity) DO NOTHING""",
        (
            receipt_id,
            rule.name,
            rule.table_name,
            candidate["identity"],
            rule.mutation_kind,
            candidate["source_sha256"],
            target_sha256,
            _table_schema_sha256(cursor, rule.table_name),
            candidate["bytes"],
            candidate["local_migration_receipt_sha256"],
        ),
    )
    if int(cursor.rowcount or 0) != 1:
        raise RuntimeError("retention row receipt collision; transaction aborted")


def _bounded_text(value: Any, *, limit: int = 600) -> str:
    return " ".join(str(value or "").split())[:limit]


def _bounded_strings(value: Any, *, count: int = 12, width: int = 400) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_bounded_text(item, limit=width) for item in value[:count]) if text]


def _bounded_standup_sections(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    retained: dict[str, list[str]] = {}
    for key in sorted(value)[:12]:
        normalized_key = _bounded_text(key, limit=80)
        items = _bounded_strings(value.get(key), count=8, width=300)
        if normalized_key and items:
            retained[normalized_key] = items
    return retained


def _bounded_discussion(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    retained: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        note = _bounded_text(item.get("note"), limit=500)
        if not note:
            continue
        retained.append(
            {
                "round": int(item.get("round")) if isinstance(item.get("round"), int) else None,
                "speaker": _bounded_text(item.get("speaker"), limit=100),
                "role": _bounded_text(item.get("role"), limit=100),
                "note": note,
            }
        )
    return retained


def _compact_job(cursor: Any, *, receipt_id: str, candidate: dict[str, Any]) -> str:
    source = dict(candidate["source"] or {})
    original_row = dict(source.get("row") or {})
    retained = {
        "schema_version": "railway_retained_job_receipt/v1",
        "compacted": True,
        "archive_state": "archived_locally",
        "retention_receipt_id": receipt_id,
        "local_migration_receipt_sha256": candidate["local_migration_receipt_sha256"],
        "source_row_sha256": candidate["source_sha256"],
        "source_bytes": candidate["bytes"],
        "terminal_status": str(original_row.get("status") or "").lower(),
        "original_result_schema_version": str((original_row.get("result_payload") or {}).get("schema_version") or "")[:120],
    }
    artifacts = [item for item in (source.get("child_artifacts") or []) if isinstance(item, dict)]
    artifact_ids = [str(item.get("artifact_id") or "") for item in artifacts]
    if artifact_ids:
        cursor.execute(
            "DELETE FROM local_codex_job_artifacts WHERE job_id=%s AND artifact_id=ANY(%s)",
            (candidate["identity"], artifact_ids),
        )
        if int(cursor.rowcount or 0) != len(artifact_ids):
            raise RuntimeError("job artifact deletion affected-row mismatch; transaction aborted")
    cursor.execute("SELECT COUNT(*) FROM local_codex_job_artifacts WHERE job_id=%s", (candidate["identity"],))
    if int(cursor.fetchone()[0] or 0) != 0:
        raise RuntimeError("job artifact deletion left an unplanned child row; transaction aborted")
    cursor.execute(
        """UPDATE local_codex_jobs SET request_payload='{}'::jsonb,context_packet='{}'::jsonb,
        result_payload=%s::jsonb,artifacts='[]'::jsonb,
        retention_contract_version='railway_retained_job_receipt/v1',updated_at=NOW()
        WHERE id::text=%s AND to_jsonb(local_codex_jobs)=%s::jsonb""",
        (_canonical_json(retained), candidate["identity"], _canonical_json(original_row)),
    )
    if int(cursor.rowcount or 0) != 1:
        raise RuntimeError("job payload compaction affected-row mismatch; transaction aborted")
    target = _row_snapshot(cursor, table_name="local_codex_jobs", identity=candidate["identity"])
    if target is None:
        raise RuntimeError("job payload compaction target disappeared; transaction aborted")
    return _sha256(target)


def _compact_standup(cursor: Any, *, receipt_id: str, candidate: dict[str, Any]) -> str:
    source = dict(candidate["source"] or {})
    original_payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
    retained = {
        "schema_version": "railway_retained_standup_receipt/v1",
        "compacted": True,
        "archive_state": "archived_locally",
        "retention_receipt_id": receipt_id,
        "local_migration_receipt_sha256": candidate["local_migration_receipt_sha256"],
        "source_row_sha256": candidate["source_sha256"],
        "source_payload_sha256": _sha256(original_payload),
        "source_bytes": candidate["bytes"],
        "original_schema_version": str(original_payload.get("schema_version") or "")[:120],
        "summary": _bounded_text(original_payload.get("summary"), limit=1000),
        "standup_kind": _bounded_text(original_payload.get("standup_kind"), limit=100),
        "portfolio_cycle_id": _bounded_text(original_payload.get("portfolio_cycle_id"), limit=160),
        "conclusion_kind": _bounded_text(original_payload.get("conclusion_kind"), limit=100),
        "agenda": _bounded_strings(original_payload.get("agenda")),
        "decisions": _bounded_strings(original_payload.get("decisions")),
        "owners": _bounded_strings(original_payload.get("owners")),
        "artifact_deltas": _bounded_strings(original_payload.get("artifact_deltas")),
        "participants": _bounded_strings(original_payload.get("participants"), count=8, width=100),
        "discussion": _bounded_discussion(original_payload.get("discussion")),
        "standup_sections": _bounded_standup_sections(original_payload.get("standup_sections")),
        "pm_snapshot": {"lines": _bounded_strings(dict(original_payload.get("pm_snapshot") or {}).get("lines"))}
        if isinstance(original_payload.get("pm_snapshot"), dict)
        else {"lines": []},
    }
    cursor.execute(
        """UPDATE standups SET payload=%s::jsonb,
        retention_contract_version='railway_retained_standup_receipt/v1',updated_at=NOW()
        WHERE id::text=%s AND to_jsonb(standups)=%s::jsonb""",
        (_canonical_json(retained), candidate["identity"], _canonical_json(source)),
    )
    if int(cursor.rowcount or 0) != 1:
        raise RuntimeError("standup payload compaction affected-row mismatch; transaction aborted")
    target = _row_snapshot(cursor, table_name="standups", identity=candidate["identity"])
    if target is None:
        raise RuntimeError("standup payload compaction target disappeared; transaction aborted")
    return _sha256(target)


def _compact_workspace_snapshot(cursor: Any, *, receipt_id: str, candidate: dict[str, Any]) -> str:
    source = dict(candidate["source"] or {})
    original_payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
    original_metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    retained = {
        "schema_version": "railway_retained_workspace_snapshot_receipt/v1",
        "compacted": True,
        "retention_receipt_id": receipt_id,
        "source_row_sha256": candidate["source_sha256"],
        "source_payload_sha256": _sha256(original_payload),
        "source_bytes": candidate["bytes"],
        "original_schema_version": str(original_payload.get("schema_version") or "")[:120],
        "lifecycle_status": str(
            (source.get("metadata") or {}).get("lifecycle_status")
            or original_payload.get("lifecycle_status")
            or original_payload.get("status")
            or ""
        ).lower()[:40],
    }
    retained_metadata = {
        **original_metadata,
        "retention_state": "compacted",
        "retained_contract": "railway_retained_workspace_snapshot_receipt/v1",
        "retention_receipt_id": receipt_id,
    }
    cursor.execute(
        """UPDATE workspace_snapshots SET payload=%s::jsonb,metadata=%s::jsonb,updated_at=NOW()
        WHERE id::text=%s AND to_jsonb(workspace_snapshots)=%s::jsonb""",
        (
            _canonical_json(retained),
            _canonical_json(retained_metadata),
            candidate["identity"],
            _canonical_json(source),
        ),
    )
    if int(cursor.rowcount or 0) != 1:
        raise RuntimeError("workspace snapshot compaction affected-row mismatch; transaction aborted")
    target = _row_snapshot(cursor, table_name="workspace_snapshots", identity=candidate["identity"])
    if target is None:
        raise RuntimeError("workspace snapshot compaction target disappeared; transaction aborted")
    return _sha256(target)


def _apply_rule(
    cursor: Any,
    *,
    receipt_id: str,
    rule: RetentionRule,
    candidates: list[dict[str, Any]],
) -> dict[str, int]:
    if rule.mutation_kind == "delete_with_daily_aggregate":
        # Apply has already re-derived the exact manifest under SERIALIZABLE and
        # locked the complete ID set. Use set-based writes so a large mirror
        # retention pass does not issue two SQL round trips per source row.
        aggregate_count = _write_automation_aggregates(cursor, receipt_id=receipt_id, rows=candidates)
        identifiers = [candidate["identity"] for candidate in candidates]
        if identifiers:
            cursor.execute("DELETE FROM automation_runs WHERE id::text=ANY(%s)", (identifiers,))
            if int(cursor.rowcount or 0) != len(identifiers):
                raise RuntimeError("automation retention affected-row mismatch; transaction aborted")
        return {"affected_rows": len(candidates), "aggregate_receipts": aggregate_count, "row_receipts": 0}

    for candidate in candidates:
        current = _row_snapshot(cursor, table_name=rule.table_name, identity=candidate["identity"])
        if current is None or _sha256(current) != candidate["source_sha256"]:
            raise RuntimeError("retention candidate preimage changed; transaction aborted")

    row_receipts = 0
    for candidate in candidates:
        if rule.mutation_kind == "compact_job_payload_and_delete_artifacts":
            target_sha256 = _compact_job(cursor, receipt_id=receipt_id, candidate=candidate)
        elif rule.mutation_kind == "compact_standup_payload":
            target_sha256 = _compact_standup(cursor, receipt_id=receipt_id, candidate=candidate)
        elif rule.mutation_kind == "compact_workspace_snapshot_payload":
            target_sha256 = _compact_workspace_snapshot(cursor, receipt_id=receipt_id, candidate=candidate)
        elif rule.mutation_kind == "delete":
            cursor.execute(
                f"DELETE FROM {rule.table_name} WHERE id::text=%s AND to_jsonb({rule.table_name})=%s::jsonb",
                (candidate["identity"], _canonical_json(candidate["source"])),
            )
            if int(cursor.rowcount or 0) != 1:
                raise RuntimeError("retention deletion affected-row mismatch; transaction aborted")
            target_sha256 = None
        else:  # pragma: no cover - rules are a closed internal contract
            raise ValueError("unsupported retention mutation")
        _write_row_receipt(
            cursor,
            receipt_id=receipt_id,
            rule=rule,
            candidate=candidate,
            target_sha256=target_sha256,
        )
        row_receipts += 1
    return {"affected_rows": len(candidates), "aggregate_receipts": 0, "row_receipts": row_receipts}


def _lock_candidates(cursor: Any, *, rule: RetentionRule, candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        return
    identifiers = [item["identity"] for item in candidates]
    cursor.execute(
        f"SELECT id FROM {rule.table_name} WHERE id::text=ANY(%s) ORDER BY id::text FOR UPDATE",
        (identifiers,),
    )
    if len(cursor.fetchall() or []) != len(identifiers):
        raise RuntimeError("retention candidate lock set changed; transaction aborted")
    if rule.table_name == "local_codex_jobs":
        cursor.execute(
            """SELECT artifact_id FROM local_codex_job_artifacts
            WHERE job_id=ANY(%s) ORDER BY artifact_id FOR UPDATE""",
            (identifiers,),
        )
        cursor.fetchall()


def _plan_payload(
    *,
    fixed_as_of: datetime,
    rules_sha256: str,
    enabled_migration_gates: tuple[str, ...],
    verified_local_migration_proofs: tuple[dict[str, str], ...],
    verified_local_automation_proofs: tuple[dict[str, str], ...],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    core = {
        "schema_version": "railway_retention_plan/v4",
        "as_of": fixed_as_of.isoformat(),
        "rules_sha256": rules_sha256,
        "enabled_migration_gates": list(enabled_migration_gates),
        "verified_local_migration_receipts": [
            item["receipt_sha256"] for item in verified_local_migration_proofs
        ],
        "verified_local_migration_proofs": list(verified_local_migration_proofs),
        "verified_local_automation_proof_manifest": {
            "rows": len(verified_local_automation_proofs),
            "manifest_sha256": _sha256(list(verified_local_automation_proofs)),
        },
        "rules": results,
    }
    return {**core, "plan_sha256": _sha256(core)}


def _plan_rule_lifecycle(result: dict[str, Any]) -> str:
    if int(result.get("candidate_rows") or 0) > 0 and result.get("mutation_status") != "blocked":
        return "planned"
    if int(result.get("candidate_rows") or 0) > 0 or int(result.get("blocked_rows") or 0) > 0:
        return "blocked"
    return "not_applicable"


def _write_plan_rule_receipts(cursor: Any, *, receipt_id: str, results: list[dict[str, Any]]) -> None:
    for result in results:
        cursor.execute(
            """INSERT INTO railway_retention_rule_receipts(
                retention_receipt_id,rule_name,lifecycle_status,candidate_rows,candidate_bytes,
                candidate_manifest_sha256,blocked_rows,blocked_reason,affected_rows
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0)
            ON CONFLICT (retention_receipt_id,rule_name) DO NOTHING""",
            (
                receipt_id,
                result["rule"],
                _plan_rule_lifecycle(result),
                result["candidate_rows"],
                result["candidate_bytes"],
                result["candidate_manifest_sha256"],
                result["blocked_rows"],
                result.get("blocked_reason"),
            ),
        )


def _update_rule_receipt(
    cursor: Any,
    *,
    receipt_id: str,
    result: dict[str, Any],
    lifecycle_status: str,
) -> None:
    cursor.execute(
        """UPDATE railway_retention_rule_receipts
        SET lifecycle_status=%s,affected_rows=%s,updated_at=NOW()
        WHERE retention_receipt_id=%s AND rule_name=%s""",
        (lifecycle_status, int(result.get("affected_rows") or 0), receipt_id, result["rule"]),
    )
    if int(cursor.rowcount or 0) != 1:
        raise RuntimeError("retention per-rule receipt lifecycle update failed")


def _validate_plan_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "railway_retention_plan/v4":
        raise ValueError("retention plan schema is unsupported")
    expected = str(payload.get("plan_sha256") or "")
    core = {key: value for key, value in payload.items() if key != "plan_sha256"}
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None or _sha256(core) != expected:
        raise ValueError("retention plan hash is invalid")


def _normalize_backup_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("backup receipt timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def run_retention(
    *,
    pool: Any,
    apply: bool = False,
    persist_plan: bool = False,
    plan_receipt_id: str | None = None,
    backup_receipt_sha256: str | None = None,
    backup_receipt_verified: bool = False,
    backup_receipt_created_at: datetime | None = None,
    backup_source_snapshot_at: datetime | None = None,
    backup_plan_receipt_id: str | None = None,
    backup_plan_sha256: str | None = None,
    enabled_migration_gates: Iterable[str] | None = None,
    verified_local_migration_receipts: Mapping[str, Mapping[str, str]] | None = None,
    verified_local_automation_runs: Mapping[str, str] | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    if apply and persist_plan:
        raise ValueError("retention plan creation and apply must be separate transactions")
    backup_created_at = _normalize_backup_time(backup_receipt_created_at)
    backup_snapshot_at = _normalize_backup_time(backup_source_snapshot_at)
    if apply and (
        not plan_receipt_id
        or not backup_receipt_sha256
        or re.fullmatch(r"[0-9a-f]{64}", backup_receipt_sha256) is None
        or not backup_receipt_verified
        or backup_created_at is None
        or backup_snapshot_at is None
        or backup_plan_receipt_id != plan_receipt_id
        or re.fullmatch(r"[0-9a-f]{64}", str(backup_plan_sha256 or "")) is None
    ):
        raise ValueError(
            "apply requires an exact persisted plan and a verified newer production-backup receipt SHA-256"
        )
    requested_gates = _normalize_gates(enabled_migration_gates)
    requested_local_proofs = _normalize_receipt_proofs(verified_local_migration_receipts)
    requested_automation_proofs = _normalize_automation_proofs(verified_local_automation_runs)
    fixed_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    planned: tuple[Any, ...] | None = None

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            if apply:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (RETENTION_LOCK_ID,))
                cursor.execute(
                    """SELECT lifecycle_status,as_of,rules_sha256,plan_sha256,plan_json,created_at
                    FROM railway_retention_receipts WHERE receipt_id=%s FOR UPDATE""",
                    (plan_receipt_id,),
                )
                planned = cursor.fetchone()
                if not planned or planned[0] != "planned":
                    raise ValueError("retention plan is missing or no longer applicable")
                fixed_as_of = planned[1].astimezone(timezone.utc)
                planned_payload = planned[4] if isinstance(planned[4], dict) else json.loads(planned[4])
                _validate_plan_payload(planned_payload)
                persisted_gates = _normalize_gates(planned_payload.get("enabled_migration_gates"))
                if requested_gates and requested_gates != persisted_gates:
                    raise ValueError("apply migration gates do not match the exact persisted plan")
                requested_gates = persisted_gates
                persisted_local_proofs = _normalize_receipt_proofs(
                    {
                        str(item.get("receipt_sha256") or ""): {
                            field: str(item.get(field) or "") for field in _LOCAL_PROOF_BINDING_FIELDS
                        }
                        for item in (planned_payload.get("verified_local_migration_proofs") or [])
                        if isinstance(item, dict)
                    }
                )
                if [item["receipt_sha256"] for item in persisted_local_proofs] != list(
                    planned_payload.get("verified_local_migration_receipts") or []
                ):
                    raise ValueError("persisted retention plan local migration proof index is invalid")
                current_local_proofs = {
                    item["receipt_sha256"]: item for item in requested_local_proofs
                }
                if any(
                    current_local_proofs.get(item["receipt_sha256"]) != item
                    for item in persisted_local_proofs
                ):
                    raise ValueError("a local migration receipt bound to the retention plan is no longer verified")
                requested_local_proofs = persisted_local_proofs
                automation_manifest = planned_payload.get("verified_local_automation_proof_manifest")
                if not isinstance(automation_manifest, dict) or set(automation_manifest) != {
                    "rows",
                    "manifest_sha256",
                } or int(automation_manifest.get("rows") or 0) < 0 or re.fullmatch(
                    r"[0-9a-f]{64}", str(automation_manifest.get("manifest_sha256") or "")
                ) is None:
                    raise ValueError("persisted retention plan local automation proof manifest is invalid")
                plan_created_at = planned[5].astimezone(timezone.utc)
                if backup_created_at <= plan_created_at:
                    raise ValueError("verified production backup must be newer than the exact retention plan")
                if backup_snapshot_at <= plan_created_at:
                    raise ValueError("production backup source snapshot must begin after the exact retention plan")
                if backup_snapshot_at > backup_created_at:
                    raise ValueError("production backup source snapshot cannot begin after its verification receipt")
                if backup_plan_sha256 != planned_payload["plan_sha256"]:
                    raise ValueError("production backup is not bound to the exact retention plan hash")
                if backup_created_at > datetime.now(timezone.utc) + timedelta(minutes=5):
                    raise ValueError("verified production backup timestamp is implausibly in the future")

            rules = retention_rules(as_of=fixed_as_of)
            contract = _rule_contract(rules, as_of=fixed_as_of)
            rules_sha256 = _sha256(contract)
            results, source_by_rule = _preview(
                cursor,
                rules,
                enabled_migration_gates=requested_gates,
                verified_local_migration_proofs=requested_local_proofs,
                verified_local_automation_proofs=requested_automation_proofs,
            )
            used_receipt_hashes = {
                str(candidate["local_migration_receipt_sha256"])
                for candidates in source_by_rule.values()
                for candidate in candidates
                if candidate.get("local_migration_receipt_sha256")
            }
            used_local_proofs = tuple(
                item for item in requested_local_proofs if item["receipt_sha256"] in used_receipt_hashes
            )
            used_automation_identities = {
                candidate["identity"]
                for candidate in source_by_rule.get("automation_non_action_detail", [])
            }
            used_automation_proofs = tuple(
                item
                for item in requested_automation_proofs
                if item["row_identity"] in used_automation_identities
            )
            plan = _plan_payload(
                fixed_as_of=fixed_as_of,
                rules_sha256=rules_sha256,
                enabled_migration_gates=requested_gates,
                verified_local_migration_proofs=used_local_proofs,
                verified_local_automation_proofs=used_automation_proofs,
                results=results,
            )

            if not apply and not persist_plan:
                connection.rollback()
                return {
                    **plan,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "mode": "dry_run",
                    "candidate_rows": sum(item["candidate_rows"] for item in results),
                    "candidate_bytes": sum(item["candidate_bytes"] for item in results),
                    "blocked_rows": sum(item["blocked_rows"] for item in results),
                    "physical_reclamation_claimed": False,
                }

            if persist_plan:
                receipt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:railway-retention:{plan['plan_sha256']}"))
                before_metrics = _database_metrics(cursor)
                idempotency_key = f"railway-retention-plan:{plan['plan_sha256']}"
                cursor.execute(
                    """INSERT INTO railway_retention_receipts(
                        receipt_id,lifecycle_status,as_of,rules_sha256,plan_sha256,plan_json,before_metrics,idempotency_key
                    ) VALUES (%s,'planned',%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                    ON CONFLICT (idempotency_key) DO NOTHING""",
                    (
                        receipt_id,
                        fixed_as_of,
                        rules_sha256,
                        plan["plan_sha256"],
                        _canonical_json(plan),
                        _canonical_json(before_metrics),
                        idempotency_key,
                    ),
                )
                inserted = int(cursor.rowcount or 0) == 1
                if inserted:
                    _write_plan_rule_receipts(cursor, receipt_id=receipt_id, results=results)
                else:
                    cursor.execute(
                        """SELECT receipt_id,lifecycle_status,as_of,rules_sha256,plan_sha256,
                        plan_json,before_metrics FROM railway_retention_receipts
                        WHERE idempotency_key=%s""",
                        (idempotency_key,),
                    )
                    existing = cursor.fetchone()
                    if not existing:
                        raise RuntimeError("retention plan idempotency collision has no durable receipt")
                    existing_plan = existing[5] if isinstance(existing[5], dict) else json.loads(existing[5])
                    if existing[1] != "planned":
                        raise ValueError(
                            "retention plan was already applied or rolled back; choose a new as_of"
                        )
                    if (
                        existing[0] != receipt_id
                        or existing[2].astimezone(timezone.utc) != fixed_as_of
                        or existing[3] != rules_sha256
                        or existing[4] != plan["plan_sha256"]
                        or _canonical_json(existing_plan) != _canonical_json(plan)
                    ):
                        raise RuntimeError("retention plan idempotency collision does not match the exact plan")
                    cursor.execute(
                        """SELECT COUNT(*) FROM railway_retention_rule_receipts
                        WHERE retention_receipt_id=%s""",
                        (receipt_id,),
                    )
                    if int(cursor.fetchone()[0] or 0) != len(results):
                        raise RuntimeError("persisted retention plan has incomplete per-rule receipts")
                    before_metrics = (
                        existing[6] if isinstance(existing[6], dict) else json.loads(existing[6])
                    )
                connection.commit()
                return {
                    **plan,
                    "mode": "plan",
                    "receipt_id": receipt_id,
                    "before_metrics": before_metrics,
                    "plan_payload_bytes": len(_canonical_json(plan).encode("utf-8")),
                    "idempotent_reuse": not inserted,
                    "physical_reclamation_claimed": False,
                }

            assert planned is not None
            if planned[2] != rules_sha256:
                raise ValueError("retention rules no longer match the persisted plan")
            if planned[3] != plan["plan_sha256"]:
                raise ValueError("retention candidates changed after planning; create a fresh plan and backup")
            persisted_payload = planned[4] if isinstance(planned[4], dict) else json.loads(planned[4])
            if _canonical_json(persisted_payload) != _canonical_json(plan):
                raise ValueError("retention candidates changed after planning; create a fresh plan and backup")

            for rule in rules:
                candidates = source_by_rule[rule.name]
                result = next(item for item in results if item["rule"] == rule.name)
                if candidates and result.get("mutation_status") != "blocked":
                    _lock_candidates(cursor, rule=rule, candidates=candidates)

            for rule, result in zip(rules, results, strict=True):
                candidates = source_by_rule[rule.name]
                if not candidates:
                    _update_rule_receipt(
                        cursor,
                        receipt_id=str(plan_receipt_id),
                        result=result,
                        lifecycle_status="blocked" if result.get("blocked_rows") else "not_applicable",
                    )
                    continue
                if result["mutation_status"] == "blocked":
                    result["skipped_reason"] = str(result.get("blocked_reason") or "retention_rule_blocked")
                    _update_rule_receipt(
                        cursor,
                        receipt_id=str(plan_receipt_id),
                        result=result,
                        lifecycle_status="blocked",
                    )
                    continue
                mutation = _apply_rule(
                    cursor,
                    receipt_id=str(plan_receipt_id),
                    rule=rule,
                    candidates=candidates,
                )
                result.update(
                    {
                        "applied": True,
                        "affected_rows": mutation["affected_rows"],
                        "aggregate_receipts": mutation["aggregate_receipts"],
                        "row_receipts": mutation["row_receipts"],
                    }
                )
                _update_rule_receipt(
                    cursor,
                    receipt_id=str(plan_receipt_id),
                    result=result,
                    lifecycle_status="partially_applied" if result.get("blocked_rows") else "applied",
                )

            after_metrics = _database_metrics(cursor)
            any_applied = any(result.get("applied") is True for result in results)
            any_blocked = any(
                int(result.get("blocked_rows") or 0) > 0
                or (int(result.get("candidate_rows") or 0) > 0 and result.get("applied") is not True)
                for result in results
            )
            if not any_applied:
                raise ValueError("retention plan has no eligible mutation; unresolved migration gates remain blocked")
            parent_lifecycle = "partially_applied" if any_blocked else "applied"
            cursor.execute(
                """UPDATE railway_retention_receipts SET lifecycle_status=%s,
                backup_manifest_sha256=%s,after_metrics=%s::jsonb,applied_at=NOW()
                WHERE receipt_id=%s AND lifecycle_status='planned'""",
                (parent_lifecycle, backup_receipt_sha256, _canonical_json(after_metrics), plan_receipt_id),
            )
            if int(cursor.rowcount or 0) != 1:
                raise RuntimeError("retention receipt lifecycle update failed")
        connection.commit()
    return {
        "schema_version": "railway_retention_receipt/v3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply",
        "lifecycle_status": parent_lifecycle,
        "receipt_id": plan_receipt_id,
        "as_of": fixed_as_of.isoformat(),
        "rules_sha256": rules_sha256,
        "plan_sha256": plan["plan_sha256"],
        "backup_receipt_sha256": backup_receipt_sha256,
        "backup_receipt_created_at": backup_created_at.isoformat() if backup_created_at else None,
        "backup_source_snapshot_at": backup_snapshot_at.isoformat() if backup_snapshot_at else None,
        "enabled_migration_gates": list(requested_gates),
        "rules": results,
        "candidate_rows": sum(item["candidate_rows"] for item in results),
        "candidate_bytes": sum(item["candidate_bytes"] for item in results),
        "blocked_rows": sum(item["blocked_rows"] for item in results),
        "after_metrics": after_metrics,
        "physical_reclamation_claimed": False,
    }
