from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from app.services import firestore_client


SCHEMA_VERSION = "firestore_retained_role_readiness/v1"
MODE = "read_only_aggregate_queries"
_CLIENT_UNSET = object()
SAFE_REASON_CODES = frozenset(
    {
        "firestore_unavailable",
        "firestore_probe_failed",
        "firestore_probe_timeout",
        "firestore_readiness_projection_rejected",
    }
)


@dataclass(frozen=True)
class FirestoreReadinessProbe:
    key: str
    scope: str
    collection: str
    consumer_role: str


# This allowlist mirrors the retained Firestore role inventoried in
# docs/integrated_system_storage_cost_and_firestore_baseline.md. A successful
# aggregate query proves that the deployed credentials can read the collection
# without transporting document bodies into this process.
READINESS_PROBES: tuple[FirestoreReadinessProbe, ...] = (
    FirestoreReadinessProbe("activity_logs", "top_level", "activity_logs", "legacy_activity_compatibility"),
    FirestoreReadinessProbe("knowledge_docs", "top_level", "knowledge_docs", "knowledge_and_drive_ingest"),
    FirestoreReadinessProbe("playbooks", "top_level", "playbooks", "playbook_product"),
    FirestoreReadinessProbe("research_insights", "top_level", "research_insights", "legacy_research_compatibility"),
    FirestoreReadinessProbe("research_tasks", "top_level", "research_tasks", "legacy_research_compatibility"),
    FirestoreReadinessProbe("system_logs", "top_level", "system_logs", "system_log_and_analytics_compatibility"),
    FirestoreReadinessProbe("prospects_top_level", "top_level", "prospects", "legacy_prospect_read_compatibility"),
    FirestoreReadinessProbe("memory_chunks", "collection_group", "memory_chunks", "memory_retrieval_fallback"),
    FirestoreReadinessProbe("ingest_jobs", "collection_group", "ingest_jobs", "ingestion_job_state"),
    FirestoreReadinessProbe(
        "prospect_discoveries",
        "collection_group",
        "prospect_discoveries",
        "prospect_discovery_history",
    ),
    FirestoreReadinessProbe("prospects_nested", "collection_group", "prospects", "canonical_prospect_authority"),
    FirestoreReadinessProbe(
        "topic_intelligence",
        "collection_group",
        "topic_intelligence",
        "topic_intelligence_and_research_pages",
    ),
)


