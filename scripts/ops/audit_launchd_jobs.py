#!/usr/bin/env python3
"""Audit local com.neo launchd jobs and mirror visible health into Ops."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs  # noqa: E402
from app.services.automation_service import list_automations  # noqa: E402

AUTOMATION_ID = "launchd_health_audit"
AUTOMATION_NAME = "Launchd Health Audit"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
DEFAULT_REPORT_PATH = WORKSPACE_ROOT / "memory/reports/launchd_health_audit_latest.json"
VENv_PYTHON = str(WORKSPACE_ROOT / ".venv-main-safe/bin/python")
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


def _loaded_labels() -> dict[str, dict[str, Any]]:
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        label = parts[2]
        if not label.startswith("com.neo."):
            continue
        loaded[label] = {
            "pid": None if parts[0] == "-" else parts[0],
            "last_exit_status": parts[1],
            "label": label,
        }
    return loaded


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
    registered_ids = {item.id for item in list_automations()}
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
        counterpart_args = counterpart_plist.get("ProgramArguments") if isinstance(counterpart_plist, dict) else None
        if installed and isinstance(counterpart_args, list) and [str(item) for item in counterpart_args] != [
            str(item) for item in program_args
        ]:
            issues.append(
                _issue(
                    kind="local_launchd_installed_plist_drift",
                    severity="warn",
                    label=label,
                    path=path,
                    message="Installed launchd plist ProgramArguments differ from the repo source plist.",
                    metadata={"repo_plist": str(counterpart)},
                )
            )

    loaded = _loaded_labels() if include_launchctl else {}
    installed_labels = {label for label, entries in plists.items() if any(entry["installed"] for entry in entries)}
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
        status = str(loaded_state.get("last_exit_status") or "")
        if label == "com.neo.launchd_health_audit":
            # The active audit run is the current health evidence. launchctl only
            # exposes the previous exit code here, so counting it would make a
            # once-failed audit keep failing itself forever.
            continue
        if status not in {"0", "-15"}:
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
            "issues": len(issues),
            "errors": sum(1 for issue in issues if issue.get("severity") == "error"),
            "warnings": sum(1 for issue in issues if issue.get("severity") == "warn"),
        },
        "plists": plists,
        "loaded": loaded,
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
    mirrored = True if args.no_mirror else _mirror(report, api_url=args.api_url, started_at=started_at, finished_at=finished_at)
    report["mirrored"] = mirrored
    _write_report(report, report_path)
    print(json.dumps({"status": "ok" if not report["issues"] else "error", "mirrored": mirrored, **report["counts"]}))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
