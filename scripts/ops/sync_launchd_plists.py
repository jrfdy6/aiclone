#!/usr/bin/env python3
"""Sync repo launchd plists into ~/Library/LaunchAgents."""
from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path("/Users/neo/Documents/Codex/AI-Clone")
SOURCE_DIR = WORKSPACE_ROOT / "automations/launchd"
SOURCE_DIRS = [
    WORKSPACE_ROOT / "automations/launchd",
    WORKSPACE_ROOT / "automations",
]
LAUNCH_AGENTS_DIR = Path.home() / "Library/LaunchAgents"
ARCHIVE_DIR = Path.home() / "Library/LaunchAgents.disabled"
OBSOLETE_LABELS = {
    "com.neo.neo_execution",
    "com.neo.pulse_standup_autoroute",
    "com.neo.sessionmetrics",
}


def _read_label(path: Path) -> str:
    with path.open("rb") as handle:
        payload = plistlib.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a plist dictionary")
    label = str(payload.get("Label") or "").strip()
    if not label:
        raise ValueError(f"{path} does not define Label")
    return label


def _run_launchctl(args: list[str], *, dry_run: bool) -> tuple[int, str]:
    if dry_run:
        return 0, "dry-run"
    # Codex Desktop runs commands in the owner's app sandbox.  Asking launchd
    # to execute the control operation in the login user's bootstrap context
    # avoids false EPERM failures while preserving the exact gui/<uid> target.
    command = ["launchctl", "asuser", str(_uid()), "launchctl", *args]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode, output


def _copy_plist(source: Path, target: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(0o644)


def _archive_obsolete(label: str, *, dry_run: bool, results: list[dict[str, Any]]) -> None:
    source = LAUNCH_AGENTS_DIR / f"{label}.plist"
    if not source.exists():
        results.append({"label": label, "action": "archive_obsolete", "status": "missing"})
        return

    code, output = _run_launchctl(["bootout", f"gui/{_uid()}", str(source)], dry_run=dry_run)
    if dry_run:
        target = ARCHIVE_DIR / source.name
    else:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        target = ARCHIVE_DIR / source.name
        source.rename(target)
    results.append(
        {
            "label": label,
            "action": "archive_obsolete",
            "status": "ok",
            "bootout_code": code,
            "bootout_output": output,
            "archived_to": str(target),
        }
    )


def _uid() -> int:
    try:
        import os

        return os.getuid()
    except Exception:
        return 501


def _normalize_label(label: str) -> str:
    normalized = str(label or "").strip()
    if not normalized:
        raise ValueError("Launchd labels cannot be empty.")
    if normalized.startswith("com.neo."):
        return normalized
    return f"com.neo.{normalized}"


def sync_plists(labels: list[str] | None, *, dry_run: bool, load: bool, archive_obsolete: bool) -> dict[str, Any]:
    if load and not labels:
        raise ValueError(
            "Refusing to load every repo launchd plist. Pass one or more explicit --label values, "
            "or use --no-load to sync plist files without enabling or bootstrapping jobs."
        )

    by_label: dict[str, Path] = {}
    for directory in SOURCE_DIRS:
        for path in sorted(directory.glob("com.neo*.plist")):
            label = _read_label(path)
            by_label.setdefault(label, path)
    requested = {_normalize_label(label) for label in labels or []}
    missing = requested.difference(by_label)
    if missing:
        raise ValueError(f"No source plist matched requested label(s): {sorted(missing)}")
    selected_labels = sorted(requested or by_label)
    selected = [by_label[label] for label in selected_labels]

    results: list[dict[str, Any]] = []
    for source in selected:
        label = _read_label(source)
        target = LAUNCH_AGENTS_DIR / source.name
        _copy_plist(source, target, dry_run=dry_run)
        result: dict[str, Any] = {
            "label": label,
            "source": str(source),
            "target": str(target),
            "action": "sync",
            "status": "ok",
        }
        if load:
            bootout_code, bootout_output = _run_launchctl(["bootout", f"gui/{_uid()}", str(target)], dry_run=dry_run)
            enable_code, enable_output = _run_launchctl(
                ["enable", f"gui/{_uid()}/{label}"],
                dry_run=dry_run,
            )
            bootstrap_code, bootstrap_output = _run_launchctl(["bootstrap", f"gui/{_uid()}", str(target)], dry_run=dry_run)
            result.update(
                {
                    "bootout_code": bootout_code,
                    "bootout_output": bootout_output,
                    "enable_code": enable_code,
                    "enable_output": enable_output,
                    "bootstrap_code": bootstrap_code,
                    "bootstrap_output": bootstrap_output,
                }
            )
            if enable_code != 0 or bootstrap_code != 0:
                result["status"] = "action_required"
        results.append(result)

    if archive_obsolete:
        for label in sorted(OBSOLETE_LABELS):
            _archive_obsolete(label, dry_run=dry_run, results=results)

    return {
        "source_dirs": [str(path) for path in SOURCE_DIRS],
        "launch_agents_dir": str(LAUNCH_AGENTS_DIR),
        "dry_run": dry_run,
        "load": load,
        "archive_obsolete": archive_obsolete,
        "count": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help=(
            "Specific label or com.neo suffix to sync. At least one label is required when loading; "
            "without labels, --no-load is required."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-load", action="store_true")
    parser.add_argument("--archive-obsolete", action="store_true")
    args = parser.parse_args()

    try:
        result = sync_plists(
            args.label or None,
            dry_run=args.dry_run,
            load=not args.no_load,
            archive_obsolete=args.archive_obsolete,
        )
    except ValueError as exc:
        parser.error(str(exc))
    for item in result["results"]:
        label = item.get("label")
        action = item.get("action")
        status = item.get("status")
        print(f"{status}: {action}: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
