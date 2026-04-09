from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

stub_builder = ModuleType("app.services.social_feed_builder_service")
stub_builder.discover_linkedin_workspace_root = lambda: Path("/tmp/linkedin-content-os")
sys.modules.setdefault("app.services.social_feed_builder_service", stub_builder)

from app.services import social_source_fetch_service


class SocialSourceFetchServiceTests(unittest.TestCase):
    def test_write_signal_preserves_existing_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp) / "workspaces" / "linkedin-content-os"
            signal_path = workspace_root / "research" / "market_signals" / "2026-04-03__rss__fixture__entry.md"
            signal_path.parent.mkdir(parents=True, exist_ok=True)

            initial_entry = {
                "kind": "market_signal",
                "title": "Fixture Entry",
                "created_at": "2026-04-09T20:07:58.724924+00:00",
                "published_at": "2026-04-03T11:00:00+00:00",
                "source_platform": "rss",
                "source_type": "article",
            }
            updated_entry = {**initial_entry, "created_at": "2026-04-09T22:08:24.392465+00:00"}

            with patch.object(social_source_fetch_service, "sync_market_signal_archive_entry", return_value={}):
                social_source_fetch_service._write_signal(signal_path, initial_entry, "# Fixture Entry\n\nBody")
                first = signal_path.read_text(encoding="utf-8")
                social_source_fetch_service._write_signal(signal_path, updated_entry, "# Fixture Entry\n\nBody")
                second = signal_path.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertIn("2026-04-09T20:07:58.724924+00:00", second)


if __name__ == "__main__":
    unittest.main()
