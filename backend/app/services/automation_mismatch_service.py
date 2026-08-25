from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.models.automations import Automation, AutomationMismatch, AutomationMismatchReport, AutomationRun
from app.services.automation_run_service import list_runs
from app.services.automation_service import automation_source_of_truth, list_automations


def _run_timestamp(run: AutomationRun) -> datetime:
    value = run.run_at or run.finished_at
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_runs_by_automation(runs: list[AutomationRun]) -> dict[str, AutomationRun]:
    latest: dict[str, AutomationRun] = {}
    for run in runs:
        if not run.automation_id:
            continue
        current = latest.get(run.automation_id)
        if current is None or _run_timestamp(run) > _run_timestamp(current):
            latest[run.automation_id] = run
    return latest


def _latest_launchd_states(runs: list[AutomationRun]) -> dict[str, dict]:
    """Return the newest aggregate installed-state observation, when present.

    High-frequency run retention may compact an automation's individual mirror
    rows before the registry entry disappears.  The launchd health audit is the
    canonical bounded observation for installed/loaded state, so its per-job
    map prevents a compacted row from being mislabeled as "never observed".
    """

    audits = [run for run in runs if run.automation_id == "launchd_health_audit"]
    if not audits:
        return {}
    latest = max(audits, key=_run_timestamp)
    states = (latest.metadata or {}).get("launchd_automation_states")
    if not isinstance(states, dict):
        return {}
    return {str(key): value for key, value in states.items() if isinstance(value, dict)}


def build_mismatch_report(
    *,
    automations: Optional[list[Automation]] = None,
    runs: Optional[list[AutomationRun]] = None,
) -> AutomationMismatchReport:
    all_runs = list_runs(limit=500) if runs is None else runs
    registry = list_automations(runs=all_runs) if automations is None else automations
    latest_by_id = _latest_runs_by_automation(all_runs)
    latest_launchd_states = _latest_launchd_states(all_runs)
    registry_by_id = {item.id: item for item in registry}
    mismatches: list[AutomationMismatch] = []

    for item in registry:
        if (
            item.status == "active"
            and item.runtime == "launchd"
            and item.id not in latest_by_id
            and item.id not in latest_launchd_states
        ):
            mismatches.append(
                AutomationMismatch(
                    kind="missing_run_record",
                    severity="info",
                    automation_id=item.id,
                    automation_name=item.name,
                    message="The active launchd automation has no observed Codex ledger run yet.",
                )
            )

    for automation_id, run in latest_by_id.items():
        if automation_id not in registry_by_id:
            mismatches.append(
                AutomationMismatch(
                    kind="unregistered_run",
                    severity="warn",
                    automation_id=automation_id,
                    automation_name=run.automation_name,
                    message="The Codex run ledger contains an automation that is not in the launchd registry.",
                    metadata={"run_id": run.id, "source": run.source, "runtime": run.runtime},
                )
            )

        launchd_issues = (run.metadata or {}).get("launchd_issues")
        if run.automation_id == "launchd_health_audit" and isinstance(launchd_issues, list):
            for issue in launchd_issues:
                if not isinstance(issue, dict):
                    continue
                mismatches.append(
                    AutomationMismatch(
                        kind=str(issue.get("kind") or "local_launchd_audit_issue"),
                        severity=str(issue.get("severity") or "warn"),
                        automation_id=str(issue.get("automation_id") or "") or None,
                        automation_name=str(issue.get("label") or issue.get("automation_name") or "") or None,
                        message=str(issue.get("message") or "Local launchd audit found an issue."),
                        metadata=issue,
                    )
                )
            if launchd_issues:
                continue

        observed_flag = (run.metadata or {}).get("has_observed_run")
        has_observed_run = bool(observed_flag) if observed_flag is not None else _run_timestamp(run) != datetime.min.replace(
            tzinfo=timezone.utc
        )
        if not has_observed_run:
            mismatches.append(
                AutomationMismatch(
                    kind="no_observed_run_yet",
                    severity="info",
                    automation_id=run.automation_id,
                    automation_name=run.automation_name,
                    message="The automation ledger entry does not contain an observed run timestamp.",
                )
            )
        elif run.status.lower() not in {"ok", "success"}:
            mismatches.append(
                AutomationMismatch(
                    kind="run_error",
                    severity="error",
                    automation_id=run.automation_id,
                    automation_name=run.automation_name,
                    message="The latest Codex automation run finished in a non-success state.",
                    metadata={"status": run.status, "error": run.error},
                )
            )
        elif (
            run.delivered is False
            and bool(run.delivery_channel or run.delivery_target)
            and not bool((run.metadata or {}).get("no_delivery"))
            and not bool((run.metadata or {}).get("delivery_optional"))
        ):
            mismatches.append(
                AutomationMismatch(
                    kind="delivery_failure",
                    severity="warn",
                    automation_id=run.automation_id,
                    automation_name=run.automation_name,
                    message="The latest automation run succeeded but did not reach its configured control-plane target.",
                    metadata={
                        "delivery_channel": run.delivery_channel,
                        "delivery_target": run.delivery_target,
                    },
                )
            )

    return AutomationMismatchReport(
        source_of_truth=automation_source_of_truth(),
        registry_count=len(registry),
        registered_launchd_count=sum(1 for item in registry if item.runtime == "launchd"),
        run_count=len(all_runs),
        mismatch_count=len(mismatches),
        action_required_count=sum(1 for run in latest_by_id.values() if run.action_required),
        mismatches=mismatches,
    )
