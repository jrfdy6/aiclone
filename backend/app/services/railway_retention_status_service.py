from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Callable, Mapping

from app.services import open_brain_db


SCHEMA_VERSION = "railway_retention_status_projection/v1"
MODE = "read_only_bounded_receipts"
STALE_AFTER_SECONDS = 48 * 60 * 60

SAFE_REASON_CODES = frozenset(
    {
        "retention_database_unavailable",
        "retention_receipt_missing",
        "retention_plan_stale",
        "retention_plan_blocked",
        "retention_apply_partial",
        "retention_backup_unbound",
        "retention_backup_requires_local_reverification",
        "retention_aggregate_mismatch",
        "retention_rollback_requires_local_backup",
        "retention_physical_cost_unmeasured",
        "retention_no_after_metrics",
        "retention_projection_failed",
    }
)
SAFE_RULE_NAMES = frozenset(
    {
        "automation_non_action_detail",
        "completed_large_job_payloads",
        "standup_payload_compaction",
        "standup_rows_after_audit_window",
        "workspace_snapshot_payload_compaction",
    }
)
SAFE_RULE_STATES = frozenset(
    {"planned", "applied", "partially_applied", "blocked", "not_applicable", "rolled_back"}
)


def _utc(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _utc(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("retention persisted JSON must be an object")
        return parsed
    if value is None:
        return {}
    raise ValueError("retention persisted value must be a JSON object")


def _nonnegative(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _metric_projection(raw: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    relations = raw.get("relation_metrics") if isinstance(raw.get("relation_metrics"), dict) else {}
    estimated_live_rows = sum(
        _nonnegative(metrics.get("estimated_live_rows"))
        for metrics in relations.values()
        if isinstance(metrics, dict)
    )
    estimated_dead_rows = sum(
        _nonnegative(metrics.get("estimated_dead_rows"))
        for metrics in relations.values()
        if isinstance(metrics, dict)
    )
    return {
        "postgres_database_bytes": _nonnegative(raw.get("database_bytes")),
        "tracked_source_relation_bytes": _nonnegative(raw.get("tracked_source_relation_bytes")),
        "tracked_retention_overhead_bytes": _nonnegative(raw.get("tracked_retention_overhead_bytes")),
        "tracked_relation_bytes": _nonnegative(raw.get("tracked_relation_bytes")),
        "estimated_live_rows": estimated_live_rows,
        "estimated_dead_rows": estimated_dead_rows,
        "row_counts_are_estimates": raw.get("row_counts_are_estimates") is not False,
        "physical_reclamation_claimed": raw.get("physical_reclamation_claimed") is True,
    }


def _rule_reason(rule_name: str, blocked_reason: Any) -> str | None:
    if not blocked_reason:
        return None
    if rule_name in {"standup_payload_compaction", "standup_rows_after_audit_window"}:
        return "active_consumer_contract_unproven"
    if rule_name == "workspace_snapshot_payload_compaction":
        return "per_type_projection_contract_unproven"
    if rule_name == "automation_non_action_detail":
        return "unresolved_nonhealthy_rows_retained"
    if rule_name == "completed_large_job_payloads":
        return "terminal_recent_or_unproven_rows_retained"
    return "migration_proof_or_gate_incomplete"


def degraded_retention_status(
    reason_code: str,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    if reason_code not in SAFE_REASON_CODES:
        reason_code = "retention_projection_failed"
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "blocked",
        "ready": False,
        "checked_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stale_after_seconds": STALE_AFTER_SECONDS,
        "reason_codes": [reason_code],
        "plan": {
            "state": "missing",
            "receipt_present": False,
            "lifecycle_status": None,
            "receipt_id": None,
            "as_of": None,
            "created_at": None,
            "applied_at": None,
            "rolled_back_at": None,
            "age_seconds": None,
            "stale": False,
            "candidate_rows": 0,
            "candidate_bytes": 0,
            "blocked_rows": 0,
            "local_archive_proof_count": 0,
        },
        "backup_binding": {
            "state": "missing",
            "bound": False,
            "manifest_recorded": False,
            "exact_plan_binding_recorded": False,
            "local_reverification_required": True,
        },
        "aggregate_compaction": {
            "state": "unavailable",
            "expected_source_rows": 0,
            "aggregated_source_rows": 0,
            "aggregate_receipt_rows": 0,
            "matches": False,
        },
        "rollback": {
            "state": "unavailable",
            "ready": False,
            "row_receipts": 0,
            "aggregate_receipts": 0,
            "requires_isolated_backup_revalidation": True,
        },
        "cost": {
            "state": "unmeasured",
            "before": None,
            "after": None,
            "logical_bytes_reduced": None,
            "logical_reduction_proven": False,
            "physical": {
                "railway_volume_before_bytes": None,
                "railway_volume_after_bytes": None,
                "measured": False,
                "reclamation_claimed": False,
            },
            "cost_reduction_proven": False,
        },
        "rules": [],
        "privacy": {
            "source_rows_returned": False,
            "source_identifiers_returned": False,
            "private_payloads_returned": False,
            "provider_errors_returned": False,
        },
    }


def build_retention_status(
    *,
    pool: Any | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Project bounded retention health from Railway receipts without mutating state."""

    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    if pool is None:
        if not open_brain_db.database_configured():
            return degraded_retention_status("retention_database_unavailable", clock=lambda: now)
        try:
            pool = open_brain_db.get_pool()
        except Exception:
            return degraded_retention_status("retention_database_unavailable", clock=lambda: now)

    try:
        with pool.connection() as connection:
            receipt = connection.execute(
                """SELECT receipt_id,lifecycle_status,as_of,backup_manifest_sha256,
                plan_json,before_metrics,after_metrics,created_at,applied_at,rolled_back_at
                FROM railway_retention_receipts ORDER BY created_at DESC LIMIT 1"""
            ).fetchone()
            if receipt is None:
                return degraded_retention_status("retention_receipt_missing", clock=lambda: now)
            receipt_id = str(receipt[0] or "")
            rule_rows = connection.execute(
                """SELECT rule_name,lifecycle_status,candidate_rows,candidate_bytes,
                blocked_rows,blocked_reason,affected_rows
                FROM railway_retention_rule_receipts
                WHERE retention_receipt_id=%s ORDER BY rule_name""",
                (receipt_id,),
            ).fetchall()
            aggregate = connection.execute(
                """SELECT COUNT(*),COALESCE(SUM(run_count),0)
                FROM automation_run_daily_receipts WHERE retention_receipt_id=%s""",
                (receipt_id,),
            ).fetchone()
            row_receipts = connection.execute(
                """SELECT COUNT(*) FROM railway_retention_row_receipts
                WHERE retention_receipt_id=%s""",
                (receipt_id,),
            ).fetchone()
    except Exception:
        return degraded_retention_status("retention_projection_failed", clock=lambda: now)

    try:
        receipt_values = tuple(receipt)
        if len(receipt_values) != 10:
            raise ValueError("retention receipt projection shape is invalid")
        receipt_id = str(receipt_values[0] or "")
        if re.fullmatch(r"[A-Za-z0-9-]{1,160}", receipt_id) is None:
            raise ValueError("retention receipt identifier is invalid")
        lifecycle_status = str(receipt_values[1] or "")
        if lifecycle_status not in {"planned", "applied", "partially_applied", "rolled_back", "failed"}:
            raise ValueError("retention receipt lifecycle is invalid")
        plan_json = _json_object(receipt_values[4])
        if plan_json.get("schema_version") != "railway_retention_plan/v4":
            raise ValueError("retention persisted plan schema is invalid")
        proof_index = plan_json.get("verified_local_migration_receipts") or []
        if (
            not isinstance(proof_index, list)
            or len(proof_index) > 100_000
            or any(re.fullmatch(r"[0-9a-f]{64}", str(item or "")) is None for item in proof_index)
        ):
            raise ValueError("retention local proof index is invalid")
        before = _metric_projection(_json_object(receipt_values[5]))
        after = _metric_projection(_json_object(receipt_values[6]))
        created_at = _utc(receipt_values[7])
        if created_at is None:
            raise ValueError("retention receipt creation time is missing")
        as_of_iso = _iso(receipt_values[2])
        created_at_iso = _iso(receipt_values[7])
        applied_at_iso = _iso(receipt_values[8])
        rolled_back_at_iso = _iso(receipt_values[9])
        rule_values = [tuple(row) for row in rule_rows]
        if len(rule_values) > 16 or any(len(row) != 7 for row in rule_values):
            raise ValueError("retention rule projection shape is invalid")
        rules = [
            {
                "rule": str(row[0]),
                "state": str(row[1]),
                "candidate_rows": _nonnegative(row[2]),
                "candidate_bytes": _nonnegative(row[3]),
                "blocked_rows": _nonnegative(row[4]),
                "affected_rows": _nonnegative(row[6]),
                "reason_code": _rule_reason(str(row[0]), row[5]),
            }
            for row in rule_values
        ]
        if any(
            item["rule"] not in SAFE_RULE_NAMES or item["state"] not in SAFE_RULE_STATES
            for item in rules
        ):
            raise ValueError("retention rule projection value is invalid")
        aggregate_values = tuple(aggregate) if aggregate is not None else (0, 0)
        row_receipt_values = tuple(row_receipts) if row_receipts is not None else (0,)
        if len(aggregate_values) < 2 or len(row_receipt_values) < 1:
            raise ValueError("retention aggregate projection shape is invalid")
    except (AttributeError, json.JSONDecodeError, OverflowError, TypeError, ValueError):
        return degraded_retention_status("retention_projection_failed", clock=lambda: now)

    age_seconds = max(0, int((now - created_at).total_seconds())) if created_at else None
    stale = age_seconds is None or age_seconds > STALE_AFTER_SECONDS
    candidate_rows = sum(item["candidate_rows"] for item in rules)
    candidate_bytes = sum(item["candidate_bytes"] for item in rules)
    blocked_rows = sum(item["blocked_rows"] for item in rules)
    local_proof_count = len(proof_index)
    backup_bound = bool(str(receipt_values[3] or ""))
    applied = lifecycle_status in {"applied", "partially_applied"}
    rolled_back = lifecycle_status == "rolled_back"

    automation_rule = next((item for item in rules if item["rule"] == "automation_non_action_detail"), None)
    aggregate_receipt_rows = _nonnegative(aggregate_values[0])
    aggregated_source_rows = _nonnegative(aggregate_values[1])
    expected_source_rows = _nonnegative((automation_rule or {}).get("affected_rows"))
    aggregate_matches = (
        expected_source_rows == aggregated_source_rows
        and (expected_source_rows == 0 or aggregate_receipt_rows > 0)
    )
    if not applied and not rolled_back:
        aggregate_state = "pending"
    elif aggregate_matches:
        aggregate_state = "ready"
    else:
        aggregate_state = "degraded"

    mutation_row_receipts = _nonnegative(row_receipt_values[0])
    if rolled_back:
        rollback_state = "completed"
        rollback_ready = True
    elif applied and backup_bound:
        rollback_state = "requires_local_backup_reverification"
        rollback_ready = False
    elif applied:
        rollback_state = "blocked_missing_backup_binding"
        rollback_ready = False
    else:
        rollback_state = "not_applicable_pre_apply"
        rollback_ready = False

    logical_bytes_reduced = None
    logical_reduction_proven = False
    if before is not None and after is not None:
        logical_bytes_reduced = before["postgres_database_bytes"] - after["postgres_database_bytes"]
        logical_reduction_proven = logical_bytes_reduced > 0
    cost_state = "measured_logical_only" if after is not None else "before_only" if before is not None else "unmeasured"

    reasons: list[str] = []
    if stale:
        reasons.append("retention_plan_stale")
    if lifecycle_status == "planned":
        reasons.append("retention_plan_blocked")
    if lifecycle_status == "partially_applied":
        reasons.append("retention_apply_partial")
    if applied and not backup_bound:
        reasons.append("retention_backup_unbound")
    elif applied:
        reasons.append("retention_backup_requires_local_reverification")
    if applied and not aggregate_matches:
        reasons.append("retention_aggregate_mismatch")
    if applied and not rollback_ready:
        reasons.append("retention_rollback_requires_local_backup")
    if after is None:
        reasons.append("retention_no_after_metrics")
    reasons.append("retention_physical_cost_unmeasured")
    reasons = list(dict.fromkeys(reasons))

    if lifecycle_status == "planned" or not backup_bound and applied:
        state = "blocked"
    elif reasons:
        state = "degraded"
    else:
        state = "ready"
    ready = state == "ready"
    return {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "ready": ready,
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "stale_after_seconds": STALE_AFTER_SECONDS,
        "reason_codes": reasons,
        "plan": {
            "state": "present",
            "receipt_present": True,
            "lifecycle_status": lifecycle_status,
            "receipt_id": receipt_id,
            "as_of": as_of_iso,
            "created_at": created_at_iso,
            "applied_at": applied_at_iso,
            "rolled_back_at": rolled_back_at_iso,
            "age_seconds": age_seconds,
            "stale": stale,
            "candidate_rows": candidate_rows,
            "candidate_bytes": candidate_bytes,
            "blocked_rows": blocked_rows,
            "local_archive_proof_count": local_proof_count,
        },
        "backup_binding": {
            "state": (
                "recorded_requires_local_reverification"
                if backup_bound
                else "missing"
            ),
            "bound": backup_bound,
            "manifest_recorded": backup_bound,
            "exact_plan_binding_recorded": backup_bound,
            "local_reverification_required": True,
        },
        "aggregate_compaction": {
            "state": aggregate_state,
            "expected_source_rows": expected_source_rows,
            "aggregated_source_rows": aggregated_source_rows,
            "aggregate_receipt_rows": aggregate_receipt_rows,
            "matches": aggregate_matches,
        },
        "rollback": {
            "state": rollback_state,
            "ready": rollback_ready,
            "row_receipts": mutation_row_receipts,
            "aggregate_receipts": aggregate_receipt_rows,
            "requires_isolated_backup_revalidation": not rolled_back,
        },
        "cost": {
            "state": cost_state,
            "before": before,
            "after": after,
            "logical_bytes_reduced": logical_bytes_reduced,
            "logical_reduction_proven": logical_reduction_proven,
            "physical": {
                "railway_volume_before_bytes": None,
                "railway_volume_after_bytes": None,
                "measured": False,
                "reclamation_claimed": False,
            },
            "cost_reduction_proven": False,
        },
        "rules": rules,
        "privacy": {
            "source_rows_returned": False,
            "source_identifiers_returned": False,
            "private_payloads_returned": False,
            "provider_errors_returned": False,
        },
    }


_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "state",
        "ready",
        "checked_at",
        "stale_after_seconds",
        "reason_codes",
        "plan",
        "backup_binding",
        "aggregate_compaction",
        "rollback",
        "cost",
        "rules",
        "privacy",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "state",
        "receipt_present",
        "lifecycle_status",
        "receipt_id",
        "as_of",
        "created_at",
        "applied_at",
        "rolled_back_at",
        "age_seconds",
        "stale",
        "candidate_rows",
        "candidate_bytes",
        "blocked_rows",
        "local_archive_proof_count",
    }
)
_BACKUP_FIELDS = frozenset(
    {"state", "bound", "manifest_recorded", "exact_plan_binding_recorded", "local_reverification_required"}
)
_AGGREGATE_FIELDS = frozenset(
    {"state", "expected_source_rows", "aggregated_source_rows", "aggregate_receipt_rows", "matches"}
)
_ROLLBACK_FIELDS = frozenset(
    {"state", "ready", "row_receipts", "aggregate_receipts", "requires_isolated_backup_revalidation"}
)
_COST_FIELDS = frozenset(
    {"state", "before", "after", "logical_bytes_reduced", "logical_reduction_proven", "physical", "cost_reduction_proven"}
)
_METRIC_FIELDS = frozenset(
    {
        "postgres_database_bytes",
        "tracked_source_relation_bytes",
        "tracked_retention_overhead_bytes",
        "tracked_relation_bytes",
        "estimated_live_rows",
        "estimated_dead_rows",
        "row_counts_are_estimates",
        "physical_reclamation_claimed",
    }
)
_PHYSICAL_FIELDS = frozenset(
    {"railway_volume_before_bytes", "railway_volume_after_bytes", "measured", "reclamation_claimed"}
)
_RULE_FIELDS = frozenset(
    {"rule", "state", "candidate_rows", "candidate_bytes", "blocked_rows", "affected_rows", "reason_code"}
)
_RULE_REASONS = frozenset(
    {
        "active_consumer_contract_unproven",
        "per_type_projection_contract_unproven",
        "unresolved_nonhealthy_rows_retained",
        "terminal_recent_or_unproven_rows_retained",
        "migration_proof_or_gate_incomplete",
    }
)


def _closed_object(value: Any, fields: frozenset[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _bounded_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10**15


def _safe_timestamp(value: Any, *, nullable: bool = True) -> bool:
    if value is None:
        return nullable
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        return _utc(value) is not None
    except (OverflowError, TypeError, ValueError):
        return False


def _safe_metrics(value: Any) -> bool:
    if value is None:
        return True
    return (
        _closed_object(value, _METRIC_FIELDS)
        and all(
            _bounded_count(value[field])
            for field in _METRIC_FIELDS
            if field not in {"row_counts_are_estimates", "physical_reclamation_claimed"}
        )
        and isinstance(value["row_counts_are_estimates"], bool)
        and isinstance(value["physical_reclamation_claimed"], bool)
    )


def retention_status_is_sanitized(receipt: Mapping[str, Any]) -> bool:
    if not _closed_object(receipt, _TOP_LEVEL_FIELDS) or receipt.get("schema_version") != SCHEMA_VERSION:
        return False
    if receipt.get("state") not in {"ready", "degraded", "blocked"} or not isinstance(receipt.get("ready"), bool):
        return False
    if receipt.get("ready") is not (receipt.get("state") == "ready"):
        return False
    if receipt.get("stale_after_seconds") != STALE_AFTER_SECONDS or not _safe_timestamp(
        receipt.get("checked_at"), nullable=False
    ):
        return False
    reasons = receipt.get("reason_codes")
    if not isinstance(reasons, list) or len(reasons) > len(SAFE_REASON_CODES) or any(
        reason not in SAFE_REASON_CODES for reason in reasons
    ):
        return False
    if receipt.get("privacy") != {
        "source_rows_returned": False,
        "source_identifiers_returned": False,
        "private_payloads_returned": False,
        "provider_errors_returned": False,
    }:
        return False

    plan = receipt.get("plan")
    if not _closed_object(plan, _PLAN_FIELDS):
        return False
    receipt_id = plan.get("receipt_id")
    if receipt_id is not None and re.fullmatch(r"[A-Za-z0-9-]{1,160}", str(receipt_id)) is None:
        return False
    if (
        plan.get("state") not in {"missing", "present"}
        or not isinstance(plan.get("receipt_present"), bool)
        or plan.get("receipt_present") is not (plan.get("state") == "present")
        or plan.get("lifecycle_status") not in {None, "planned", "applied", "partially_applied", "rolled_back", "failed"}
        or any(not _safe_timestamp(plan.get(field)) for field in ("as_of", "created_at", "applied_at", "rolled_back_at"))
        or (plan.get("age_seconds") is not None and not _bounded_count(plan.get("age_seconds")))
        or not isinstance(plan.get("stale"), bool)
        or any(
            not _bounded_count(plan.get(field))
            for field in ("candidate_rows", "candidate_bytes", "blocked_rows", "local_archive_proof_count")
        )
    ):
        return False

    backup = receipt.get("backup_binding")
    aggregate = receipt.get("aggregate_compaction")
    rollback = receipt.get("rollback")
    cost = receipt.get("cost")
    if not _closed_object(backup, _BACKUP_FIELDS) or backup.get("state") not in {
        "missing",
        "recorded_requires_local_reverification",
    } or any(not isinstance(backup.get(field), bool) for field in _BACKUP_FIELDS if field != "state"):
        return False
    if not _closed_object(aggregate, _AGGREGATE_FIELDS) or aggregate.get("state") not in {
        "unavailable",
        "pending",
        "ready",
        "degraded",
    } or any(
        not _bounded_count(aggregate.get(field))
        for field in ("expected_source_rows", "aggregated_source_rows", "aggregate_receipt_rows")
    ) or not isinstance(aggregate.get("matches"), bool):
        return False
    if not _closed_object(rollback, _ROLLBACK_FIELDS) or rollback.get("state") not in {
        "unavailable",
        "completed",
        "requires_local_backup_reverification",
        "blocked_missing_backup_binding",
        "not_applicable_pre_apply",
    } or any(
        not _bounded_count(rollback.get(field)) for field in ("row_receipts", "aggregate_receipts")
    ) or any(
        not isinstance(rollback.get(field), bool)
        for field in ("ready", "requires_isolated_backup_revalidation")
    ):
        return False
    if not _closed_object(cost, _COST_FIELDS) or cost.get("state") not in {
        "unmeasured",
        "before_only",
        "measured_logical_only",
    } or not _safe_metrics(cost.get("before")) or not _safe_metrics(cost.get("after")):
        return False
    logical_bytes = cost.get("logical_bytes_reduced")
    if logical_bytes is not None and (not isinstance(logical_bytes, int) or isinstance(logical_bytes, bool)):
        return False
    if any(
        not isinstance(cost.get(field), bool)
        for field in ("logical_reduction_proven", "cost_reduction_proven")
    ):
        return False
    physical = cost.get("physical")
    if not _closed_object(physical, _PHYSICAL_FIELDS) or any(
        physical.get(field) is not None and not _bounded_count(physical.get(field))
        for field in ("railway_volume_before_bytes", "railway_volume_after_bytes")
    ) or any(not isinstance(physical.get(field), bool) for field in ("measured", "reclamation_claimed")):
        return False

    rules = receipt.get("rules")
    if not isinstance(rules, list) or len(rules) > 16:
        return False
    return all(
        _closed_object(rule, _RULE_FIELDS)
        and rule.get("rule") in SAFE_RULE_NAMES
        and rule.get("state") in SAFE_RULE_STATES
        and (rule.get("reason_code") is None or rule.get("reason_code") in _RULE_REASONS)
        and all(
            _bounded_count(rule.get(field))
            for field in ("candidate_rows", "candidate_bytes", "blocked_rows", "affected_rows")
        )
        for rule in rules
    )
