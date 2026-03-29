from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.models import PersonaDelta
from app.services.social_expression_engine import social_expression_engine
from app.services.social_feed_builder_service import build_feed
from app.services.social_source_asset_service import build_source_asset_inventory
from app.services.workspace_snapshot_service import workspace_snapshot_service

social_feedback_module = importlib.import_module("app.services.social_feedback_service")
social_feed_builder_module = importlib.import_module("app.services.social_feed_builder_service")
social_long_form_signal_module = importlib.import_module("app.services.social_long_form_signal_service")
social_persona_review_module = importlib.import_module("app.services.social_persona_review_service")
daily_brief_module = importlib.import_module("app.services.daily_brief_service")
persona_route_module = importlib.import_module("app.routes.persona")
brain_route_module = importlib.import_module("app.routes.brain")
content_generation_module = importlib.import_module("app.routes.content_generation")
content_context_service_module = importlib.import_module("app.services.content_generation_context_service")
workspace_snapshot_module = importlib.import_module("app.services.workspace_snapshot_service")
persona_promotion_module = importlib.import_module("app.services.persona_promotion_service")
persona_promotion_utils_module = importlib.import_module("app.services.persona_promotion_utils")
persona_promotion_extractor_module = importlib.import_module("app.services.persona_promotion_extractor")
belief_engine_module = importlib.import_module("app.services.social_belief_engine")
persona_bundle_writer_module = importlib.import_module("app.services.persona_bundle_writer")
persona_bundle_context_module = importlib.import_module("app.services.persona_bundle_context_service")


