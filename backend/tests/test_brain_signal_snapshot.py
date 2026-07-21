from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models import (
    BrainSignal,
    BrainSignalCreateRequest,
    BrainSignalSnapshotChunkRequest,
    BrainSignalSnapshotCommitRequest,
    BrainSignalSnapshotRequest,
    BrainWorkspaceSnapshotSyncRequest,
)
from app.services import brain_signal_service


brain_routes = importlib.import_module("app.routes.brain")


def _signal(signal_id: str, summary: str) -> BrainSignal:
    now = datetime.now(timezone.utc)
    return BrainSignal(
        id=signal_id,
        source_kind="test",
        source_ref=signal_id,
        raw_summary=summary,
        created_at=now,
        updated_at=now,
    )


class BrainSignalSnapshotTests(unittest.TestCase):
    def test_snapshot_validation_requires_full_matching_count(self) -> None:
        with self.assertRaises(ValidationError):
            BrainSignalSnapshotRequest(
                generated_at="2026-07-20T12:00:00Z",
                count=2,
                signals=[_signal("signal-1", "One signal")],
            )

    def test_railway_reads_prefer_persisted_snapshot_over_packaged_file(self) -> None:
        persisted_signal = _signal("persisted", "Persisted Postgres signal")
        file_signal = _signal("file", "Packaged filesystem signal")
        persisted = {
            "schema_version": "brain_signals/v1",
            "generated_at": "2026-07-20T12:00:00Z",
            "source": "codex_local_runner",
            "count": 1,
            "signals": [persisted_signal.model_dump(mode="json")],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            signals_path.write_text(json.dumps(file_signal.model_dump(mode="json")) + "\n", encoding="utf-8")
            with (
                patch.object(brain_signal_service, "SIGNALS_PATH", signals_path),
                patch.object(brain_signal_service, "get_snapshot_payload", return_value=persisted),
            ):
                signals = brain_signal_service.list_signals()

        self.assertEqual([signal.id for signal in signals], ["persisted"])

    def test_local_signal_read_modify_write_is_locked_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"

            def create(index: int) -> None:
                brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="concurrency-test",
                        source_ref=f"source-{index}",
                        raw_summary=f"Concurrent signal {index}",
                    )
                )

            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path):
                with ThreadPoolExecutor(max_workers=8) as executor:
                    list(executor.map(create, range(40)))
                snapshot = brain_signal_service.build_local_brain_signal_snapshot()
                lines = [line for line in signals_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(snapshot["count"], 40)
        self.assertEqual(len(lines), 40)
        self.assertEqual(len({json.loads(line)["id"] for line in lines}), 40)

    def test_authenticated_snapshot_route_uses_monotonic_workspace_storage(self) -> None:
        signal = _signal("signal-1", "Mirrored local signal")
        payload = BrainSignalSnapshotRequest(
            generated_at="2026-07-20T12:00:00Z",
            count=1,
            signals=[signal],
        )
        stored = {"id": "brain-snapshot-1", "updated_at": "2026-07-20T12:01:00Z"}
        with patch.object(brain_routes, "upsert_snapshot_monotonic", return_value=(stored, True)) as upsert:
            response = brain_routes.publish_brain_signal_snapshot(payload)

        self.assertTrue(response["stored"])
        self.assertEqual(response["snapshot_id"], "brain-snapshot-1")
        self.assertEqual(upsert.call_args.args[:2], ("shared_ops", "brain_signals"))
        self.assertEqual(upsert.call_args.args[2]["signals"][0]["id"], "signal-1")

    def test_workspace_snapshot_sync_accepts_only_explicit_brain_read_models(self) -> None:
        payload = BrainWorkspaceSnapshotSyncRequest(
            generated_at="2026-07-20T12:00:00Z",
            source_assets={"schema_version": "source_assets/v1", "items": []},
            long_form_routes={"schema_version": "long_form_routes/v1", "route_counts": {}},
        )
        stored = {"id": "workspace-snapshot", "updated_at": "2026-07-20T12:01:00Z"}
        with patch.object(brain_routes, "upsert_snapshot_monotonic", return_value=(stored, True)) as upsert:
            response = brain_routes.publish_brain_workspace_snapshots(payload)

        self.assertTrue(response["stored"])
        self.assertEqual(set(response["snapshots"]), {"source_assets", "long_form_routes"})
        self.assertEqual(upsert.call_count, 2)
        self.assertEqual(
            {call.args[1] for call in upsert.call_args_list},
            {"brain_source_assets_preview", "brain_long_form_routes_summary"},
        )

    def test_workspace_snapshot_sync_rejects_db_owned_persona_summary(self) -> None:
        with self.assertRaises(ValidationError):
            BrainWorkspaceSnapshotSyncRequest(
                generated_at="2026-07-20T12:00:00Z",
                persona_review_summary={"counts": {"brain_pending_review": 4}},
            )

    def test_chunk_manifest_commit_and_persisted_read_reconstruct_full_snapshot(self) -> None:
        snapshot_id = str(uuid4())
        signals = [_signal("signal-1", "First"), _signal("signal-2", "Second")]
        chunks = [
            BrainSignalSnapshotChunkRequest(
                snapshot_id=snapshot_id,
                generated_at="2026-07-20T12:00:00Z",
                chunk_index=index,
                chunk_count=2,
                total_count=2,
                signals=[signal],
            ).model_dump(mode="json")
            for index, signal in enumerate(signals)
        ]
        persisted = {
            brain_routes._brain_signal_chunk_type(snapshot_id, index): chunk
            for index, chunk in enumerate(chunks)
        }
        commit = BrainSignalSnapshotCommitRequest(
            snapshot_id=snapshot_id,
            generated_at="2026-07-20T12:00:00Z",
            chunk_count=2,
            total_count=2,
        )

        def store_manifest(_workspace, _snapshot_type, payload, **_kwargs):
            return ({"id": "manifest-row", "updated_at": "2026-07-20T12:01:00Z", "payload": payload}, True)

        with (
            patch.object(brain_routes, "list_snapshot_payloads", return_value=persisted),
            patch.object(brain_routes, "upsert_snapshot_monotonic", side_effect=store_manifest) as upsert,
            patch.object(brain_routes, "delete_snapshot_types") as delete,
        ):
            response = brain_routes.commit_brain_signal_snapshot(commit)

        self.assertTrue(response["stored"])
        self.assertEqual(response["count"], 2)
        delete.assert_not_called()
        manifest = upsert.call_args.args[2]
        self.assertEqual(manifest["schema_version"], "brain_signals_manifest/v1")
        self.assertEqual(len(manifest["chunks"]), 2)

        with (
            patch.object(brain_signal_service, "get_snapshot_payload", return_value=manifest),
            patch.object(brain_signal_service, "list_snapshot_payloads", return_value=persisted),
        ):
            reconstructed = brain_signal_service.list_signals()
        self.assertEqual({signal.id for signal in reconstructed}, {"signal-1", "signal-2"})

    def test_chunk_commit_rejects_missing_or_mismatched_chunk(self) -> None:
        snapshot_id = str(uuid4())
        commit = BrainSignalSnapshotCommitRequest(
            snapshot_id=snapshot_id,
            generated_at="2026-07-20T12:00:00Z",
            chunk_count=1,
            total_count=1,
        )
        with patch.object(brain_routes, "list_snapshot_payloads", return_value={}):
            with self.assertRaisesRegex(Exception, "missing"):
                brain_routes.commit_brain_signal_snapshot(commit)

    def test_malformed_snapshot_timestamp_is_a_validation_error_not_server_error(self) -> None:
        app = FastAPI()
        app.include_router(brain_routes.router)
        client = TestClient(app)

        response = client.post(
            "/api/brain/signals/snapshot",
            json={
                "generated_at": "not-a-timestamp",
                "count": 0,
                "signals": [],
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
