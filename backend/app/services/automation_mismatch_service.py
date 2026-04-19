from __future__ import annotations

from datetime import datetime, timezone

from app.models.automations import AutomationMismatch, AutomationMismatchReport
from app.services.automation_run_service import list_runs
from app.services.automation_service import (
    STATIC_FALLBACK_IDS,
    automation_source_of_truth,
    list_automations,
    openclaw_jobs_snapshot,
)


def _run_timestamp(run) -> datetime:
    value = run.run_at or run.finished_at
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_runs_by_automation(runs: list) -> list:
    latest: dict[str, object] = {}
    for run in runs:
        automation_id = str(getattr(run, "automation_id", "") or "")
        if not automation_id:
            continue
        current = latest.get(automation_id)
        if current is None or _run_timestamp(run) > _run_timestamp(current):
            latest[automation_id] = run
    return list(latest.values())


def build_mismatch_report() -> AutomationMismatchReport:
    source = automation_source_of_truth()
    jobs = openclaw_jobs_snapshot()
    automations = list_automations()
    all_runs = list_runs(limit=max(200, len(automations) + 20))
    latest_runs = _latest_runs_by_automation(all_runs)

    mismatches: list[AutomationMismatch] = []

    openclaw_ids = {str(job.get("id") or "") for job in jobs if str(job.get("id") or "").strip()}
    mirrored = [item for item in automations if item.source == "openclaw_jobs_json"]
    mirrored_ids = {item.id for item in mirrored}
    run_ids = {item.automation_id for item in latest_runs if item.automation_id}

    if "openclaw_jobs_json" in source:
        for missing_id in sorted(openclaw_ids - mirrored_ids):
            mismatches.append(
                AutomationMismatch(
                    kind="missing_openclaw_job_in_backend",
                    severity="error",
                    automation_id=missing_id,
                    message="OpenClaw jobs.json contains a job that is not mirrored into backend automations.",
                )
            )

        for extra_id in sorted(mirrored_ids - openclaw_ids):
            mismatches.append(
                AutomationMismatch(
                    kind="orphan_mirrored_automation",
                    severity="warn",
                    automation_id=extra_id,
                    message="Backend mirrored an OpenClaw automation that is no longer present in jobs.json.",
                )
            )

        for item in automations:
            if item.source == "static_registry" and item.id not in STATIC_FALLBACK_IDS:
                mismatches.append(
                    AutomationMismatch(
                        kind="unexpected_static_registry_item",
                        severity="warn",
                        automation_id=item.id,
                        automation_name=item.name,
                        message="A static registry automation is still surfacing while OpenClaw is the active source of truth.",
                    )
                )

    for item in mirrored:
        if item.id not in run_ids:
            mismatches.append(
                AutomationMismatch(
                    kind="missing_run_record",
                    severity="warn",
                    automation_id=item.id,
                    automation_name=item.name,
                    message="The mirrored automation does not have a latest run entry.",
                )
            )

    for run in latest_runs:
        has_observed_run = bool((run.metadata or {}).get("has_observed_run")) or run.run_at is not None
        if not has_observed_run:
            mismatches.append(
                AutomationMismatch(
                    kind="no_observed_run_yet",
                    severity="info",
                    automation_id=run.automation_id,
                    automation_name=run.automation_name,
                    message="The automation does not have an observed run yet.",
                )
            )
        elif run.status not in {"ok", "success"}:
            mismatches.append(
                AutomationMismatch(
                    kind="run_error",
                    severity="error",
                    automation_id=run.automation_id,
                    automation_name=run.automation_name,
                    message="The latest automation run finished in a non-success state.",
                    metadata={
                        "status": run.status,
                        "error": run.error,
                    },
                )
            )
        elif (
            run.delivered is False
            and not bool((run.metadata or {}).get("no_reply"))
            and not bool((run.metadata or {}).get("no_delivery"))
        ):
            mismatches.append(
                AutomationMismatch(
                    kind="delivery_failure",
                    severity="warn",
                    automation_id=run.automation_id,
                    automation_name=run.automation_name,
                    message="The latest automation run succeeded but did not deliver to its target.",
                    metadata={
                        "delivery_channel": run.delivery_channel,
                        "delivery_target": run.delivery_target,
                    },
                )
            )

    action_required_count = sum(1 for run in latest_runs if run.action_required)
    return AutomationMismatchReport(
        source_of_truth=source,
        openclaw_job_count=len(jobs),
        mirrored_openclaw_automation_count=len(mirrored),
        run_count=len(all_runs),
        mismatch_count=len(mismatches),
        action_required_count=action_required_count,
        mismatches=mismatches,
    )
