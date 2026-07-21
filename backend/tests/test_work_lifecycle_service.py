from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import work_lifecycle_service  # noqa: E402


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class WorkLifecycleServiceTests(unittest.TestCase):
    def test_build_work_lifecycle_report_derives_stages_from_existing_state(self) -> None:
        signals = [
            SimpleNamespace(
                id="signal-new",
                source_workspace_key="shared_ops",
                review_status="new",
                route_decision={},
                updated_at=_utc("2026-04-25T20:00:00Z"),
                digest="New signal",
                raw_summary="New signal",
            ),
            SimpleNamespace(
                id="signal-reviewed",
                source_workspace_key="feezie-os",
                review_status="reviewed",
                route_decision={},
                updated_at=_utc("2026-04-25T20:10:00Z"),
                digest="Reviewed signal",
                raw_summary="Reviewed signal",
            ),
            SimpleNamespace(
                id="signal-ignored",
                source_workspace_key="shared_ops",
                review_status="ignored",
                route_decision={},
                updated_at=_utc("2026-04-25T20:20:00Z"),
                digest="Ignored signal",
                raw_summary="Ignored signal",
            ),
        ]
        cards = [
            SimpleNamespace(
                id="card-routed",
                title="Queued card",
                status="todo",
                updated_at=_utc("2026-04-25T20:30:00Z"),
                payload={"workspace_key": "shared_ops", "execution": {"state": "queued"}},
            ),
            SimpleNamespace(
                id="card-written",
                title="Review card",
                status="review",
                updated_at=_utc("2026-04-25T20:40:00Z"),
                payload={
                    "workspace_key": "shared_ops",
                    "execution": {"state": "review"},
                    "latest_execution_result": {"result_id": "result-1", "summary": "Done", "status": "done"},
                },
            ),
            SimpleNamespace(
                id="card-closed",
                title="Closed card",
                status="done",
                updated_at=_utc("2026-04-25T20:50:00Z"),
                payload={
                    "workspace_key": "shared_ops",
                    "execution": {"state": "closed"},
                    "latest_execution_result": {"result_id": "result-2", "summary": "Closed", "status": "done"},
                },
            ),
        ]
        standups = [
            SimpleNamespace(
                id="standup-prepared",
                workspace_key="shared_ops",
                status="prepared",
                source="standup_prep",
                payload={},
                created_at=_utc("2026-04-25T19:00:00Z"),
            ),
            SimpleNamespace(
                id="standup-completed",
                workspace_key="shared_ops",
                status="completed",
                source="standup_promotion",
                payload={"pm_updates": [{"title": "Follow up"}]},
                created_at=_utc("2026-04-25T19:10:00Z"),
            ),
        ]

        with patch.object(work_lifecycle_service, "list_signals", return_value=signals), patch.object(
            work_lifecycle_service, "list_cards", return_value=cards
        ), patch.object(work_lifecycle_service, "list_standups", return_value=standups):
            payload = work_lifecycle_service.build_work_lifecycle_report()

        self.assertEqual(payload.get("schema_version"), "work_lifecycle_report/v1")
        self.assertEqual(((payload.get("brain_signals") or {}).get("counts_by_stage") or {}).get("captured"), 1)
        self.assertEqual(((payload.get("brain_signals") or {}).get("counts_by_stage") or {}).get("promoted"), 1)
        self.assertEqual(((payload.get("brain_signals") or {}).get("counts_by_stage") or {}).get("closed"), 1)
        self.assertEqual(((payload.get("pm_cards") or {}).get("counts_by_stage") or {}).get("routed"), 1)
        self.assertEqual(((payload.get("pm_cards") or {}).get("counts_by_stage") or {}).get("written_back"), 1)
        self.assertEqual(((payload.get("pm_cards") or {}).get("counts_by_stage") or {}).get("closed"), 1)
        self.assertEqual(((payload.get("standups") or {}).get("counts_by_stage") or {}).get("promoted"), 1)
        self.assertEqual(((payload.get("standups") or {}).get("counts_by_stage") or {}).get("routed"), 1)
        self.assertEqual(((payload.get("execution_results") or {}).get("counts_by_stage") or {}).get("written_back"), 1)
        self.assertEqual(((payload.get("execution_results") or {}).get("counts_by_stage") or {}).get("closed"), 1)


if __name__ == "__main__":
    unittest.main()