def _bounded_timeout(value: float, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = maximum
    return min(max(parsed, minimum), maximum)


def _probe_collection(client: Any, probe: FirestoreReadinessProbe, timeout_seconds: float) -> None:
    if probe.scope == "top_level":
        query = client.collection(probe.collection)
    elif probe.scope == "collection_group":
        query = client.collection_group(probe.collection)
    else:  # pragma: no cover - the immutable manifest is validated by tests.
        raise ValueError("unsupported Firestore readiness scope")

    # Aggregation is intentional: readiness needs access proof, not document
    # bodies, identifiers, or PII. Disable SDK retries so this gate owns its
    # complete latency budget.
    query.count().get(timeout=timeout_seconds, retry=None)


def _check_payload(
    probe: FirestoreReadinessProbe,
    *,
    state: str,
    duration_ms: int,
    reason_codes: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "key": probe.key,
        "scope": probe.scope,
        "collection": probe.collection,
        "consumer_role": probe.consumer_role,
        "state": state,
        "duration_ms": max(0, min(int(duration_ms), 120_000)),
        "reason_codes": list(dict.fromkeys(reason_codes))[:4],
    }


def check_firestore_readiness(
    *,
    client: Any = _CLIENT_UNSET,
    overall_timeout_seconds: float = 8.0,
    per_probe_timeout_seconds: float = 4.0,
    max_workers: int = 6,
    clock: Callable[[], datetime] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return a bounded, content-free readiness receipt for retained Firestore reads."""

    overall_timeout = _bounded_timeout(overall_timeout_seconds, minimum=0.05, maximum=30.0)
    per_probe_timeout = _bounded_timeout(
        per_probe_timeout_seconds,
        minimum=0.05,
        maximum=overall_timeout,
    )
    worker_count = max(1, min(int(max_workers), len(READINESS_PROBES), 12))
    now = clock or (lambda: datetime.now(timezone.utc))
    started = monotonic()
    resolved_client = firestore_client.get_firestore_client() if client is _CLIENT_UNSET else client

    if resolved_client is None:
        checks = [
            _check_payload(
                probe,
                state="degraded",
                duration_ms=0,
                reason_codes=("firestore_unavailable",),
            )
            for probe in READINESS_PROBES
        ]
    else:
        executor = ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="firestore-readiness")
        future_to_probe: dict[Future[None], tuple[FirestoreReadinessProbe, float]] = {}
        try:
            for probe in READINESS_PROBES:
                probe_started = monotonic()
                future = executor.submit(_probe_collection, resolved_client, probe, per_probe_timeout)
                future_to_probe[future] = (probe, probe_started)

            done, pending = wait(tuple(future_to_probe), timeout=overall_timeout)
            checks_by_key: dict[str, dict[str, Any]] = {}
            for future in done:
                probe, probe_started = future_to_probe[future]
                duration_ms = round((monotonic() - probe_started) * 1_000)
                try:
                    future.result()
                except Exception:
                    checks_by_key[probe.key] = _check_payload(
                        probe,
                        state="degraded",
                        duration_ms=duration_ms,
                        reason_codes=("firestore_probe_failed",),
                    )
                else:
                    checks_by_key[probe.key] = _check_payload(
                        probe,
                        state="ready",
                        duration_ms=duration_ms,
                    )

            for future in pending:
                probe, probe_started = future_to_probe[future]
                future.cancel()
                checks_by_key[probe.key] = _check_payload(
                    probe,
                    state="degraded",
                    duration_ms=round((monotonic() - probe_started) * 1_000),
                    reason_codes=("firestore_probe_timeout",),
                )
            checks = [checks_by_key[probe.key] for probe in READINESS_PROBES]
        finally:
            # Provider calls receive their own shorter timeout and have retries
            # disabled. Do not make the HTTP/CLI caller wait beyond the outer
            # deadline if a broken fake or transport ignores that contract.
            executor.shutdown(wait=False, cancel_futures=True)

    passed = sum(1 for check in checks if check["state"] == "ready")
    failed = len(checks) - passed
    reason_codes = list(
        dict.fromkeys(
            reason
            for check in checks
            for reason in check["reason_codes"]
        )
    )
    checked_at = now()
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    duration_ms = round((monotonic() - started) * 1_000)
    ready = failed == 0
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "ready" if ready else "degraded",
        "ready": ready,
        "checked_at": checked_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration_ms": max(0, min(duration_ms, 120_000)),
        "mode": MODE,
        "required_check_count": len(checks),
        "passed_check_count": passed,
        "failed_check_count": failed,
        "reason_codes": reason_codes,
        "checks": checks,
        "privacy": {
            "document_bodies_returned": False,
            "document_ids_returned": False,
            "provider_errors_returned": False,
        },
    }


def degraded_readiness_receipt(
    reason_code: str,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Build a complete fail-closed receipt from one fixed public reason code."""

    if reason_code not in SAFE_REASON_CODES:
        reason_code = "firestore_readiness_projection_rejected"
    now = clock or (lambda: datetime.now(timezone.utc))
    checked_at = now()
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checks = [
        _check_payload(
            probe,
            state="degraded",
            duration_ms=0,
            reason_codes=(reason_code,),
        )
        for probe in READINESS_PROBES
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "degraded",
        "ready": False,
        "checked_at": checked_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration_ms": 0,
        "mode": MODE,
        "required_check_count": len(checks),
        "passed_check_count": 0,
        "failed_check_count": len(checks),
        "reason_codes": [reason_code],
        "checks": checks,
        "privacy": {
            "document_bodies_returned": False,
            "document_ids_returned": False,
            "provider_errors_returned": False,
        },
    }


def receipt_is_sanitized(receipt: dict[str, Any]) -> bool:
    """Guard the authenticated projection against accidental contract expansion."""

    allowed_top_level = {
        "schema_version",
        "state",
        "ready",
        "checked_at",
        "duration_ms",
        "mode",
        "required_check_count",
        "passed_check_count",
        "failed_check_count",
        "reason_codes",
        "checks",
        "privacy",
    }
    allowed_check = {
        "key",
        "scope",
        "collection",
        "consumer_role",
        "state",
        "duration_ms",
        "reason_codes",
    }
    if not isinstance(receipt, dict) or set(receipt) != allowed_top_level:
        return False
    if receipt.get("schema_version") != SCHEMA_VERSION or receipt.get("mode") != MODE:
        return False
    if receipt.get("state") not in {"ready", "degraded"} or not isinstance(receipt.get("ready"), bool):
        return False
    checked_at = receipt.get("checked_at")
    if not isinstance(checked_at, str) or len(checked_at) > 40:
        return False
    try:
        datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    for field in (
        "duration_ms",
        "required_check_count",
        "passed_check_count",
        "failed_check_count",
    ):
        value = receipt.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 120_000:
            return False
    reasons = receipt.get("reason_codes")
    if not isinstance(reasons, list) or any(reason not in SAFE_REASON_CODES for reason in reasons):
        return False
    if receipt.get("privacy") != {
        "document_bodies_returned": False,
        "document_ids_returned": False,
        "provider_errors_returned": False,
    }:
        return False
    checks = receipt.get("checks")
    if not isinstance(checks, list) or len(checks) != len(READINESS_PROBES):
        return False
    if receipt.get("required_check_count") != len(checks):
        return False
    for probe, check in zip(READINESS_PROBES, checks):
        if not isinstance(check, dict) or set(check) != allowed_check:
            return False
        if (
            check.get("key") != probe.key
            or check.get("scope") != probe.scope
            or check.get("collection") != probe.collection
            or check.get("consumer_role") != probe.consumer_role
            or check.get("state") not in {"ready", "degraded"}
        ):
            return False
        duration = check.get("duration_ms")
        check_reasons = check.get("reason_codes")
        if isinstance(duration, bool) or not isinstance(duration, int) or not 0 <= duration <= 120_000:
            return False
        if not isinstance(check_reasons, list) or any(reason not in SAFE_REASON_CODES for reason in check_reasons):
            return False
        if (check["state"] == "ready" and check_reasons) or (
            check["state"] == "degraded" and not check_reasons
        ):
            return False
    passed = sum(1 for check in checks if check["state"] == "ready")
    failed = len(checks) - passed
    if receipt.get("passed_check_count") != passed or receipt.get("failed_check_count") != failed:
        return False
    expected_ready = failed == 0
    if receipt.get("state") != ("ready" if expected_ready else "degraded"):
        return False
    if bool(receipt.get("ready")) != expected_ready:
        return False
    return (expected_ready and not reasons) or (not expected_ready and bool(reasons))
