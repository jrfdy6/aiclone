from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.automation_service import list_automations
from app.services.gmail_inbox_service import gmail_connection_status
from app.services.local_codex_generation_service import list_codex_jobs

EMAIL_DRAFT_CANARY_WORKSPACE_SLUG = "email-drafts"
_ACTIVE_JOB_STATUSES = {"pending", "claimed", "running"}
_QUEUE_STATUS_ORDER = ("pending", "claimed", "running", "completed", "failed", "canceled")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _age_minutes(timestamp: datetime | None, *, now: datetime) -> int | None:
    if timestamp is None:
        return None
    age = now - timestamp
    return max(0, int(age.total_seconds() // 60))


def _job_time(job: dict[str, Any], *fields: str) -> datetime | None:
    for field in fields:
        parsed = _parse_timestamp(job.get(field))
        if parsed is not None:
            return parsed
    return None


def _job_brief(job: dict[str, Any], *, age_minutes: int | None = None) -> dict[str, Any]:
    payload = {
        "job_id": str(job.get("id") or ""),
        "status": str(job.get("status") or ""),
        "workspace_slug": str(job.get("workspace_slug") or ""),
        "created_at": job.get("created_at"),
        "claimed_at": job.get("claimed_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "failed_at": job.get("failed_at"),
        "claimed_by": job.get("claimed_by"),
        "error_message": job.get("error_message"),
    }
    if age_minutes is not None:
        payload["age_minutes"] = age_minutes
    return payload


def _latest_timestamp(jobs: list[dict[str, Any]], field: str) -> str | None:
    timestamps = [ts.isoformat() for ts in (_parse_timestamp(job.get(field)) for job in jobs) if ts is not None]
    return max(timestamps) if timestamps else None


def _recent_jobs(jobs: list[dict[str, Any]], *, field: str, limit: int = 5) -> list[dict[str, Any]]:
    ranked: list[tuple[datetime, dict[str, Any]]] = []
    for job in jobs:
        parsed = _parse_timestamp(job.get(field))
        if parsed is not None:
            ranked.append((parsed, job))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [_job_brief(job) for _, job in ranked[:limit]]


def _build_provider_check(provider_status: dict[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in ("configured", "connected", "dependencies_ready", "drafts_enabled")
        if not bool(provider_status.get(field))
    ]
    status = "fail" if missing else "pass"
    return {
        "name": "gmail_provider",
        "status": status,
        "missing_requirements": missing,
        "account_email": provider_status.get("account_email"),
        "drafts_enabled": bool(provider_status.get("drafts_enabled")),
        "connected": bool(provider_status.get("connected")),
        "error": provider_status.get("error"),
    }


def _build_queue_check(
    jobs: list[dict[str, Any]],
    *,
    now: datetime,
    stale_pending_minutes: int,
    stale_running_minutes: int,
    include_samples: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    status_counts = {status: 0 for status in _QUEUE_STATUS_ORDER}
    stale_pending_jobs: list[dict[str, Any]] = []
    stale_running_jobs: list[dict[str, Any]] = []
    recent_failures_window = now - timedelta(hours=24)
    recent_failed_jobs: list[dict[str, Any]] = []

    for job in jobs:
        status = str(job.get("status") or "").strip().lower()
        if status not in status_counts:
            status_counts[status] = 0
        status_counts[status] += 1

        if status == "pending":
            age = _age_minutes(_job_time(job, "created_at", "updated_at"), now=now)
            if age is not None and age >= stale_pending_minutes:
                stale_pending_jobs.append(_job_brief(job, age_minutes=age))
        elif status in {"claimed", "running"}:
            age = _age_minutes(_job_time(job, "started_at", "claimed_at", "updated_at", "created_at"), now=now)
            if age is not None and age >= stale_running_minutes:
                stale_running_jobs.append(_job_brief(job, age_minutes=age))

        failed_at = _parse_timestamp(job.get("failed_at"))
        if failed_at is not None and failed_at >= recent_failures_window:
            recent_failed_jobs.append(job)

    active_count = sum(status_counts.get(status, 0) for status in _ACTIVE_JOB_STATUSES)
    stale_count = len(stale_pending_jobs) + len(stale_running_jobs)
    queue_fail_reasons: list[str] = []
    queue_warn_reasons: list[str] = []

    if stale_pending_jobs:
        queue_fail_reasons.append("stale_pending_jobs")
    if stale_running_jobs:
        queue_fail_reasons.append("stale_running_jobs")
    if active_count > 1:
        queue_fail_reasons.append("multiple_active_jobs")
    if recent_failed_jobs:
        queue_warn_reasons.append("recent_failed_jobs")

    queue_status = "fail" if queue_fail_reasons else ("warn" if queue_warn_reasons else "pass")
    queue_payload = {
        "workspace_slug": EMAIL_DRAFT_CANARY_WORKSPACE_SLUG,
        "total_jobs": len(jobs),
        "status_counts": status_counts,
        "active_count": active_count,
        "stale_pending_count": len(stale_pending_jobs),
        "stale_running_count": len(stale_running_jobs),
        "stale_job_count": stale_count,
        "latest_completed_at": _latest_timestamp(jobs, "completed_at"),
        "latest_failed_at": _latest_timestamp(jobs, "failed_at"),
        "thresholds": {
            "stale_pending_minutes": stale_pending_minutes,
            "stale_running_minutes": stale_running_minutes,
        },
        "recent_failed_count_24h": len(recent_failed_jobs),
    }
    if include_samples:
        queue_payload["stale_pending_jobs"] = stale_pending_jobs
        queue_payload["stale_running_jobs"] = stale_running_jobs
        queue_payload["recent_failed_jobs"] = _recent_jobs(recent_failed_jobs, field="failed_at")
        queue_payload["recent_completed_jobs"] = _recent_jobs(jobs, field="completed_at")

    queue_check = {
        "name": "email_draft_queue",
        "status": queue_status,
        "fail_reasons": queue_fail_reasons,
        "warn_reasons": queue_warn_reasons,
        "workspace_slug": EMAIL_DRAFT_CANARY_WORKSPACE_SLUG,
        "active_count": active_count,
        "stale_job_count": stale_count,
        "recent_failed_count_24h": len(recent_failed_jobs),
    }
    return queue_check, queue_payload


def _build_bridge_registry_check() -> tuple[dict[str, Any], dict[str, Any]]:
    automations = list_automations()
    target = next((item for item in automations if str(getattr(item, "id", "")).strip() == "email_codex_bridge"), None)
    if target is None:
        registry_payload = {
            "configured": False,
            "automation_id": "email_codex_bridge",
            "status": None,
            "workspace_slug": EMAIL_DRAFT_CANARY_WORKSPACE_SLUG,
            "launch_agent": None,
            "source": None,
            "runtime": None,
        }
        registry_check = {
            "name": "email_codex_bridge_registry",
            "status": "fail",
            "fail_reasons": ["missing_registry_entry"],
        }
        return registry_check, registry_payload

    metrics = dict(getattr(target, "metrics", {}) or {})
    workspace_slug = str(metrics.get("workspace_slug") or "")
    launch_agent = str(metrics.get("launch_agent") or "")
    status_value = str(getattr(target, "status", "") or "")
    fail_reasons: list[str] = []
    if status_value.lower() != "active":
        fail_reasons.append("automation_not_active")
    if workspace_slug and workspace_slug != EMAIL_DRAFT_CANARY_WORKSPACE_SLUG:
        fail_reasons.append("workspace_slug_mismatch")

    registry_payload = {
        "configured": True,
        "automation_id": str(getattr(target, "id", "") or ""),
        "status": status_value,
        "workspace_slug": workspace_slug or EMAIL_DRAFT_CANARY_WORKSPACE_SLUG,
        "launch_agent": launch_agent or None,
        "source": str(getattr(target, "source", "") or ""),
        "runtime": str(getattr(target, "runtime", "") or ""),
    }
    registry_check = {
        "name": "email_codex_bridge_registry",
        "status": "fail" if fail_reasons else "pass",
        "fail_reasons": fail_reasons,
    }
    return registry_check, registry_payload


def build_email_draft_canary_report(*, include_samples: bool = True) -> dict[str, Any]:
    now = _utcnow()
    stale_pending_minutes = _parse_positive_int_env("EMAIL_DRAFT_CANARY_STALE_PENDING_MINUTES", 20)
    stale_running_minutes = _parse_positive_int_env("EMAIL_DRAFT_CANARY_STALE_RUNNING_MINUTES", 30)
    provider_status = gmail_connection_status()
    queue_jobs = list_codex_jobs(workspace_slug=EMAIL_DRAFT_CANARY_WORKSPACE_SLUG)

    provider_check = _build_provider_check(provider_status)
    queue_check, queue_payload = _build_queue_check(
        queue_jobs,
        now=now,
        stale_pending_minutes=stale_pending_minutes,
        stale_running_minutes=stale_running_minutes,
        include_samples=include_samples,
    )
    registry_check, registry_payload = _build_bridge_registry_check()
    checks = [provider_check, queue_check, registry_check]
    failing = [check for check in checks if check.get("status") == "fail"]
    warning = [check for check in checks if check.get("status") == "warn"]

    return {
        "schema_version": "email_draft_canary_report/v1",
        "generated_at": now.isoformat(),
        "workspace_slug": EMAIL_DRAFT_CANARY_WORKSPACE_SLUG,
        "provider": provider_status,
        "queue": queue_payload,
        "bridge_registry": registry_payload,
        "summary": {
            "status": "fail" if failing else ("warn" if warning else "pass"),
            "checks_run": len(checks),
            "failing_checks": len(failing),
            "warning_checks": len(warning),
        },
        "checks": checks,
    }
