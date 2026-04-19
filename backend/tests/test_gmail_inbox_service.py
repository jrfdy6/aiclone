from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import gmail_inbox_service


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


if __name__ == "__main__":
    unittest.main()
