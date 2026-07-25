#!/usr/bin/env python3
"""Read-only inventory of legacy and private generated state.

The audit compares the project-level ``memory`` and ``workspaces`` trees with
their counterparts under ``AI_CLONE_STATE_ROOT``. It emits metadata only:
paths, counts, byte sizes, SHA-256 hashes, and status values. It never creates,
moves, edits, or deletes anything in either tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import PROJECT_ROOT, STATE_ROOT


SCHEMA = "generated_state_audit/v1"
LANES = ("memory", "workspaces")
HASH_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class FileMetadata:
    path: Path
    size_bytes: int
    sha256: str

    def as_report(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class AuditIssue:
    path: Path
    logical_path: str | None = None

    def as_report(self) -> dict[str, str]:
        report = {"path": str(self.path), "status": "error"}
        if self.logical_path is not None:
            report["logical_path"] = self.logical_path
        return report


@dataclass
class SideScan:
    files: dict[str, FileMetadata] = field(default_factory=dict)
    failed_files: set[str] = field(default_factory=set)
    workspaces: set[str] = field(default_factory=set)
    root_statuses: dict[str, str] = field(default_factory=dict)
    issues: list[AuditIssue] = field(default_factory=list)


def _absolute(path: Path) -> Path:
    """Return an absolute display path without requiring it to exist."""

    return path.expanduser().absolute()


def _sha256_file(path: Path) -> tuple[int, str]:
    """Fingerprint one regular file without following a final symlink."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError

        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)

        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    current = os.stat(path, follow_symlinks=False)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    identity_current = (
        current.st_dev,
        current.st_ino,
        current.st_size,
        current.st_mtime_ns,
    )
    if identity_before != identity_after or identity_after != identity_current:
        raise OSError

    return after.st_size, digest.hexdigest()


def _scan_lane(root: Path, lane: str, result: SideScan) -> None:
    root = _absolute(root)
    try:
        root_stat = os.stat(root, follow_symlinks=False)
    except FileNotFoundError:
        result.root_statuses[lane] = "absent"
        return
    except OSError:
        result.root_statuses[lane] = "error"
        result.issues.append(AuditIssue(path=root))
        return

    if not stat.S_ISDIR(root_stat.st_mode):
        result.root_statuses[lane] = "error"
        result.issues.append(AuditIssue(path=root))
        return

    result.root_statuses[lane] = "present"
    stack: list[tuple[Path, PurePosixPath, int]] = [(root, PurePosixPath(lane), 0)]

    while stack:
        directory, logical_directory, depth = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError:
            result.issues.append(
                AuditIssue(path=directory, logical_path=logical_directory.as_posix())
            )
            continue

        directories: list[tuple[Path, PurePosixPath, int]] = []
        for entry in entries:
            physical_path = Path(entry.path)
            logical_path = logical_directory / entry.name
            logical_text = logical_path.as_posix()
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError:
                result.issues.append(
                    AuditIssue(path=physical_path, logical_path=logical_text)
                )
                continue

            if stat.S_ISDIR(entry_stat.st_mode):
                if lane == "workspaces" and depth == 0:
                    result.workspaces.add(logical_text)
                directories.append((physical_path, logical_path, depth + 1))
                continue

            if not stat.S_ISREG(entry_stat.st_mode):
                result.issues.append(
                    AuditIssue(path=physical_path, logical_path=logical_text)
                )
                continue

            try:
                size_bytes, sha256 = _sha256_file(physical_path)
            except OSError:
                result.failed_files.add(logical_text)
                result.issues.append(
                    AuditIssue(path=physical_path, logical_path=logical_text)
                )
                continue

            result.files[logical_text] = FileMetadata(
                path=_absolute(physical_path),
                size_bytes=size_bytes,
                sha256=sha256,
            )

        stack.extend(reversed(directories))


def _scan_side(root: Path) -> SideScan:
    result = SideScan()
    for lane in LANES:
        _scan_lane(root / lane, lane, result)
    return result


def _file_status(
    legacy: FileMetadata | None,
    state: FileMetadata | None,
    *,
    failed: bool,
) -> str:
    if failed:
        return "error"
    if legacy is None:
        return "state_only"
    if state is None:
        return "legacy_only"
    if legacy.size_bytes == state.size_bytes and legacy.sha256 == state.sha256:
        return "identical"
    return "different"


def _build_file_reports(legacy: SideScan, state: SideScan) -> list[dict[str, Any]]:
    logical_paths = sorted(
        set(legacy.files)
        | set(state.files)
        | legacy.failed_files
        | state.failed_files
    )
    reports: list[dict[str, Any]] = []
    for logical_path in logical_paths:
        legacy_metadata = legacy.files.get(logical_path)
        state_metadata = state.files.get(logical_path)
        report: dict[str, Any] = {
            "path": logical_path,
            "status": _file_status(
                legacy_metadata,
                state_metadata,
                failed=(
                    logical_path in legacy.failed_files
                    or logical_path in state.failed_files
                ),
            ),
        }
        if legacy_metadata is not None:
            report["legacy"] = legacy_metadata.as_report()
        if state_metadata is not None:
            report["state"] = state_metadata.as_report()
        reports.append(report)
    return reports


