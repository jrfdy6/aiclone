from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import audit_generated_state


def _write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def _tree_snapshot(root: Path) -> list[tuple[str, str, int, str]]:
    if not root.exists():
        return []

    snapshot: list[tuple[str, str, int, str]] = []
    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot.append((relative_path, "directory", 0, ""))
        elif path.is_file():
            contents = path.read_bytes()
            snapshot.append(
                (
                    relative_path,
                    "file",
                    len(contents),
                    hashlib.sha256(contents).hexdigest(),
                )
            )
    return snapshot


class GeneratedStateAuditTests(unittest.TestCase):
    def test_inventory_is_metadata_only_dynamic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "private-state"

            _write(project_root / "memory" / "identical.md", b"same")
            _write(state_root / "memory" / "identical.md", b"same")
            _write(project_root / "memory" / "changed.md", b"legacy")
            _write(state_root / "memory" / "changed.md", b"state")
            _write(
                project_root / "memory" / "legacy-only.md",
                b"CONTENT_MUST_NEVER_APPEAR_IN_REPORT",
            )
            _write(state_root / "memory" / "state-only.db", b"private")

            _write(
                project_root
                / "workspaces"
                / "alpha"
                / "runtime"
                / "same.json",
                b"{}",
            )
            _write(
                state_root
                / "workspaces"
                / "alpha"
                / "runtime"
                / "same.json",
                b"{}",
            )
            _write(
                state_root
                / "workspaces"
                / "future-workspace-key"
                / "runtime"
                / "new.json",
                b'{"status":"new"}',
            )
            (project_root / "workspaces" / "empty-legacy-workspace").mkdir(
                parents=True
            )
            (state_root / "workspaces" / "empty-state-workspace").mkdir(
                parents=True
            )

            project_before = _tree_snapshot(project_root)
            state_before = _tree_snapshot(state_root)
            report = audit_generated_state.audit_generated_state(
                project_root=project_root,
                state_root=state_root,
            )

            self.assertEqual(_tree_snapshot(project_root), project_before)
            self.assertEqual(_tree_snapshot(state_root), state_before)

        self.assertEqual(report["status"], "differences")
        self.assertEqual(report["summary"]["counts"]["audit_errors"], 0)
        statuses = {
            item["path"]: item["status"] for item in report["files"]
        }
        self.assertEqual(statuses["memory/identical.md"], "identical")
        self.assertEqual(statuses["memory/changed.md"], "different")
        self.assertEqual(statuses["memory/legacy-only.md"], "legacy_only")
        self.assertEqual(statuses["memory/state-only.db"], "state_only")
        self.assertEqual(
            statuses["workspaces/alpha/runtime/same.json"], "identical"
        )
        self.assertEqual(
            statuses["workspaces/future-workspace-key/runtime/new.json"],
            "state_only",
        )

        workspace_statuses = {
            item["path"]: item["status"] for item in report["workspaces"]
        }
        self.assertEqual(workspace_statuses["workspaces/alpha"], "identical")
        self.assertEqual(
            workspace_statuses["workspaces/future-workspace-key"],
            "state_only",
        )
        self.assertEqual(
            workspace_statuses["workspaces/empty-legacy-workspace"],
            "legacy_only",
        )
        self.assertEqual(
            workspace_statuses["workspaces/empty-state-workspace"],
            "state_only",
        )

        serialized = json.dumps(report)
        self.assertNotIn("CONTENT_MUST_NEVER_APPEAR_IN_REPORT", serialized)
        expected_hash = hashlib.sha256(
            b"CONTENT_MUST_NEVER_APPEAR_IN_REPORT"
        ).hexdigest()
        legacy_only = next(
            item
            for item in report["files"]
            if item["path"] == "memory/legacy-only.md"
        )
        self.assertEqual(legacy_only["legacy"]["sha256"], expected_hash)

    def test_legacy_only_data_is_not_an_audit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "private-state"
            _write(project_root / "memory" / "legacy.md", b"legacy")

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = audit_generated_state.main(
                    [
                        "--project-root",
                        str(project_root),
                        "--state-root",
                        str(state_root),
                        "--compact",
                    ]
                )

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "differences")
        self.assertEqual(report["summary"]["counts"]["legacy_only"], 1)
        self.assertEqual(report["summary"]["counts"]["audit_errors"], 0)

    def test_actual_read_error_is_reported_and_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "private-state"
            _write(
                project_root / "memory" / "unreadable.md",
                b"SENSITIVE_BODY_NEVER_PRINT",
            )

            stdout = StringIO()
            with (
                patch.object(
                    audit_generated_state,
                    "_sha256_file",
                    side_effect=PermissionError,
                ),
                redirect_stdout(stdout),
            ):
                exit_code = audit_generated_state.main(
                    [
                        "--project-root",
                        str(project_root),
                        "--state-root",
                        str(state_root),
                        "--compact",
                    ]
                )

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["summary"]["counts"]["audit_errors"], 1)
        self.assertEqual(report["files"][0]["status"], "error")
        self.assertEqual(report["errors"][0]["status"], "error")
        self.assertNotIn("SENSITIVE_BODY_NEVER_PRINT", stdout.getvalue())

    def test_runtime_path_environment_overrides_drive_cli_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "configured-project"
            state_root = root / "configured-state"
            _write(project_root / "memory" / "same.md", b"same")
            _write(state_root / "memory" / "same.md", b"same")

            environment = os.environ.copy()
            environment["AI_CLONE_ROOT"] = str(project_root)
            environment["AI_CLONE_STATE_ROOT"] = str(state_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_ROOT / "audit_generated_state.py"),
                    "--compact",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "identical")
        self.assertEqual(
            Path(report["roots"]["legacy"][0]["path"]).resolve(),
            (project_root / "memory").resolve(),
        )
        self.assertEqual(
            Path(report["roots"]["state"][0]["path"]).resolve(),
            (state_root / "memory").resolve(),
        )

    def test_missing_roots_are_empty_not_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = audit_generated_state.audit_generated_state(
                project_root=root / "missing-project",
                state_root=root / "missing-state",
            )

        self.assertEqual(report["status"], "empty")
        self.assertEqual(report["summary"]["counts"]["file_paths"], 0)
        self.assertEqual(report["summary"]["counts"]["audit_errors"], 0)
        self.assertEqual(report["errors"], [])

    def test_summary_only_omits_per_file_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "state"
            _write(project_root / "memory" / "legacy.md", b"legacy")
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = audit_generated_state.main(
                    [
                        "--project-root",
                        str(project_root),
                        "--state-root",
                        str(state_root),
                        "--summary-only",
                    ]
                )

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertNotIn("files", report)
        self.assertEqual(report["summary"]["counts"]["legacy_only"], 1)


if __name__ == "__main__":
    unittest.main()
