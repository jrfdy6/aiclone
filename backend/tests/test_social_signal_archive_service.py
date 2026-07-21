from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_signal_archive_service import sync_market_signal_archive_entry


class SocialSignalArchiveServiceTests(unittest.TestCase):
    def test_existing_archive_fields_are_preserved_on_resync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp) / "workspaces" / "linkedin-content-os"
            signals_root = workspace_root / "research" / "market_signals"
            archive_root = workspace_root / "research" / "market_signal_archive"
            signals_root.mkdir(parents=True, exist_ok=True)
            archive_root.mkdir(parents=True, exist_ok=True)

            signal_path = signals_root / "2026-04-03__rss__hard-fork__fixture.md"
            signal_path.write_text(
                """---
kind: market_signal
title: Fixture Signal
created_at: '2026-04-09T20:07:58.724924+00:00'
published_at: '2026-04-03T11:00:00+00:00'
source_platform: rss
source_type: article
source_url: https://example.com/signal
author: Fixture Author
priority_lane: ai
summary: Fixture summary
why_it_matters: Fixture relevance
supporting_claims:
  - Fixture supporting claim
topics:
  - ai
---

# Fixture Signal

Fixture body
""",
                encoding="utf-8",
            )

            first = sync_market_signal_archive_entry(signal_path, workspace_root)
            manifest_path = archive_root / "2026-04.jsonl"
            markdown_path = archive_root / "2026-04.md"
            manifest_before = manifest_path.read_text(encoding="utf-8")
            markdown_before = markdown_path.read_text(encoding="utf-8")

            signal_path.write_text(
                """---
kind: market_signal
title: Fixture Signal
created_at: '2026-04-09T22:08:24.392465+00:00'
published_at: '2026-04-03T11:00:00+00:00'
source_platform: rss
source_type: article
source_url: https://example.com/signal
author: Fixture Author
priority_lane: ai
summary: Fixture summary
why_it_matters: Fixture relevance
supporting_claims:
  - Fixture supporting claim
topics:
  - ai
---

# Fixture Signal

Fixture body
""",
                encoding="utf-8",
            )

            second = sync_market_signal_archive_entry(signal_path, workspace_root)

            self.assertEqual(second["created_at"], first["created_at"])
            self.assertEqual(second["archived_at"], first["archived_at"])
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), manifest_before)
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), markdown_before)


if __name__ == "__main__":
    unittest.main()
