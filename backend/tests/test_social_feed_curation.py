from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import json

import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_feed_builder_service import build_feed


class SocialFeedCurationTest(unittest.TestCase):
    def test_uses_tracked_archive_when_runtime_signal_files_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            archive_root = workspace_root / "research" / "market_signal_archive"
            archive_root.mkdir(parents=True, exist_ok=True)

            record = {
                "id": "2026-03-28__rss__archived-signal",
                "kind": "market_signal",
                "title": "Archived enrollment signal",
                "source_path": "research/market_signals/2026-03-28__rss__archived-signal.md",
                "source_platform": "rss",
                "source_type": "article",
                "source_url": "https://example.com/archived-signal",
                "author": "Higher Ed Source",
                "priority_lane": "admissions",
                "created_at": "2026-03-28T00:00:00+00:00",
                "published_at": "2026-03-28T00:00:00+00:00",
                "summary": "Archived research still informs the feed.",
                "why_it_matters": "Durable research should survive git cleanup.",
                "headline_candidates": ["Archived enrollment signal"],
                "supporting_claims": ["Archived research still informs the feed."],
                "topics": ["Durable research"],
                "trust_notes": [],
                "body_text": "# Archived enrollment signal\n\nArchived research still informs the feed.",
                "source_metadata": {"extraction_method": "archive_backfill"},
                "engagement": {},
                "archive_month": "2026-03",
                "archive_manifest_path": "research/market_signal_archive/2026-03.jsonl",
                "archive_markdown_path": "research/market_signal_archive/2026-03.md",
            }
            (archive_root / "2026-03.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            (archive_root / "2026-03.md").write_text(
                "# Market Signal Archive - 2026-03\n\n## Archived enrollment signal\n\nArchived research still informs the feed.\n",
                encoding="utf-8",
            )

            feed = build_feed(workspace_root=workspace_root)
            items = feed.get("items") or []

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].get("title"), "Archived enrollment signal")
            self.assertEqual(items[0].get("platform"), "rss")

    def test_applies_curation_rules_and_platform_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            research_root = workspace_root / "research" / "market_signals"
            research_root.mkdir(parents=True, exist_ok=True)
            (workspace_root / "research" / "watchlists.yaml").write_text(
                """topics:
  - ai implementation in education
filters:
  prioritize:
    - operator language
  avoid:
    - generic hustle content
curation:
  min_total_score: 0
  target_feed_size: 2
  platform_limits:
    linkedin: 1
    rss: 1
  platform_boosts:
    linkedin: 10
    rss: 5
  lane_boosts:
    ai: 12
  keyword_boosts:
    - phrase: agent orchestration
      weight: 10
  blocked_phrases:
    - quit your job
""",
                encoding="utf-8",
            )

            (research_root / "2026-03-28__linkedin__a.md").write_text(
                """---
kind: market_signal
title: Agent orchestration for school teams
created_at: '2026-03-28T00:00:00+00:00'
source_platform: linkedin
source_type: post
source_url: https://example.com/linkedin-a
author: Operator One
priority_lane: ai
summary: Agent orchestration improves workflow clarity for school teams.
why_it_matters: Operator language for AI implementation in education.
---

# Agent orchestration for school teams

Agent orchestration improves workflow clarity for school teams.
""",
                encoding="utf-8",
            )
            (research_root / "2026-03-28__linkedin__b.md").write_text(
                """---
kind: market_signal
title: Another LinkedIn AI signal
created_at: '2026-03-28T00:00:00+00:00'
source_platform: linkedin
source_type: post
source_url: https://example.com/linkedin-b
author: Operator Two
priority_lane: ai
summary: Operator language for AI implementation in education.
why_it_matters: Useful but should be capped by platform limit.
---

# Another LinkedIn AI signal

Operator language for AI implementation in education.
""",
                encoding="utf-8",
            )
            (research_root / "2026-03-28__rss__real.md").write_text(
                """---
kind: market_signal
title: Enrollment teams need workflow clarity
created_at: '2026-03-28T00:00:00+00:00'
source_platform: rss
source_type: article
source_url: https://example.com/rss
author: Higher Ed Source
priority_lane: admissions
summary: Workflow clarity shapes enrollment outcomes and family trust.
why_it_matters: Operator language for admissions leadership.
---

# Enrollment teams need workflow clarity

Workflow clarity shapes enrollment outcomes and family trust.
""",
                encoding="utf-8",
            )
            (research_root / "2026-03-28__reddit__blocked.md").write_text(
                """---
kind: market_signal
title: Quit your job and let AI do the work
created_at: '2026-03-28T00:00:00+00:00'
source_platform: reddit
source_type: post
source_url: https://example.com/reddit
author: Hype Poster
priority_lane: ai
summary: Quit your job and let AI do the work.
why_it_matters: This should be blocked by curation.
---

# Quit your job and let AI do the work

Quit your job and let AI do the work.
""",
                encoding="utf-8",
            )

            feed = build_feed(workspace_root=workspace_root)
            items = feed.get("items") or []
            titles = [item.get("title") for item in items]

            self.assertEqual(len(items), 2)
            self.assertIn("Agent orchestration for school teams", titles)
            self.assertIn("Enrollment teams need workflow clarity", titles)
            self.assertNotIn("Quit your job and let AI do the work", titles)
            self.assertEqual(sum(1 for item in items if item.get("platform") == "linkedin"), 1)
            self.assertEqual(feed.get("curation_summary", {}).get("selected_platform_mix", {}).get("linkedin"), 1)
            self.assertGreaterEqual(feed.get("curation_summary", {}).get("rejected_count", 0), 1)


if __name__ == "__main__":
    unittest.main()
