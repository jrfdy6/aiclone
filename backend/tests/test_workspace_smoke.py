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
from app.services.social_expression_engine import social_expression_engine
from app.services.social_feed_builder_service import build_feed
from app.services.workspace_snapshot_service import workspace_snapshot_service

social_feedback_module = importlib.import_module("app.services.social_feedback_service")
social_feed_builder_module = importlib.import_module("app.services.social_feed_builder_service")
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

    def test_social_feed_builder_filters_placeholder_saved_signals(self) -> None:
        research_root = self.fixture_root / "research" / "market_signals"
        research_root.mkdir(parents=True, exist_ok=True)
        placeholder_path = research_root / "2026-03-28__reddit__placeholder.md"
        real_path = research_root / "2026-03-28__rss__real.md"

        placeholder_path.write_text(
            """---
kind: market_signal
title: r/ai_in_education signal snapshot
created_at: '2026-03-28T00:00:00+00:00'
source_platform: reddit
source_type: post
source_url: https://reddit.com/r/ai_in_education
author: reddit
summary: Placeholder capture for r/ai_in_education.
why_it_matters: Practitioner edge cases and growth experiments
---

# Reddit placeholder

Placeholder capture for r/ai_in_education.
""",
            encoding="utf-8",
        )
        real_path.write_text(
            """---
kind: market_signal
title: NSF Awards $11 Million for K-12 AI Teacher Training
created_at: '2026-03-28T00:00:00+00:00'
source_platform: rss
source_type: article
source_url: https://example.com/nsf-ai-teacher-training
author: Higher Ed Source
priority_lane: program-leadership
summary: New funding is going into AI teacher training programs across K-12 systems.
why_it_matters: Leadership, training capacity, and implementation readiness signals.
---

# NSF Awards $11 Million for K-12 AI Teacher Training

New funding is going into AI teacher training programs across K-12 systems.
""",
            encoding="utf-8",
        )

        feed = build_feed(workspace_root=self.fixture_root)
        titles = [item.get("title") for item in feed.get("items") or []]

        self.assertIn("NSF Awards $11 Million for K-12 AI Teacher Training", titles)
        self.assertNotIn("r/ai_in_education signal snapshot", titles)

        placeholder_path.unlink(missing_ok=True)
        real_path.unlink(missing_ok=True)

    def test_social_feed_builder_preserves_existing_linkedin_items_when_refreshing_safe_sources(self) -> None:
        research_root = self.fixture_root / "research" / "market_signals"
        research_root.mkdir(parents=True, exist_ok=True)
        rss_path = research_root / "2026-03-28__rss__real.md"
        rss_path.write_text(
            """---
kind: market_signal
title: Kentucky Senate passes bill making it easier to cut faculty
created_at: '2026-03-28T00:00:00+00:00'
source_platform: rss
source_type: article
source_url: https://example.com/faculty-cuts
author: Higher Ed Source
priority_lane: admissions
summary: Faculty groups have slammed the measure and colleges are watching it closely.
why_it_matters: Higher-ed operations and enrollment-adjacent execution signals.
---

# Kentucky Senate passes bill making it easier to cut faculty

Faculty groups have slammed the measure and colleges are watching it closely.
""",
            encoding="utf-8",
        )

        feed = build_feed(workspace_root=self.fixture_root)
        titles = [item.get("title") for item in feed.get("items") or []]

        self.assertIn("AI agents fail from lack of context, not lack of smarts", titles)
        self.assertIn("Kentucky Senate passes bill making it easier to cut faculty", titles)

        rss_path.unlink(missing_ok=True)

    def test_workspace_root_discovery_prefers_top_level_workspace_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            top_level = base / "workspaces" / "linkedin-content-os"
            backend_copy = base / "backend" / "workspaces" / "linkedin-content-os"
            (top_level / "plans").mkdir(parents=True, exist_ok=True)
            (backend_copy / "plans").mkdir(parents=True, exist_ok=True)
            (top_level / "plans" / "social_feed.json").write_text("{}", encoding="utf-8")
            (backend_copy / "plans" / "social_feed.json").write_text("{}", encoding="utf-8")

            with patch.object(social_feed_builder_module, "_candidate_roots", return_value=[base, base / "backend"]):
                discovered = social_feed_builder_module.discover_linkedin_workspace_root()

            self.assertEqual(discovered, top_level.resolve())

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

    def test_split_lane_outputs_stay_materially_distinct(self) -> None:
        response = self.client.post(
            "/api/workspace/ingest-signal",
            json={
                "text": (
                    "AI agents fail from lack of context, not lack of smarts. "
                    "Teams need cleaner handoffs, stronger ownership, and better judgment around outputs."
                ),
                "priority_lane": "ai",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        variants = (payload.get("preview_item") or {}).get("lens_variants") or {}

        ai_comment = (variants.get("ai") or {}).get("comment", "").lower()
        ops_comment = (variants.get("ops-pm") or {}).get("comment", "").lower()
        leadership_comment = (variants.get("program-leadership") or {}).get("comment", "").lower()
        current_role_comment = (variants.get("current-role") or {}).get("comment", "").lower()
        therapy_comment = (variants.get("therapy") or {}).get("comment", "").lower()
        referral_comment = (variants.get("referral") or {}).get("comment", "").lower()

        self.assertNotEqual(ai_comment, ops_comment)
        self.assertIn("judgment", ai_comment)
        self.assertTrue(any(term in ops_comment for term in ["ownership", "handoff", "cadence", "workflow"]))
        self.assertTrue(any(term in leadership_comment for term in ["leadership", "shared standards", "coaching"]))
        self.assertTrue(any(term in current_role_comment for term in ["current role", "students", "families", "this week", "next owner"]))
        self.assertTrue(any(term in therapy_comment for term in ["attuned", "container", "emotional", "regulated"]))
        self.assertTrue(any(term in referral_comment for term in ["referral", "handoff", "partner", "confidence"]))

    def test_generic_source_phrase_is_not_blindly_echoed_into_current_role_comment(self) -> None:
        response = self.client.post(
            "/api/workspace/ingest-signal",
            json={
                "text": (
                    "I’ve been reflecting on the role of AI in education and its rapid advancement.\n\n"
                    "The real challenge in the classroom isn’t motivating students to use AI, it’s helping them learn to use it well.\n\n"
                    "AI is a tool, not a substitute for judgment, skepticism, or foundational knowledge. You can’t prompt your way through what you don’t understand.\n\n"
                    "Whether it’s analyzing financial statements, applying accounting standards, preparing for the CPA exam, or navigating future careers, core knowledge still matters. In fact, it matters more than ever."
                ),
                "priority_lane": "current-role",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        current_role = ((payload.get("preview_item") or {}).get("lens_variants") or {}).get("current-role") or {}
        comment = current_role.get("comment", "").lower()
        warnings = ((current_role.get("evaluation") or {}).get("warnings") or [])

        self.assertNotIn(
            "the real challenge in the classroom isn’t motivating students to use ai, it’s helping them learn to use it well.",
            comment,
        )
        self.assertNotIn(
            "the bigger challenge is less motivating students to use ai and more helping them learn to use it well.",
            comment,
        )
        self.assertIn(
            "the challenge is not motivating students to use ai. it is helping them learn to use it well.",
            comment,
        )
        self.assertNotIn("more than ever", comment)
        self.assertNotIn("copy still contains generic language", warnings)
        self.assertGreater((current_role.get("evaluation") or {}).get("expression_delta", 0.0), 0.0)

    def test_expression_engine_flags_flattened_contrast_as_degraded(self) -> None:
        source = "The real challenge in the classroom isn’t motivating students to use AI, it’s helping them learn to use it well."
        degraded = "The bigger challenge is less motivating students to use AI and more helping them learn to use it well."
        preserved = "The challenge is not motivating students to use AI. It is helping them learn to use it well."

        degraded_assessment = social_expression_engine.compare(source, degraded)
        preserved_assessment = social_expression_engine.compare(source, preserved)

        self.assertEqual(degraded_assessment["source_structure"], "contrast-direct")
        self.assertFalse(degraded_assessment["structure_preserved"])
        self.assertLess(degraded_assessment["expression_delta"], 0.0)
        self.assertIn("rewrite lost source contrast structure", degraded_assessment["warnings"])

        self.assertTrue(preserved_assessment["structure_preserved"])
        self.assertGreater(preserved_assessment["expression_delta"], 0.0)

    def test_expression_engine_preserves_other_high_value_pattern_families(self) -> None:
        cases = [
            (
                "AI agents fail not because models are weak but because enterprise context is missing.",
                "The issue is not that models are weak. It is that enterprise context is missing.",
                "contrast-causal",
            ),
            (
                "AI is a tool, not a substitute for judgment, skepticism, or foundational knowledge.",
                "The tool can help, but it cannot replace judgment, skepticism, or foundational knowledge.",
                "boundary-substitute",
            ),
            (
                "AI can augment parts of the work, but humans still need to teach, correct, connect, and make meaning.",
                "AI can support parts of the work, but people still need to teach, correct, connect, and make meaning.",
                "boundary-augment",
            ),
            (
                "If you want better higher ed content, start with your admissions team.",
                "If you want better higher ed content, you have to start closer to your admissions team.",
                "directive-start-with",
            ),
        ]

        for source, preserved, expected_structure in cases:
            with self.subTest(source=source):
                assessment = social_expression_engine.compare(source, preserved)
                self.assertEqual(assessment["source_structure"], expected_structure)
                self.assertEqual(assessment["output_structure"], expected_structure)
                self.assertTrue(assessment["structure_preserved"])
                self.assertGreaterEqual(assessment["expression_delta"], 0.0)


if __name__ == "__main__":
    unittest.main()
