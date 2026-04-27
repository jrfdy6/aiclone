from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import gmail_inbox_service
from app.models import EmailMessage, EmailThread


CLIENT_PAYLOAD = {
    "installed": {
        "client_id": "test-client-id.apps.googleusercontent.com",
        "project_id": "openclawneo",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": "test-client-secret",
        "redirect_uris": ["http://localhost"],
    }
}

TOKEN_PAYLOAD = {
    "token": "ya29.test-token",
    "refresh_token": "1//test-refresh-token",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "test-client-id.apps.googleusercontent.com",
    "client_secret": "test-client-secret",
    "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
}


@unittest.skipIf(gmail_inbox_service.Credentials is None, "google-auth dependencies not installed")
class GmailInboxServiceTests(unittest.TestCase):
    def test_connection_status_reads_client_and_token_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GOOGLE_GMAIL_OAUTH_CLIENT_JSON": json.dumps(CLIENT_PAYLOAD),
                "GOOGLE_GMAIL_OAUTH_TOKEN_JSON": json.dumps(TOKEN_PAYLOAD),
            },
            clear=False,
        ):
            status = gmail_inbox_service.gmail_connection_status()

        self.assertTrue(status["configured"])
        self.assertTrue(status["token_present"])
        self.assertTrue(status["refreshable"])
        self.assertTrue(status["connected"])
        self.assertIsNone(status["error"])

    def test_save_gmail_draft_builds_create_payload(self) -> None:
        now = datetime.now(timezone.utc)
        thread = EmailThread(
            id="thread-1",
            provider="gmail",
            provider_thread_id="gmail-thread-1",
            subject="Family intake question",
            from_address="parent.intake@example.org",
            to_addresses=["neo512235+fusion@gmail.com"],
            messages=[
                EmailMessage(
                    id="msg-1",
                    direction="inbound",
                    from_address="parent.intake@example.org",
                    to_addresses=["neo512235+fusion@gmail.com"],
                    cc_addresses=[],
                    subject="Family intake question",
                    body_text="Can you explain your intake process?",
                    internet_message_id="<msg-1@example.org>",
                    references_header="<older@example.org>",
                    received_at=now,
                )
            ],
            draft_subject="Re: Family intake question",
            draft_body="Happy to explain the intake process.\n\nThanks,\nJohnnie Fields",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )

        service_mock = Mock()
        drafts_mock = service_mock.users.return_value.drafts.return_value
        drafts_mock.create.return_value.execute.return_value = {
            "id": "draft-123",
            "message": {"id": "gmail-msg-123", "threadId": "gmail-thread-1"},
        }

        with patch.dict(
            os.environ,
            {
                "GOOGLE_GMAIL_ENABLE_DRAFTS": "1",
                "GOOGLE_GMAIL_OAUTH_CLIENT_JSON": json.dumps(CLIENT_PAYLOAD),
                "GOOGLE_GMAIL_OAUTH_TOKEN_JSON": json.dumps(TOKEN_PAYLOAD),
            },
            clear=False,
        ), patch.object(gmail_inbox_service, "_load_credentials", return_value=Mock()), patch.object(
            gmail_inbox_service,
            "build",
            return_value=service_mock,
        ):
            result = gmail_inbox_service.save_gmail_draft(thread)

        self.assertEqual(result["action"], "created")
        self.assertEqual(result["draft_id"], "draft-123")
        create_kwargs = drafts_mock.create.call_args.kwargs
        self.assertEqual(create_kwargs["userId"], "me")
        payload = create_kwargs["body"]["message"]
        self.assertEqual(payload["threadId"], "gmail-thread-1")
        raw = payload["raw"]
        padded = raw + ("=" * (-len(raw) % 4))
        decoded = gmail_inbox_service.base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        self.assertIn("Subject: Re: Family intake question", decoded)
        self.assertIn("In-Reply-To: <msg-1@example.org>", decoded)
        self.assertIn("References: <older@example.org> <msg-1@example.org>", decoded)
        self.assertIn("Happy to explain the intake process.", decoded)


if __name__ == "__main__":
    unittest.main()
