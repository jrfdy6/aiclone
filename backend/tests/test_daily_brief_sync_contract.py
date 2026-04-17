from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services import daily_brief_service  # noqa: E402


class DailyBriefSyncContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_sync_daily_briefs_from_markdown_rejects_stale_latest_date(self) -> None:
        raw_markdown = """# Morning Daily Brief - 2026-04-15

### Highlights:
- Daily log input processing completed without errors.
"""

        with self.assertRaisesRegex(
            ValueError,
            "Latest brief date 2026-04-15 does not match expected 2026-04-16",
        ):
            daily_brief_service.sync_daily_briefs_from_markdown(
                raw_markdown,
                expected_latest_brief_date=date(2026, 4, 16),
            )

    def test_sync_daily_briefs_route_returns_400_for_stale_markdown(self) -> None:
        response = self.client.post(
            "/api/briefs/sync",
            json={
                "raw_markdown": "# Morning Daily Brief - 2026-04-15\n\n- stale brief\n",
                "expected_latest_brief_date": "2026-04-16",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Latest brief date 2026-04-15 does not match expected 2026-04-16", response.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
