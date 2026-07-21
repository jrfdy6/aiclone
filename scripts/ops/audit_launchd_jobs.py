#!/usr/bin/env python3
"""Audit local com.neo launchd jobs and mirror visible health into Ops."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path("/Users/neo/Documents/Codex/AI-Clone")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs  # noqa: E402
from app.services.automation_service import list_automations  # noqa: E402
from runtime_paths import RUNTIME_ROOT  # noqa: E402

AUTOMATION_ID = "launchd_health_audit"
AUTOMATION_NAME = "Launchd Health Audit"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
DEFAULT_REPORT_PATH = WORKSPACE_ROOT / "memory/reports/launchd_health_audit_latest.json"
VENv_PYTHON = str(RUNTIME_ROOT / "venv/bin/python")
LOCAL_LAUNCH_AGENTS = Path.home() / "Library/LaunchAgents"
REPO_LAUNCHD_DIRS = [
    WORKSPACE_ROOT / "automations/launchd",
    WORKSPACE_ROOT / "automations",
]
LABEL_TO_AUTOMATION_ID = {
    "com.neo.jean_claude_execution": "jean_claude_execution_dispatch",
    "com.neo.neo_execution": "neo_execution",
}
ALLOW_GENERIC_PYTHON = {
    "com.neo.persona_bundle_sync",
}
REPO_MANAGED_TARGET_LABELS = frozenset(
    {
        "com.neo.brain_canonical_memory_sync",
        "com.neo.codex_workspace_execution",
        "com.neo.content_safe_operator_lessons",
        "com.neo.feezie_codex_bridge",
        "com.neo.feezie_content_pipeline",
        "com.neo.jean_claude_execution",
        "com.neo.meeting_watchdog",
        "com.neo.morning_daily_brief",
        "com.neo.neo_guest",
        "com.neo.operator_story_signals",
        "com.neo.pm_review_resolution",
        "com.neo.portfolio_standup_prep",
        "com.neo.post_sync_dispatch",
        "com.neo.workspace_agent_dispatch",
        "com.neo.youtube_watchlist_auto_ingest",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _label_to_automation_id(label: str) -> str:
    if label in LABEL_TO_AUTOMATION_ID:
        return LABEL_TO_AUTOMATION_ID[label]
    if label.startswith("com.neo."):
        return label.removeprefix("com.neo.")
    return label


def _plist_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in [LOCAL_LAUNCH_AGENTS, *REPO_LAUNCHD_DIRS]:
        if directory.exists():
            paths.extend(sorted(directory.glob("com.neo*.plist")))
    return paths


def _read_plist(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _is_installed(path: Path) -> bool:
    try:
        return path.parent.resolve() == LOCAL_LAUNCH_AGENTS.resolve()
    except OSError:
        return False


def _repo_counterpart(path: Path, label: str) -> Path | None:
    for directory in REPO_LAUNCHD_DIRS:
        candidate = directory / f"{label}.plist"
        if candidate.exists():
            return candidate
    return None


def _plist_drift_fields(installed: dict[str, Any], repo: dict[str, Any]) -> list[str]:
    missing = object()
    return sorted(
        key
        for key in set(installed).union(repo)
        if installed.get(key, missing) != repo.get(key, missing)
    )


def _script_args(program_args: list[Any]) -> list[str]:
    args = [str(item) for item in program_args]
    scripts: list[str] = []
    workspace_prefix = str(WORKSPACE_ROOT)
    for value in args:
        if value.startswith(workspace_prefix) and (value.endswith(".py") or value.endswith(".sh")):
            scripts.append(value)
    return scripts


def _missing_paths(program_args: list[Any]) -> list[str]:
    missing: list[str] = []
    for value in _script_args(program_args):
        if not Path(value).exists():
            missing.append(value)
    return missing


def _uses_generic_python(program_args: list[Any]) -> bool:
    args = [str(item) for item in program_args]
    if len(args) >= 2 and args[0] == "/usr/bin/env" and args[1] == "python3":
        return True
    return bool(args and args[0] in {"python3", "/usr/bin/python3", "/usr/local/bin/python3"})


def _uses_workspace_venv(program_args: list[Any]) -> bool:
    args = [str(item) for item in program_args]
    return bool(args and args[0] == VENv_PYTHON)


def _run_launchctl_read(args: list[str]) -> tuple[bool, str, str | None]:
    try:
        result = subprocess.run(
            ["launchctl", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return False, "", f"{type(exc).__name__}: {exc}"
    if result.returncode != 0:
        error = (result.stderr or result.stdout or f"launchctl exited {result.returncode}").strip()
        return False, result.stdout or "", error
    return True, result.stdout or "", None


def _launchctl_record(pid: str, status: str, label: str, *, source: str) -> dict[str, Any]:
    return {
        "pid": None if pid in {"-", "0"} else pid,
        "last_exit_status": status if re.fullmatch(r"-?\d+", status) else None,
        "label": label,
        "observed_via": [source],
    }


def _parse_launchctl_list(output: str) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        label = parts[2]
        if not label.startswith("com.neo."):
            continue
        loaded[label] = _launchctl_record(parts[0], parts[1], label, source="launchctl_list")
    return loaded


def _parse_launchctl_print(output: str) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    loaded: dict[str, dict[str, Any]] = {}
    disabled: dict[str, bool] = {}
    service_pattern = re.compile(r"^\s*(\d+|-)\s+(\S+)\s+(com\.neo\.[A-Za-z0-9._-]+)\s*$")
    disabled_pattern = re.compile(
        r'^\s*"(com\.neo\.[A-Za-z0-9._-]+)"\s*=>\s*(disabled|enabled|true|false)\s*$'
    )
    for line in output.splitlines():
        service_match = service_pattern.match(line)
        if service_match:
            pid, status, label = service_match.groups()
            loaded[label] = _launchctl_record(pid, status, label, source="launchctl_print")
            continue
        disabled_match = disabled_pattern.match(line)
        if disabled_match:
            label, state = disabled_match.groups()
            disabled[label] = state in {"disabled", "true"}
    return loaded, disabled


def _merge_loaded_labels(
    primary: dict[str, dict[str, Any]],
    secondary: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = {label: dict(state) for label, state in primary.items()}
    for label, state in secondary.items():
        current = merged.get(label)
        if current is None:
            merged[label] = dict(state)
            continue
        sources = [str(item) for item in current.get("observed_via") or []]
        for source in state.get("observed_via") or []:
            if source not in sources:
                sources.append(str(source))
        current["observed_via"] = sources
        for field in ("pid", "last_exit_status"):
            if current.get(field) is None and state.get(field) is not None:
                current[field] = state[field]
    return merged


def _launchctl_snapshot() -> dict[str, Any]:
    list_ok, list_output, list_error = _run_launchctl_read(["list"])
    domain = f"gui/{os.getuid()}"
    print_ok, print_output, print_error = _run_launchctl_read(["print", domain])

    list_loaded = _parse_launchctl_list(list_output) if list_ok else {}
    print_loaded, disabled = _parse_launchctl_print(print_output) if print_ok else ({}, {})
    errors = []
    if list_error:
        errors.append(f"launchctl list: {list_error}")
    if print_error:
        errors.append(f"launchctl print {domain}: {print_error}")
    return {
        "available": list_ok or print_ok,
        "list_available": list_ok,
        "domain_available": print_ok,
        "domain": domain,
        "loaded": _merge_loaded_labels(list_loaded, print_loaded),
        "disabled": disabled,
        "errors": errors,
    }


def _loaded_labels() -> dict[str, dict[str, Any]]:
    """Compatibility wrapper for callers that only need the merged loaded-service map."""

    return _launchctl_snapshot()["loaded"]


def _issue(
    *,
    kind: str,
    severity: str,
    label: str,
    message: str,
    path: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "kind": kind,
        "severity": severity,
        "label": label,
        "automation_id": _label_to_automation_id(label),
        "message": message,
    }
    if path is not None:
        payload["path"] = str(path)
    if metadata:
        payload.update(metadata)
    return payload


def audit_launchd_jobs(*, include_launchctl: bool = True) -> dict[str, Any]:
    registered_automations = list_automations()
    registered_ids = {item.id for item in registered_automations}
    active_registered_ids = {
        item.id
        for item in registered_automations
        if str(getattr(item, "status", "active") or "active").strip().lower() == "active"
    }
    repo_target_labels = {
        label
        for label in REPO_MANAGED_TARGET_LABELS
        if _label_to_automation_id(label) in active_registered_ids
    }
    plists: dict[str, list[dict[str, Any]]] = {}
    issues: list[dict[str, Any]] = []

    for path in _plist_paths():
        plist = _read_plist(path)
        if plist is None:
            issues.append(
                _issue(
                    kind="local_launchd_unreadable_plist",
                    severity="error",
                    label=path.stem,
                    path=path,
                    message="A com.neo launchd plist could not be parsed.",
                )
            )
            continue
        label = str(plist.get("Label") or path.stem)
        program_args = plist.get("ProgramArguments") or []
        if not isinstance(program_args, list):
            program_args = []
        installed = _is_installed(path)
        plists.setdefault(label, []).append(
            {
                "path": str(path),
                "installed": installed,
                "program_arguments": [str(item) for item in program_args],
            }
        )

        automation_id = _label_to_automation_id(label)
        if installed and automation_id not in registered_ids:
            issues.append(
                _issue(
                    kind="local_launchd_loaded_unregistered",
                    severity="warn",
                    label=label,
                    path=path,
                    message="Installed com.neo launchd job is not represented in the backend automation registry.",
                )
            )

        missing = _missing_paths(program_args)
        for missing_path in missing:
            issues.append(
                _issue(
                    kind="local_launchd_missing_program",
                    severity="error",
                    label=label,
                    path=path,
                    message="Installed com.neo launchd job points at a missing workspace script.",
                    metadata={"missing_path": missing_path},
                )
            )

        if installed and _uses_generic_python(program_args) and label not in ALLOW_GENERIC_PYTHON:
            issues.append(
                _issue(
                    kind="local_launchd_generic_python",
                    severity="warn",
                    label=label,
                    path=path,
                    message="Installed com.neo launchd job uses generic python3 instead of the workspace venv.",
                    metadata={"expected_python": VENv_PYTHON},
                )
            )

        counterpart = _repo_counterpart(path, label) if installed else None
        counterpart_plist = _read_plist(counterpart) if counterpart else None
        drift_fields = (
            _plist_drift_fields(plist, counterpart_plist)
            if installed and isinstance(counterpart_plist, dict)
            else []
        )
        if drift_fields:
            issues.append(
                _issue(
                    kind="local_launchd_installed_plist_drift",
                    severity="error" if label in repo_target_labels else "warn",
                    label=label,
                    path=path,
                    message="Installed launchd plist configuration differs from the repo source plist.",
                    metadata={
                        "repo_plist": str(counterpart),
                        "drift_fields": drift_fields,
                        "repo_managed_target": label in repo_target_labels,
                    },
                )
            )

    launchctl = (
        _launchctl_snapshot()
        if include_launchctl
        else {
            "available": False,
            "list_available": False,
            "domain_available": False,
            "domain": f"gui/{os.getuid()}",
            "loaded": {},
            "disabled": {},
            "errors": [],
            "skipped": True,
        }
    )
    loaded = launchctl["loaded"]
    disabled = launchctl["disabled"]
    installed_labels = {label for label, entries in plists.items() if any(entry["installed"] for entry in entries)}
    repo_labels = {label for label, entries in plists.items() if any(not entry["installed"] for entry in entries)}

    for label in sorted(repo_target_labels):
        if label not in repo_labels:
            issues.append(
                _issue(
                    kind="local_launchd_repo_target_missing_source",
                    severity="error",
                    label=label,
                    message="A required repo-managed launchd target has no source plist.",
                    metadata={"repo_managed_target": True},
                )
            )
        if label not in installed_labels:
            issues.append(
                _issue(
                    kind="local_launchd_repo_target_not_installed",
                    severity="error",
                    label=label,
                    message="A required repo-managed launchd target is not installed in ~/Library/LaunchAgents.",
                    metadata={"repo_managed_target": True, "source_present": label in repo_labels},
                )
            )

    if include_launchctl and not launchctl["available"]:
        issues.append(
            _issue(
                kind="local_launchd_state_unavailable",
                severity="warn",
                label="launchctl.gui_domain",
                message="launchctl state could not be read; the audit cannot claim that installed jobs are healthy.",
                metadata={"launchctl_errors": launchctl["errors"]},
            )
        )
    elif include_launchctl and not launchctl["domain_available"]:
        issues.append(
            _issue(
                kind="local_launchd_domain_state_unavailable",
                severity="warn",
                label="launchctl.gui_domain",
                message="The full launchctl GUI-domain state could not be read, so disabled and list-omitted jobs were not fully audited.",
                metadata={"launchctl_errors": launchctl["errors"]},
            )
        )

    relevant_labels = installed_labels.union(loaded).union(repo_target_labels)
    enablement = {
        label: "disabled" if disabled.get(label) is True else "enabled" if disabled.get(label) is False else "default"
        for label in sorted(relevant_labels)
    }
    if launchctl["domain_available"]:
        for label in sorted(relevant_labels):
            if disabled.get(label) is True:
                issues.append(
                    _issue(
                        kind="local_launchd_job_disabled",
                        severity="error" if label in repo_target_labels else "warn",
                        label=label,
                        message="launchctl marks this relevant com.neo job as disabled.",
                        metadata={
                            "installed": label in installed_labels,
                            "loaded": label in loaded,
                            "repo_managed_target": label in repo_target_labels,
                        },
                    )
                )
        for label in sorted(installed_labels.difference(loaded).difference(repo_target_labels)):
            issues.append(
                _issue(
                    kind="local_launchd_installed_not_loaded",
                    severity="warn",
                    label=label,
                    message="The plist is installed in ~/Library/LaunchAgents but the job is absent from the launchctl GUI domain.",
                    metadata={"enablement": enablement[label]},
                )
            )
        for label in sorted(repo_target_labels.difference(loaded)):
            issues.append(
                _issue(
                    kind="local_launchd_repo_target_not_loaded",
                    severity="error",
                    label=label,
                    message="A required repo-managed launchd target is absent from the launchctl GUI domain.",
                    metadata={
                        "installed": label in installed_labels,
                        "enablement": enablement[label],
                        "repo_managed_target": True,
                    },
                )
            )

    for label, loaded_state in loaded.items():
        if label not in installed_labels:
            issues.append(
                _issue(
                    kind="local_launchd_loaded_without_installed_plist",
                    severity="warn",
                    label=label,
                    message="launchctl has a com.neo job loaded that is not present in ~/Library/LaunchAgents.",
                    metadata=loaded_state,
                )
            )
        status_value = loaded_state.get("last_exit_status")
        status = str(status_value) if status_value is not None else ""
        if label == "com.neo.launchd_health_audit":
            # The active audit run is the current health evidence. launchctl only
            # exposes the previous exit code here, so counting it would make a
            # once-failed audit keep failing itself forever.
            continue
        if status and status not in {"0", "-15"}:
            issues.append(
                _issue(
                    kind="local_launchd_nonzero_last_exit",
                    severity="error",
                    label=label,
                    message="launchctl reports a nonzero last exit status for this com.neo job.",
                    metadata=loaded_state,
                )
            )

    return {
        "schema_version": "launchd_health_audit/v1",
        "generated_at": _utc_now().isoformat().replace("+00:00", "Z"),
        "workspace_root": str(WORKSPACE_ROOT),
        "counts": {
            "plist_labels": len(plists),
            "installed_labels": len(installed_labels),
            "loaded_labels": len(loaded),
            "repo_target_labels": len(repo_target_labels),
            "repo_target_installed_labels": len(repo_target_labels.intersection(installed_labels)),
            "repo_target_loaded_labels": len(repo_target_labels.intersection(loaded)),
            "repo_target_missing_install": len(repo_target_labels.difference(installed_labels)),
            "repo_target_unloaded": (
                len(repo_target_labels.difference(loaded)) if launchctl["domain_available"] else 0
            ),
            "disabled_relevant_labels": sum(1 for label in relevant_labels if disabled.get(label) is True),
            "issues": len(issues),
            "errors": sum(1 for issue in issues if issue.get("severity") == "error"),
            "warnings": sum(1 for issue in issues if issue.get("severity") == "warn"),
        },
        "plists": plists,
        "repo_target_labels": sorted(repo_target_labels),
        "loaded": loaded,
        "enablement": enablement,
        "launchctl": {
            "available": launchctl["available"],
            "list_available": launchctl["list_available"],
            "domain_available": launchctl["domain_available"],
            "domain": launchctl["domain"],
            "errors": launchctl["errors"],
            "skipped": bool(launchctl.get("skipped")),
        },
        "issues": issues,
    }


def _write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mirror(report: dict[str, Any], *, api_url: str, started_at: datetime, finished_at: datetime) -> bool:
    issue_count = int((report.get("counts") or {}).get("issues") or 0)
    status = "error" if issue_count else "ok"
    run = build_run_payload(
        run_id=f"{AUTOMATION_ID}::{finished_at.isoformat()}",
        automation_id=AUTOMATION_ID,
        automation_name=AUTOMATION_NAME,
        status=status,
        source="local_launchd_registry",
        runtime="launchd",
        run_at=started_at,
        finished_at=finished_at,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        error=f"{issue_count} local launchd issue(s) detected." if issue_count else None,
        scope="shared_ops",
        action_required=bool(issue_count),
        metadata={
            "has_observed_run": True,
            "summary": f"Launchd audit found {issue_count} issue(s).",
            "launchd_issues": report.get("issues") or [],
            "launchd_counts": report.get("counts") or {},
        },
    )
    return mirror_runs(api_url, [run])


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local com.neo launchd jobs.")
    parser.add_argument("--api-url", default=os.environ.get("AICLONE_API_URL", DEFAULT_API_URL))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--no-mirror", action="store_true")
    parser.add_argument("--skip-launchctl", action="store_true")
    args = parser.parse_args()

    started_at = _utc_now()
    report = audit_launchd_jobs(include_launchctl=not args.skip_launchctl)
    report_path = Path(args.report_path)
    _write_report(report, report_path)
    finished_at = _utc_now()
    mirrored = False if args.no_mirror else _mirror(report, api_url=args.api_url, started_at=started_at, finished_at=finished_at)
    report["mirrored"] = mirrored
    _write_report(report, report_path)
    print(json.dumps({"status": "ok" if not report["issues"] else "error", "mirrored": mirrored, **report["counts"]}))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
