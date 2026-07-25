from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.models import BrainSignal, BrainSignalCreateRequest, BrainSignalRouteRequest, BrainYouTubeWatchlistIngestRequest
from app.services.brain_local_action_queue_service import build_brain_local_action


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
RUNNABLE_GATE_FIELDS = {
    "execution_gate_decision": "AUTO_EXECUTE",
    "execution_gate_approval_state": "not_required",
    "execution_gate_intent_hash": "sha256:" + ("0" * 64),
    "execution_gate_authorization_current": True,
}


def _load_runner():
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    path = SCRIPTS_ROOT / "runners" / "run_codex_workspace_execution.py"
    spec = importlib.util.spec_from_file_location("brain_local_action_runner_test_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runner from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrainLocalActionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = _load_runner()

    def test_queue_selector_accepts_brain_local_action_without_codex_packet(self) -> None:
        entry = {
            **RUNNABLE_GATE_FIELDS,
            "card_id": "brain-card-1",
            "workspace_key": "shared_ops",
            "execution_mode": "brain_local_action",
            "target_agent": "Brain Local Action",
            "execution_state": "queued",
            "executor_status": "queued",
            "last_transition_at": "2026-07-20T12:00:00Z",
        }

        selected = self.runner._select_entry([entry], card_id=None, workspace_key="shared_ops")

        self.assertEqual(selected, entry)

    def test_deterministic_signal_dispatch_mirrors_snapshot_and_never_invokes_codex(self) -> None:
        request = BrainSignalCreateRequest(
            source_kind="manual",
            source_ref="runner-test",
            raw_summary="The runner should execute this without model inference.",
        )
        action = build_brain_local_action(
            "signal_create",
            {"signal": request.model_dump(mode="json", exclude_none=True)},
        )
        now = datetime.now(timezone.utc)
        signal = BrainSignal(
            id="signal-runner-test",
            source_kind=request.source_kind,
            source_ref=request.source_ref,
            raw_summary=request.raw_summary,
            created_at=now,
            updated_at=now,
        )

        with (
            mock.patch("app.services.brain_signal_service.create_signal", return_value=signal) as create_signal,
            mock.patch.object(
                self.runner,
                "_mirror_local_brain_signal_snapshot",
                return_value=(
                    {"count": 1, "generated_at": "2026-07-20T12:00:00Z"},
                    {"snapshot_id": "snapshot-1", "disposition": "stored"},
                ),
            ) as mirror,
            mock.patch.object(self.runner, "_run_codex") as run_codex,
        ):
            result = self.runner._run_brain_local_action(
                action,
                card_id="brain-card-1",
                api_url="https://control.example.test",
            )

        create_signal.assert_called_once()
        mirror.assert_called_once_with("https://control.example.test")
        run_codex.assert_not_called()
        self.assertEqual(result["status"], "done")
        self.assertIn("without invoking Codex", result["summary"])
        self.assertEqual(result["brain_local_action_metadata"]["signal_snapshot"]["snapshot_id"], "snapshot-1")

    def test_youtube_dispatch_mirrors_watchlist_and_brain_workspace_snapshots(self) -> None:
        request = BrainYouTubeWatchlistIngestRequest(url="https://www.youtube.com/watch?v=local-runner")
        action = build_brain_local_action(
            "youtube_watchlist_ingest",
            {"request": request.model_dump(mode="json", exclude_none=True)},
        )
        refreshed = {
            "source_assets": {"generated_at": "2026-07-20T12:00:00Z", "items": []},
            "persona_review_summary": {"generated_at": "2026-07-20T12:00:00Z", "counts": {}},
        }
        youtube_payload = {
            "schema_version": "youtube_watchlist/v1",
            "generated_at": "2026-07-20T12:00:00Z",
            "workspace": "linkedin-content-os",
            "data_mode": "live_refresh",
            "channels": [],
            "runtime": {},
            "auto_ingest": {},
            "counts": {},
            "pending_transcript_backfill": [],
        }
        with (
            mock.patch(
                "app.services.youtube_watchlist_service.ingest_youtube_watchlist_video",
                return_value={"asset_id": "youtube-asset", "source_path": "knowledge/ingestions/source.md"},
            ) as ingest,
            mock.patch(
                "app.services.youtube_watchlist_service.build_youtube_watchlist_payload",
                return_value=youtube_payload,
            ),
            mock.patch(
                "app.services.workspace_snapshot_service.workspace_snapshot_service.refresh_persisted_linkedin_os_state",
                return_value=refreshed,
            ),
            mock.patch.object(
                self.runner,
                "_mirror_youtube_watchlist_snapshot",
                return_value={"snapshot_id": "youtube-snapshot", "disposition": "stored"},
            ) as mirror_youtube,
            mock.patch.object(
                self.runner,
                "_mirror_brain_workspace_snapshots",
                return_value={
                    "snapshots": {
                        "source_assets": {"stored": True, "snapshot_id": "source-snapshot"},
                        "persona_review_summary": {"stored": True, "snapshot_id": "persona-snapshot"},
                    }
                },
            ) as mirror_workspace,
            mock.patch.object(self.runner, "_run_codex") as run_codex,
        ):
            result = self.runner._run_brain_local_action(
                action,
                card_id="youtube-card",
                api_url="https://control.example.test",
            )

        ingest.assert_called_once()
        self.assertFalse(ingest.call_args.kwargs["run_refresh"])
        mirror_youtube.assert_called_once_with("https://control.example.test", youtube_payload)
        mirror_workspace.assert_called_once_with("https://control.example.test", refreshed)
        run_codex.assert_not_called()
        metadata = result["brain_local_action_metadata"]
        self.assertEqual(metadata["youtube_watchlist_snapshot"]["snapshot_id"], "youtube-snapshot")
        self.assertEqual(metadata["workspace_snapshots"]["source_assets"]["snapshot_id"], "source-snapshot")

    def test_large_full_signal_snapshot_is_split_into_bounded_manifest_chunks(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        signals = [
            {
                "id": f"signal-{index}",
                "source_kind": "large-test",
                "raw_summary": "x" * 5_000,
                "created_at": now,
                "updated_at": now,
            }
            for index in range(500)
        ]
        snapshot = {
            "schema_version": "brain_signals/v1",
            "generated_at": "2026-07-20T12:00:00Z",
            "source": "codex_local_runner",
            "count": len(signals),
            "signals": signals,
        }

        chunks, manifest = self.runner._build_brain_signal_snapshot_chunks(snapshot)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(manifest["total_count"], 500)
        self.assertEqual(manifest["chunk_count"], len(chunks))
        self.assertEqual(sum(len(chunk["signals"]) for chunk in chunks), 500)
        self.assertTrue(all(len(json.dumps(chunk).encode("utf-8")) <= 448 * 1024 for chunk in chunks))

    def test_compact_workspace_previews_are_bounded_and_exclude_persona(self) -> None:
        huge = "z" * 250_000
        refreshed = {
            "source_assets": {
                "workspace": "linkedin-content-os",
                "counts": {f"count-{index}": huge for index in range(100)},
                "items": [{"asset_id": str(index), "title": huge, "source_url": huge} for index in range(100)],
            },
            "content_reservoir": {"counts": {"total": 10_000}, "items": [{"body": huge}]},
            "long_form_routes": {"route_counts": {f"route-{index}": huge for index in range(100)}},
            "persona_review_summary": {"counts": {"brain_pending_review": 99}, "items": [{"notes": huge}]},
        }

        compacted = self.runner._compact_brain_workspace_snapshots(refreshed)

        self.assertNotIn("persona_review_summary", compacted)
        self.assertLess(len(json.dumps(compacted).encode("utf-8")), 256 * 1024)
        self.assertEqual(len(compacted["source_assets"]["items"]), 12)

    def test_stale_signed_signal_route_is_rejected_before_any_effect(self) -> None:
        now = datetime.now(timezone.utc)
        signed = BrainSignal(
            id="stale-signal",
            source_kind="manual",
            raw_summary="Original summary",
            created_at=now,
            updated_at=now,
        )
        changed = signed.model_copy(update={"raw_summary": "Changed after queue", "updated_at": now})
        route = BrainSignalRouteRequest(
            route="canonical_memory",
            summary="Promote the original signal.",
            canonical_memory_targets=["learnings"],
        )
        action = build_brain_local_action(
            "signal_route",
            {
                "signal_id": signed.id,
                "signal": signed.model_dump(mode="json"),
                "route": route.model_dump(mode="json", exclude_none=True),
            },
        )
        with (
            mock.patch("app.services.brain_signal_service.get_local_signal", return_value=changed),
            mock.patch.object(self.runner, "_execute_canonical_memory_route") as local_effect,
            mock.patch.object(self.runner, "_fetch_json") as remote_effect,
            mock.patch("app.services.brain_signal_service.route_signal") as route_signal,
        ):
            with self.assertRaisesRegex(RuntimeError, "Stale Brain signal route"):
                self.runner._run_brain_local_action(action, card_id="route-card", api_url="https://control.example.test")

        local_effect.assert_not_called()
        remote_effect.assert_not_called()
        route_signal.assert_not_called()

    def test_same_route_card_retry_skips_effect_and_resumes_snapshot_mirror(self) -> None:
        now = datetime.now(timezone.utc)
        signed = BrainSignal(
            id="retry-signal",
            source_kind="manual",
            raw_summary="Original summary",
            created_at=now,
            updated_at=now,
        )
        route = BrainSignalRouteRequest(
            route="canonical_memory",
            summary="Promote the original signal.",
            canonical_memory_targets=["learnings"],
        )
        applied = signed.model_copy(
            update={
                "review_status": "routed",
                "route_decision": {
                    "latest": {
                        "route": "canonical_memory",
                        "brain_local_action_card_id": "route-card",
                    }
                },
            }
        )
        action = build_brain_local_action(
            "signal_route",
            {
                "signal_id": signed.id,
                "signal": signed.model_dump(mode="json"),
                "route": route.model_dump(mode="json", exclude_none=True),
            },
        )
        with (
            mock.patch("app.services.brain_signal_service.get_local_signal", return_value=applied),
            mock.patch.object(self.runner, "_execute_canonical_memory_route") as local_effect,
            mock.patch("app.services.brain_signal_service.route_signal") as route_signal,
            mock.patch.object(
                self.runner,
                "_mirror_local_brain_signal_snapshot",
                return_value=(
                    {"count": 1, "generated_at": "2026-07-20T12:00:00Z"},
                    {"snapshot_id": "snapshot-retry", "disposition": "stored"},
                ),
            ) as mirror,
        ):
            result = self.runner._run_brain_local_action(
                action,
                card_id="route-card",
                api_url="https://control.example.test",
            )

        local_effect.assert_not_called()
        route_signal.assert_not_called()
        mirror.assert_called_once()
        self.assertEqual(result["status"], "done")

    def test_canonical_and_workspace_local_effects_are_idempotent(self) -> None:
        signal = {
            "id": "effect-signal",
            "source_kind": "manual",
            "source_workspace_key": "shared_ops",
            "raw_summary": "A durable local effect.",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)

            with mock.patch.object(self.runner, "MEMORY_ROOT", temp_root / "state" / "memory"):
                first = self.runner._execute_canonical_memory_route(
                    signal=signal,
                    route={
                        "route": "canonical_memory",
                        "workspace_key": "shared_ops",
                        "summary": "Keep this once.",
                        "canonical_memory_targets": ["persistent_state", "learnings"],
                    },
                    card_id="canonical-card",
                )
                second = self.runner._execute_canonical_memory_route(
                    signal=signal,
                    route={
                        "route": "canonical_memory",
                        "workspace_key": "shared_ops",
                        "summary": "Keep this once.",
                        "canonical_memory_targets": ["persistent_state", "learnings"],
                    },
                    card_id="canonical-card",
                )

            for item in first["canonical_memory"]["targets"]:
                text = Path(item["path"]).read_text(encoding="utf-8")
                self.assertEqual(text.count("brain-local-action:canonical-card"), 1)
            self.assertTrue(all(item["reused"] for item in second["canonical_memory"]["targets"]))

            project_root = temp_root / "project"
            (project_root / "workspaces" / "shared-ops").mkdir(parents=True)
            with mock.patch.object(self.runner, "WORKSPACE_ROOT", project_root):
                workspace_first = self.runner._execute_workspace_local_route(
                    signal=signal,
                    route={"route": "workspace_local", "workspace_key": "shared_ops", "summary": "Keep local."},
                    card_id="workspace-card",
                )
                workspace_second = self.runner._execute_workspace_local_route(
                    signal=signal,
                    route={"route": "workspace_local", "workspace_key": "shared_ops", "summary": "Keep local."},
                    card_id="workspace-card",
                )
            artifact = Path(workspace_first["workspace_local"]["artifact_path"])
            self.assertTrue(artifact.exists())
            self.assertTrue(workspace_second["workspace_local"]["reused"])

    def test_empty_scheduled_poll_does_not_write_ledger_or_mirror_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                api_url="https://aiclone-production-32dc.up.railway.app",
                mode="api",
                workspace_key=None,
                card_id=None,
                limit=50,
                model="gpt-test",
                reasoning_effort="high",
                timeout_seconds=30,
                worker_id="test-worker",
                output_root=temp_dir,
                dry_run=False,
            )
            with (
                mock.patch.object(self.runner, "parse_args", return_value=args),
                mock.patch.object(self.runner, "_optional_backend_imports", return_value={}),
                mock.patch.object(
                    self.runner,
                    "_reconcile_pending_results",
                    return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
                ),
                mock.patch.object(
                    self.runner,
                    "_recover_stale_claims",
                    return_value={"requeued_count": 0, "surfaced_count": 0},
                ),
                mock.patch.object(self.runner, "_load_host_action_automation_cards", return_value=[]),
                mock.patch.object(self.runner, "_load_queue", return_value=("api", [])),
                mock.patch.object(self.runner, "_append_jsonl") as append_ledger,
                mock.patch.object(self.runner, "mirror_runs") as mirror_runs,
            ):
                return_code = self.runner.main()

        self.assertEqual(return_code, 0)
        append_ledger.assert_not_called()
        mirror_runs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
