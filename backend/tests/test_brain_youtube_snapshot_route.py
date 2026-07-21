from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import BrainYouTubeWatchlistSnapshotRequest  # noqa: E402


brain_routes = importlib.import_module("app.routes.brain")


class BrainYouTubeSnapshotRouteTests(unittest.TestCase):
    def test_local_runner_snapshot_is_persisted_for_read_only_brain_get(self) -> None:
        payload = BrainYouTubeWatchlistSnapshotRequest(
            generated_at="2026-07-20T12:00:00Z",
            channels=[{"name": "Operator channel", "videos": [{"title": "A video"}]}],
            counts={"channels": 1, "videos": 1},
        )
        stored = {"id": "snapshot-1", "updated_at": "2026-07-20T12:01:00Z"}
        with patch.object(brain_routes, "upsert_snapshot_monotonic", return_value=(stored, True)) as upsert:
            response = brain_routes.publish_youtube_watchlist_snapshot(payload)

        upsert.assert_called_once()
        call_args = upsert.call_args
        self.assertEqual(call_args.args[:2], ("linkedin-content-os", "youtube_watchlist"))
        self.assertEqual(call_args.args[2]["schema_version"], "youtube_watchlist/v1")
        self.assertEqual(response["snapshot_id"], "snapshot-1")
        self.assertEqual(response["video_count"], 1)

    def test_snapshot_route_fails_closed_when_storage_is_unavailable(self) -> None:
        payload = BrainYouTubeWatchlistSnapshotRequest(generated_at="2026-07-20T12:00:00Z")
        with patch.object(brain_routes, "upsert_snapshot_monotonic", return_value=(None, False)):
            with self.assertRaises(HTTPException) as raised:
                brain_routes.publish_youtube_watchlist_snapshot(payload)
        self.assertEqual(raised.exception.status_code, 503)

    def test_older_or_equal_snapshot_never_overwrites_newer_payload(self) -> None:
        payload = BrainYouTubeWatchlistSnapshotRequest(
            generated_at="2026-07-20T12:00:00Z",
            channels=[{"name": "Older channel state", "videos": []}],
        )
        current = {
            "id": "snapshot-newer",
            "updated_at": "2026-07-20T12:10:00Z",
            "payload": {"generated_at": "2026-07-20T12:05:00Z"},
        }
        with patch.object(brain_routes, "upsert_snapshot_monotonic", return_value=(current, False)) as upsert:
            response = brain_routes.publish_youtube_watchlist_snapshot(payload)

        self.assertFalse(response["stored"])
        self.assertEqual(response["disposition"], "stale_or_equal_ignored")
        self.assertEqual(response["snapshot_id"], "snapshot-newer")
        self.assertEqual(upsert.call_args.kwargs["generated_at"].isoformat(), "2026-07-20T12:00:00+00:00")

    def test_malformed_generated_at_returns_validation_error(self) -> None:
        app = FastAPI()
        app.include_router(brain_routes.router)
        response = TestClient(app).post(
            "/api/brain/youtube-watchlist/snapshot",
            json={"generated_at": "not-a-timestamp", "channels": []},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
