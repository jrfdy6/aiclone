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

WORKSPACE_ROOT = Path(
    os.getenv("AI_CLONE_ROOT") or Path(__file__).resolve().parents[2]
).expanduser().resolve()
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs  # noqa: E402
from app.services.automation_service import (  # noqa: E402
    CONFIGURED_LAUNCHD_AUTOMATION_IDS,
    LAUNCHD_HEALTH_STATE_SCHEMA,
    automation_registry_ids,
)
from runtime_paths import (  # noqa: E402
    RUNTIME_ROOT,
    STATE_ROOT,
    memory_state_path,
    seed_memory_state_file,
)

AUTOMATION_ID = "launchd_health_audit"
AUTOMATION_NAME = "Launchd Health Audit"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
REPORT_LOGICAL_REF = "memory/reports/launchd_health_audit_latest.json"
DEFAULT_REPORT_PATH = memory_state_path(
    "reports/launchd_health_audit_latest.json",
    state_root=STATE_ROOT,
)
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
AUTOMATION_ID_TO_LABEL = {
    automation_id: label for label, automation_id in LABEL_TO_AUTOMATION_ID.items()
}
ALLOW_GENERIC_PYTHON = {
    "com.neo.persona_bundle_sync",
}
# These 17 jobs are required activation targets. The three core maintenance
# jobs below are still configured and fully observed, but are not allowed to
# make target selection circular by defining the audit contract from runtime
# registry status.
REPO_MANAGED_TARGET_LABELS = frozenset(
    AUTOMATION_ID_TO_LABEL.get(automation_id, f"com.neo.{automation_id}")
    for automation_id in CONFIGURED_LAUNCHD_AUTOMATION_IDS.difference(
        {"codex_chronicle_sync", "codex_memory_sync", "launchd_health_audit"}
    )
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


def _automation_id_to_label(automation_id: str) -> str:
    return AUTOMATION_ID_TO_LABEL.get(automation_id, f"com.neo.{automation_id}")


def _path_free_automation_states(
    *,
    observed_at: str,
    registered_ids: set[str],
    repo_target_labels: set[str],
    repo_labels: set[str],
    installed_labels: set[str],
    loaded: dict[str, dict[str, Any]],
    disabled: dict[str, bool],
    launchctl: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the only host-state payload allowed to leave the operator Mac."""

    observed_labels = (
        set(repo_target_labels)
        .union(repo_labels)
        .union(installed_labels)
        .union(loaded)
        .union(_automation_id_to_label(item) for item in registered_ids)
    )
    states: dict[str, dict[str, Any]] = {}
    for label in sorted(observed_labels):
        automation_id = _label_to_automation_id(label)
        label_issues = [
            issue
            for issue in issues
            if str(issue.get("automation_id") or "") == automation_id
        ]
        error_count = sum(
            1 for issue in label_issues if issue.get("severity") == "error"
        )
        warning_count = sum(
            1 for issue in label_issues if issue.get("severity") == "warn"
        )
        loaded_value: bool | None
        if label in loaded:
            loaded_value = True
        elif launchctl.get("domain_available"):
            loaded_value = False
        else:
            loaded_value = None

        enabled_value: bool | None
        if launchctl.get("domain_available"):
            enabled_value = disabled.get(label) is not True
        else:
            enabled_value = None

        installed = label in installed_labels
        source_present = label in repo_labels
        required = label in repo_target_labels
        configured = automation_id in registered_ids and source_present
        healthy = bool(
            configured
            and installed
            and loaded_value is True
            and enabled_value is True
            and error_count == 0
        )
        last_exit_status = None
        if isinstance(loaded.get(label), dict):
            candidate = loaded[label].get("last_exit_status")
            if candidate is not None and re.fullmatch(r"-?\d+", str(candidate)):
                last_exit_status = str(candidate)
        states[automation_id] = {
            "observed_at": observed_at,
            "configured": configured,
            "required": required,
            "source_present": source_present,
            "installed": installed,
            "loaded": loaded_value,
            "enabled": enabled_value,
            "healthy": healthy,
            "last_exit_status": last_exit_status,
            "issue_count": len(label_issues),
            "error_count": error_count,
            "warning_count": warning_count,
        }
    return states


def _path_free_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Project a local audit issue without paths, host details, or commands."""

    safe = {
        "kind": str(issue.get("kind") or "local_launchd_audit_issue"),
        "severity": str(issue.get("severity") or "warn"),
        "automation_id": str(issue.get("automation_id") or "") or None,
        "message": str(issue.get("message") or "Local launchd audit found an issue."),
    }
    for key in (
        "drift_fields",
        "repo_managed_target",
        "source_present",
        "installed",
        "loaded",
        "enablement",
        "last_exit_status",
    ):
        value = issue.get(key)
        if isinstance(value, (bool, int, float, str, list)) or value is None:
            safe[key] = value
    return safe


def _path_free_state_map(raw_states: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_states, dict):
        return {}
    safe_states: dict[str, dict[str, Any]] = {}
    boolean_fields = {
        "configured",
        "required",
        "source_present",
        "installed",
        "loaded",
        "enabled",
        "healthy",
    }
    count_fields = {"issue_count", "error_count", "warning_count"}
    for raw_id, raw_state in raw_states.items():
        automation_id = str(raw_id)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", automation_id):
            continue
        if not isinstance(raw_state, dict):
            continue
        state: dict[str, Any] = {}
        for field in boolean_fields:
            value = raw_state.get(field)
            state[field] = value if isinstance(value, bool) else None
        for field in count_fields:
            value = raw_state.get(field)
            state[field] = max(0, int(value)) if isinstance(value, int) else 0
        exit_status = raw_state.get("last_exit_status")
        state["last_exit_status"] = (
            str(exit_status)
            if exit_status is not None and re.fullmatch(r"-?\d+", str(exit_status))
            else None
        )
        safe_states[automation_id] = state
    return safe_states


def audit_launchd_jobs(
    *,
    include_launchctl: bool = True,
    target_labels: set[str] | frozenset[str] | None = None,
    registered_ids: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    # Target selection is deliberately independent of list_automations().
    # Registry status is derived from this audit, so filtering audit targets by
    # registry status would create a circular "active because active" claim.
    repo_target_labels = set(
        REPO_MANAGED_TARGET_LABELS if target_labels is None else target_labels
    )
    known_registry_ids = set(
        automation_registry_ids() if registered_ids is None else registered_ids
    )
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
        if installed and automation_id not in known_registry_ids:
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

    observed_at = _utc_now().isoformat().replace("+00:00", "Z")
    automation_states = _path_free_automation_states(
        observed_at=observed_at,
        registered_ids=known_registry_ids,
        repo_target_labels=repo_target_labels,
        repo_labels=repo_labels,
        installed_labels=installed_labels,
        loaded=loaded,
        disabled=disabled,
        launchctl=launchctl,
        issues=issues,
    )
    return {
        "schema_version": "launchd_health_audit/v2",
        "generated_at": observed_at,
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
        "automation_state_schema": LAUNCHD_HEALTH_STATE_SCHEMA,
        "automation_states": automation_states,
        "issues": issues,
    }


def _write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _report_write_path(path: Path) -> Path:
    if path.expanduser().resolve() != DEFAULT_REPORT_PATH.expanduser().resolve():
        return path
    return seed_memory_state_file(
        "reports/launchd_health_audit_latest.json",
        project_root=WORKSPACE_ROOT,
        state_root=STATE_ROOT,
    )


def _mirror(report: dict[str, Any], *, api_url: str, started_at: datetime, finished_at: datetime) -> bool:
    issue_count = int((report.get("counts") or {}).get("issues") or 0)
    status = "error" if issue_count else "ok"
    observed_at = str(report.get("generated_at") or "").strip()
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        observed_at = ""
    safe_states = _path_free_state_map(report.get("automation_states"))
    safe_issues = [
        _path_free_issue(issue)
        for issue in (report.get("issues") or [])
        if isinstance(issue, dict)
    ]
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
            "launchd_issues": safe_issues,
            "launchd_counts": report.get("counts") or {},
            "launchd_state_schema": LAUNCHD_HEALTH_STATE_SCHEMA,
            "launchd_observed_at": observed_at,
            "launchd_automation_states": safe_states,
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
    report_path = _report_write_path(Path(args.report_path))
    _write_report(report, report_path)
    finished_at = _utc_now()
    mirrored = False if args.no_mirror else _mirror(report, api_url=args.api_url, started_at=started_at, finished_at=finished_at)
    report["mirrored"] = mirrored
    _write_report(report, report_path)
    print(json.dumps({"status": "ok" if not report["issues"] else "error", "mirrored": mirrored, **report["counts"]}))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
