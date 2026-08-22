from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


PUBLIC_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PUBLIC_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import social_feed_refresh as refresh_module  # noqa: E402
from app.services import social_source_fetch_service as fetch_module  # noqa: E402
from app.services import workspace_snapshot_service as snapshot_module  # noqa: E402


REQUIRED_RUNTIME_PATHS = {
    "scripts/runtime_http.py",
    "scripts/runtime_paths.py",
    "scripts/personal-brand/build_social_feed.py",
    "scripts/personal-brand/fetch_reddit_signals.py",
    "scripts/personal-brand/fetch_rss_signals.py",
    "scripts/personal-brand/generate_linkedin_reaction_queue.py",
    "scripts/personal-brand/linkedin_idea_qualification.py",
    "scripts/personal-brand/linkedin_strategy_utils.py",
    "scripts/personal-brand/refresh_social_feed.py",
    "scripts/personal-brand/sync_market_signal_archive.py",
}


def test_public_checkout_contains_the_safe_feed_runtime() -> None:
    missing = sorted(path for path in REQUIRED_RUNTIME_PATHS if not (PUBLIC_ROOT / path).is_file())
    assert missing == []


def test_missing_refresh_entrypoint_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        missing_script = Path(temp_dir) / "missing" / "refresh_social_feed.py"
        with patch.object(refresh_module, "SCRIPT_PATH", missing_script), pytest.raises(FileNotFoundError):
            refresh_module._run_command(skip_fetch=False, sources="safe")


def test_privacy_reduced_checkout_uses_the_public_safe_watchlist() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        missing_workspace = root / "checkout" / "workspaces" / "linkedin-content-os"
        state_root = root / "state" / "workspaces" / "feezie-os"
        with patch.object(
            fetch_module,
            "discover_linkedin_workspace_root",
            return_value=missing_workspace,
        ), patch.object(fetch_module, "workspace_state_root", return_value=state_root):
            watchlist = fetch_module.ensure_watchlist()

    assert watchlist == fetch_module.DEFAULT_WATCHLIST
    assert not missing_workspace.exists()


def test_snapshot_builder_reads_the_generated_feed_not_the_absent_workspace_tree() -> None:
    source_root = Path("/public/workspaces/linkedin-content-os")
    private_root = Path("/runtime/state")
    generated_root = private_root / "workspaces" / "feezie-os"
    payload = {
        "generated_at": "2026-08-22T02:49:05+00:00",
        "items": [
            {
                "lens_variants": {"current-role": {}},
                "source_class": "short_form",
                "unit_kind": "full_post",
                "response_modes": ["comment"],
            }
        ],
    }
    with patch.object(snapshot_module, "_discover_linkedin_root", return_value=source_root), patch.object(
        snapshot_module,
        "PRIVATE_STATE_ROOT",
        private_root,
    ), patch.object(
        snapshot_module,
        "build_social_feed_runtime_payload",
        return_value=payload,
    ) as build_feed:
        result = snapshot_module._build_social_feed_payload()

    assert result == payload
    build_feed.assert_called_once_with(generated_root, source_workspace_root=source_root)


def test_public_refresh_fetchers_materialize_ephemeral_feed_inputs() -> None:
    script_path = PUBLIC_ROOT / "scripts" / "personal-brand" / "refresh_social_feed.py"
    spec = importlib.util.spec_from_file_location("public_refresh_social_feed", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with patch.object(module, "run_script") as run_script:
        module.run_fetcher("rss", compact_output=True)

    run_script.assert_called_once_with(
        module.SCRIPTS_ROOT / "fetch_rss_signals.py",
        "--include-legacy-workspace-projection",
        compact_output=True,
    )