def _workspace_report(
    workspace_path: str,
    *,
    legacy: SideScan,
    state: SideScan,
    file_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    prefix = f"{workspace_path}/"
    scoped_reports = [
        report for report in file_reports if report["path"].startswith(prefix)
    ]
    legacy_present = workspace_path in legacy.workspaces
    state_present = workspace_path in state.workspaces
    has_error = any(report["status"] == "error" for report in scoped_reports)
    has_error = has_error or any(
        issue.logical_path == workspace_path
        or (
            issue.logical_path is not None
            and issue.logical_path.startswith(prefix)
        )
        for issue in (*legacy.issues, *state.issues)
    )

    if has_error:
        status_value = "error"
    elif not legacy_present:
        status_value = "state_only"
    elif not state_present:
        status_value = "legacy_only"
    elif all(report["status"] == "identical" for report in scoped_reports):
        status_value = "identical"
    else:
        status_value = "different"

    legacy_files = [
        metadata
        for logical_path, metadata in legacy.files.items()
        if logical_path.startswith(prefix)
    ]
    state_files = [
        metadata
        for logical_path, metadata in state.files.items()
        if logical_path.startswith(prefix)
    ]
    return {
        "path": workspace_path,
        "status": status_value,
        "counts": {
            "file_paths": len(scoped_reports),
            "legacy_files": len(legacy_files),
            "state_files": len(state_files),
        },
        "sizes": {
            "legacy_bytes": sum(item.size_bytes for item in legacy_files),
            "state_bytes": sum(item.size_bytes for item in state_files),
        },
    }


def audit_generated_state(
    *,
    project_root: Path = PROJECT_ROOT,
    state_root: Path = STATE_ROOT,
) -> dict[str, Any]:
    """Build a deterministic, metadata-only comparison report."""

    project_root = _absolute(Path(project_root))
    state_root = _absolute(Path(state_root))
    legacy = _scan_side(project_root)
    state = _scan_side(state_root)
    file_reports = _build_file_reports(legacy, state)

    issues = sorted(
        (*legacy.issues, *state.issues),
        key=lambda issue: (issue.logical_path or "", str(issue.path)),
    )
    workspaces = [
        _workspace_report(
            workspace_path,
            legacy=legacy,
            state=state,
            file_reports=file_reports,
        )
        for workspace_path in sorted(legacy.workspaces | state.workspaces)
    ]

    status_counts = {
        status_value: sum(
            report["status"] == status_value for report in file_reports
        )
        for status_value in (
            "identical",
            "different",
            "legacy_only",
            "state_only",
            "error",
        )
    }
    if issues:
        overall_status = "error"
    elif any(
        status_counts[status_value]
        for status_value in ("different", "legacy_only", "state_only")
    ):
        overall_status = "differences"
    elif file_reports:
        overall_status = "identical"
    else:
        overall_status = "empty"

    return {
        "schema": SCHEMA,
        "status": overall_status,
        "roots": {
            "legacy": [
                {
                    "path": str(project_root / lane),
                    "status": legacy.root_statuses[lane],
                }
                for lane in LANES
            ],
            "state": [
                {
                    "path": str(state_root / lane),
                    "status": state.root_statuses[lane],
                }
                for lane in LANES
            ],
        },
        "summary": {
            "status": overall_status,
            "counts": {
                "file_paths": len(file_reports),
                "legacy_files": len(legacy.files),
                "state_files": len(state.files),
                "workspaces": len(workspaces),
                "audit_errors": len(issues),
                **status_counts,
            },
            "sizes": {
                "legacy_bytes": sum(
                    metadata.size_bytes for metadata in legacy.files.values()
                ),
                "state_bytes": sum(
                    metadata.size_bytes for metadata in state.files.values()
                ),
            },
        },
        "workspaces": workspaces,
        "files": file_reports,
        "errors": [issue.as_report() for issue in issues],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only metadata audit of project memory/workspaces versus "
            "AI_CLONE_STATE_ROOT."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root containing legacy memory and workspaces trees.",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=STATE_ROOT,
        help="Private state root; defaults to runtime_paths.STATE_ROOT.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON instead of indented JSON.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit per-file rows and emit only roots, totals, workspaces, and errors.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = audit_generated_state(
        project_root=args.project_root,
        state_root=args.state_root,
    )
    output = report
    if args.summary_only:
        output = {
            key: report[key]
            for key in ("schema", "status", "roots", "summary", "workspaces", "errors")
        }
    if args.compact:
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(output, indent=2, sort_keys=True))
    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
