from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "personal-brand" / "refresh_social_feed.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("refresh_social_feed_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RefreshSocialFeedPipelineTests(unittest.TestCase):
    def test_default_refresh_appends_market_archive_and_brain_flow(self) -> None:
        module = load_script_module()
        calls: list[list[str]] = []

        def fake_run(command: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(module, "sync_watchlist_auto_ingest") as sync_watchlist, patch.object(
            module.subprocess,
            "run",
            side_effect=fake_run,
        ), patch.object(
            sys,
            "argv",
            ["refresh_social_feed.py", "--skip-brain-context-sync"],
        ):
            module.main()

        sync_watchlist.assert_called_once_with(run_refresh=False)
        script_names = [Path(command[1]).name for command in calls]
        self.assertEqual(
            script_names,
            [
                "fetch_reddit_signals.py",
                "fetch_rss_signals.py",
                "sync_market_signal_archive.py",
                "build_social_feed.py",
                "refresh_linkedin_strategy.py",
                "source_intelligence_register_existing.py",
                "brain_signal_intake.py",
                "bank_autonomous_posts.py",
            ],
        )

    def test_brain_context_sync_is_optional_by_default(self) -> None:
        module = load_script_module()
        calls: list[list[str]] = []

        def fake_run(command: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if Path(command[1]).name == "brain_canonical_memory_sync.py":
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(module, "sync_watchlist_auto_ingest"), patch.object(
            module.subprocess,
            "run",
            side_effect=fake_run,
        ), patch.object(
            sys,
            "argv",
            ["refresh_social_feed.py", "--skip-fetch"],
        ):
            module.main()

        script_names = [Path(command[1]).name for command in calls]
        self.assertIn("brain_canonical_memory_sync.py", script_names)
        self.assertIn("brain_signal_intake.py", script_names)
        self.assertEqual(script_names[-1], "bank_autonomous_posts.py")

    def test_skip_brain_flow_keeps_refresh_local(self) -> None:
        module = load_script_module()
        calls: list[list[str]] = []

        def fake_run(command: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(module, "sync_watchlist_auto_ingest") as sync_watchlist, patch.object(
            module.subprocess,
            "run",
            side_effect=fake_run,
        ), patch.object(
            sys,
            "argv",
            ["refresh_social_feed.py", "--skip-fetch", "--skip-brain-flow"],
        ):
            module.main()

        sync_watchlist.assert_not_called()
        script_names = [Path(command[1]).name for command in calls]
        self.assertEqual(
            script_names,
            [
                "sync_market_signal_archive.py",
                "build_social_feed.py",
                "refresh_linkedin_strategy.py",
                "bank_autonomous_posts.py",
            ],
        )

    def test_skip_content_bank_keeps_refresh_from_writing_terminal_event(self) -> None:
        module = load_script_module()
        calls: list[list[str]] = []

        def fake_run(command: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(module, "sync_watchlist_auto_ingest"), patch.object(
            module.subprocess,
            "run",
            side_effect=fake_run,
        ), patch.object(
            sys,
            "argv",
            ["refresh_social_feed.py", "--skip-fetch", "--skip-brain-flow", "--skip-content-bank"],
        ):
            module.main()

        script_names = [Path(command[1]).name for command in calls]
        self.assertNotIn("bank_autonomous_posts.py", script_names)


if __name__ == "__main__":
    unittest.main()
