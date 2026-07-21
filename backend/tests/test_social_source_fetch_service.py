from __future__ import annotations

import sys
import tempfile
import unittest
import json
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
    def test_build_rss_entry_uses_article_preview_when_available(self) -> None:
        source = {
            "url": "https://www.oneusefulthing.org/feed",
            "label": "AI-native Ops (Substack)",
            "platform": "substack",
            "purpose": "AI workflow design, operator judgment, and education implementation signals",
            "priority_lane": "ai",
        }
        entry = {
            "title": "Claude Dispatch and the Power of Interfaces",
            "summary": "We often lack the tools for the job, even if the AI is capable enough",
            "link": "https://www.oneusefulthing.org/p/claude-dispatch-and-the-power-of",
            "published_at": "2026-03-31T22:34:37+00:00",
            "author": "AI-native Ops (Substack)",
            "guid": "https://www.oneusefulthing.org/p/claude-dispatch-and-the-power-of",
        }
        article_preview = {
            "title": "Claude Dispatch and the Power of Interfaces",
            "author": "Ethan Mollick",
            "text": (
                "We often lack the tools for the job, even if the AI is capable enough. "
                "Interfaces decide whether the capability actually reaches the operator in a usable form. "
                "The constraint is rarely raw intelligence alone."
            ),
        }

        signal, body, filename = social_source_fetch_service._build_rss_entry(
            source,
            entry,
            article_preview=article_preview,
        )

        self.assertEqual(signal["author"], "Ethan Mollick")
        self.assertEqual(signal["summary"], "We often lack the tools for the job, even if the AI is capable enough. Interfaces decide whether the capability actually reaches the operator in a usable form.")
        self.assertIn("Interfaces decide whether the capability actually reaches the operator in a usable form.", signal["raw_text"])
        self.assertIn("The constraint is rarely raw intelligence alone.", signal["supporting_claims"])
        self.assertEqual(signal["source_metadata"]["extraction_method"], "rss_feed+article_preview")
        self.assertIn("ai-native-ops-substack", filename)
        self.assertIn("claude-dispatch-and-the-power-of", filename)
        self.assertIn("Interfaces decide whether the capability actually reaches the operator in a usable form.", body)

    def test_backfill_article_signal_sources_restores_missing_archived_article(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp) / "workspaces" / "linkedin-content-os"
            archive_root = workspace_root / "research" / "market_signal_archive"
            archive_root.mkdir(parents=True, exist_ok=True)
            manifest = archive_root / "2026-03.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "id": "2026-03-12__rss__ai-native-ops-substack__https-www-oneusefulthing-org-p-the-shape-of-the-thing",
                        "kind": "market_signal",
                        "title": "The Shape of the Thing",
                        "source_path": "research/market_signals/2026-03-12__rss__ai-native-ops-substack__https-www-oneusefulthing-org-p-the-shape-of-the-thing.md",
                        "source_platform": "substack",
                        "source_type": "article",
                        "source_url": "https://www.oneusefulthing.org/p/the-shape-of-the-thing",
                        "author": "Ethan Mollick",
                        "priority_lane": "ai",
                        "role_alignment": "market_signal",
                        "created_at": "2026-04-09T22:08:23.819807+00:00",
                        "published_at": "2026-03-12T14:10:07+00:00",
                        "summary": "Where we are right now, and what likely happens next",
                        "why_it_matters": "AI workflow design, operator judgment, and education implementation signals",
                        "core_claim": "The Shape of the Thing",
                        "headline_candidates": ["The Shape of the Thing"],
                        "supporting_claims": ["Where we are right now, and what likely happens next"],
                        "topics": ["AI workflow design, operator judgment, and education implementation signals"],
                        "watchlist_matches": ["rss", "AI-native Ops (Substack)"],
                        "body_text": "# The Shape of the Thing\n\nWhere we are right now, and what likely happens next",
                        "source_metadata": {
                            "extraction_method": "rss_feed",
                            "feed_label": "AI-native Ops (Substack)",
                            "feed_url": "https://www.oneusefulthing.org/feed",
                        },
                        "engagement": {},
                        "archive_month": "2026-03",
                        "archive_manifest_path": "research/market_signal_archive/2026-03.jsonl",
                        "archive_markdown_path": "research/market_signal_archive/2026-03.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(
                social_source_fetch_service,
                "_article_preview_for_url",
                return_value={
                    "title": "The Shape of the Thing",
                    "author": "Ethan Mollick",
                    "text": (
                        "We are at the stage where AI systems are becoming easier to use in public, but the underlying shape is still changing. "
                        "What matters is whether operators can tell what has stabilized and what still needs translation."
                    ),
                },
            ), patch.object(social_source_fetch_service, "sync_market_signal_archive_entry", return_value={}):
                result = social_source_fetch_service.backfill_article_signal_sources(workspace_root)

            signal_path = workspace_root / "research" / "market_signals" / "2026-03-12__rss__ai-native-ops-substack__https-www-oneusefulthing-org-p-the-shape-of-the-thing.md"
            self.assertTrue(signal_path.exists())
            rendered = signal_path.read_text(encoding="utf-8")
            self.assertIn("rss_feed+article_preview", rendered)
            self.assertIn("What matters is whether operators can tell what has stabilized and what still needs translation.", rendered)
            self.assertEqual(result["restored_count"], 1)

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
