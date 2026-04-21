#!/usr/bin/env python3
"""Verify that runtime outputs stay out of tracked canonical paths."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import RUNTIME_MEMORY_RELATIVE_PATHS


REQUIRED_GITIGNORE_LINES = (
    "memory/runtime/",
    "memory/reports/memory_health_*.md",
    "workspaces/*/runtime/",
    "workspaces/*/reports/",
    "workspaces/*/standups/",
    "workspaces/linkedin-content-os/docs/backlog_seed_status_20??-??-??.md",
    "workspaces/linkedin-content-os/docs/operating_rhythm_status_20??-??-??.md",
    "workspaces/linkedin-content-os/drafts/feezie_owner_review_packet_20??????.md",
    "workspaces/shared-ops/docs/workspace_pack_executive_review_20??-??-??.md",
    "workspaces/shared-ops/docs/heartbeat_verification_20??-??-??.md",
    "workspaces/shared-ops/docs/openclaw_codex_smoke_followup_20??-??-??.md",
    "workspaces/shared-ops/docs/workspace_identity_alignment_20??-??-??.md",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(WORKSPACE_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _status_lines(*paths: str) -> list[str]:
    result = _git("status", "--short", "--", *paths)
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _is_tracked(relative_path: str) -> bool:
    return _git("ls-files", "--error-unmatch", "--", relative_path).returncode == 0


def _read_gitignore() -> str:
    return (WORKSPACE_ROOT / ".gitignore").read_text(encoding="utf-8")


def build_report() -> dict[str, object]:
    runtime_write_paths = sorted(RUNTIME_MEMORY_RELATIVE_PATHS.values())
    protected_canonical_paths = sorted(RUNTIME_MEMORY_RELATIVE_PATHS.keys())
    gitignore_text = _read_gitignore()
    missing_gitignore_lines = [line for line in REQUIRED_GITIGNORE_LINES if line not in gitignore_text]
    tracked_runtime_paths = [path for path in runtime_write_paths if _is_tracked(path)]
    dirty_protected_paths = _status_lines(*protected_canonical_paths)

    ok = not missing_gitignore_lines and not tracked_runtime_paths and not dirty_protected_paths
    return {
        "ok": ok,
        "runtime_write_paths": runtime_write_paths,
        "protected_canonical_paths": protected_canonical_paths,
        "missing_gitignore_lines": missing_gitignore_lines,
        "tracked_runtime_paths": tracked_runtime_paths,
        "dirty_protected_paths": dirty_protected_paths,
    }


def print_text(report: dict[str, object]) -> None:
    print("Repo hygiene")
    print(f"- ok: `{report['ok']}`")
    print(f"- runtime write paths: `{len(report['runtime_write_paths'])}`")
    if report["missing_gitignore_lines"]:
        print("- missing .gitignore lines:")
        for item in report["missing_gitignore_lines"]:
            print(f"  - {item}")
    if report["tracked_runtime_paths"]:
        print("- runtime paths unexpectedly tracked:")
        for item in report["tracked_runtime_paths"]:
            print(f"  - {item}")
    if report["dirty_protected_paths"]:
        print("- protected canonical paths are dirty:")
        for item in report["dirty_protected_paths"]:
            print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
