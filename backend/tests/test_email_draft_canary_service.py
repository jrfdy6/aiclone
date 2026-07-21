from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import email_draft_canary_service  # noqa: E402


class EmailDraftCanaryServiceTests(unittest.TestCase):
    def test_canary_report_passes_when_provider_queue_and_registry_are_healthy(self) -> None:
        with patch.object(
            email_draft_canary_service,
            "gmail_connection_status",
            return_value={
                "configured": True,
                "connected": True,
                "dependencies_ready": True,
                "drafts_enabled": True,
                "send_enabled": False,
                "account_email": "neo@example.com",
                "token_present": True,
                "refreshable": True,
                "scopes": ["gmail.readonly", "gmail.compose"],
                "error": None,
            },
        ), patch.object(
            email_draft_canary_service,
            "list_codex_jobs",
            return_value=[
                {
                    "id": "job-complete",
                    "workspace_slug": "email-drafts",
                    "status": "completed",
                    "created_at": "2026-04-26T05:00:00+00:00",
                    "completed_at": "2026-04-26T05:02:00+00:00",
                }
            ],
        ), patch.object(
            email_draft_canary_service,
            "list_automations",
            return_value=[
                SimpleNamespace(
                    id="email_codex_bridge",
                    status="active",
                    source="local_launchd_registry",
                    runtime="launchd",
                    metrics={
                        "workspace_slug": "email-drafts",
                        "launch_agent": "automations/launchd/com.neo.email_codex_bridge.plist",
                    },
                )
            ],
        ):
            payload = email_draft_canary_service.build_email_draft_canary_report(include_samples=False)

        self.assertEqual(payload.get("schema_version"), "email_draft_canary_report/v1")
        self.assertEqual((payload.get("summary") or {}).get("status"), "pass")
        self.assertEqual(((payload.get("queue") or {}).get("workspace_slug")), "email-drafts")
        self.assertEqual(((payload.get("queue") or {}).get("stale_job_count")), 0)
        self.assertEqual(((payload.get("bridge_registry") or {}).get("status")), "active")

    def test_canary_report_fails_for_disconnected_provider_and_stale_jobs(self) -> None:
        with patch.object(
            email_draft_canary_service,
            "gmail_connection_status",
            return_value={
                "configured": True,
                "connected": False,
                "dependencies_ready": True,
                "drafts_enabled": False,
                "send_enabled": False,
                "account_email": "neo@example.com",
                "token_present": True,
                "refreshable": True,
                "scopes": ["gmail.readonly"],
                "error": "missing compose scope",
            },
        ), patch.object(
            email_draft_canary_service,
            "list_codex_jobs",
            return_value=[
                {
                    "id": "job-stale",
                    "workspace_slug": "email-drafts",
                    "status": "pending",
                    "created_at": "2026-04-26T00:00:00+00:00",
                },
                {
                    "id": "job-failed",
                    "workspace_slug": "email-drafts",
                    "status": "failed",
                    "created_at": "2026-04-26T05:00:00+00:00",
                    "failed_at": "2026-04-26T05:03:00+00:00",
                    "error_message": "worker unavailable",
                },
            ],
        ), patch.object(
            email_draft_canary_service,
            "list_automations",
            return_value=[],
        ), patch.dict(
            "os.environ",
            {
                "EMAIL_DRAFT_CANARY_STALE_PENDING_MINUTES": "5",
                "EMAIL_DRAFT_CANARY_STALE_RUNNING_MINUTES": "10",
            },
            clear=False,
        ):
            payload = email_draft_canary_service.build_email_draft_canary_report()

        self.assertEqual((payload.get("summary") or {}).get("status"), "fail")
        checks = {item.get("name"): item for item in (payload.get("checks") or [])}
        self.assertEqual((checks.get("gmail_provider") or {}).get("status"), "fail")
        self.assertEqual((checks.get("email_draft_queue") or {}).get("status"), "fail")
        self.assertEqual((checks.get("email_codex_bridge_registry") or {}).get("status"), "fail")
        self.assertEqual(((payload.get("queue") or {}).get("stale_pending_count")), 1)


if __name__ == "__main__":
    unittest.main()
