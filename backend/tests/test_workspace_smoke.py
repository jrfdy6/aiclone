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
persona_route_module = importlib.import_module("app.routes.persona")
workspace_snapshot_module = importlib.import_module("app.services.workspace_snapshot_service")


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
        transcripts_dir = Path(cls.temp_dir.name) / "knowledge" / "aiclone" / "transcripts"
        ingestions_dir = Path(cls.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "fixture_transcript_asset"
        plans_dir.mkdir(parents=True, exist_ok=True)
        analytics_dir.mkdir(parents=True, exist_ok=True)
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

        cls.patches = [
            patch.object(workspace_snapshot_module, "LINKEDIN_ROOT", cls.fixture_root),
            patch.object(workspace_snapshot_module, "get_snapshot_payload", lambda *args, **kwargs: None),
            patch.object(workspace_snapshot_module, "upsert_snapshot", lambda *args, **kwargs: None),
            patch.object(workspace_snapshot_module, "_transcripts_root", lambda: transcripts_dir),
            patch.object(workspace_snapshot_module, "_ingestions_root", lambda: Path(cls.temp_dir.name) / "knowledge" / "ingestions"),
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

        with patch.object(
            workspace_snapshot_module.social_persona_review_service,
            "sync_long_form_worldview_reviews",
            return_value=sync_result,
        ) as sync_mock, patch.object(workspace_snapshot_module.persona_delta_service, "list_deltas", return_value=[]):
            snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()

        summary = snapshot.get("persona_review_summary") or {}
        self.assertEqual((summary.get("long_form_sync") or {}).get("created_count"), 2)
        self.assertEqual((summary.get("long_form_sync") or {}).get("resolved_stale"), 1)
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
