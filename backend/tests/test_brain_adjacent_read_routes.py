from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import OpenBrainHealth, OpenBrainSearchRequest, OpenBrainSearchResponse  # noqa: E402
from app.models.automations import AutomationMismatchReport, AutomationRunMirrorRequest  # noqa: E402
from app.routes import automations, open_brain  # noqa: E402


class BrainAdjacentReadRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_automation_index_is_read_only_and_does_not_block_event_loop(self) -> None:
        def slow_list_runs(*, limit: int):
            time.sleep(0.15)
            return []

        report = AutomationMismatchReport(source_of_truth="codex_launchd_registry+codex_run_ledger")
        with (
            patch.object(automations.automation_run_service, "sync_codex_run_ledger") as sync_ledger,
            patch.object(automations.automation_run_service, "list_runs", side_effect=slow_list_runs),
            patch.object(automations, "list_automations", return_value=[]),
            patch.object(automations.automation_mismatch_service, "build_mismatch_report", return_value=report),
        ):
            started = time.monotonic()
            route_task = asyncio.create_task(automations.automations_index())
            await asyncio.sleep(0)
            await asyncio.sleep(0.01)
            loop_delay = time.monotonic() - started
            payload = await route_task

        self.assertLess(loop_delay, 0.1)
        sync_ledger.assert_not_called()
        self.assertEqual(payload["ledger_sync_count"], 0)
        self.assertFalse(payload["ledger_sync_performed"])

    async def test_automation_read_routes_never_mirror_local_ledger(self) -> None:
        report = AutomationMismatchReport(source_of_truth="codex_launchd_registry+codex_run_ledger")
        with (
            patch.object(automations.automation_run_service, "sync_codex_run_ledger") as sync_ledger,
            patch.object(automations.automation_run_service, "list_runs", return_value=[]),
            patch.object(automations, "list_automations", return_value=[]),
            patch.object(automations.automation_mismatch_service, "build_mismatch_report", return_value=report),
        ):
            runs_payload = await automations.automation_runs_index(limit=25)
            mismatch_payload = await automations.automation_mismatches_index()

        sync_ledger.assert_not_called()
        self.assertEqual(runs_payload["count"], 0)
        self.assertEqual(mismatch_payload, report)

    async def test_explicit_automation_mirror_write_is_preserved_and_offloaded(self) -> None:
        request = AutomationRunMirrorRequest(runs=[])

        def slow_upsert(_runs):
            time.sleep(0.15)
            return 0

        with patch.object(automations.automation_run_service, "upsert_runs", side_effect=slow_upsert) as upsert:
            started = time.monotonic()
            route_task = asyncio.create_task(automations.automation_runs_mirror(request))
            await asyncio.sleep(0)
            await asyncio.sleep(0.01)
            loop_delay = time.monotonic() - started
            response = await route_task

        self.assertLess(loop_delay, 0.1)
        upsert.assert_called_once_with([])
        self.assertTrue(response.success)
        self.assertEqual(response.count, 0)

    async def test_explicit_automation_mirror_returns_503_when_storage_fails(self) -> None:
        request = AutomationRunMirrorRequest(runs=[])
        with patch.object(
            automations.automation_run_service,
            "upsert_runs",
            side_effect=automations.automation_run_service.AutomationRunMirrorError("database unavailable"),
        ):
            with self.assertRaises(HTTPException) as raised:
                await automations.automation_runs_mirror(request)

        self.assertEqual(raised.exception.status_code, 503)

    async def test_open_brain_search_is_offloaded_and_preserves_response(self) -> None:
        request = OpenBrainSearchRequest(query="durable memory", top_k=3)
        expected = OpenBrainSearchResponse(query="durable memory", results=[])

        def slow_search(_payload):
            time.sleep(0.15)
            return expected

        with patch.object(open_brain.open_brain_service, "search_memory", side_effect=slow_search):
            started = time.monotonic()
            route_task = asyncio.create_task(open_brain.search_open_brain(request))
            await asyncio.sleep(0)
            await asyncio.sleep(0.01)
            loop_delay = time.monotonic() - started
            response = await route_task

        self.assertLess(loop_delay, 0.1)
        self.assertEqual(response, expected)

    async def test_open_brain_health_is_offloaded(self) -> None:
        expected = OpenBrainHealth(embedder_dimension=1024)

        def slow_health():
            time.sleep(0.15)
            return expected

        with patch.object(open_brain.open_brain_service, "fetch_health", side_effect=slow_health):
            started = time.monotonic()
            route_task = asyncio.create_task(open_brain.open_brain_health())
            await asyncio.sleep(0)
            await asyncio.sleep(0.01)
            loop_delay = time.monotonic() - started
            response = await route_task

        self.assertLess(loop_delay, 0.1)
        self.assertEqual(response, expected)


if __name__ == "__main__":
    unittest.main()
