from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402

email_route_module = importlib.import_module("app.routes.email_ops")


class EmailOpsCanaryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_email_canary_route_returns_no_store_payload(self) -> None:
        fake_payload = {
            "schema_version": "email_draft_canary_report/v1",
            "summary": {"status": "pass", "checks_run": 3},
            "queue": {"workspace_slug": "email-drafts", "stale_job_count": 0},
        }
        with patch.object(email_route_module, "build_email_draft_canary_report", return_value=fake_payload):
            response = self.client.get("/api/email/canary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload.get("schema_version"), "email_draft_canary_report/v1")
        self.assertEqual((payload.get("summary") or {}).get("status"), "pass")
        self.assertEqual((payload.get("queue") or {}).get("workspace_slug"), "email-drafts")

    def test_email_draft_lifecycle_route_returns_response_payload(self) -> None:
        fake_thread = {
            "id": "thread-1",
            "provider": "gmail",
            "provider_thread_id": "thread-1",
            "provider_labels": [],
            "workspace_key": "fusion-os",
            "lane": "primary",
            "status": "routed",
            "subject": "Thread",
            "from_address": "person@example.com",
            "from_name": None,
            "organization": None,
            "to_addresses": ["neo512235+fusion@gmail.com"],
            "alias_hint": None,
            "confidence_score": 0.92,
            "needs_human": False,
            "high_value": False,
            "high_risk": False,
            "sla_at_risk": False,
            "linked_opportunity_id": None,
            "summary": None,
            "excerpt": None,
            "routing_reasons": ["alias:fusion"],
            "messages": [],
            "draft_subject": None,
            "draft_body": None,
            "draft_type": None,
            "draft_mode": None,
            "draft_engine": None,
            "draft_source_mode": None,
            "draft_generated_at": None,
            "draft_job_id": None,
            "draft_audit": None,
            "draft_confidence": None,
            "provider_draft_id": None,
            "provider_draft_status": None,
            "provider_draft_saved_at": None,
            "provider_draft_error": None,
            "last_message_at": "2026-04-26T06:00:00+00:00",
            "manual_workspace_key": None,
            "manual_lane": None,
            "manual_notes": None,
            "last_route_source": "auto",
            "pm_card_id": None,
            "created_at": "2026-04-26T06:00:00+00:00",
            "updated_at": "2026-04-26T06:00:00+00:00",
        }
        with patch.object(
            email_route_module,
            "update_thread_draft_lifecycle",
            return_value=(fake_thread, "Local draft cleared."),
        ):
            response = self.client.post(
                "/api/email/threads/thread-1/draft/lifecycle",
                json={"action": "clear_local_draft"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("action"), "clear_local_draft")
        self.assertEqual(payload.get("message"), "Local draft cleared.")
        self.assertEqual((payload.get("thread") or {}).get("id"), "thread-1")


if __name__ == "__main__":
    unittest.main()
