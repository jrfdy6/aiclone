from __future__ import annotations

import importlib.util
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts/ops/audit_launchd_jobs.py"
SPEC = importlib.util.spec_from_file_location("audit_launchd_jobs", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["audit_launchd_jobs"] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_plist(path: Path, *, label: str, program_args: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump({"Label": label, "ProgramArguments": program_args}, handle)


class LaunchdHealthAuditTests(unittest.TestCase):
    def test_audit_flags_missing_script_and_generic_python_in_installed_plist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            missing_script = root / "workspace/scripts/missing.py"
            label = "com.neo.sessionmetrics"
            _write_plist(
                local_agents / f"{label}.plist",
                label=label,
                program_args=["/usr/bin/env", "python3", str(missing_script)],
            )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "WORKSPACE_ROOT", root / "workspace"),
                patch.object(MODULE, "_loaded_labels", return_value={}),
                patch.object(MODULE, "list_automations", return_value=[]),
            ):
                report = MODULE.audit_launchd_jobs()

        kinds = {issue["kind"] for issue in report["issues"]}
        self.assertIn("local_launchd_loaded_unregistered", kinds)
        self.assertIn("local_launchd_missing_program", kinds)
        self.assertIn("local_launchd_generic_python", kinds)

    def test_audit_flags_installed_plist_drift_from_repo_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            label = "com.neo.brain_canonical_memory_sync"
            _write_plist(
                local_agents / f"{label}.plist",
                label=label,
                program_args=["/usr/bin/env", "python3", "/Users/neo/.openclaw/workspace/scripts/brain_canonical_memory_sync.py"],
            )
            _write_plist(
                repo_launchd / f"{label}.plist",
                label=label,
                program_args=[
                    "/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python",
                    "/Users/neo/.openclaw/workspace/scripts/brain_canonical_memory_sync.py",
                ],
            )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "_loaded_labels", return_value={}),
                patch.object(MODULE, "list_automations", return_value=[]),
            ):
                report = MODULE.audit_launchd_jobs()

        kinds = {issue["kind"] for issue in report["issues"]}
        self.assertIn("local_launchd_installed_plist_drift", kinds)


if __name__ == "__main__":
    unittest.main()