SAMPLE_FEED = {
    "generated_at": "2026-03-28T01:00:00+00:00",
    "workspace": "linkedin-content-os",
    "strategy_mode": "production",
    "items": [
        {
            "id": "fixture__signal-001",
            "platform": "linkedin",
            "source_type": "post",
            "source_class": "short_form",
            "unit_kind": "full_post",
            "response_modes": ["comment", "repost", "post_seed", "belief_evidence"],
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
        memory_dir = Path(cls.temp_dir.name) / "memory"
        transcripts_dir = Path(cls.temp_dir.name) / "knowledge" / "aiclone" / "transcripts"
        ingestions_dir = Path(cls.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "fixture_transcript_asset"
        plans_dir.mkdir(parents=True, exist_ok=True)
        analytics_dir.mkdir(parents=True, exist_ok=True)
        memory_dir.mkdir(parents=True, exist_ok=True)
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        ingestions_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / "social_feed.json").write_text(json.dumps(SAMPLE_FEED, indent=2), encoding="utf-8")
        (analytics_dir / "feed_feedback_summary.json").write_text(
            json.dumps(SAMPLE_FEEDBACK_SUMMARY, indent=2),
            encoding="utf-8",
        )
        (transcripts_dir / "2026-03-06_goat-os-episode-1.md").write_text(
            """---
title: Goat OS Bootcamp – Episode 1 (Bedrock)
source: YouTube live (https://www.youtube.com/live/jf9D4Oh7RwI)
received: 2026-03-05
raw_path: downloads/transcripts/jf9D4Oh7RwI.txt
tags: [ops, brain, lab]
---

## Summary
- Episode 1 is all about bootstrapping a fresh Goat OS agent.
""",
            encoding="utf-8",
        )
        (ingestions_dir / "normalized.md").write_text(
            """---
id: from_pilot_to_payoff_fixture
title: From Pilot To Payoff
source_type: youtube_transcript
captured_at: '2026-03-21T22:07:15Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=P5yznR8dUj4
author: unknown
raw_files:
- raw/transcript.txt
word_count: 10177
summary: AI pilots fail because teams miss some critical elements.
---

# Clean Transcript / Document
AI pilots fail because teams miss some critical elements.
""",
            encoding="utf-8",
        )
        (memory_dir / "daily-briefs.md").write_text(
            """# Morning Daily Brief - 2026-03-28

- Media routes are now feeding planning and persona review from one shared source system.
- Brain queue and workspace snapshot should agree on long-form worldview evidence.

## Notes
Shared source intelligence should stay visible in the brief layer.

# Morning Daily Brief - 2026-03-27

- Earlier brief content.
""",
            encoding="utf-8",
        )

        cls.patches = [
            patch.object(workspace_snapshot_module, "_discover_linkedin_root", return_value=cls.fixture_root),
            patch.object(workspace_snapshot_module, "get_snapshot_payload", lambda *args, **kwargs: None),
            patch.object(workspace_snapshot_module, "upsert_snapshot", lambda *args, **kwargs: None),
            patch.object(workspace_snapshot_module, "_transcripts_root", lambda: transcripts_dir),
            patch.object(workspace_snapshot_module, "_ingestions_root", lambda: Path(cls.temp_dir.name) / "knowledge" / "ingestions"),
            patch.object(social_feedback_module, "FEEDBACK_DIR", analytics_dir),
            patch.object(social_feedback_module, "FEEDBACK_PATH", analytics_dir / "feed_feedback.md"),
            patch.object(social_feedback_module, "FEEDBACK_JSONL_PATH", analytics_dir / "feed_feedback.jsonl"),
            patch.object(social_feedback_module, "FEEDBACK_SUMMARY_PATH", analytics_dir / "feed_feedback_summary.json"),
            patch.object(social_feedback_module, "upsert_snapshot", lambda *args, **kwargs: None),
            patch.object(daily_brief_module, "_WORKSPACE_CANDIDATES", (Path(cls.temp_dir.name),)),
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
        self.assertIn(items[0].get("source_class"), {"short_form", "article", "long_form_media", "manual"})
        self.assertTrue(items[0].get("unit_kind"))
        self.assertIsInstance(items[0].get("response_modes"), list)
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

    def test_social_feed_builder_preserves_real_safe_source_items_and_backfills_source_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "linkedin-content-os"
            plans_dir = workspace_root / "plans"
            research_root = workspace_root / "research" / "market_signals"
            plans_dir.mkdir(parents=True, exist_ok=True)
            research_root.mkdir(parents=True, exist_ok=True)

            feed_payload = {
                "generated_at": "2026-03-28T00:00:00+00:00",
                "workspace": "linkedin-content-os",
                "strategy_mode": "production",
                "items": [
                    {
                        "id": "rss__kentucky",
                        "platform": "rss",
                        "title": "Kentucky Senate passes bill making it easier to cut faculty",
                        "author": "Higher Ed Source",
                        "source_url": "https://example.com/faculty-cuts",
                        "summary": "Faculty groups have slammed the measure and colleges are watching it closely.",
                        "standout_lines": ["Faculty groups have slammed the measure and colleges are watching it closely."],
                        "comment_draft": "Admissions teams usually hear the market before the rest of the institution does.",
                        "repost_draft": "The repeated questions are often the clearest signal.",
                        "lens_variants": {"admissions": {"comment": "Admissions teams usually hear the market before the rest of the institution does.", "repost": "The repeated questions are often the clearest signal.", "evaluation": {"overall": 7.6, "warnings": []}}},
                        "ranking": {"total": 175.0},
                    }
                ],
            }
            (plans_dir / "social_feed.json").write_text(json.dumps(feed_payload, indent=2), encoding="utf-8")

            feed = build_feed(workspace_root=workspace_root)
            items = feed.get("items") or []

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].get("platform"), "rss")
            self.assertEqual(items[0].get("source_class"), "article")
            self.assertEqual(items[0].get("unit_kind"), "paragraph")
            self.assertEqual(items[0].get("response_modes"), ["comment", "repost", "post_seed", "belief_evidence"])

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

    def test_social_feed_builder_uses_alternate_workspace_feed_for_linkedin_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            top_level = base / "workspaces" / "linkedin-content-os"
            backend_copy = base / "backend" / "workspaces" / "linkedin-content-os"
            (top_level / "plans").mkdir(parents=True, exist_ok=True)
            (backend_copy / "plans").mkdir(parents=True, exist_ok=True)
            (top_level / "research" / "market_signals").mkdir(parents=True, exist_ok=True)

            top_level_feed = {
                "generated_at": "2026-03-28T00:00:00+00:00",
                "workspace": "linkedin-content-os",
                "strategy_mode": "production",
                "items": [],
            }
            backend_feed = dict(SAMPLE_FEED)

            (top_level / "plans" / "social_feed.json").write_text(json.dumps(top_level_feed, indent=2), encoding="utf-8")
            (backend_copy / "plans" / "social_feed.json").write_text(json.dumps(backend_feed, indent=2), encoding="utf-8")
            (top_level / "research" / "market_signals" / "2026-03-28__rss__real.md").write_text(
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

            with patch.object(social_feed_builder_module, "_candidate_roots", return_value=[base, base / "backend"]):
                feed = build_feed(workspace_root=top_level)

            titles = [item.get("title") for item in feed.get("items") or []]
            self.assertIn("Kentucky Senate passes bill making it easier to cut faculty", titles)
            self.assertIn("AI agents fail from lack of context, not lack of smarts", titles)

    def test_workspace_snapshot_service_returns_live_sections(self) -> None:
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
        social_feed = snapshot.get("social_feed") or {}
        source_assets = snapshot.get("source_assets") or {}
        persona_review_summary = snapshot.get("persona_review_summary") or {}
        items = social_feed.get("items") or []
        asset_items = source_assets.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))
        self.assertGreater(len(asset_items), 0)
        self.assertEqual(asset_items[0].get("source_class"), "long_form_media")
        self.assertIn("counts", persona_review_summary)
        self.assertIsInstance(persona_review_summary.get("recent"), list)
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
        source_assets = payload.get("source_assets") or {}
        persona_review_summary = payload.get("persona_review_summary") or {}
        items = social_feed.get("items") or []
        asset_items = source_assets.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertTrue(items[0].get("lens_variants"))
        self.assertGreater(len(asset_items), 0)
        self.assertIn("counts", persona_review_summary)

    def test_daily_briefs_attach_live_source_intelligence_to_latest_brief(self) -> None:
        fake_payloads = {
            "weekly_plan": {
                "generated_at": "2026-03-28T12:00:00+00:00",
                "base_generated_at": "2026-03-27 19:21",
                "source_counts": {"drafts": 1, "media": 3, "belief_evidence": 2},
                "media_post_seeds": [
                    {
                        "title": "Media seed one",
                        "priority_lane": "ai",
                        "source_kind": "long_form_post_seed",
                        "route_reason": "Strong original-post angle",
                    }
                ],
                "belief_evidence_candidates": [
                    {
                        "title": "Belief candidate one",
                        "priority_lane": "ai",
                        "source_kind": "long_form_belief_evidence",
                        "route_reason": "Durable worldview evidence",
                        "target_file": "identity/claims.md",
                    }
                ],
                "media_summary": {
                    "generated_at": "2026-03-28T12:00:00+00:00",
                    "route_counts": {"comment": 1, "post_seed": 3, "belief_evidence": 2},
                    "primary_route_counts": {"comment": 1, "post_seed": 2, "belief_evidence": 1},
                },
            },
            "long_form_routes": {},
            "source_assets": {"counts": {"total": 5, "long_form_media": 5, "pending_segmentation": 0, "feed_ready": 0}},
            "persona_review_summary": {
                "generated_at": "2026-03-28T12:00:00+00:00",
                "belief_relation_counts": {"qualified_agreement": 3, "translation": 1},
                "recent": [
                    {
                        "trait": "The key point is that teams fail when they chase tools before workflow clarity.",
                        "belief_relation": "system_translation",
                        "review_source": "long_form_media.segment",
                        "target_file": "identity/claims.md",
                    }
                ],
            },
        }

        with patch.object(daily_brief_module, "_load_from_db", return_value=[]), patch.object(
            daily_brief_module,
            "_snapshot_payloads",
            return_value=fake_payloads,
        ):
            briefs = daily_brief_module.list_daily_briefs(limit=5)

        self.assertGreaterEqual(len(briefs), 2)
        latest = briefs[0]
        older = briefs[1]
        overlay = latest.metadata.get("source_intelligence") or {}
        self.assertTrue(latest.metadata.get("source_intelligence_live"))
        self.assertEqual(overlay.get("media_post_seed_count"), 1)
        self.assertEqual(overlay.get("belief_evidence_candidate_count"), 1)
        self.assertEqual((overlay.get("belief_relation_counts") or {}).get("qualified_agreement"), 3)
        self.assertEqual(((overlay.get("top_media_post_seeds") or [{}])[0]).get("title"), "Media seed one")
        self.assertFalse(older.metadata.get("source_intelligence_live"))
        self.assertIsNone(older.metadata.get("source_intelligence"))

    def test_daily_briefs_route_surfaces_source_intelligence_overlay(self) -> None:
        fake_payloads = {
            "weekly_plan": {
                "generated_at": "2026-03-28T12:00:00+00:00",
                "source_counts": {"media": 2, "belief_evidence": 1},
                "media_post_seeds": [],
                "belief_evidence_candidates": [],
                "media_summary": {
                    "generated_at": "2026-03-28T12:00:00+00:00",
                    "route_counts": {"post_seed": 2, "belief_evidence": 1},
                    "primary_route_counts": {"post_seed": 2, "belief_evidence": 1},
                },
            },
            "long_form_routes": {},
            "source_assets": {"counts": {"total": 5}},
            "persona_review_summary": {"belief_relation_counts": {"system_translation": 1}, "recent": []},
        }

        with patch.object(daily_brief_module, "_load_from_db", return_value=[]), patch.object(
            daily_brief_module,
            "_snapshot_payloads",
            return_value=fake_payloads,
        ):
            response = self.client.get("/api/briefs/?limit=5")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload)
        self.assertTrue(payload[0]["metadata"].get("source_intelligence_live"))
        self.assertEqual(
            ((payload[0]["metadata"].get("source_intelligence") or {}).get("route_counts") or {}).get("post_seed"),
            2,
        )

    def test_source_asset_inventory_exposes_long_form_media_without_feed_routing(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        items = inventory.get("items") or []
        self.assertGreaterEqual(len(items), 1)
        self.assertTrue(all(item.get("source_class") == "long_form_media" for item in items))
        self.assertTrue(all(item.get("response_modes") == ["post_seed", "belief_evidence"] for item in items))
        self.assertTrue(all(item.get("feed_ready") is False for item in items))

    def test_workspace_snapshot_rebuilds_persisted_empty_source_assets_from_runtime(self) -> None:
        empty_persisted = {
            "generated_at": "2026-03-28T00:00:00+00:00",
            "workspace": "linkedin-content-os",
            "items": [],
            "counts": {
                "total": 0,
                "long_form_media": 0,
                "pending_segmentation": 0,
                "feed_ready": 0,
                "by_channel": {},
            },
        }

        def fake_get_snapshot_payload(workspace_key: str, snapshot_type: str):
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_SOURCE_ASSETS:
                return empty_persisted
            return None

        with patch.object(workspace_snapshot_module, "get_snapshot_payload", fake_get_snapshot_payload):
            snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()

        source_assets = snapshot.get("source_assets") or {}
        items = source_assets.get("items") or []
        self.assertGreater(len(items), 0)
        self.assertEqual(source_assets.get("counts", {}).get("total"), len(items))

    def test_long_form_route_summary_returns_segment_routes(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )

        summary = social_long_form_signal_module.build_long_form_route_summary(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=2,
            max_segments_per_asset=2,
        )

        self.assertGreater(summary.get("assets_considered", 0), 0)
        self.assertGreater(summary.get("segments_total", 0), 0)
        route_counts = summary.get("route_counts") or {}
        self.assertGreater(route_counts.get("belief_evidence", 0), 0)
        self.assertGreater(route_counts.get("post_seed", 0), 0)
        self.assertLess(route_counts.get("comment", 0), route_counts.get("belief_evidence", 0))
        candidates = summary.get("candidates") or []
        self.assertTrue(candidates)
        primary_routes = {candidate.get("primary_route") for candidate in candidates}
        self.assertTrue(primary_routes & {"post_seed", "belief_evidence"})
        self.assertIn(candidates[0].get("primary_route"), {"comment", "post_seed", "belief_evidence"})
        self.assertIsInstance(candidates[0].get("response_modes"), list)

    def test_weekly_plan_augmentation_uses_shared_long_form_routes(self) -> None:
        weekly_plan = {
            "generated_at": "2026-03-28T00:00:00+00:00",
            "workspace": "workspaces/linkedin-content-os",
            "positioning_model": [],
            "priority_lanes": [],
            "recommendations": [],
            "hold_items": [],
            "market_signals": [],
            "research_notes": [],
            "source_counts": {"drafts": 1, "media": 0, "research": 0},
        }
        long_form_routes = {
            "generated_at": "2026-03-28T01:30:00+00:00",
            "assets_considered": 2,
            "segments_total": 3,
            "route_counts": {"comment": 0, "repost": 0, "post_seed": 2, "belief_evidence": 1},
            "primary_route_counts": {"comment": 0, "repost": 0, "post_seed": 2, "belief_evidence": 1},
            "candidates": [
                {
                    "title": "Route source",
                    "segment": "The key point is that teams fail when they chase tools before workflow clarity.",
                    "primary_route": "post_seed",
                    "route_reason": "segment is stronger as an original post angle than a direct reaction",
                    "route_score": 11,
                    "lane_hint": "program-leadership",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/source",
                    "target_file": "identity/VOICE_PATTERNS.md",
                    "response_modes": ["post_seed", "belief_evidence"],
                    "belief_summary": "people, process, and culture as the main levers of leadership",
                },
                {
                    "title": "Route source",
                    "segment": "AI literacy is judgment, not just access.",
                    "primary_route": "belief_evidence",
                    "route_reason": "segment is better suited to persona language or worldview capture",
                    "route_score": 10,
                    "lane_hint": "ai",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/source",
                    "target_file": "identity/claims.md",
                    "response_modes": ["post_seed", "belief_evidence"],
                    "belief_summary": "an AI practitioner, not just a passive user",
                },
            ],
        }

        augmented = workspace_snapshot_module._augment_weekly_plan_payload(weekly_plan, long_form_routes)

        self.assertEqual(augmented.get("generated_at"), "2026-03-28T01:30:00+00:00")
        self.assertEqual(augmented.get("base_generated_at"), "2026-03-28T00:00:00+00:00")
        self.assertEqual(augmented.get("source_counts", {}).get("media"), 1)
        self.assertEqual(augmented.get("source_counts", {}).get("belief_evidence"), 1)
        self.assertEqual(len(augmented.get("media_post_seeds") or []), 1)
        self.assertEqual(len(augmented.get("belief_evidence_candidates") or []), 1)
        self.assertEqual((augmented.get("media_post_seeds") or [{}])[0].get("source_kind"), "long_form_post_seed")
        self.assertEqual((augmented.get("belief_evidence_candidates") or [{}])[0].get("source_kind"), "long_form_belief_evidence")
        self.assertEqual((augmented.get("media_summary") or {}).get("assets_considered"), 2)
        self.assertEqual((augmented.get("media_summary") or {}).get("generated_at"), "2026-03-28T01:30:00+00:00")

    def test_weekly_plan_snapshot_refreshes_when_runtime_media_routes_change(self) -> None:
        persisted = {
            "generated_at": "2026-03-28T00:00:00+00:00",
            "workspace": "workspaces/linkedin-content-os",
            "positioning_model": [],
            "priority_lanes": [],
            "recommendations": [],
            "hold_items": [],
            "market_signals": [],
            "research_notes": [],
            "source_counts": {"drafts": 1, "media": 0, "research": 0},
        }
        runtime = {
            **persisted,
            "source_counts": {"drafts": 1, "media": 1, "research": 0, "belief_evidence": 1},
            "media_post_seeds": [
                {
                    "title": "Route source",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "priority_lane": "program-leadership",
                }
            ],
            "belief_evidence_candidates": [
                {
                    "title": "Belief route",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "priority_lane": "ai",
                }
            ],
        }

        def fake_get_snapshot_payload(workspace_key: str, snapshot_type: str):
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN:
                return persisted
            return None

        def fake_runtime_snapshot(snapshot_type: str):
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN:
                return runtime
            return None

        with patch.object(workspace_snapshot_module, "get_snapshot_payload", fake_get_snapshot_payload), patch.object(
            workspace_snapshot_module,
            "_runtime_snapshot_payload",
            side_effect=fake_runtime_snapshot,
        ), patch.object(workspace_snapshot_module, "upsert_snapshot"):
            payload = workspace_snapshot_module._load_snapshot(workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN)

        self.assertEqual(payload.get("source_counts", {}).get("media"), 1)
        self.assertEqual(len(payload.get("media_post_seeds") or []), 1)
        self.assertEqual(len(payload.get("belief_evidence_candidates") or []), 1)

    def test_weekly_plan_runtime_payload_uses_current_long_form_routes(self) -> None:
        weekly_plan = {
            "generated_at": "2026-03-28T00:00:00+00:00",
            "workspace": "workspaces/linkedin-content-os",
            "positioning_model": [],
            "priority_lanes": [],
            "recommendations": [],
            "hold_items": [],
            "market_signals": [],
            "research_notes": [],
            "source_counts": {"drafts": 6, "media": 0, "research": 4},
        }
        long_form_routes = {
            "generated_at": "2026-03-28T02:45:00+00:00",
            "assets_considered": 4,
            "segments_total": 6,
            "route_counts": {"comment": 1, "repost": 0, "post_seed": 6, "belief_evidence": 6},
            "primary_route_counts": {"comment": 1, "repost": 0, "post_seed": 3, "belief_evidence": 2},
            "candidates": [
                {
                    "title": "Route source",
                    "segment": "The key point is that teams fail when they chase tools before workflow clarity.",
                    "primary_route": "post_seed",
                    "route_reason": "segment is stronger as an original post angle than a direct reaction",
                    "route_score": 11,
                    "lane_hint": "program-leadership",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/source",
                    "target_file": "identity/VOICE_PATTERNS.md",
                    "response_modes": ["post_seed", "belief_evidence"],
                    "belief_summary": "people, process, and culture as the main levers of leadership",
                },
                {
                    "title": "Belief route",
                    "segment": "AI literacy is judgment, not just access.",
                    "primary_route": "belief_evidence",
                    "route_reason": "segment is better suited to persona language or worldview capture",
                    "route_score": 10,
                    "lane_hint": "ai",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/source",
                    "target_file": "identity/claims.md",
                    "response_modes": ["post_seed", "belief_evidence"],
                    "belief_summary": "an AI practitioner, not just a passive user",
                },
            ],
        }

        with patch.object(workspace_snapshot_module, "_build_weekly_plan_payload", return_value=weekly_plan), patch.object(
            workspace_snapshot_module,
            "_current_long_form_routes_payload",
            return_value=long_form_routes,
        ):
            payload = workspace_snapshot_module._runtime_snapshot_payload(workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN)

        self.assertEqual(payload.get("generated_at"), "2026-03-28T02:45:00+00:00")
        self.assertEqual(payload.get("base_generated_at"), "2026-03-28T00:00:00+00:00")
        self.assertEqual(payload.get("source_counts", {}).get("media"), 1)
        self.assertEqual(payload.get("source_counts", {}).get("belief_evidence"), 1)
        self.assertEqual(len(payload.get("media_post_seeds") or []), 1)
        self.assertEqual(len(payload.get("belief_evidence_candidates") or []), 1)

    def test_snapshot_response_loads_long_form_routes_before_weekly_plan(self) -> None:
        calls: list[str] = []

        def fake_load_snapshot(snapshot_type: str):
            calls.append(snapshot_type)
            return {"snapshot_type": snapshot_type}

        with patch.object(workspace_snapshot_module, "_load_snapshot", side_effect=fake_load_snapshot), patch.object(
            workspace_snapshot_module,
            "_load_workspace_files",
            return_value=[],
        ), patch.object(
            workspace_snapshot_module,
            "_load_doc_entries",
            return_value=[],
        ), patch.object(
            workspace_snapshot_module.social_feed_refresh_service,
            "get_status",
            return_value={"running": False, "last_run": None, "started_at": None, "error": None},
        ):
            snapshot = workspace_snapshot_module.workspace_snapshot_service.get_linkedin_os_snapshot()

        self.assertLess(
            calls.index(workspace_snapshot_module.SNAPSHOT_LONG_FORM_ROUTES),
            calls.index(workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN),
        )
        self.assertEqual(snapshot.get("long_form_routes", {}).get("snapshot_type"), workspace_snapshot_module.SNAPSHOT_LONG_FORM_ROUTES)
        self.assertEqual(snapshot.get("weekly_plan", {}).get("snapshot_type"), workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN)

    def test_refresh_persisted_state_refreshes_long_form_routes_before_weekly_plan(self) -> None:
        calls: list[str] = []

        def fake_runtime_snapshot(snapshot_type: str):
            calls.append(snapshot_type)
            return {"snapshot_type": snapshot_type}

        with patch.object(
            workspace_snapshot_module,
            "_runtime_snapshot_payload",
            side_effect=fake_runtime_snapshot,
        ), patch.object(
            workspace_snapshot_module,
            "_persist_snapshot",
            side_effect=lambda snapshot_type, payload, source: payload,
        ):
            refreshed = workspace_snapshot_module.workspace_snapshot_service.refresh_persisted_linkedin_os_state()

        self.assertLess(
            calls.index(workspace_snapshot_module.SNAPSHOT_LONG_FORM_ROUTES),
            calls.index(workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN),
        )
        self.assertIn(workspace_snapshot_module.SNAPSHOT_LONG_FORM_ROUTES, refreshed)
        self.assertIn(workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN, refreshed)

    def test_snapshot_response_reconciles_weekly_plan_against_loaded_long_form_routes(self) -> None:
        stale_weekly_plan = {
            "generated_at": "2026-03-27 19:21",
            "workspace": "workspaces/linkedin-content-os",
            "positioning_model": [],
            "priority_lanes": [],
            "recommendations": [],
            "hold_items": [],
            "market_signals": [],
            "research_notes": [],
            "source_counts": {"drafts": 6, "media": 0, "research": 4},
        }
        long_form_routes = {
            "assets_considered": 4,
            "segments_total": 6,
            "route_counts": {"comment": 1, "repost": 0, "post_seed": 6, "belief_evidence": 6},
            "primary_route_counts": {"comment": 1, "repost": 0, "post_seed": 3, "belief_evidence": 2},
            "candidates": [
                {
                    "title": "Route source",
                    "segment": "The key point is that teams fail when they chase tools before workflow clarity.",
                    "primary_route": "post_seed",
                    "route_reason": "segment is stronger as an original post angle than a direct reaction",
                    "route_score": 11,
                    "lane_hint": "program-leadership",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/source",
                    "target_file": "identity/VOICE_PATTERNS.md",
                    "response_modes": ["post_seed", "belief_evidence"],
                    "belief_summary": "people, process, and culture as the main levers of leadership",
                },
                {
                    "title": "Belief route",
                    "segment": "AI literacy is judgment, not just access.",
                    "primary_route": "belief_evidence",
                    "route_reason": "segment is better suited to persona language or worldview capture",
                    "route_score": 10,
                    "lane_hint": "ai",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/source",
                    "target_file": "identity/claims.md",
                    "response_modes": ["post_seed", "belief_evidence"],
                    "belief_summary": "an AI practitioner, not just a passive user",
                },
            ],
        }

        def fake_load_snapshot(snapshot_type: str):
            mapping = {
                workspace_snapshot_module.SNAPSHOT_SOURCE_ASSETS: {"items": [], "counts": {"total": 0}},
                workspace_snapshot_module.SNAPSHOT_LONG_FORM_ROUTES: long_form_routes,
                workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN: stale_weekly_plan,
                workspace_snapshot_module.SNAPSHOT_PERSONA_REVIEW_SUMMARY: {"counts": {}, "recent": []},
                workspace_snapshot_module.SNAPSHOT_REACTION_QUEUE: {"comment_opportunities": [], "post_seeds": []},
                workspace_snapshot_module.SNAPSHOT_SOCIAL_FEED: {"items": [{"lens_variants": {}, "source_class": "short_form", "unit_kind": "full_post", "response_modes": []}]},
                workspace_snapshot_module.SNAPSHOT_FEEDBACK_SUMMARY: {"total_events": 0},
            }
            return mapping[snapshot_type]

        with patch.object(workspace_snapshot_module, "_load_snapshot", side_effect=fake_load_snapshot), patch.object(
            workspace_snapshot_module,
            "_load_workspace_files",
            return_value=[],
        ), patch.object(
            workspace_snapshot_module,
            "_load_doc_entries",
            return_value=[],
        ), patch.object(
            workspace_snapshot_module.social_feed_refresh_service,
            "get_status",
            return_value={"running": False, "last_run": None, "started_at": None, "error": None},
        ):
            snapshot = workspace_snapshot_module.workspace_snapshot_service.get_linkedin_os_snapshot()

        weekly_plan = snapshot.get("weekly_plan") or {}
        self.assertEqual(weekly_plan.get("source_counts", {}).get("media"), 1)
        self.assertEqual(weekly_plan.get("source_counts", {}).get("belief_evidence"), 1)
        self.assertEqual(len(weekly_plan.get("media_post_seeds") or []), 1)
        self.assertEqual(len(weekly_plan.get("belief_evidence_candidates") or []), 1)

    def test_workspace_snapshot_keeps_nonempty_persisted_source_assets_when_runtime_inventory_is_empty(self) -> None:
        persisted = {
            "generated_at": "2026-03-28T00:00:00+00:00",
            "workspace": "linkedin-content-os",
            "items": [
                {
                    "asset_id": "persisted-asset",
                    "title": "Persisted asset",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_class": "long_form_media",
                    "response_modes": ["post_seed", "belief_evidence"],
                }
            ],
            "counts": {
                "total": 1,
                "long_form_media": 1,
                "pending_segmentation": 1,
                "feed_ready": 0,
                "by_channel": {"youtube": 1},
            },
        }

        with patch.object(workspace_snapshot_module, "get_snapshot_payload", return_value=persisted), patch.object(
            workspace_snapshot_module,
            "_build_source_assets_payload",
            return_value={
                "generated_at": "2026-03-28T00:01:00+00:00",
                "workspace": "linkedin-content-os",
                "items": [],
                "counts": {
                    "total": 0,
                    "long_form_media": 0,
                    "pending_segmentation": 0,
                    "feed_ready": 0,
                    "by_channel": {},
                },
            },
        ):
            snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()

        source_assets = snapshot.get("source_assets") or {}
        self.assertEqual(source_assets.get("counts", {}).get("total"), 1)
        self.assertEqual((source_assets.get("items") or [{}])[0].get("asset_id"), "persisted-asset")

    def test_load_doc_entries_discovers_operating_and_workspace_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sop_dir = tmp_path / "SOPs"
            workspace_docs_dir = tmp_path / "workspaces" / "linkedin-content-os" / "docs"
            sop_dir.mkdir(parents=True)
            workspace_docs_dir.mkdir(parents=True)

            (sop_dir / "brain_workspace_boundary_sop.md").write_text("# Brain Boundary\nControl plane rules.\n", encoding="utf-8")
            (workspace_docs_dir / "source_expansion_implementation_plan.md").write_text(
                "# Source Expansion\nRoute long-form sources.\n",
                encoding="utf-8",
            )
            standalone = tmp_path / "AGENTS.md"
            standalone.write_text("# AGENTS\nStartup contract.\n", encoding="utf-8")

            with patch.object(
                workspace_snapshot_module,
                "_discover_doc_roots",
                return_value=[(sop_dir, "Operating Docs"), (workspace_docs_dir, "Workspace Reference")],
            ), patch.object(
                workspace_snapshot_module,
                "_discover_doc_targets",
                return_value=[(standalone, "Operating Docs")],
            ), patch.object(
                workspace_snapshot_module,
                "ROOT",
                tmp_path,
            ):
                entries = workspace_snapshot_module._load_doc_entries()

        paths = {entry["path"] for entry in entries}
        groups = {entry["path"]: entry.get("group") for entry in entries}
        sop_path = next((path for path in paths if path.endswith("SOPs/brain_workspace_boundary_sop.md")), None)
        workspace_doc_path = next(
            (path for path in paths if path.endswith("workspaces/linkedin-content-os/docs/source_expansion_implementation_plan.md")),
            None,
        )
        agents_path = next((path for path in paths if path.endswith("AGENTS.md")), None)

        self.assertIsNotNone(sop_path)
        self.assertIsNotNone(workspace_doc_path)
        self.assertIsNotNone(agents_path)
        self.assertEqual(groups[sop_path], "Operating Docs")
        self.assertEqual(groups[workspace_doc_path], "Workspace Reference")

    def test_source_assets_payload_falls_back_to_long_form_review_metadata_when_inventory_is_empty(self) -> None:
        delta = PersonaDelta(
            id="delta-review-derived",
            capture_id=None,
            persona_target="feeze.core",
            trait="Trait A",
            notes="notes",
            status="draft",
            metadata={
                "review_source": "long_form_media.segment",
                "source_asset_id": "asset-review-derived",
                "source_class": "long_form_media",
                "source_channel": "youtube",
                "source_type": "youtube_transcript",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "source_path": "knowledge/ingestions/2026/03/example/normalized.md",
                "evidence_source": "Example Source",
                "segment_excerpt": "A durable segment.",
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        with patch.object(
            workspace_snapshot_module,
            "build_source_asset_inventory",
            return_value={
                "generated_at": "2026-03-28T00:01:00+00:00",
                "workspace": "linkedin-content-os",
                "items": [],
                "counts": {
                    "total": 0,
                    "long_form_media": 0,
                    "pending_segmentation": 0,
                    "feed_ready": 0,
                    "by_channel": {},
                },
            },
        ), patch.object(workspace_snapshot_module.persona_delta_service, "list_deltas", return_value=[delta]):
            payload = workspace_snapshot_module._build_source_assets_payload()

        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("backfill_source"), "persona_review_summary")
        self.assertEqual(payload.get("counts", {}).get("total"), 1)
        self.assertEqual((payload.get("items") or [{}])[0].get("asset_id"), "asset-review-derived")
        self.assertEqual((payload.get("items") or [{}])[0].get("source_channel"), "youtube")

    def test_workspace_snapshot_includes_persona_review_lifecycle_summary(self) -> None:
        now = datetime.now(timezone.utc)
        deltas = [
            PersonaDelta(
                id="delta-workspace",
                persona_target="feeze.core",
                trait="Reusable phrase",
                notes="Approved from workspace",
                status="approved",
                metadata={
                    "review_source": "linkedin_workspace.feed_quote",
                    "approval_state": "approved_from_workspace",
                    "target_file": "identity/VOICE_PATTERNS.md",
                },
                created_at=now,
            ),
            PersonaDelta(
                id="delta-brain-pending",
                persona_target="feeze.core",
                trait="Needs nuance",
                notes="Pending review",
                status="draft",
                metadata={"target_file": "identity/claims.md"},
                created_at=now,
            ),
            PersonaDelta(
                id="delta-promotion",
                persona_target="feeze.core",
                trait="Queued for promotion",
                notes="Approved with promotion items",
                status="approved",
                metadata={
                    "pending_promotion": True,
                    "review_source": "brain.persona.ui",
                    "target_file": "history/story_bank.md",
                },
                created_at=now,
            ),
            PersonaDelta(
                id="delta-committed",
                persona_target="feeze.core",
                trait="Committed item",
                notes="Already promoted",
                status="committed",
                metadata={"target_file": "identity/claims.md"},
                created_at=now,
                committed_at=now,
            ),
        ]

        with patch.object(workspace_snapshot_module.persona_delta_service, "list_deltas", return_value=deltas):
            snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()

        summary = snapshot.get("persona_review_summary") or {}
        counts = summary.get("counts") or {}

        self.assertEqual(counts.get("total"), 4)
        self.assertEqual(counts.get("workspace_saved"), 1)
        self.assertEqual(counts.get("brain_pending_review"), 1)
        self.assertEqual(counts.get("pending_promotion"), 1)
        self.assertEqual(counts.get("committed"), 1)

    def test_workspace_snapshot_includes_long_form_routes(self) -> None:
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
        long_form_routes = snapshot.get("long_form_routes") or {}
        self.assertGreaterEqual(long_form_routes.get("assets_considered", 0), 1)
        self.assertIn("route_counts", long_form_routes)
        self.assertIsInstance(long_form_routes.get("candidates"), list)

    def test_persona_deltas_route_supports_brain_queue_view(self) -> None:
        now = datetime.now(timezone.utc)
        deltas = [
            PersonaDelta(
                id="delta-history",
                persona_target="feeze.core",
                trait="Historical workspace save",
                notes="Already saved from workspace",
                status="approved",
                metadata={
                    "review_source": "linkedin_workspace.feed_quote",
                    "approval_state": "approved_from_workspace",
                    "target_file": "identity/VOICE_PATTERNS.md",
                },
                created_at=now,
            ),
            PersonaDelta(
                id="delta-longform",
                persona_target="feeze.core",
                trait="If your CEO is visibly using AI for prompting and agents, you're 5.2 times more likely to be successful with AI.",
                notes="Active long-form review",
                status="reviewed",
                metadata={
                    "review_source": "long_form_media.segment",
                    "target_file": "identity/claims.md",
                    "phrase_candidates": ["visibly using AI"],
                    "frameworks": ["leadership adoption"],
                },
                created_at=now,
            ),
        ]

        with patch.object(persona_route_module.persona_delta_service, "list_deltas", return_value=deltas):
            response = self.client.get("/api/persona/deltas?limit=100&view=brain_queue")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload[0]["id"], "delta-longform")
        self.assertEqual(payload[0]["metadata"]["queue_stage"], "brain_pending_review")
        self.assertTrue(payload[0]["metadata"]["queue_promotion_ready"])
        self.assertIn("queue_priority_score", payload[0]["metadata"])
        self.assertEqual(payload[1]["metadata"]["queue_stage"], "workspace_saved")

    def test_long_form_persona_review_sync_creates_brain_review_deltas(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        created_payloads = []
        now = datetime.now(timezone.utc)

        def fake_create_delta(payload):
            created_payloads.append(payload)
            return PersonaDelta(
                id=f"delta-{len(created_payloads)}",
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=now,
            )

        with patch.object(social_persona_review_module.persona_delta_service, "get_delta_by_review_key", return_value=None), patch.object(
            social_persona_review_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ):
            result = social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets=inventory,
                max_assets=2,
                max_segments_per_asset=2,
            )

        self.assertGreater(result.get("created_count", 0), 0)
        self.assertEqual(result.get("created_count"), len(created_payloads))
        self.assertTrue(all(payload.persona_target == "feeze.core" for payload in created_payloads))
        self.assertTrue(all(payload.metadata.get("review_source") == "long_form_media.segment" for payload in created_payloads))
        self.assertTrue(all(payload.metadata.get("response_mode") == "belief_evidence" for payload in created_payloads))
        self.assertTrue(all(payload.metadata.get("target_file") for payload in created_payloads))
        self.assertTrue(all(payload.metadata.get("source_path") for payload in created_payloads))
        self.assertTrue(all(payload.metadata.get("why_showing") for payload in created_payloads))
        self.assertTrue(all(payload.metadata.get("review_prompt") for payload in created_payloads))
        self.assertTrue(
            all(
                any(payload.metadata.get(key) for key in ("talking_points", "phrase_candidates", "frameworks", "anecdotes", "stats"))
                for payload in created_payloads
            )
        )

    def test_long_form_persona_review_sync_filters_heading_and_owner_note_noise(self) -> None:
        noisy_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "noisy_transcript_asset"
        noisy_dir.mkdir(parents=True, exist_ok=True)
        (noisy_dir / "normalized.md").write_text(
            """---
id: noisy_transcript_asset
title: Noisy Transcript Asset
source_type: youtube_transcript
captured_at: '2026-03-22T22:07:15Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=noisy123
author: unknown
raw_files:
- raw/noisy.txt
word_count: 88
summary: 'Transcript Host: This is a short validation transcript for the media background queue.'
---

# Clean Transcript / Document
Transcript
Host: The key point is that teams fail when they chase tools before workflow clarity.
Another useful lesson is that leadership has to translate the pattern into a repeatable process.

## Owner Notes
- **Open questions:** What build implications matter, what persona implications matter, and what should be emphasized?

## Follow-ups
- [ ] Review build implications in OpenClaw.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        noisy_items = [item for item in (inventory.get("items") or []) if item.get("asset_id") == "noisy_transcript_asset"]
        created_payloads = []
        now = datetime.now(timezone.utc)

        def fake_create_delta(payload):
            created_payloads.append(payload)
            return PersonaDelta(
                id=f"noisy-{len(created_payloads)}",
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=now,
            )

        with patch.object(social_persona_review_module.persona_delta_service, "get_delta_by_review_key", return_value=None), patch.object(
            social_persona_review_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ), patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[]):
            social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets={"items": noisy_items},
                max_assets=1,
                max_segments_per_asset=2,
            )

        combined_text = " ".join(
            [
                payload.trait + " " + (payload.notes or "")
                for payload in created_payloads
            ]
        ).lower()
        self.assertGreater(len(created_payloads), 0)
        self.assertNotIn("# clean transcript / document", combined_text)
        self.assertNotIn("open questions", combined_text)
        self.assertNotIn("pending owner review", combined_text)
        self.assertIn("teams fail when they chase tools before workflow clarity", combined_text)

    def test_long_form_persona_review_sync_resolves_stale_draft_segments(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        asset = next(item for item in (inventory.get("items") or []) if item.get("asset_id") == "from_pilot_to_payoff_fixture")
        stale_delta = PersonaDelta(
            id="stale-delta",
            persona_target="feeze.core",
            trait="Stale autogenerated segment",
            notes="Old segment",
            status="draft",
            metadata={
                "review_key": "long-form:stale",
                "review_source": "long_form_media.segment",
                "source_asset_id": "from_pilot_to_payoff_fixture",
            },
            created_at=datetime.now(timezone.utc),
        )

        update_calls = []

        def fake_update_delta(delta_id, payload):
            update_calls.append((delta_id, payload))
            return stale_delta

        with patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[stale_delta]), patch.object(
            social_persona_review_module.persona_delta_service,
            "get_delta_by_review_key",
            return_value=None,
        ), patch.object(social_persona_review_module.persona_delta_service, "create_delta"), patch.object(
            social_persona_review_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update_delta,
        ):
            result = social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets={"items": [asset]},
                max_assets=1,
                max_segments_per_asset=1,
            )

        self.assertEqual(result.get("resolved_stale"), 1)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0], "stale-delta")
        self.assertEqual(update_calls[0][1].status, "resolved")
        self.assertEqual(update_calls[0][1].metadata.get("sync_state"), "stale_segment")

    def test_long_form_persona_review_sync_refreshes_existing_draft_metadata(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        candidates = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=1,
            max_segments_per_asset=1,
        ).get("candidates") or []
        candidate = next(item for item in candidates if "belief_evidence" in (item.get("response_modes") or []))
        review_key = candidate.get("candidate_id")
        belief_summary = ((candidate.get("assessment") or {}).get("belief_summary")) or ""
        existing_delta = PersonaDelta(
            id="existing-delta",
            persona_target="feeze.core",
            trait="Old autogenerated trait",
            notes=f"Candidate segment:\nOld text\n\nBelief relation: {belief_summary}",
            status="draft",
            metadata={
                "review_key": review_key,
                "review_source": "long_form_media.segment",
                "source_asset_id": candidate.get("asset_id"),
            },
            created_at=datetime.now(timezone.utc),
        )

        update_calls = []

        def fake_update_delta(delta_id, payload):
            update_calls.append((delta_id, payload))
            return existing_delta

        with patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[existing_delta]), patch.object(
            social_persona_review_module.persona_delta_service,
            "get_delta_by_review_key",
            return_value=existing_delta,
        ), patch.object(social_persona_review_module.persona_delta_service, "create_delta"), patch.object(
            social_persona_review_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update_delta,
        ):
            result = social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets=inventory,
                max_assets=1,
                max_segments_per_asset=1,
            )

        self.assertEqual(result.get("created_count"), 0)
        self.assertEqual(result.get("refreshed_existing"), 1)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0], "existing-delta")
        self.assertIn("belief_relation", update_calls[0][1].metadata)
        self.assertIn("Belief summary:", update_calls[0][1].notes or "")

    def test_long_form_persona_review_sync_prefers_worldview_lines_over_self_credential_lines(self) -> None:
        credential_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "credential_heavy_transcript"
        credential_dir.mkdir(parents=True, exist_ok=True)
        (credential_dir / "normalized.md").write_text(
            """---
id: credential_heavy_transcript
title: Credential Heavy Transcript
source_type: youtube_transcript
captured_at: '2026-03-23T10:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=cred123
author: unknown
raw_files:
- raw/cred.txt
word_count: 98
summary: 'Thank you everyone. I have been working in AI since 2013.'
---

# Clean Transcript / Document
Thank you everyone. I have been working in AI since 2013. I am the Chief Business Officer for a unicorn software company.
The more useful lesson is that teams fail when they chase tools before workflow clarity.
And if your CEO is using AI for prompting and agents, you are far more likely to be successful because the culture changes with the tooling.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        items = [item for item in (inventory.get("items") or []) if item.get("asset_id") == "credential_heavy_transcript"]
        created_payloads = []
        now = datetime.now(timezone.utc)

        def fake_create_delta(payload):
            created_payloads.append(payload)
            return PersonaDelta(
                id=f"cred-{len(created_payloads)}",
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=now,
            )

        with patch.object(social_persona_review_module.persona_delta_service, "get_delta_by_review_key", return_value=None), patch.object(
            social_persona_review_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ), patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[]):
            social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets={"items": items},
                max_assets=1,
                max_segments_per_asset=2,
            )

        combined_text = " ".join((payload.trait + " " + (payload.notes or "")) for payload in created_payloads).lower()
        self.assertIn("teams fail when they chase tools before workflow clarity", combined_text)
        self.assertNotIn("i have been working in ai since 2013", combined_text)
        self.assertNotIn("chief business officer", combined_text)

    def test_long_form_persona_review_sync_avoids_weak_context_fragments_and_definitions(self) -> None:
        fragment_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "fragment_heavy_transcript"
        fragment_dir.mkdir(parents=True, exist_ok=True)
        (fragment_dir / "normalized.md").write_text(
            """---
id: fragment_heavy_transcript
title: Fragment Heavy Transcript
source_type: youtube_transcript
captured_at: '2026-03-28T00:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=fragmentheavy
author: unknown
raw_files:
- raw/transcript.txt
word_count: 9000
summary: Leadership and workflow questions matter more than generic definitions.
---

# Clean Transcript / Document
But my team and I thought, why does it have to be that way?
And even if I identify a handful of those opportunities, how do I overcome the inherent organizational challenges of talent, culture, and resistance to change of business processes?
And at Obsidian Strategies, where we work to identify and implement the most impactful AI applications to increase operational efficiencies, enhance customer experience, and drive revenue.
Machine learning is a subset of AI that uses math and statistical processes to create models that pour over vast bodies of data to make predictions.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        items = [item for item in (inventory.get("items") or []) if item.get("asset_id") == "fragment_heavy_transcript"]
        created_payloads = []
        now = datetime.now(timezone.utc)

        def fake_create_delta(payload):
            created_payloads.append(payload)
            return PersonaDelta(
                id=f"frag-{len(created_payloads)}",
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=now,
            )

        with patch.object(social_persona_review_module.persona_delta_service, "get_delta_by_review_key", return_value=None), patch.object(
            social_persona_review_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ), patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[]):
            social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets={"items": items},
                max_assets=1,
                max_segments_per_asset=2,
            )

        combined_text = " ".join((payload.trait + " " + (payload.notes or "")) for payload in created_payloads).lower()
        self.assertIn("organizational challenges of talent, culture, and resistance to change", combined_text)
        self.assertIn("the practical work is to identify and implement the most impactful ai applications", combined_text)
        self.assertIn("operational efficiencies, enhance customer experience, and drive revenue", combined_text)
        self.assertNotIn("why does it have to be that way", combined_text)
        self.assertNotIn("machine learning is a subset of ai", combined_text)
        self.assertNotIn("at obsidian strategies", combined_text)

    def test_long_form_persona_review_sync_avoids_deictic_dashboard_fragments(self) -> None:
        dashboard_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "dashboard_fragment_transcript"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        (dashboard_dir / "normalized.md").write_text(
            """---
id: dashboard_fragment_transcript
title: Dashboard Fragment Transcript
source_type: youtube_transcript
captured_at: '2026-03-28T00:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=dashboardfragment
author: unknown
raw_files:
- raw/transcript.txt
word_count: 9000
summary: Leadership behavior drives AI implementation outcomes.
---

        # Clean Transcript / Document
        But if your CEO is using it for prompting and for agents, brainstorming with you, doing cross-team groups with you, you're 5.2 times more likely to be successful with AI because they're talking about it.
        So it answers questions when my team is sleeping, for example, but the number one thing I'm super proud about is that element in green.
        But the better question would be if we rebuilt that customer service function from scratch knowing that AI is here, what would that look like?
        We're gonna start with leadership and talk a little bit about why leaders also impact the return on investment for an AI project.
        Sometimes they miss some very critical elements not because they weren't thinking about it but because that AI magic takes over.
        """,
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        items = [item for item in (inventory.get("items") or []) if item.get("asset_id") == "dashboard_fragment_transcript"]
        created_payloads = []
        now = datetime.now(timezone.utc)

        def fake_create_delta(payload):
            created_payloads.append(payload)
            return PersonaDelta(
                id=f"dash-{len(created_payloads)}",
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=now,
            )

        with patch.object(social_persona_review_module.persona_delta_service, "get_delta_by_review_key", return_value=None), patch.object(
            social_persona_review_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ), patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[]):
            social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets={"items": items},
                max_assets=1,
                max_segments_per_asset=2,
            )

        combined_text = " ".join((payload.trait + " " + (payload.notes or "")) for payload in created_payloads).lower()
        self.assertIn("5.2 times more likely to be successful with ai", combined_text)
        self.assertIn("return on investment for an ai project", combined_text)
        self.assertIn("if your ceo is visibly using ai for prompting and agents", combined_text)
        self.assertNotIn("we're gonna start with leadership", combined_text)
        self.assertNotIn("that element in green", combined_text)
        self.assertNotIn("ai magic takes over", combined_text)

    def test_workspace_snapshot_persona_review_summary_runs_long_form_sync(self) -> None:
        sync_result = {
            "assets_considered": 2,
            "created_count": 2,
            "skipped_existing": 1,
            "skipped_no_segments": 0,
            "resolved_stale": 1,
            "created": [
                {"id": "delta-a", "trait": "Trait A", "target_file": "identity/claims.md"},
                {"id": "delta-b", "trait": "Trait B", "target_file": "history/story_bank.md"},
            ],
        }
        delta = PersonaDelta(
            id="delta-a",
            capture_id=None,
            persona_target="feeze.core",
            trait="Trait A",
            notes="notes",
            status="draft",
            metadata={
                "review_source": "long_form_media.segment",
                "target_file": "identity/claims.md",
                "belief_relation": "translation",
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        with patch.object(
            workspace_snapshot_module.social_persona_review_service,
            "sync_long_form_worldview_reviews",
            return_value=sync_result,
        ) as sync_mock, patch.object(workspace_snapshot_module.persona_delta_service, "list_deltas", return_value=[delta]):
            snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()

        summary = snapshot.get("persona_review_summary") or {}
        self.assertEqual((summary.get("long_form_sync") or {}).get("created_count"), 2)
        self.assertEqual((summary.get("long_form_sync") or {}).get("resolved_stale"), 1)
        self.assertEqual((summary.get("belief_relation_counts") or {}).get("translation"), 1)
        self.assertEqual((summary.get("recent") or [{}])[0].get("belief_relation"), "translation")
        sync_mock.assert_called()

    def test_persona_review_summary_refreshes_when_recent_changes_without_count_change(self) -> None:
        persisted = {
            "generated_at": "2026-03-28T00:00:00+00:00",
            "workspace": "linkedin-content-os",
            "counts": {
                "total": 2,
                "brain_pending_review": 1,
                "workspace_saved": 1,
                "approved_unpromoted": 0,
                "pending_promotion": 0,
                "committed": 0,
            },
            "status_counts": {"draft": 1, "approved": 1},
            "review_source_counts": {"long_form_media.segment": 1, "linkedin_workspace.feed_quote": 1},
            "target_file_counts": {"identity/claims.md": 1},
            "recent": [
                {
                    "id": "delta-old",
                    "trait": "Old trait",
                    "status": "draft",
                    "stage": "brain_pending_review",
                    "review_source": "long_form_media.segment",
                }
            ],
            "long_form_sync": {
                "assets_considered": 1,
                "created_count": 0,
                "skipped_existing": 1,
                "skipped_no_segments": 0,
                "resolved_stale": 0,
                "created": [],
            },
        }
        runtime = {
            **persisted,
            "generated_at": "2026-03-28T00:05:00+00:00",
            "recent": [
                {
                    "id": "delta-new",
                    "trait": "New trait",
                    "status": "draft",
                    "stage": "brain_pending_review",
                    "review_source": "long_form_media.segment",
                }
            ],
            "long_form_sync": {
                "assets_considered": 1,
                "created_count": 1,
                "skipped_existing": 0,
                "skipped_no_segments": 0,
                "resolved_stale": 1,
                "created": [{"id": "delta-new", "trait": "New trait"}],
            },
        }
        persisted_result: dict[str, dict] = {}

        def fake_get_snapshot_payload(workspace_key: str, snapshot_type: str):
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_PERSONA_REVIEW_SUMMARY:
                return persisted
            return None

        def fake_runtime_payload(snapshot_type: str):
            if snapshot_type == workspace_snapshot_module.SNAPSHOT_PERSONA_REVIEW_SUMMARY:
                return runtime
            return None

        def fake_upsert_snapshot(workspace_key: str, snapshot_type: str, payload: dict, metadata: dict | None = None):
            persisted_result["payload"] = payload

        with patch.object(workspace_snapshot_module, "get_snapshot_payload", side_effect=fake_get_snapshot_payload), patch.object(
            workspace_snapshot_module,
            "_runtime_snapshot_payload",
            side_effect=fake_runtime_payload,
        ), patch.object(workspace_snapshot_module, "upsert_snapshot", side_effect=fake_upsert_snapshot):
            payload = workspace_snapshot_module._load_snapshot(workspace_snapshot_module.SNAPSHOT_PERSONA_REVIEW_SUMMARY)

        self.assertEqual((payload or {}).get("recent", [{}])[0].get("id"), "delta-new")
        self.assertEqual((payload or {}).get("long_form_sync", {}).get("created_count"), 1)
        self.assertEqual((persisted_result.get("payload") or {}).get("recent", [{}])[0].get("id"), "delta-new")

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
        self.assertEqual(preview_item.get("source_class"), "manual")
        self.assertTrue(preview_item.get("unit_kind"))
        self.assertIsInstance(preview_item.get("response_modes"), list)

    def test_brain_ingest_long_form_route_registers_source_asset(self) -> None:
        now = datetime.now(timezone.utc)
        response = self.client.post(
            "/api/brain/ingest-long-form",
            json={
                "url": "https://www.youtube.com/watch?v=brain123",
                "title": "Brain-owned ingest test",
                "notes": "This should enter the shared source system from Brain first.",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("source_channel"), "youtube")
        self.assertEqual(payload.get("source_type"), "youtube_transcript")
        self.assertIn("source_assets", payload)
        self.assertGreaterEqual(((payload.get("source_assets") or {}).get("counts") or {}).get("total", 0), 1)
        normalized_path = (
            Path(self.temp_dir.name)
            / "knowledge"
            / "ingestions"
            / now.strftime("%Y")
            / now.strftime("%m")
            / payload["asset_id"]
            / "normalized.md"
        )
        self.assertTrue(normalized_path.exists())
        normalized_text = normalized_path.read_text(encoding="utf-8")
        self.assertIn("Brain-owned ingest test", normalized_text)
        self.assertIn("https://www.youtube.com/watch?v=brain123", normalized_text)

    def test_brain_control_plane_route_returns_canonical_payload(self) -> None:
        fake_payload = {
            "generated_at": "2026-03-28T19:30:00+00:00",
            "automations": [{"id": "daily_brief", "name": "Daily Brief", "schedule": "Daily", "status": "active", "channel": "brain"}],
            "telemetry": {"captures": {"total": 11, "last_24h": 1, "last_7d": 3}, "vectors": {"total": 0, "with_expiry": 0, "overdue": 0}, "recent_captures": []},
            "telemetry_health": {"database_connected": True, "vector_extension": False, "embedder_dimension": 1536, "dimension_match": False, "capture_count": 11, "vector_count": 0, "non_expired_vector_count": 0, "search_ready": False},
            "workspace_snapshot": {"doc_entries": [{"path": "SOPs/example.md"}], "workspace_files": [{"path": "workspaces/linkedin-content-os/README.md"}]},
            "summary": {"automation_count": 1, "capture_count": 11, "doc_count": 1},
        }
        with patch.object(brain_route_module, "build_brain_control_plane", return_value=fake_payload):
            response = self.client.get("/api/brain/control-plane")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual((payload.get("summary") or {}).get("automation_count"), 1)
        self.assertEqual(((payload.get("workspace_snapshot") or {}).get("doc_entries") or [{}])[0].get("path"), "SOPs/example.md")

    def test_persona_brain_queue_route_sets_no_store_cache_header(self) -> None:
        delta = PersonaDelta(
            id="delta-brain-queue-cache",
            capture_id=None,
            persona_target="feeze.core",
            trait="Trait under review",
            notes=None,
            status="draft",
            metadata={},
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )
        with patch.object(persona_route_module.persona_delta_service, "list_deltas", return_value=[delta]):
            response = self.client.get("/api/persona/deltas?limit=10&view=brain_queue")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual((payload[0].get("metadata") or {}).get("queue_stage"), "brain_pending_review")

    def test_apply_brain_review_persists_owner_response_metadata(self) -> None:
        delta = PersonaDelta(
            id="delta-review",
            capture_id=None,
            persona_target="feeze.core",
            trait="Trait under review",
            notes="Original note",
            status="draft",
            metadata={
                "review_source": "long_form_media.segment",
                "talking_points": [{"id": "tp-1", "label": "Point", "content": "Point content"}],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        def fake_update(delta_id: str, payload):
            merged = dict(delta.metadata)
            merged.update(payload.metadata or {})
            return delta.model_copy(update={"status": payload.status or delta.status, "metadata": merged})

        with patch.object(persona_route_module.persona_delta_service, "get_delta", return_value=delta), patch.object(
            persona_route_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update,
        ):
            updated = persona_route_module.persona_delta_service.apply_brain_review(
                "delta-review",
                mode="reviewed",
                response_kind="nuance",
                reflection_excerpt="This needs more context from my experience.",
                resolution_capture_id="capture-123",
                selected_promotion_items=[],
            )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "in_review")
        self.assertEqual((updated.metadata or {}).get("owner_response_kind"), "nuance")
        self.assertEqual((updated.metadata or {}).get("resolution_capture_id"), "capture-123")
        self.assertIn("This needs more context", (updated.metadata or {}).get("owner_response_excerpt", ""))

    def test_brain_persona_review_route_returns_annotated_delta(self) -> None:
        delta = PersonaDelta(
            id="delta-route-review",
            capture_id=None,
            persona_target="feeze.core",
            trait="Route-level review delta",
            notes="Original note",
            status="reviewed",
            metadata={
                "review_source": "brain.persona.ui",
                "owner_response_kind": "agree",
                "owner_response_excerpt": "This matches how I think about it.",
                "talking_points": [{"id": "tp-1", "label": "Point", "content": "Point content"}],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )
        with patch.object(brain_route_module.persona_delta_service, "apply_brain_review", return_value=delta):
            response = self.client.post(
                "/api/brain/persona-review/delta-route-review",
                json={
                    "mode": "reviewed",
                    "response_kind": "agree",
                    "reflection_excerpt": "This matches how I think about it.",
                    "resolution_capture_id": "capture-456",
                    "selected_promotion_items": [],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual((payload.get("metadata") or {}).get("owner_response_kind"), "agree")
        self.assertIn("queue_stage", payload.get("metadata") or {})

    def test_brain_persona_review_route_preserves_semantic_promotion_fields(self) -> None:
        delta = PersonaDelta(
            id="delta-route-review-semantic",
            capture_id=None,
            persona_target="feeze.core",
            trait="Semantic review delta",
            notes="Original note",
            status="in_review",
            metadata={},
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )
        with patch.object(brain_route_module.persona_delta_service, "apply_brain_review", return_value=delta) as apply_review:
            response = self.client.post(
                "/api/brain/persona-review/delta-route-review-semantic",
                json={
                    "mode": "approved",
                    "response_kind": "nuance",
                    "reflection_excerpt": "This reflects a real shipped capability.",
                    "resolution_capture_id": "capture-789",
                    "selected_promotion_items": [
                        {
                            "id": "initiative-1",
                            "kind": "stat",
                            "label": "Proof point",
                            "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                            "evidence": "Artifact-backed proof from the review source.",
                            "targetFile": "history/initiatives.md",
                            "artifactSummary": "Shipped AI operating pattern with quantified success signal.",
                            "artifactKind": "metric_or_proof_point",
                            "artifactRef": "youtube:P5Yznr8Duj4",
                            "deltaSummary": "Promotion candidate for initiatives canon.",
                            "reviewInterpretation": "This proves a durable operator capability.",
                            "capabilitySignal": "Can translate AI execution into operator language.",
                            "positioningSignal": "AI systems operator with real implementation judgment.",
                            "leverageSignal": "Supports future content and positioning around workflow clarity.",
                            "proofSignal": "5.2x success signal tied to visible prompting/agent usage.",
                            "proofStrength": "strong",
                            "gateDecision": "allow",
                            "gateReason": "Artifact-backed proof is present.",
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        sent_items = apply_review.call_args.kwargs["selected_promotion_items"]
        self.assertEqual(sent_items[0]["artifactSummary"], "Shipped AI operating pattern with quantified success signal.")
        self.assertEqual(sent_items[0]["proofStrength"], "strong")
        self.assertEqual(sent_items[0]["gateDecision"], "allow")

    def test_promote_delta_to_canon_marks_delta_committed(self) -> None:
        delta = PersonaDelta(
            id="delta-promote",
            capture_id=None,
            persona_target="feeze.core",
            trait="Promote this to canon",
            notes="Promotion note",
            status="approved",
            metadata={
                "pending_promotion": True,
                "target_file": "identity/claims.md",
                "selected_promotion_items": [
                    {
                        "id": "claim-1",
                        "kind": "talking_point",
                        "label": "Claim",
                        "content": "Operator clarity matters more than hype.",
                        "targetFile": "identity/claims.md",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        def fake_update(delta_id: str, payload):
            merged = dict(delta.metadata)
            merged.update(payload.metadata or {})
            return delta.model_copy(update={"status": payload.status or delta.status, "metadata": merged, "committed_at": datetime.now(timezone.utc)})

        with patch.object(persona_promotion_module.persona_delta_service, "get_delta", return_value=delta), patch.object(
            persona_promotion_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update,
        ), patch.object(
            persona_promotion_module,
            "write_promotion_items_to_bundle",
            return_value={"bundle_root": "/tmp/persona", "written_files": ["identity/claims.md"], "file_results": {"identity/claims.md": {"added": 1, "skipped": 0}}},
        ):
            updated = persona_promotion_module.promote_delta_to_canon("delta-promote")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "committed")
        self.assertFalse((updated.metadata or {}).get("pending_promotion"))
        self.assertEqual((updated.metadata or {}).get("committed_item_count"), 1)
        self.assertEqual((updated.metadata or {}).get("bundle_written_files"), ["identity/claims.md"])
        self.assertEqual(((updated.metadata or {}).get("local_bundle_sync") or {}).get("state"), "pending")

    def test_promote_delta_to_canon_blocks_initiative_without_artifact_anchor(self) -> None:
        delta = PersonaDelta(
            id="delta-promote-initiative-blocked",
            capture_id=None,
            persona_target="feeze.core",
            trait="Weak initiative promotion",
            notes="Reflective note only",
            status="approved",
            metadata={
                "pending_promotion": True,
                "target_file": "history/initiatives.md",
                "selected_promotion_items": [
                    {
                        "id": "initiative-weak-1",
                        "kind": "talking_point",
                        "label": "Talking point",
                        "content": "This idea feels important to how I think about AI.",
                        "targetFile": "history/initiatives.md",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        with patch.object(persona_promotion_module.persona_delta_service, "get_delta", return_value=delta):
            with self.assertRaisesRegex(ValueError, "Cannot commit to initiatives canon"):
                persona_promotion_module.promote_delta_to_canon("delta-promote-initiative-blocked")

    def test_normalize_selected_promotion_items_preserves_semantic_slots(self) -> None:
        delta = PersonaDelta(
            id="delta-semantic-normalize",
            capture_id=None,
            persona_target="feeze.core",
            trait="Semantic normalization delta",
            notes="Original note",
            status="approved",
            metadata={
                "owner_response_kind": "nuance",
                "owner_response_excerpt": "This should be treated as interpretive context only.",
                "selected_promotion_items": [
                    {
                        "id": "initiative-1",
                        "kind": "stat",
                        "label": "Proof point",
                        "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                        "evidence": "Artifact-backed proof from the review source.",
                        "targetFile": "history/initiatives.md",
                        "artifactSummary": "Shipped AI operating pattern with quantified success signal.",
                        "artifactKind": "metric_or_proof_point",
                        "artifactRef": "youtube:P5Yznr8Duj4",
                        "deltaSummary": "Promotion candidate for initiatives canon.",
                        "reviewInterpretation": "This proves a durable operator capability.",
                        "capabilitySignal": "Can translate AI execution into operator language.",
                        "positioningSignal": "AI systems operator with real implementation judgment.",
                        "leverageSignal": "Supports future content and positioning around workflow clarity.",
                        "proofSignal": "5.2x success signal tied to visible prompting/agent usage.",
                        "proofStrength": "strong",
                        "gateDecision": "allow",
                        "gateReason": "Artifact-backed proof is present.",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        normalized = persona_promotion_utils_module.normalize_selected_promotion_items(delta)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["artifact_summary"], "Shipped AI operating pattern with quantified success signal.")
        self.assertEqual(normalized[0]["capability_signal"], "Can translate AI execution into operator language.")
        self.assertEqual(normalized[0]["proof_strength"], "strong")
        self.assertEqual(normalized[0]["gate_decision"], "allow")

    def test_brain_persona_promote_route_returns_committed_delta(self) -> None:
        delta = PersonaDelta(
            id="delta-route-promote",
            capture_id=None,
            persona_target="feeze.core",
            trait="Route-level promote delta",
            notes="Original note",
            status="committed",
            metadata={
                "selected_promotion_items": [
                    {
                        "id": "claim-1",
                        "kind": "talking_point",
                        "label": "Claim",
                        "content": "Operator clarity matters more than hype.",
                        "targetFile": "identity/claims.md",
                    }
                ],
                "committed_target_files": ["identity/claims.md"],
                "bundle_written_files": ["identity/claims.md"],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=datetime.now(timezone.utc),
        )
        with patch.object(brain_route_module, "promote_delta_to_canon", return_value=delta), patch.object(
            brain_route_module,
            "build_committed_persona_overlay",
            return_value={"counts": {"items": 1, "deltas": 1, "target_files": 1}},
        ):
            response = self.client.post("/api/brain/persona-promote/delta-route-promote")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual((payload.get("delta") or {}).get("status"), "committed")
        self.assertEqual((payload.get("overlay_counts") or {}).get("items"), 1)
        self.assertEqual(payload.get("bundle_written_files"), ["identity/claims.md"])

    def test_brain_persona_reroute_route_returns_updated_delta(self) -> None:
        delta = PersonaDelta(
            id="delta-route-reroute",
            capture_id=None,
            persona_target="feeze.core",
            trait="Route-level reroute delta",
            notes="Original note",
            status="approved",
            metadata={
                "pending_promotion": True,
                "target_file": "identity/claims.md",
                "selected_promotion_items": [
                    {
                        "id": "claim-1",
                        "kind": "talking_point",
                        "label": "Claim",
                        "content": "Operator clarity matters more than hype.",
                        "targetFile": "identity/claims.md",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )
        with patch.object(brain_route_module, "reroute_delta_promotion", return_value=delta):
            response = self.client.post(
                "/api/brain/persona-reroute/delta-route-reroute",
                json={"target_file": "identity/claims.md"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("target_file"), "identity/claims.md")
        self.assertEqual((payload.get("delta") or {}).get("id"), "delta-route-reroute")

    def test_persona_bundle_writer_persists_claims_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir) / "knowledge" / "persona" / "feeze"
            with patch.object(persona_bundle_writer_module, "resolve_persona_bundle_root", return_value=bundle_root):
                result = persona_bundle_writer_module.write_promotion_items_to_bundle(
                    [
                        {
                            "id": "claim-1",
                            "kind": "talking_point",
                            "label": "Claim",
                            "content": "Operator clarity matters more than hype.",
                            "evidence": "Saved from Brain review.",
                            "target_file": "identity/claims.md",
                            "trait": "Promote this to canon",
                        }
                    ]
                )

            claims_path = bundle_root / "identity" / "claims.md"
            self.assertTrue(claims_path.exists())
            self.assertIn("Operator clarity matters more than hype.", claims_path.read_text(encoding="utf-8"))
            self.assertEqual(result.get("written_files"), ["identity/claims.md"])

    def test_persona_bundle_writer_uses_semantic_initiative_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir) / "knowledge" / "persona" / "feeze"
            with patch.object(persona_bundle_writer_module, "resolve_persona_bundle_root", return_value=bundle_root):
                result = persona_bundle_writer_module.write_promotion_items_to_bundle(
                    [
                        {
                            "id": "initiative-1",
                            "kind": "stat",
                            "label": "Proof point",
                            "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                            "evidence": "Review note that should not become proof.",
                            "target_file": "history/initiatives.md",
                            "trait": "Pilot to payoff",
                            "canon_purpose": "Use quantified AI execution proof to ground initiative-level canon.",
                            "canon_value": "Strengthens Johnnie's positioning as an AI systems operator grounded in real execution.",
                            "canon_proof": "5.2x success signal tied to visible prompting and agent usage.",
                        }
                    ]
                )

            initiatives_path = bundle_root / "history" / "initiatives.md"
            content = initiatives_path.read_text(encoding="utf-8")
            self.assertTrue(initiatives_path.exists())
            self.assertIn("Use quantified AI execution proof to ground initiative-level canon.", content)
            self.assertIn("Strengthens Johnnie's positioning as an AI systems operator grounded in real execution.", content)
            self.assertIn("5.2x success signal tied to visible prompting and agent usage.", content)
            self.assertNotIn("Review note that should not become proof.", content)
            self.assertEqual(result.get("written_files"), ["history/initiatives.md"])

    def test_extract_canonical_promotion_items_marks_initiatives_without_artifacts_blocked(self) -> None:
        extracted = persona_promotion_extractor_module.extract_canonical_promotion_items(
            [
                {
                    "id": "initiative-weak-1",
                    "kind": "talking_point",
                    "label": "Talking point",
                    "content": "This idea feels important to how I think about AI.",
                    "target_file": "history/initiatives.md",
                    "owner_response_excerpt": "I really like this line.",
                }
            ]
        )

        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["gate_decision"], "block")
        self.assertEqual(extracted[0]["proof_strength"], "weak")

    def test_reroute_delta_promotion_updates_target_file_and_selected_items(self) -> None:
        delta = PersonaDelta(
            id="delta-reroute",
            capture_id=None,
            persona_target="feeze.core",
            trait="Weak initiative promotion",
            notes="Reflective note only",
            status="approved",
            metadata={
                "pending_promotion": True,
                "target_file": "history/initiatives.md",
                "selected_promotion_items": [
                    {
                        "id": "initiative-weak-1",
                        "kind": "talking_point",
                        "label": "Talking point",
                        "content": "This idea feels important to how I think about AI.",
                        "targetFile": "history/initiatives.md",
                        "gateDecision": "block",
                        "gateReason": "Initiatives canon requires an explicit artifact or output anchor.",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        def fake_update(delta_id: str, payload):
            merged = dict(delta.metadata)
            merged.update(payload.metadata or {})
            return delta.model_copy(update={"status": payload.status or delta.status, "metadata": merged})

        with patch.object(persona_promotion_module.persona_delta_service, "get_delta", return_value=delta), patch.object(
            persona_promotion_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update,
        ):
            updated = persona_promotion_module.reroute_delta_promotion("delta-reroute", target_file="identity/claims.md")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "approved")
        self.assertEqual((updated.metadata or {}).get("target_file"), "identity/claims.md")
        self.assertEqual(((updated.metadata or {}).get("selected_promotion_items") or [{}])[0].get("targetFile"), "identity/claims.md")
        self.assertEqual(((updated.metadata or {}).get("selected_promotion_items") or [{}])[0].get("gateDecision"), "allow")
        self.assertEqual((updated.metadata or {}).get("rerouted_from_target_file"), "history/initiatives.md")

    def test_persona_bundle_context_retrieves_committed_claim_for_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir) / "knowledge" / "persona" / "feeze"
            claims_path = bundle_root / "identity" / "claims.md"
            claims_path.parent.mkdir(parents=True, exist_ok=True)
            claims_path.write_text(
                """---
title: "Claims"
persona_id: "johnnie_fields"
target_file: "identity/claims.md"
generated_at: "2026-03-28T00:00:00+00:00"
---

| Claim | Type | Evidence | Usage rule |
| --- | --- | --- | --- |
| Teams fail when they chase tools before workflow clarity. | philosophical | Promoted from Brain review. | Safe for AI strategy and operator writing. |
""",
                encoding="utf-8",
            )

            with patch.object(persona_bundle_context_module, "resolve_persona_bundle_root", return_value=bundle_root):
                chunks = persona_bundle_context_module.retrieve_bundle_persona_chunks(
                    query_text="workflow clarity for AI teams",
                    category="value",
                    channel="linkedin_post",
                    top_k=3,
                )

            self.assertGreaterEqual(len(chunks), 1)
            self.assertIn("workflow clarity", (chunks[0].get("chunk") or "").lower())
            self.assertEqual(chunks[0].get("metadata", {}).get("source_kind"), "canonical_bundle")

    def test_persona_bundle_context_loads_typed_metadata_for_bundle_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = Path(temp_dir) / "knowledge" / "persona" / "feeze"
            claims_path = bundle_root / "identity" / "claims.md"
            initiatives_path = bundle_root / "history" / "initiatives.md"
            stories_path = bundle_root / "history" / "story_bank.md"
            claims_path.parent.mkdir(parents=True, exist_ok=True)
            initiatives_path.parent.mkdir(parents=True, exist_ok=True)
            stories_path.parent.mkdir(parents=True, exist_ok=True)

            claims_path.write_text(
                """| Claim | Type | Evidence | Usage rule |
| --- | --- | --- | --- |
| Prompting plus agent orchestration beats prompting alone. | positioning | Promoted from Brain review. | Safe for AI systems and operator writing. |
""",
                encoding="utf-8",
            )
            initiatives_path.write_text(
                """## AI Clone / Brain System
- Purpose: Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance.
- Value to persona: Proves Johnnie can turn messy AI/operator work into durable operating surfaces.
- Public-facing proof: Brain, Ops, planner, and briefs now read from the same routed workspace state.
- Use when: Use for posts about AI systems, operator clarity, and workflow orchestration.
""",
                encoding="utf-8",
            )
            stories_path.write_text(
                """## Lunch Before Coaching
- Story type: leadership
- Use when: leadership, coaching, trust-building
- Core point: Taking a struggling AC to lunch as a peer changed the relationship and improved adoption.
""",
                encoding="utf-8",
            )

            with patch.object(persona_bundle_context_module, "resolve_persona_bundle_root", return_value=bundle_root):
                chunks = persona_bundle_context_module.load_bundle_persona_chunks()

        by_path = {chunk.get("source_file_id"): chunk for chunk in chunks}

        claim_meta = by_path["identity/claims.md"]["metadata"]
        self.assertEqual(claim_meta.get("memory_role"), "core")
        self.assertEqual(claim_meta.get("proof_kind"), "claim")
        self.assertFalse(claim_meta.get("artifact_backed"))
        self.assertIn("ai_systems", claim_meta.get("domain_tags", []))
        self.assertIn("tech_ai", claim_meta.get("audience_tags", []))
        self.assertIn("always_on", claim_meta.get("usage_modes", []))

        initiative_meta = by_path["history/initiatives.md"]["metadata"]
        self.assertEqual(initiative_meta.get("memory_role"), "proof")
        self.assertEqual(initiative_meta.get("proof_kind"), "initiative")
        self.assertEqual(initiative_meta.get("proof_strength"), "strong")
        self.assertTrue(initiative_meta.get("artifact_backed"))
        self.assertIn("ai_systems", initiative_meta.get("domain_tags", []))
        self.assertIn("proof_anchor", initiative_meta.get("usage_modes", []))

        story_meta = by_path["history/story_bank.md"]["metadata"]
        self.assertEqual(story_meta.get("memory_role"), "story")
        self.assertEqual(story_meta.get("story_kind"), "leadership")
        self.assertEqual(story_meta.get("proof_strength"), "medium")
        self.assertIn("story_anchor", story_meta.get("usage_modes", []))

    def test_persona_bundle_context_reads_committed_overlay_for_immediate_content_use(self) -> None:
        with patch.object(
            persona_bundle_context_module,
            "build_committed_persona_overlay",
            return_value={
                "by_target_file": {
                    "identity/claims.md": [
                        {
                            "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                            "evidence": "Promoted from Brain review.",
                        }
                    ]
                }
            },
        ), patch.object(persona_bundle_context_module, "resolve_persona_bundle_root", return_value=Path("/tmp/does-not-exist")):
            chunks = persona_bundle_context_module.retrieve_bundle_persona_chunks(
                query_text="CEO prompting and agent usage",
                category="value",
                channel="linkedin_post",
                top_k=3,
            )

        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn("5.2x more likely", (chunks[0].get("chunk") or ""))
        self.assertEqual(chunks[0].get("metadata", {}).get("source_kind"), "committed_overlay")

    def test_persona_bundle_context_overlay_chunks_include_typed_metadata(self) -> None:
        with patch.object(
            persona_bundle_context_module,
            "build_committed_persona_overlay",
            return_value={
                "by_target_file": {
                    "history/initiatives.md": [
                        {
                            "canon_value": "Strengthens Johnnie's positioning as an AI systems operator grounded in real execution.",
                            "canon_proof": "Brain, Ops, planner, and briefs now share the same routed workspace state.",
                            "artifact_summary": "AI Clone / Brain system rollout",
                            "proof_strength": "strong",
                        }
                    ]
                }
            },
        ):
            chunks = persona_bundle_context_module.load_committed_overlay_chunks()

        self.assertEqual(len(chunks), 1)
        metadata = chunks[0].get("metadata", {})
        self.assertEqual(metadata.get("memory_role"), "proof")
        self.assertEqual(metadata.get("proof_kind"), "initiative")
        self.assertEqual(metadata.get("proof_strength"), "strong")
        self.assertTrue(metadata.get("artifact_backed"))
        self.assertIn("proof_anchor", metadata.get("usage_modes", []))

    def test_persona_bundle_context_prefers_semantic_initiative_overlay_fields(self) -> None:
        with patch.object(
            persona_bundle_context_module,
            "build_committed_persona_overlay",
            return_value={
                "by_target_file": {
                    "history/initiatives.md": [
                        {
                            "content": "Raw review-shaped content that should not lead.",
                            "evidence": "Reflective note that should not lead.",
                            "canon_value": "Strengthens Johnnie's positioning as an AI systems operator grounded in real execution.",
                            "canon_proof": "5.2x success signal tied to visible prompting and agent usage.",
                        }
                    ]
                }
            },
        ), patch.object(persona_bundle_context_module, "resolve_persona_bundle_root", return_value=Path("/tmp/does-not-exist")):
            chunks = persona_bundle_context_module.retrieve_bundle_persona_chunks(
                query_text="AI systems operator",
                category="value",
                channel="linkedin_post",
                top_k=3,
            )

        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn("AI systems operator grounded in real execution", (chunks[0].get("chunk") or ""))
        self.assertIn("5.2x success signal tied to visible prompting and agent usage", (chunks[0].get("chunk") or ""))
        self.assertNotIn("Raw review-shaped content", (chunks[0].get("chunk") or ""))

    def test_content_generation_prefers_bundle_persona_chunks(self) -> None:
        class _FakeResponse:
            def __init__(self, content: str) -> None:
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResponse("Bundle-first option")

        class _FakeChat:
            def __init__(self) -> None:
                self.completions = _FakeCompletions()

        class _FakeClient:
            def __init__(self) -> None:
                self.chat = _FakeChat()

        bundle_chunk = {
            "chunk": "Teams fail when they chase tools before workflow clarity.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "source": "canonical persona bundle",
                "source_kind": "canonical_bundle",
                "prompt_section": "CORE CANON",
                "memory_role": "core",
            },
        }
        context_pack = content_context_service_module.ContentGenerationContext(
            persona_chunks=[bundle_chunk],
            example_chunks=[],
            core_chunks=[bundle_chunk],
            proof_chunks=[],
            story_chunks=[],
            ambient_chunks=[],
            topic_anchor_chunks=[bundle_chunk],
            proof_anchor_chunks=[bundle_chunk],
            story_anchor_chunks=[],
            grounding_mode="proof_ready",
            grounding_reason="Artifact-backed proof is available.",
            framing_modes=["operator_lesson", "contrarian_reframe", "drama_tension"],
            primary_claims=["Teams fail when they chase tools before workflow clarity."],
            proof_packets=["Workflow clarity -> Teams fail when they chase tools before workflow clarity."],
            story_beats=[],
            disallowed_moves=["Do not invent metrics."],
            persona_context_summary="Teams fail when they chase tools before workflow clarity.",
        )

        with patch.object(
            content_generation_module,
            "build_content_generation_context",
            return_value=context_pack,
        ), patch.object(
            content_generation_module,
            "get_openai_client",
            return_value=_FakeClient(),
        ):
            response = self.client.post(
                "/api/content-generation/generate",
                json={
                    "user_id": "default-user",
                    "topic": "workflow clarity",
                    "content_type": "linkedin_post",
                    "category": "value",
                    "audience": "tech_ai",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("success"))
        self.assertIn("workflow clarity", (payload.get("persona_context") or "").lower())
        self.assertEqual(payload.get("options"), ["Bundle-first option"])

    def test_content_generation_context_service_splits_typed_lanes_and_preserves_framing_modes(self) -> None:
        bundle_chunks = [
            {
                "chunk": "Builds and translates AI execution patterns into clear operator guidance.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "identity/philosophy.md",
                    "file_name": "identity/philosophy.md",
                    "memory_role": "core",
                    "proof_strength": "none",
                    "artifact_backed": False,
                },
            },
            {
                "chunk": "AI Clone / Brain System. Proof: Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
                "persona_tag": "VENTURES",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "history/initiatives.md",
                    "file_name": "history/initiatives.md",
                    "memory_role": "proof",
                    "proof_strength": "strong",
                    "artifact_backed": True,
                },
            },
            {
                "chunk": "When I stopped letting handoffs stay vague, the work moved faster and the team trusted the system more.",
                "persona_tag": "EXPERIENCES",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "history/story_bank.md",
                    "file_name": "history/story_bank.md",
                    "memory_role": "story",
                    "proof_strength": "medium",
                    "artifact_backed": False,
                },
            },
        ]
        legacy_support = {
            "chunk": "The best operator posts create tension first, then land the lesson cleanly.",
            "persona_tag": "EXPERIENCES",
            "metadata": {
                "source": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
                "file_name": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
            },
        }
        legacy_example = {
            "chunk": "Real talk: vague handoffs are where good ideas go to die.",
            "persona_tag": "LINKEDIN_EXAMPLES",
            "metadata": {
                "source": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
                "file_name": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
            },
        }

        def _fake_retrieve_similar(**kwargs):
            if kwargs.get("tag_filter") == ["LINKEDIN_EXAMPLES"]:
                return [legacy_example]
            return [legacy_support]

        with patch.object(content_context_service_module, "embed_text", return_value=[0.1, 0.2, 0.3]), patch.object(
            content_context_service_module,
            "retrieve_bundle_persona_chunks",
            return_value=bundle_chunks,
        ), patch.object(
            content_context_service_module,
            "retrieve_weighted",
            return_value=[],
        ), patch.object(
            content_context_service_module,
            "retrieve_similar",
            side_effect=_fake_retrieve_similar,
        ):
            context_pack = content_context_service_module.build_content_generation_context(
                user_id="default-user",
                topic="agent orchestration",
                context="",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
            )

        self.assertEqual(context_pack.grounding_mode, "proof_ready")
        self.assertTrue(any(chunk.get("metadata", {}).get("memory_role") == "core" for chunk in context_pack.core_chunks))
        self.assertTrue(any(chunk.get("metadata", {}).get("memory_role") == "proof" for chunk in context_pack.proof_chunks))
        self.assertTrue(any(chunk.get("metadata", {}).get("memory_role") == "story" for chunk in context_pack.story_chunks))
        self.assertIn("contrarian_reframe", context_pack.framing_modes)
        self.assertIn("drama_tension", context_pack.framing_modes)
        self.assertGreaterEqual(len(context_pack.primary_claims), 1)
        self.assertGreaterEqual(len(context_pack.proof_packets), 1)
        self.assertEqual(context_pack.example_chunks, [legacy_example])

    def test_content_generation_context_service_drops_off_domain_tech_ai_support_and_fails_closed(self) -> None:
        bundle_chunks = [
            {
                "chunk": "Builds and translates AI execution patterns into clear operator guidance.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "identity/philosophy.md",
                    "file_name": "identity/philosophy.md",
                    "memory_role": "core",
                    "proof_strength": "none",
                    "artifact_backed": False,
                },
            },
            {
                "chunk": "Salesforce migration across three admissions instances reduced confusion for counselors and program launches.",
                "persona_tag": "VENTURES",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "history/initiatives.md",
                    "file_name": "history/initiatives.md",
                    "memory_role": "proof",
                    "proof_strength": "strong",
                    "artifact_backed": True,
                },
            },
            {
                "chunk": "At Fordham, clear documentation helped the team stop duplicating work across enrollment seasons.",
                "persona_tag": "EXPERIENCES",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "history/story_bank.md",
                    "file_name": "history/story_bank.md",
                    "memory_role": "story",
                    "proof_strength": "medium",
                    "artifact_backed": False,
                },
            },
        ]

        with patch.object(content_context_service_module, "embed_text", return_value=[0.1, 0.2, 0.3]), patch.object(
            content_context_service_module,
            "retrieve_bundle_persona_chunks",
            return_value=bundle_chunks,
        ), patch.object(
            content_context_service_module,
            "retrieve_weighted",
            return_value=[],
        ), patch.object(
            content_context_service_module,
            "retrieve_similar",
            return_value=[],
        ):
            context_pack = content_context_service_module.build_content_generation_context(
                user_id="default-user",
                topic="agent orchestration",
                context="",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
            )

        combined_text = " ".join(chunk.get("chunk", "") for chunk in context_pack.persona_chunks)
        self.assertEqual(context_pack.grounding_mode, "principle_only")
        self.assertFalse(any("Salesforce migration" in chunk.get("chunk", "") for chunk in context_pack.proof_anchor_chunks))
        self.assertEqual(context_pack.story_anchor_chunks, [])
        self.assertNotIn("Salesforce migration", combined_text)
        self.assertNotIn("Fordham", combined_text)

    def test_build_content_prompt_includes_grounding_mode_and_framing_modes(self) -> None:
        persona_chunks = [
            {
                "chunk": "Builds and translates AI execution patterns into clear operator guidance.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON", "memory_role": "core"},
            },
            {
                "chunk": "AI Clone / Brain System. Proof: Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
                "persona_tag": "VENTURES",
                "metadata": {"prompt_section": "SUPPORTING CANON", "memory_role": "proof"},
            },
        ]

        prompt = content_generation_module.build_content_prompt(
            topic="agent orchestration",
            context="",
            content_type="linkedin_post",
            category="value",
            pacer_elements=[],
            tone="expert_direct",
            persona_chunks=persona_chunks,
            example_chunks=[],
            audience="tech_ai",
            topic_anchor_chunks=persona_chunks[:1],
            eligible_story_chunks=[],
            proof_anchor_chunks=persona_chunks[1:],
            grounding_mode="proof_ready",
            grounding_reason="Artifact-backed proof is available, so the post can lead with real evidence.",
            framing_modes=["contrarian_reframe", "drama_tension", "operator_lesson"],
            primary_claims=["Builds and translates AI execution patterns into clear operator guidance."],
            proof_packets=["AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views."],
            story_beats=[],
            disallowed_moves=["Do not invent outcomes."],
        )

        self.assertIn("## GROUNDING MODE:", prompt)
        self.assertIn("Current mode: `proof_ready`", prompt)
        self.assertIn("## APPROVED FRAMING MODES", prompt)
        self.assertIn("`contrarian_reframe`", prompt)
        self.assertIn("`drama_tension`", prompt)
        self.assertIn("## PRIMARY CLAIMS YOU MAY MAKE:", prompt)
        self.assertIn("## APPROVED PROOF PACKETS:", prompt)

    def test_build_content_prompt_principle_only_mode_forbids_named_case_study_reach(self) -> None:
        persona_chunks = [
            {
                "chunk": "Builds and translates AI execution patterns into clear operator guidance.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON", "memory_role": "core"},
            }
        ]

        prompt = content_generation_module.build_content_prompt(
            topic="agent orchestration",
            context="",
            content_type="linkedin_post",
            category="value",
            pacer_elements=[],
            tone="expert_direct",
            persona_chunks=persona_chunks,
            example_chunks=[],
            audience="tech_ai",
            topic_anchor_chunks=persona_chunks,
            eligible_story_chunks=[],
            proof_anchor_chunks=[],
            grounding_mode="principle_only",
            grounding_reason="No AI/operator proof survived the domain gate, so the post should stay principle-led.",
            framing_modes=["operator_lesson", "warning"],
            primary_claims=["Builds and translates AI execution patterns into clear operator guidance."],
            proof_packets=[],
            story_beats=[],
            disallowed_moves=["Do not use named metrics, case studies, employers, or systems unless they appear directly in the approved primary claims."],
        )

        self.assertIn("`principle_only`", prompt)
        self.assertIn("do not reach for named projects, employers, metrics, or case studies", prompt.lower())
        self.assertIn("Only reference named ventures, employers, systems, programs, or stories if they appear in the TOPIC / ELIGIBLE STORY / PROOF anchors above", prompt)

    def test_option_mentions_approved_proof_requires_meaningful_overlap(self) -> None:
        proof_packets = [
            "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views."
        ]

        self.assertTrue(
            content_generation_module.option_mentions_approved_proof(
                "Brain and Ops now read from the same workspace state instead of isolated views.",
                proof_packets,
            )
        )
        self.assertFalse(
            content_generation_module.option_mentions_approved_proof(
                "Agent orchestration matters because clarity is important for good workflows.",
                proof_packets,
            )
        )

    def test_enforce_grounding_on_options_repairs_generic_proof_ready_drafts(self) -> None:
        class _FakeResponse:
            def __init__(self, content: str) -> None:
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResponse(
                    "Brain and Ops now read from the same workspace state instead of isolated views.\n---OPTION---\n"
                    "Daily briefs and planner share the same routed workspace state.\n---OPTION---\n"
                    "Long-form routing now flows through the same shared workspace state."
                )

        class _FakeChat:
            def __init__(self) -> None:
                self.completions = _FakeCompletions()

        class _FakeClient:
            def __init__(self) -> None:
                self.chat = _FakeChat()

        repaired = content_generation_module.enforce_grounding_on_options(
            client=_FakeClient(),
            topic="agent orchestration",
            audience="tech_ai",
            content_type="linkedin_post",
            grounding_mode="proof_ready",
            rough_options=[
                "Agent orchestration helps teams stay aligned.",
                "Clear workflows matter for AI systems.",
                "Good orchestration keeps things efficient.",
            ],
            primary_claims=["Builds and translates AI execution patterns into clear operator guidance."],
            proof_packets=[
                "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views."
            ],
            framing_modes=["operator_lesson", "contrarian_reframe", "drama_tension"],
        )

        self.assertEqual(len(repaired), 3)
        self.assertTrue(all("workspace state" in option.lower() or "brain" in option.lower() for option in repaired))

    def test_curate_persona_prompt_chunks_orders_core_support_legacy_then_retrieval(self) -> None:
        bundle_chunks = [
            {
                "chunk": "Core philosophy about workflow clarity.",
                "persona_tag": "PHILOSOPHY",
                "source_file_id": "identity/philosophy.md",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "identity/philosophy.md",
                    "file_name": "identity/philosophy.md",
                },
            },
            {
                "chunk": "Supporting story about stakeholder trust.",
                "persona_tag": "EXPERIENCES",
                "source_file_id": "history/story_bank.md",
                "metadata": {
                    "source": "canonical persona bundle",
                    "source_kind": "canonical_bundle",
                    "bundle_path": "history/story_bank.md",
                    "file_name": "history/story_bank.md",
                },
            },
        ]
        legacy_support_chunks = [
            {
                "chunk": "Legacy bridge-builder positioning from the optimized persona file.",
                "persona_tag": "BIO_FACTS",
                "metadata": {"source": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md", "file_name": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md"},
            }
        ]
        retrieved_chunks = [
            {
                "chunk": "Fresh retrieval support from a newer working note.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"source": "operator-note.md", "file_name": "operator-note.md"},
            }
        ]

        curated = content_generation_module.curate_persona_prompt_chunks(
            bundle_chunks=bundle_chunks,
            legacy_support_chunks=legacy_support_chunks,
            retrieved_chunks=retrieved_chunks,
            top_k=4,
        )

        sections = [item.get("metadata", {}).get("prompt_section") for item in curated]
        self.assertEqual(
            sections,
            ["CORE CANON", "SUPPORTING CANON", "LEGACY SUPPORT", "RETRIEVAL SUPPORT"],
        )

    def test_retrieve_curated_example_chunks_prefers_legacy_linkedin_examples(self) -> None:
        calls = []
        legacy_example = {
            "chunk": "Legacy LinkedIn example",
            "metadata": {"source": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md", "file_name": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md"},
        }

        def _fake_retrieve_similar(**kwargs):
            calls.append(kwargs)
            if kwargs.get("source_filter") == "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md" and kwargs.get("tag_filter") == ["LINKEDIN_EXAMPLES"]:
                return [legacy_example]
            return []

        with patch.object(content_generation_module, "retrieve_similar", side_effect=_fake_retrieve_similar):
            results = content_generation_module.retrieve_curated_example_chunks(
                user_id="default-user",
                query_embedding=[0.1, 0.2, 0.3],
                content_type="linkedin_post",
                top_k=3,
            )

        self.assertEqual(results, [legacy_example])
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(calls[0].get("source_filter"), "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md")
        self.assertEqual(calls[0].get("tag_filter"), ["LINKEDIN_EXAMPLES"])

    def test_select_eligible_story_chunks_requires_topic_overlap(self) -> None:
        persona_chunks = [
            {
                "chunk": "Operator clarity matters more than hype for AI systems.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON"},
            },
            {
                "chunk": "Fashion journey story about closet organization and style misses.",
                "persona_tag": "VENTURES",
                "metadata": {"prompt_section": "LEGACY SUPPORT"},
            },
            {
                "chunk": "Built workflow automation around prompting and agent handoffs.",
                "persona_tag": "VENTURES",
                "metadata": {"prompt_section": "SUPPORTING CANON"},
            },
        ]

        stories = content_generation_module.select_eligible_story_chunks(
            persona_chunks,
            topic="agent orchestration",
            audience="tech_ai",
            limit=3,
        )

        self.assertEqual(len(stories), 1)
        self.assertIn("agent handoffs", stories[0].get("chunk", ""))

    def test_build_content_prompt_warns_when_no_relevant_story_anchor_exists(self) -> None:
        persona_chunks = [
            {
                "chunk": "Teams fail when they chase tools before workflow clarity.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON"},
            },
            {
                "chunk": "Fashion journey story about closet organization and style misses.",
                "persona_tag": "VENTURES",
                "metadata": {"prompt_section": "LEGACY SUPPORT"},
            },
        ]

        prompt = content_generation_module.build_content_prompt(
            topic="agent orchestration",
            context="",
            content_type="linkedin_post",
            category="value",
            pacer_elements=[],
            tone="expert_direct",
            persona_chunks=persona_chunks,
            example_chunks=[],
            audience="tech_ai",
        )

        self.assertIn("No directly relevant story anchor found. Do not force one.", prompt)
        self.assertIn("Stay in the operator / AI systems lane", prompt)

    def test_select_proof_anchor_chunks_prefers_evidence_bearing_operator_chunks(self) -> None:
        persona_chunks = [
            {
                "chunk": "Teams fail when they chase tools before workflow clarity.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON"},
            },
            {
                "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. Evidence: Active AI Clone / Brain system build work and public operator framing.",
                "persona_tag": "BIO_FACTS",
                "metadata": {"prompt_section": "CORE CANON"},
            },
            {
                "chunk": "Created more structured, durable operating surfaces across Brain and Workspace.",
                "persona_tag": "EXPERIENCES",
                "metadata": {"prompt_section": "SUPPORTING CANON"},
            },
        ]

        proof_chunks = content_generation_module.select_proof_anchor_chunks(
            persona_chunks,
            topic="agent orchestration",
            audience="tech_ai",
            limit=2,
        )

        self.assertGreaterEqual(len(proof_chunks), 1)
        self.assertIn("Evidence:", proof_chunks[0].get("chunk", ""))

    def test_select_proof_anchor_chunks_skips_low_focus_numeric_wins_for_operator_topics(self) -> None:
        persona_chunks = [
            {
                "chunk": "AI Clone / Brain System. Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance. Value: Proves Johnnie can turn messy AI/operator work into durable operating surfaces that support memory, planning, review, and content generation. Proof: Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
                "persona_tag": "VENTURES",
                "metadata": {"prompt_section": "SUPPORTING CANON"},
            },
            {
                "chunk": "Best Practices work improved front row utilization 300% and MC Follow-up 30% while also increasing team participation. Use when: AI systems, workflow clarity, operating cadence, restart-safe execution.",
                "persona_tag": "EXPERIENCES",
                "metadata": {"prompt_section": "SUPPORTING CANON"},
            },
        ]

        proof_chunks = content_generation_module.select_proof_anchor_chunks(
            persona_chunks,
            topic="workflow clarity",
            audience="tech_ai",
            limit=4,
        )

        combined_text = " ".join(chunk.get("chunk", "") for chunk in proof_chunks)
        self.assertIn("AI Clone / Brain System", combined_text)
        self.assertNotIn("front row utilization 300%", combined_text)

    def test_build_content_prompt_includes_proof_anchors_for_operator_topics(self) -> None:
        persona_chunks = [
            {
                "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. Evidence: Active AI Clone / Brain system build work and public operator framing.",
                "persona_tag": "BIO_FACTS",
                "metadata": {"prompt_section": "CORE CANON"},
            },
            {
                "chunk": "Builds and translates AI execution patterns into clear operator guidance.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON"},
            },
        ]

        prompt = content_generation_module.build_content_prompt(
            topic="agent orchestration",
            context="",
            content_type="linkedin_post",
            category="value",
            pacer_elements=[],
            tone="expert_direct",
            persona_chunks=persona_chunks,
            example_chunks=[],
            audience="tech_ai",
        )

        self.assertIn("## PROOF ANCHORS:", prompt)
        self.assertIn("Each option must include at least one concrete proof anchor", prompt)
        self.assertIn("Do not translate one metric into another", prompt)

    def test_build_content_prompt_strips_use_when_from_persona_and_proof_sections(self) -> None:
        persona_chunks = [
            {
                "chunk": "Unified Brain, Ops, daily briefs, and planner around one shared snapshot contract so operator context travels across the system instead of living in isolated tools. Use when: AI systems, workflow clarity, operating cadence, restart-safe execution.",
                "persona_tag": "BIO_FACTS",
                "metadata": {"prompt_section": "CORE CANON"},
            }
        ]

        prompt = content_generation_module.build_content_prompt(
            topic="workflow clarity",
            context="",
            content_type="linkedin_post",
            category="value",
            pacer_elements=[],
            tone="expert_direct",
            persona_chunks=persona_chunks,
            example_chunks=[],
            audience="tech_ai",
        )

        self.assertIn("Unified Brain, Ops, daily briefs, and planner around one shared snapshot contract", prompt)
        self.assertNotIn("Use when: AI systems, workflow clarity, operating cadence, restart-safe execution.", prompt)

    def test_build_content_prompt_hides_off_topic_support_chunks_for_operator_topics(self) -> None:
        persona_chunks = [
            {
                "chunk": "Builds and translates AI execution patterns into clear operator guidance.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON"},
            },
            {
                "chunk": "AI Clone / Brain System. Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance. Value: Proves Johnnie can turn messy AI/operator work into durable operating surfaces that support memory, planning, review, and content generation. Proof: Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
                "persona_tag": "VENTURES",
                "metadata": {"prompt_section": "SUPPORTING CANON"},
            },
            {
                "chunk": "When I launched the wiki for Fordham MSW documentation, version control was a nightmare until I gathered input and created a quality-assurance process.",
                "persona_tag": "EXPERIENCES",
                "metadata": {"prompt_section": "SUPPORTING CANON"},
            },
        ]

        prompt = content_generation_module.build_content_prompt(
            topic="agent orchestration",
            context="",
            content_type="linkedin_post",
            category="value",
            pacer_elements=[],
            tone="expert_direct",
            persona_chunks=persona_chunks,
            example_chunks=[],
            audience="tech_ai",
        )

        self.assertIn("AI Clone / Brain System", prompt)
        self.assertNotIn("Fordham MSW documentation", prompt)

    def test_filter_example_chunks_by_topic_drops_off_topic_legacy_examples(self) -> None:
        example_chunks = [
            {
                "chunk": "When I launched the wiki for Fordham MSW documentation, version control was a nightmare until I created a quality-assurance process.",
                "persona_tag": "LINKEDIN_EXAMPLES",
                "metadata": {"source": "JOHNNIE_FIELDS_PERSONA.md"},
            },
            {
                "chunk": "Prompting plus agent orchestration works best when every handoff is explicit and every proof surface is shared.",
                "persona_tag": "LINKEDIN_EXAMPLES",
                "metadata": {"source": "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md"},
            },
        ]

        filtered = content_generation_module.filter_example_chunks_by_topic(
            example_chunks,
            topic="agent orchestration",
            audience="tech_ai",
            limit=3,
        )

        self.assertEqual(len(filtered), 1)
        self.assertIn("agent orchestration", filtered[0].get("chunk", "").lower())

    def test_social_belief_engine_load_persona_truth_includes_committed_claim_overlay(self) -> None:
        belief_engine_module.load_persona_truth.cache_clear()
        with patch.object(
            belief_engine_module,
            "build_committed_persona_overlay",
            return_value={
                "by_target_file": {
                    "identity/claims.md": [
                        {
                            "id": "claim-1",
                            "kind": "talking_point",
                            "label": "Claim",
                            "content": "Operator clarity matters more than hype.",
                            "evidence": "Promoted from Brain review.",
                        }
                    ]
                }
            },
        ):
            truth = belief_engine_module.load_persona_truth()

        self.assertTrue(any("Operator clarity matters more than hype." in row.get("claim", "") for row in truth["claims"]))
        belief_engine_module.load_persona_truth.cache_clear()

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
