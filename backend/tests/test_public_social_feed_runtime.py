from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
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


REQUIRED_SOURCE_RUNTIME_PATHS = {
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
DEPLOYMENT_FILE_MAPPINGS = {
    "scripts/runtime_http.py": "backend/scripts/runtime_http.py",
    **{
        path: f"backend/{path}"
        for path in REQUIRED_SOURCE_RUNTIME_PATHS
        if path.startswith("scripts/personal-brand/")
    },
}


def test_public_checkout_contains_the_safe_feed_runtime() -> None:
    manifest = json.loads((PUBLIC_ROOT / "release" / "public_source_manifest.json").read_text(encoding="utf-8"))
    mappings = manifest.get("file_mappings") or {}
    assert {path: mappings.get(path) for path in DEPLOYMENT_FILE_MAPPINGS} == DEPLOYMENT_FILE_MAPPINGS

    projected_tree = (PUBLIC_ROOT / ".public-release" / "receipt.json").is_file()
    required = (
        {"scripts/runtime_paths.py", *DEPLOYMENT_FILE_MAPPINGS.values()}
        if projected_tree
        else {"scripts/runtime_http.py", *REQUIRED_SOURCE_RUNTIME_PATHS}
    )
    missing = sorted(path for path in required if not (PUBLIC_ROOT / path).is_file())
    assert missing == []


def test_missing_refresh_entrypoint_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        missing_script = Path(temp_dir) / "missing" / "refresh_social_feed.py"
        with patch.object(refresh_module, "SCRIPT_PATH", missing_script), pytest.raises(FileNotFoundError):
            refresh_module._run_command(skip_fetch=False, sources="safe")


def test_public_strict_refresh_rejects_empty_feed_before_any_snapshot_write() -> None:
    with patch.object(
        snapshot_module,
        "_runtime_snapshot_payload",
        return_value=None,
    ), patch.object(
        snapshot_module.workspace_snapshot_service,
        "refresh_persisted_source_grounding_state",
    ) as refresh_grounding, patch.object(snapshot_module, "_persist_snapshot") as persist:
        with pytest.raises(RuntimeError, match="did not produce a usable feed"):
            snapshot_module.workspace_snapshot_service.refresh_persisted_social_feed_state(
                require_usable_feed=True,
                require_durable=True,
            )

    refresh_grounding.assert_not_called()
    persist.assert_not_called()


def test_public_refresh_state_cannot_succeed_after_persistence_failure() -> None:
    idle_state = {
        "running": False,
        "state": "idle",
        "run_id": None,
        "queued_at": None,
        "last_run": None,
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    with patch.dict(refresh_module._state, idle_state, clear=True), patch.object(
        refresh_module,
        "_run_command",
    ), patch.object(
        refresh_module,
        "_persist_workspace_snapshots",
        side_effect=refresh_module.SocialFeedPersistenceError("bounded persistence failure"),
    ):
        queued = refresh_module.social_feed_refresh_service.queue_refresh()
        with pytest.raises(refresh_module.SocialFeedPersistenceError):
            refresh_module.social_feed_refresh_service.run_refresh(
                skip_fetch=True,
                sources="safe",
                run_id=str(queued["run_id"]),
            )
        status = refresh_module.social_feed_refresh_service.get_status()

    assert status["state"] == "failed"
    assert status["running"] is False
    assert status["last_run"] is None
    assert status["completed_at"] >= status["started_at"]


def test_public_background_refresh_contains_an_already_recorded_failure() -> None:
    idle_state = {
        "running": False,
        "state": "idle",
        "run_id": None,
        "queued_at": None,
        "last_run": None,
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    with patch.dict(refresh_module._state, idle_state, clear=True), patch.object(
        refresh_module,
        "_run_command",
        side_effect=RuntimeError("bounded background failure"),
    ), patch.object(refresh_module, "_persist_workspace_snapshots") as persist:
        queued = refresh_module.social_feed_refresh_service.queue_refresh()
        refresh_module.social_feed_refresh_service.run_refresh_background(
            str(queued["run_id"]),
            skip_fetch=True,
            sources="safe",
        )
        status = refresh_module.social_feed_refresh_service.get_status()

    persist.assert_not_called()
    assert status["state"] == "failed"
    assert status["running"] is False
    assert status["last_run"] is None
    assert status["completed_at"] >= status["started_at"]


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
    with tempfile.TemporaryDirectory() as temp_dir:
        runtime_root = Path(temp_dir) / "public"
        source_root = runtime_root / "workspaces" / "linkedin-content-os"
        private_root = Path(temp_dir) / "runtime" / "state"
        generated_root = private_root / "workspaces" / "feezie-os"
        generated_root.mkdir(parents=True)
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
        with patch.object(snapshot_module, "ROOT", runtime_root), patch.object(
            snapshot_module,
            "_discover_linkedin_root",
            return_value=source_root,
        ), patch.object(
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
    script_path = PUBLIC_ROOT / "backend" / "scripts" / "personal-brand" / "refresh_social_feed.py"
    if not script_path.is_file():
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


def _materialize_backend_service_root(service_root: Path) -> None:
    shutil.copytree(
        BACKEND_ROOT,
        service_root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    if (service_root / "scripts" / "personal-brand" / "refresh_social_feed.py").is_file():
        return
    for source_relative, target_relative in DEPLOYMENT_FILE_MAPPINGS.items():
        target = service_root / Path(target_relative).relative_to("backend")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PUBLIC_ROOT / source_relative, target)


def test_backend_only_service_root_runs_safe_feed_and_reaction_builders_without_owner_workspace(
    tmp_path: Path,
) -> None:
    service_root = tmp_path / "backend-service"
    state_root = tmp_path / "private-state"
    _materialize_backend_service_root(service_root)

    plan_root = state_root / "workspaces" / "feezie-os" / "plans"
    plan_root.mkdir(parents=True)
    (plan_root / "social_feed.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-08-21T12:00:00+00:00",
                "workspace": "linkedin-content-os",
                "strategy_mode": "production",
                "items": [
                    {
                        "id": "rss__public-safe-runtime",
                        "platform": "rss",
                        "source_type": "article",
                        "source_class": "short_form",
                        "unit_kind": "full_post",
                        "response_modes": ["comment", "post"],
                        "source_lane": "market_signal",
                        "capture_method": "saved_signal",
                        "title": "Visible decision gates improve execution clarity",
                        "author": "Public Runtime Fixture",
                        "source_url": "https://example.com/public-safe-runtime",
                        "published_at": "2026-08-21T11:30:00+00:00",
                        "captured_at": "2026-08-21T12:00:00+00:00",
                        "summary": "Visible decision gates help operators coordinate work without guessing.",
                        "standout_lines": ["Explicit ownership makes the next authorized action easier to see."],
                        "engagement": {"likes": 0, "comments": 0, "shares": 0},
                        "ranking": {"total": 80.0},
                        "lenses": ["ops-pm"],
                        "comment_draft": "Visible ownership is the part that makes this useful in practice.",
                        "repost_draft": "A decision gate works only when the next owner can see it.",
                        "lens_variants": {
                            "ops-pm": {
                                "comment": "Visible ownership is the part that makes this useful in practice.",
                                "repost": "A decision gate works only when the next owner can see it.",
                            }
                        },
                        "why_it_matters": "Synthetic public-safe deployment evidence.",
                        "core_claim": "Visible decision gates improve execution clarity.",
                        "supporting_claims": ["Explicit ownership makes the next authorized action easier to see."],
                        "topic_tags": ["operations", "leadership"],
                        "source_metadata": {"extraction_method": "saved_signal"},
                        "belief_assessment": {"stance": "translate", "role_safety": "safe"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    probe = """
import json
from pathlib import Path

from app.services import social_feed_refresh as refresh
from app.services import workspace_snapshot_service as snapshots

service_root = Path.cwd().resolve()
assert refresh.ROOT == service_root
assert refresh.SCRIPT_PATH == service_root / "scripts" / "personal-brand" / "refresh_social_feed.py"
assert refresh.SCRIPT_PATH.is_file()
assert not (service_root / "workspaces" / "linkedin-content-os").exists()

refresh._run_command(skip_fetch=True, sources="safe")
social_feed = snapshots._build_social_feed_payload()
reaction_queue = snapshots._build_reaction_queue_payload()
assert social_feed is not None
assert snapshots._snapshot_is_usable(snapshots.SNAPSHOT_SOCIAL_FEED, social_feed)
assert reaction_queue is not None
assert snapshots._snapshot_is_usable(snapshots.SNAPSHOT_REACTION_QUEUE, reaction_queue)
print(json.dumps({"feed_items": len(social_feed["items"]), "reaction_queue_ready": True}))
"""
    environment = os.environ.copy()
    environment.update(
        {
            "AI_CLONE_ROOT": str(service_root),
            "AI_CLONE_STATE_ROOT": str(state_root),
            "PYTHONPATH": str(service_root),
        }
    )
    for name in ("DATABASE_URL", "CONTROL_PLANE_SERVICE_TOKEN", "AI_CLONE_SECRETS_ROOT"):
        environment.pop(name, None)
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=service_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout.strip().splitlines()[-1])
    assert receipt == {"feed_items": 1, "reaction_queue_ready": True}
