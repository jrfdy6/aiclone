from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.services.social_feed_builder_service import build_feed
from app.services.workspace_snapshot_service import workspace_snapshot_service

social_feedback_module = importlib.import_module("app.services.social_feedback_service")
workspace_snapshot_module = importlib.import_module("app.services.workspace_snapshot_service")


SAMPLE_FEED = {
    "generated_at": "2026-03-28T01:00:00+00:00",
    "workspace": "linkedin-content-os",
    "strategy_mode": "production",
    "items": [
        {
            "id": "fixture__signal-001",
            "platform": "linkedin",
            "source_lane": "market_signal",
            "capture_method": "fixture",
            "title": "AI agents fail from lack of context, not lack of smarts",
            "author": "Fixture Author",
            "source_url": "https://example.com/post",
            "source_path": "research/market_signals/fixture.md",
            "published_at": "2026-03-28T00:00:00+00:00",
            "captured_at": "2026-03-28T00:05:00+00:00",
            "summary": "Fixture summary",
            "standout_lines": ["AI agents fail from lack of context, not lack of smarts."],
            "engagement": {"likes": 0, "comments": 0, "shares": 0},
            "ranking": {"priority_network": 50, "topic_match": 0, "recency": 99, "engagement": 0, "persona_fit": 10, "source_quality": 15, "total": 174},
            "lenses": ["ai"],
            "comment_draft": "Fixture comment draft",
            "repost_draft": "Fixture repost draft",
            "lens_variants": {
                "ai": {
                    "comment": "Fixture AI comment",
                    "repost": "Fixture AI repost",
                    "quick_reply": "Fixture quick reply",
                    "stance": "reinforce",
                    "agreement_level": "high",
                    "belief_used": "AI systems need clean context to be useful.",
                    "belief_summary": "Context quality matters more than model hype.",
                    "experience_anchor": "AI Clone build work",
                    "experience_summary": "Experience anchoring from real build work.",
                    "role_safety": "safe",
                    "techniques": ["contrarian_reframe", "authority_snap"],
                    "emotional_profile": ["clarity", "authority"],
                    "technique_reason": "Fixture technique reason",
                    "evaluation": {"overall": 8.2, "warnings": []},
                }
            },
            "why_it_matters": "Fixture relevance note",
            "notes": [],
            "core_claim": "Fixture core claim",
            "supporting_claims": [],
            "topic_tags": ["ai"],
            "trust_notes": [],
            "source_metadata": {},
            "belief_assessment": {
                "stance": "reinforce",
                "agreement_level": "high",
                "belief_used": "AI systems need clean context to be useful.",
                "belief_summary": "Context quality matters more than model hype.",
                "experience_anchor": "AI Clone build work",
                "experience_summary": "Experience anchoring from real build work.",
                "role_safety": "safe",
            },
            "technique_assessment": {
                "techniques": ["contrarian_reframe", "authority_snap"],
                "emotional_profile": ["clarity", "authority"],
                "reason": "Fixture technique reason",
            },
            "evaluation": {"overall": 8.2, "warnings": []},
        }
    ],
}

SAMPLE_FEEDBACK_SUMMARY = {
    "generated_at": "2026-03-28T01:00:00+00:00",
    "total_events": 0,
    "decision_counts": {},
    "lens_counts": {},
    "stance_counts": {},
    "technique_counts": {},
    "average_evaluation_overall": None,
    "low_score_events": [],
    "recent_events": [],
}


class WorkspaceSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.temp_dir.name) / "linkedin-content-os"
        plans_dir = cls.fixture_root / "plans"
        analytics_dir = cls.fixture_root / "analytics"
        plans_dir.mkdir(parents=True, exist_ok=True)
        analytics_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / "social_feed.json").write_text(json.dumps(SAMPLE_FEED, indent=2), encoding="utf-8")
        (analytics_dir / "feed_feedback_summary.json").write_text(
            json.dumps(SAMPLE_FEEDBACK_SUMMARY, indent=2),
            encoding="utf-8",
        )

        cls.patches = [
            patch.object(workspace_snapshot_module, "LINKEDIN_ROOT", cls.fixture_root),
            patch.object(workspace_snapshot_module, "get_snapshot_payload", lambda *args, **kwargs: None),
            patch.object(workspace_snapshot_module, "upsert_snapshot", lambda *args, **kwargs: None),
            patch.object(social_feedback_module, "FEEDBACK_DIR", analytics_dir),
            patch.object(social_feedback_module, "FEEDBACK_PATH", analytics_dir / "feed_feedback.md"),
            patch.object(social_feedback_module, "FEEDBACK_JSONL_PATH", analytics_dir / "feed_feedback.jsonl"),
            patch.object(social_feedback_module, "FEEDBACK_SUMMARY_PATH", analytics_dir / "feed_feedback_summary.json"),
            patch.object(social_feedback_module, "upsert_snapshot", lambda *args, **kwargs: None),
        ]
        for patcher in cls.patches:
            patcher.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        for patcher in reversed(cls.patches):
            patcher.stop()
        cls.temp_dir.cleanup()

    def test_social_feed_builder_returns_rich_items(self) -> None:
        feed = build_feed(workspace_root=self.fixture_root)
        items = feed.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))
        self.assertTrue(feed.get("generated_at"))

    def test_workspace_snapshot_service_returns_live_sections(self) -> None:
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
        social_feed = snapshot.get("social_feed") or {}
        items = social_feed.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))
        self.assertIn("feedback_summary", snapshot)
        self.assertIn("refresh_status", snapshot)

    def test_health_route(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "healthy")

    def test_workspace_snapshot_route(self) -> None:
        response = self.client.get("/api/workspace/linkedin-os-snapshot")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        social_feed = payload.get("social_feed") or {}
        items = social_feed.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))

    def test_ingest_signal_route(self) -> None:
        response = self.client.post(
            "/api/workspace/ingest-signal",
            json={
                "text": "AI agents fail from lack of context, not lack of smarts. Teams need cleaner workflow context.",
                "priority_lane": "ai",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        preview_item = payload.get("preview_item") or {}
        self.assertTrue(preview_item.get("lens_variants"))
        self.assertIn("title", preview_item)


if __name__ == "__main__":
    unittest.main()
