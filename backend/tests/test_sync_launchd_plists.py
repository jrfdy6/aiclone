from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ops" / "sync_launchd_plists.py"
SPEC = importlib.util.spec_from_file_location("sync_launchd_plists", MODULE_PATH)
assert SPEC and SPEC.loader
sync_launchd_plists = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_launchd_plists)


def test_bulk_load_requires_at_least_one_explicit_label() -> None:
    with (
        patch.object(sync_launchd_plists, "_copy_plist") as copy_plist,
        patch.object(sync_launchd_plists, "_run_launchctl") as run_launchctl,
        pytest.raises(ValueError, match="Refusing to load every repo launchd plist"),
    ):
        sync_launchd_plists.sync_plists(
            None,
            dry_run=False,
            load=True,
            archive_obsolete=False,
        )

    copy_plist.assert_not_called()
    run_launchctl.assert_not_called()


def test_no_load_may_sync_all_repo_plists_without_launchctl_mutations() -> None:
    with (
        patch.object(sync_launchd_plists, "_copy_plist") as copy_plist,
        patch.object(sync_launchd_plists, "_run_launchctl") as run_launchctl,
    ):
        result = sync_launchd_plists.sync_plists(
            None,
            dry_run=False,
            load=False,
            archive_obsolete=False,
        )

    assert result["load"] is False
    assert result["count"] > 1
    assert copy_plist.call_count == result["count"]
    run_launchctl.assert_not_called()


def test_load_rejects_partially_unmatched_label_sets() -> None:
    with (
        patch.object(sync_launchd_plists, "_copy_plist") as copy_plist,
        patch.object(sync_launchd_plists, "_run_launchctl") as run_launchctl,
        pytest.raises(ValueError, match="com.neo.typo_does_not_exist"),
    ):
        sync_launchd_plists.sync_plists(
            ["codex_memory_sync", "typo_does_not_exist"],
            dry_run=False,
            load=True,
            archive_obsolete=False,
        )

    copy_plist.assert_not_called()
    run_launchctl.assert_not_called()


def test_load_reenables_label_before_bootstrap() -> None:
    calls: list[list[str]] = []

    def fake_launchctl(args: list[str], *, dry_run: bool) -> tuple[int, str]:
        calls.append(args)
        return 0, "ok"

    with (
        patch.object(sync_launchd_plists, "_run_launchctl", side_effect=fake_launchctl),
        patch.object(sync_launchd_plists, "_copy_plist"),
    ):
        result = sync_launchd_plists.sync_plists(
            ["codex_memory_sync"],
            dry_run=False,
            load=True,
            archive_obsolete=False,
        )

    assert result["results"][0]["status"] == "ok"
    verbs = [call[0] for call in calls]
    assert verbs == ["bootout", "enable", "bootstrap"]
    assert calls[1][-1].endswith("/com.neo.codex_memory_sync")


def test_launchctl_runs_in_login_user_context() -> None:
    with (
        patch.object(sync_launchd_plists, "_uid", return_value=501),
        patch.object(sync_launchd_plists.subprocess, "run") as run,
    ):
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        run.return_value.stderr = ""

        assert sync_launchd_plists._run_launchctl(
            ["bootstrap", "gui/501", "/tmp/com.neo.example.plist"],
            dry_run=False,
        ) == (0, "ok")

    assert run.call_args.args[0] == [
        "launchctl",
        "asuser",
        "501",
        "launchctl",
        "bootstrap",
        "gui/501",
        "/tmp/com.neo.example.plist",
    ]
