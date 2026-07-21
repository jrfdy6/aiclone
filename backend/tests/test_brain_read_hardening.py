from __future__ import annotations

import asyncio
import importlib
import sys
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

brain_routes = importlib.import_module("app.routes.brain")
brief_routes = importlib.import_module("app.routes.briefs")
persona_routes = importlib.import_module("app.routes.persona")
from app.models import PersonaDelta  # noqa: E402


class BrainReadHardeningTests(unittest.TestCase):
    def test_persona_delta_detail_rejects_malformed_uuid_before_storage(self) -> None:
        app = FastAPI()
        app.include_router(persona_routes.router)
        with patch.object(persona_routes.persona_delta_service, "get_delta") as get_delta:
            response = TestClient(app).get("/api/persona/deltas/not-a-uuid")

        self.assertEqual(response.status_code, 422)
        get_delta.assert_not_called()

    def test_control_plane_read_runs_off_event_loop(self) -> None:
        event_loop_thread_id: int | None = None
        service_thread_id: int | None = None

        def slow_build() -> dict[str, object]:
            nonlocal service_thread_id
            service_thread_id = threading.get_ident()
            time.sleep(0.08)
            return {"summary": {"automation_count": 1}}

        async def exercise() -> tuple[dict[str, object], int]:
            nonlocal event_loop_thread_id
            event_loop_thread_id = threading.get_ident()
            finished = asyncio.Event()
            ticks = 0

            async def invoke() -> dict[str, object]:
                try:
                    return await brain_routes.get_brain_control_plane(Response())
                finally:
                    finished.set()

            async def heartbeat() -> None:
                nonlocal ticks
                while not finished.is_set():
                    ticks += 1
                    await asyncio.sleep(0.005)

            result, _ = await asyncio.gather(invoke(), heartbeat())
            return result, ticks

        with patch.object(brain_routes, "build_brain_control_plane", side_effect=slow_build):
            payload, ticks = asyncio.run(exercise())

        self.assertEqual((payload.get("summary") or {}).get("automation_count"), 1)
        self.assertIsNotNone(service_thread_id)
        self.assertNotEqual(service_thread_id, event_loop_thread_id)
        self.assertGreaterEqual(ticks, 5)

    def test_control_plane_read_has_server_deadline(self) -> None:
        release = threading.Event()

        def blocked_build() -> dict[str, object]:
            release.wait(timeout=1)
            return {}

        async def exercise() -> tuple[HTTPException, float]:
            started_at = time.monotonic()
            try:
                await brain_routes.get_brain_control_plane(Response())
            except HTTPException as exc:
                elapsed = time.monotonic() - started_at
                release.set()
                return exc, elapsed
            raise AssertionError("expected the bounded read to time out")

        with patch.object(brain_routes, "build_brain_control_plane", side_effect=blocked_build), patch.object(
            brain_routes,
            "BRAIN_READ_TIMEOUT_SECONDS",
            0.02,
        ):
            raised, elapsed = asyncio.run(exercise())

        self.assertEqual(raised.status_code, 504)
        self.assertLess(elapsed, 0.25)

    def test_youtube_get_uses_persisted_read_api(self) -> None:
        persisted = {"data_mode": "persisted", "channels": [], "counts": {"channels": 0, "videos": 0}}
        with patch.object(
            brain_routes,
            "build_persisted_youtube_watchlist_payload",
            return_value=persisted,
        ) as persisted_read:
            payload = asyncio.run(brain_routes.get_youtube_watchlist())

        persisted_read.assert_called_once_with()
        self.assertEqual(payload.get("data_mode"), "persisted")

    def test_brief_and_persona_reads_are_bounded_and_offloaded(self) -> None:
        event_loop_thread_id: int | None = None
        brief_thread_id: int | None = None
        persona_thread_id: int | None = None

        def brief_read(*, limit: int):
            nonlocal brief_thread_id
            brief_thread_id = threading.get_ident()
            self.assertEqual(limit, 100)
            return []

        def persona_read(*, limit: int, status: str | None):
            nonlocal persona_thread_id
            persona_thread_id = threading.get_ident()
            self.assertEqual(limit, 100)
            self.assertIsNone(status)
            return []

        async def exercise() -> None:
            nonlocal event_loop_thread_id
            event_loop_thread_id = threading.get_ident()
            await asyncio.gather(
                brief_routes.list_daily_briefs(Response(), limit=100_000),
                persona_routes.list_persona_deltas(Response(), limit=100_000),
            )

        with patch.object(brief_routes.daily_brief_service, "list_daily_briefs", side_effect=brief_read), patch.object(
            persona_routes.persona_delta_service,
            "list_deltas",
            side_effect=persona_read,
        ):
            asyncio.run(exercise())

        self.assertIsNotNone(brief_thread_id)
        self.assertIsNotNone(persona_thread_id)
        self.assertNotEqual(brief_thread_id, event_loop_thread_id)
        self.assertNotEqual(persona_thread_id, event_loop_thread_id)

    def test_persona_delta_detail_is_annotated_offloaded_and_returns_404(self) -> None:
        now = datetime.now(timezone.utc)
        delta = PersonaDelta(
            id="delta-outside-first-page",
            persona_target="feeze.core",
            trait="A durable operator belief",
            status="draft",
            metadata={},
            created_at=now,
        )
        event_loop_thread_id: int | None = None
        service_thread_id: int | None = None

        def read_delta(delta_id: str):
            nonlocal service_thread_id
            service_thread_id = threading.get_ident()
            self.assertEqual(delta_id, delta.id)
            return delta

        async def exercise():
            nonlocal event_loop_thread_id
            event_loop_thread_id = threading.get_ident()
            response = Response()
            result = await persona_routes.get_persona_delta(delta.id, response)
            return result, response

        with patch.object(persona_routes.persona_delta_service, "get_delta", side_effect=read_delta):
            result, response = asyncio.run(exercise())

        self.assertEqual(result.id, delta.id)
        self.assertEqual((result.metadata or {}).get("queue_stage"), "brain_pending_review")
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        self.assertIsNotNone(service_thread_id)
        self.assertNotEqual(service_thread_id, event_loop_thread_id)

        with patch.object(persona_routes.persona_delta_service, "get_delta", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(persona_routes.get_persona_delta("missing", Response()))
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
