from __future__ import annotations

import importlib.util
import json
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts/ops/audit_launchd_jobs.py"
SPEC = importlib.util.spec_from_file_location("audit_launchd_jobs", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules["audit_launchd_jobs"] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_plist(path: Path, *, label: str, program_args: list[str], **configuration: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(
            {"Label": label, "ProgramArguments": program_args, **configuration},
            handle,
        )


def _snapshot(
    *,
    loaded: dict[str, dict] | None = None,
    disabled: dict[str, bool] | None = None,
    available: bool = True,
    domain_available: bool = True,
) -> dict:
    return {
        "available": available,
        "list_available": available,
        "domain_available": domain_available,
        "domain": "gui/501",
        "loaded": loaded or {},
        "disabled": disabled or {},
        "errors": [] if available else ["launchctl unavailable"],
    }


class LaunchdHealthAuditTests(unittest.TestCase):
    def test_full_pm_execution_chain_is_a_required_health_target(self) -> None:
        self.assertTrue(
            {
                "com.neo.jean_claude_execution",
                "com.neo.workspace_agent_dispatch",
                "com.neo.codex_workspace_execution",
                "com.neo.pm_review_resolution",
            }.issubset(MODULE.REPO_MANAGED_TARGET_LABELS)
        )

    def test_brain_and_feezie_freshness_jobs_are_required_health_targets(self) -> None:
        self.assertTrue(
            {
                "com.neo.morning_daily_brief",
                "com.neo.operator_story_signals",
                "com.neo.content_safe_operator_lessons",
                "com.neo.feezie_content_pipeline",
                "com.neo.feezie_codex_bridge",
            }.issubset(MODULE.REPO_MANAGED_TARGET_LABELS)
        )

    def test_active_standup_loop_jobs_are_required_repo_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_launchd = root / "repo-launchd"
            labels = (
                "com.neo.meeting_watchdog",
                "com.neo.portfolio_standup_prep",
                "com.neo.post_sync_dispatch",
            )
            for label in labels:
                _write_plist(
                    repo_launchd / f"{label}.plist",
                    label=label,
                    program_args=[MODULE.VENv_PYTHON, f"/opt/aiclone/{label}.py"],
                    StartInterval=1800,
                )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", root / "LaunchAgents"),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
                patch.object(
                    MODULE,
                    "list_automations",
                    return_value=[
                        SimpleNamespace(id="meeting_watchdog", status="active"),
                        SimpleNamespace(id="portfolio_standup_prep", status="active"),
                        SimpleNamespace(id="post_sync_dispatch", status="active"),
                    ],
                ),
            ):
                report = MODULE.audit_launchd_jobs()

        self.assertEqual(report["repo_target_labels"], list(labels))
        for label in labels:
            target_kinds = {
                issue["kind"] for issue in report["issues"] if issue["label"] == label
            }
            self.assertEqual(
                target_kinds,
                {
                    "local_launchd_repo_target_not_installed",
                    "local_launchd_repo_target_not_loaded",
                },
            )

    def test_required_repo_target_reports_missing_install_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            label = "com.neo.brain_canonical_memory_sync"
            _write_plist(
                repo_launchd / f"{label}.plist",
                label=label,
                program_args=[MODULE.VENv_PYTHON, "/opt/aiclone/brain_sync.py"],
                StartInterval=1800,
            )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
                patch.object(
                    MODULE,
                    "list_automations",
                    return_value=[SimpleNamespace(id="brain_canonical_memory_sync", status="active")],
                ),
            ):
                report = MODULE.audit_launchd_jobs()

        target_issues = [issue for issue in report["issues"] if issue["label"] == label]
        self.assertEqual(
            {issue["kind"] for issue in target_issues},
            {
                "local_launchd_repo_target_not_installed",
                "local_launchd_repo_target_not_loaded",
            },
        )
        self.assertTrue(all(issue["severity"] == "error" for issue in target_issues))
        self.assertEqual(report["repo_target_labels"], [label])
        self.assertEqual(report["counts"]["repo_target_labels"], 1)
        self.assertEqual(report["counts"]["repo_target_missing_install"], 1)
        self.assertEqual(report["counts"]["repo_target_unloaded"], 1)
        self.assertEqual(report["counts"]["errors"], 2)

    def test_paused_repo_target_does_not_require_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            label = "com.neo.youtube_watchlist_auto_ingest"
            _write_plist(
                repo_launchd / f"{label}.plist",
                label=label,
                program_args=[MODULE.VENv_PYTHON, "/opt/aiclone/youtube.py"],
                StartInterval=7200,
            )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
                patch.object(
                    MODULE,
                    "list_automations",
                    return_value=[SimpleNamespace(id="youtube_watchlist_auto_ingest", status="paused")],
                ),
            ):
                report = MODULE.audit_launchd_jobs()

        self.assertEqual(report["repo_target_labels"], [])
        self.assertFalse(
            any(issue["kind"].startswith("local_launchd_repo_target_") for issue in report["issues"])
        )

    def test_installed_required_repo_target_reports_unloaded_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            label = "com.neo.youtube_watchlist_auto_ingest"
            args = [MODULE.VENv_PYTHON, "/opt/aiclone/youtube.py"]
            for directory in (local_agents, repo_launchd):
                _write_plist(
                    directory / f"{label}.plist",
                    label=label,
                    program_args=args,
                    StartInterval=7200,
                )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
                patch.object(
                    MODULE,
                    "list_automations",
                    return_value=[SimpleNamespace(id="youtube_watchlist_auto_ingest", status="active")],
                ),
            ):
                report = MODULE.audit_launchd_jobs()

        target_issues = [issue for issue in report["issues"] if issue["label"] == label]
        self.assertEqual(
            [issue["kind"] for issue in target_issues],
            ["local_launchd_repo_target_not_loaded"],
        )
        self.assertEqual(report["counts"]["repo_target_installed_labels"], 1)
        self.assertEqual(report["counts"]["repo_target_loaded_labels"], 0)
        self.assertEqual(report["counts"]["repo_target_missing_install"], 0)
        self.assertEqual(report["counts"]["repo_target_unloaded"], 1)
        self.assertEqual(report["counts"]["errors"], 1)

    def test_required_repo_target_reports_missing_source_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            label = "com.neo.brain_canonical_memory_sync"
            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", root / "LaunchAgents"),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [root / "repo-launchd"]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
                patch.object(
                    MODULE,
                    "list_automations",
                    return_value=[SimpleNamespace(id="brain_canonical_memory_sync", status="active")],
                ),
            ):
                report = MODULE.audit_launchd_jobs()

        target_kinds = {
            issue["kind"] for issue in report["issues"] if issue["label"] == label
        }
        self.assertIn("local_launchd_repo_target_missing_source", target_kinds)
        self.assertIn("local_launchd_repo_target_not_installed", target_kinds)
        self.assertIn("local_launchd_repo_target_not_loaded", target_kinds)

    def test_required_repo_target_start_interval_drift_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            label = "com.neo.codex_workspace_execution"
            args = [MODULE.VENv_PYTHON, "/opt/aiclone/codex_runner.py"]
            _write_plist(
                local_agents / f"{label}.plist",
                label=label,
                program_args=args,
                RunAtLoad=True,
                StartInterval=300,
            )
            _write_plist(
                repo_launchd / f"{label}.plist",
                label=label,
                program_args=args,
                RunAtLoad=True,
                StartInterval=60,
            )
            loaded = {
                label: {
                    "pid": None,
                    "last_exit_status": "0",
                    "label": label,
                    "observed_via": ["launchctl_print"],
                }
            }

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot(loaded=loaded)),
                patch.object(
                    MODULE,
                    "list_automations",
                    return_value=[SimpleNamespace(id="codex_workspace_execution", status="active")],
                ),
            ):
                report = MODULE.audit_launchd_jobs()

        drift = next(
            issue for issue in report["issues"] if issue["kind"] == "local_launchd_installed_plist_drift"
        )
        self.assertEqual(drift["severity"], "error")
        self.assertEqual(drift["drift_fields"], ["StartInterval"])
        self.assertTrue(drift["repo_managed_target"])
        self.assertEqual(report["counts"]["repo_target_installed_labels"], 1)
        self.assertEqual(report["counts"]["repo_target_loaded_labels"], 1)
        self.assertEqual(report["counts"]["errors"], 1)

    def test_parse_launchctl_print_reads_services_and_enablement(self) -> None:
        output = """
        services = {
            0 0 com.neo.codex_memory_sync
            38580 -15 com.neo.email_codex_bridge
        }
        disabled services = {
            "com.neo.codex_memory_sync" => enabled
            "com.neo.email_codex_bridge" => disabled
        }
        """

        loaded, disabled = MODULE._parse_launchctl_print(output)

        self.assertEqual(set(loaded), {"com.neo.codex_memory_sync", "com.neo.email_codex_bridge"})
        self.assertIsNone(loaded["com.neo.codex_memory_sync"]["pid"])
        self.assertEqual(loaded["com.neo.email_codex_bridge"]["last_exit_status"], "-15")
        self.assertEqual(
            disabled,
            {"com.neo.codex_memory_sync": False, "com.neo.email_codex_bridge": True},
        )

    def test_launchctl_snapshot_uses_domain_print_when_list_omits_job(self) -> None:
        domain_output = """
        services = {
            1365 - com.neo.watchtranscripts
        }
        disabled services = {
            "com.neo.watchtranscripts" => disabled
        }
        """
        with patch.object(
            MODULE,
            "_run_launchctl_read",
            side_effect=[
                (True, "PID Status Label\n", None),
                (True, domain_output, None),
            ],
        ):
            snapshot = MODULE._launchctl_snapshot()

        self.assertIn("com.neo.watchtranscripts", snapshot["loaded"])
        self.assertEqual(snapshot["loaded"]["com.neo.watchtranscripts"]["observed_via"], ["launchctl_print"])
        self.assertTrue(snapshot["disabled"]["com.neo.watchtranscripts"])

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
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
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
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot()),
                patch.object(MODULE, "list_automations", return_value=[]),
            ):
                report = MODULE.audit_launchd_jobs()

        kinds = {issue["kind"] for issue in report["issues"]}
        self.assertIn("local_launchd_installed_plist_drift", kinds)

    def test_audit_flags_installed_job_that_is_disabled_and_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            script = workspace / "scripts/run_codex_memory_sync.py"
            script.parent.mkdir(parents=True)
            script.write_text("pass\n", encoding="utf-8")
            label = "com.neo.codex_memory_sync"
            _write_plist(
                local_agents / f"{label}.plist",
                label=label,
                program_args=[MODULE.VENv_PYTHON, str(script)],
            )

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "WORKSPACE_ROOT", workspace),
                patch.object(
                    MODULE,
                    "_launchctl_snapshot",
                    return_value=_snapshot(disabled={label: True}),
                ),
                patch.object(MODULE, "list_automations", return_value=[SimpleNamespace(id="codex_memory_sync")]),
            ):
                report = MODULE.audit_launchd_jobs()

        kinds = {issue["kind"] for issue in report["issues"]}
        self.assertIn("local_launchd_job_disabled", kinds)
        self.assertIn("local_launchd_installed_not_loaded", kinds)
        self.assertEqual(report["enablement"][label], "disabled")

    def test_audit_finds_print_only_loaded_job_without_installed_plist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            local_agents = root / "LaunchAgents"
            repo_launchd = root / "repo-launchd"
            script = workspace / "scripts/watch_transcripts.py"
            script.parent.mkdir(parents=True)
            script.write_text("pass\n", encoding="utf-8")
            label = "com.neo.watchtranscripts"
            _write_plist(
                repo_launchd / f"{label}.plist",
                label=label,
                program_args=[MODULE.VENv_PYTHON, str(script)],
            )
            domain_output = f"""
            services = {{
                1365 - {label}
            }}
            disabled services = {{
                \"{label}\" => disabled
            }}
            """

            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", local_agents),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [repo_launchd]),
                patch.object(MODULE, "WORKSPACE_ROOT", workspace),
                patch.object(
                    MODULE,
                    "_run_launchctl_read",
                    side_effect=[
                        (True, "PID Status Label\n", None),
                        (True, domain_output, None),
                    ],
                ),
                patch.object(MODULE, "list_automations", return_value=[SimpleNamespace(id="watchtranscripts")]),
            ):
                report = MODULE.audit_launchd_jobs()

        kinds = {issue["kind"] for issue in report["issues"]}
        self.assertIn("local_launchd_loaded_without_installed_plist", kinds)
        self.assertIn("local_launchd_job_disabled", kinds)
        self.assertEqual(report["counts"]["loaded_labels"], 1)

    def test_audit_reports_unavailable_launchctl_state_instead_of_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(MODULE, "LOCAL_LAUNCH_AGENTS", root / "LaunchAgents"),
                patch.object(MODULE, "REPO_LAUNCHD_DIRS", [root / "repo-launchd"]),
                patch.object(MODULE, "_launchctl_snapshot", return_value=_snapshot(available=False, domain_available=False)),
                patch.object(MODULE, "list_automations", return_value=[]),
            ):
                report = MODULE.audit_launchd_jobs()

        self.assertIn("local_launchd_state_unavailable", {issue["kind"] for issue in report["issues"]})
        self.assertEqual(report["counts"]["warnings"], 1)

    def test_no_mirror_reports_that_mirroring_was_skipped(self) -> None:
        report = {
            "issues": [],
            "counts": {"issues": 0, "errors": 0, "warnings": 0},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "audit.json"
            with (
                patch.object(sys, "argv", ["audit_launchd_jobs.py", "--no-mirror", "--report-path", str(report_path)]),
                patch.object(MODULE, "audit_launchd_jobs", return_value=report),
                patch.object(MODULE, "_mirror") as mirror,
            ):
                return_code = MODULE.main()

            saved = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(return_code, 0)
        self.assertFalse(saved["mirrored"])
        mirror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
