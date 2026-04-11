from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.models import PMCard, PersonaDelta
from app.services.social_expression_engine import social_expression_engine
from app.services.social_feed_builder_service import build_feed
from app.services.social_source_asset_service import build_source_asset_inventory
from app.services.workspace_snapshot_service import workspace_snapshot_service

social_feedback_module = importlib.import_module("app.services.social_feedback_service")
social_feed_builder_module = importlib.import_module("app.services.social_feed_builder_service")
social_long_form_signal_module = importlib.import_module("app.services.social_long_form_signal_service")
social_persona_review_module = importlib.import_module("app.services.social_persona_review_service")
daily_brief_module = importlib.import_module("app.services.daily_brief_service")
brief_reaction_module = importlib.import_module("app.services.brief_reaction_service")
persona_route_module = importlib.import_module("app.routes.persona")
brain_route_module = importlib.import_module("app.routes.brain")
content_generation_module = importlib.import_module("app.routes.content_generation")
content_context_service_module = importlib.import_module("app.services.content_generation_context_service")
workspace_snapshot_module = importlib.import_module("app.services.workspace_snapshot_service")
persona_queue_module = importlib.import_module("app.services.persona_review_queue_service")
persona_promotion_module = importlib.import_module("app.services.persona_promotion_service")
persona_promotion_utils_module = importlib.import_module("app.services.persona_promotion_utils")
persona_promotion_extractor_module = importlib.import_module("app.services.persona_promotion_extractor")
belief_engine_module = importlib.import_module("app.services.social_belief_engine")
persona_bundle_writer_module = importlib.import_module("app.services.persona_bundle_writer")
persona_bundle_context_module = importlib.import_module("app.services.persona_bundle_context_service")
linkedin_owner_review_module = importlib.import_module("app.services.linkedin_owner_review_service")
pm_card_service_module = importlib.import_module("app.services.pm_card_service")


class _FakeBriefReactionCursor:
    def __init__(self) -> None:
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params) -> None:
        if "INSERT INTO brief_reactions" not in query:
            raise AssertionError(f"Unexpected query executed in test: {query}")
        self.row = {
            "id": params[0],
            "brief_id": params[1],
            "item_key": params[2],
            "item_title": params[3],
            "reaction_kind": params[4],
            "text": params[5],
            "source_kind": params[6],
            "source_url": params[7],
            "source_path": params[8],
            "linked_delta_id": params[9],
            "linked_capture_id": params[10],
            "metadata": getattr(params[11], "obj", params[11]),
            "created_at": datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
        }

    def fetchone(self):
        return self.row


class _FakeBriefReactionConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FakeBriefReactionCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, row_factory=None):
        return self.cursor_instance

    def commit(self) -> None:
        return None


class _FakeBriefReactionPool:
    def __init__(self) -> None:
        self.connection_instance = _FakeBriefReactionConnection()

    def connection(self):
        return self.connection_instance


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

    def test_social_feed_builder_applies_curation_rules_and_platform_limits(self) -> None:
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

    def test_owner_review_assessment_conditional_approve_stays_revise(self) -> None:
        assessment = linkedin_owner_review_module._build_owner_review_assessment(
            {
                "packet_recommendation": "**Approve for scheduling after one lived proof line lands.**",
                "source_kind": "feezie_queue",
                "first_pass_draft": "This draft already has enough words to avoid the short-draft warning. " * 12,
                "proof_anchors": ["../../knowledge/persona/feeze/history/story_bank.md"],
                "core_angle": "Systems fail when context is fuzzy.",
                "why_now": "The audience is already seeing this problem in AI tooling.",
                "revision_goals": ["add one lived proof line"],
            }
        )

        self.assertEqual(assessment.get("suggested_decision"), "revise")
        self.assertEqual(assessment.get("confidence"), "high")
        self.assertIn("conditional", " ".join(assessment.get("reasons") or []).lower())
        self.assertEqual(assessment.get("missing_items"), [])

    def test_owner_review_assessment_approve_with_missing_proof_stays_cautious(self) -> None:
        assessment = linkedin_owner_review_module._build_owner_review_assessment(
            {
                "packet_recommendation": "**Approve for scheduling**",
                "source_kind": "feezie_queue",
                "first_pass_draft": "This draft already has enough words to avoid the short-draft warning. " * 3,
                "proof_anchors": [],
                "core_angle": "Cheap models win when the surrounding system is better designed.",
                "why_now": "",
            }
        )

        self.assertEqual(assessment.get("suggested_decision"), "approve")
        self.assertEqual(assessment.get("confidence"), "medium")
        self.assertIn("The owner packet already recommends approval or scheduling.", assessment.get("reasons") or [])
        self.assertIn("No proof anchors are attached yet.", assessment.get("missing_items") or [])
        self.assertIn("The timing or audience consequence is not stated explicitly.", assessment.get("missing_items") or [])

    def test_owner_review_assessment_park_with_multiple_gaps_raises_confidence(self) -> None:
        assessment = linkedin_owner_review_module._build_owner_review_assessment(
            {
                "packet_recommendation": "**Park for later**",
                "source_kind": "feezie_queue",
                "first_pass_draft": "",
                "proof_anchors": [],
                "core_angle": "",
                "why_now": "",
            }
        )

        self.assertEqual(assessment.get("suggested_decision"), "park")
        self.assertEqual(assessment.get("confidence"), "high")
        self.assertIn("parking", " ".join(assessment.get("reasons") or []).lower())
        self.assertIn("There is no first-pass draft attached yet.", assessment.get("missing_items") or [])
        self.assertIn("No proof anchors are attached yet.", assessment.get("missing_items") or [])
        self.assertIn("The core angle is not stated explicitly.", assessment.get("missing_items") or [])
        self.assertIn("The timing or audience consequence is not stated explicitly.", assessment.get("missing_items") or [])

    def test_owner_review_assessment_latent_transform_surfaces_translation_gaps(self) -> None:
        assessment = linkedin_owner_review_module._build_owner_review_assessment(
            {
                "source_kind": "latent_transform",
                "latent_reason": "needs_context_translation",
                "first_pass_draft": "",
                "proof_anchors": [],
                "core_angle": "",
                "why_now": "",
                "revision_goals": [],
            }
        )

        self.assertEqual(assessment.get("suggested_decision"), "revise")
        self.assertEqual(assessment.get("confidence"), "high")
        self.assertIn("latent transform lane", " ".join(assessment.get("reasons") or []).lower())
        self.assertIn("The audience consequence is still implied rather than clearly named.", assessment.get("missing_items") or [])
        self.assertIn("There is no first-pass draft attached yet.", assessment.get("missing_items") or [])
        self.assertIn("No proof anchors are attached yet.", assessment.get("missing_items") or [])

    def test_linkedin_owner_review_route_reads_and_updates_drafts(self) -> None:
        drafts_dir = self.fixture_root / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        queue_path = drafts_dir / "queue_01.md"
        draft_path = drafts_dir / "feezie-001_cheap-models-better-systems.md"
        packet_path = drafts_dir / "feezie_owner_review_packet_20260409.md"

        queue_path.write_text(
            """# FEEZIE Draft Queue 01

## Queue

### FEEZIE-001 - Cheap models, better systems
- Lane: `ai`
- Format: long-form LinkedIn post
- Core angle: Constraint-led systems work beats model worship.
- Proof anchors:
  - `../../knowledge/persona/feeze/history/story_bank.md`
- Why now: the AI Clone / Brain work is active and publicly legible.
- Status: owner_review_draft (`drafts/feezie-001_cheap-models-better-systems.md`)
- Owner packet: latest `drafts/feezie_owner_review_packet_YYYYMMDD.md` entry for `FEEZIE-001`
- Approval status: `owner_review_required`
""",
            encoding="utf-8",
        )
        draft_path.write_text(
            """---
title: "Cheap models, better systems"
lane: ai
publish_posture: owner_review_required
---

# Cheap models, better systems

## Why this draft exists
- Queue item: `FEEZIE-001`

## First-pass draft

This is the first pass.

## Owner notes
- Keep this grounded in proof.
""",
            encoding="utf-8",
        )
        packet_path.write_text(
            """# FEEZIE Owner Review Packet

## FEEZIE-001 — Cheap models, better systems
- **Lane / Format:** `ai` | long-form post
- **Recommended action:** **Approve for scheduling**

**Owner decision**
- [ ] Approve for scheduling
- [ ] Revise (note specifics below)
- [ ] Park for later

**Draft copy**
> This is the first pass.

**Revision notes (if needed):**

---

## Next steps after owner review
1. Ping Jean-Claude.
""",
            encoding="utf-8",
        )

        response = self.client.get("/api/workspace/linkedin-os-owner-review")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        items = payload.get("items") or []
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("queue_id"), "FEEZIE-001")
        self.assertEqual(items[0].get("publish_posture"), "owner_review_required")
        self.assertIsNone(items[0].get("current_notes"))
        self.assertIn("This is the first pass.", items[0].get("first_pass_draft") or "")
        self.assertEqual((items[0].get("system_assessment") or {}).get("suggested_decision"), "approve")

        created_card = PMCard(
            id="owner-review-card-1",
            title="Schedule approved FEEZIE draft - FEEZIE-001",
            owner="Neo",
            status="todo",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id="FEEZIE-001",
            payload={"workspace_key": "linkedin-os"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def fake_create_card(payload):
            self.assertEqual(payload.payload.get("workspace_key"), "linkedin-os")
            self.assertEqual((payload.payload.get("owner_review") or {}).get("decision"), "approve")
            self.assertIsNone(payload.link_id)
            return created_card

        def fake_dispatch_card(card_id, payload):
            self.assertEqual(card_id, created_card.id)
            self.assertEqual(payload.execution_state, "queued")
            return SimpleNamespace(
                card=created_card,
                queue_entry=SimpleNamespace(target_agent="Jean-Claude", execution_state="queued"),
            )

        with (
            patch.object(linkedin_owner_review_module.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(linkedin_owner_review_module.pm_card_service, "create_card", side_effect=fake_create_card),
            patch.object(linkedin_owner_review_module.pm_card_service, "dispatch_card", side_effect=fake_dispatch_card),
        ):
            update_response = self.client.post(
                "/api/workspace/linkedin-os-owner-review/FEEZIE-001",
                json={"decision": "approve", "notes": "Ship this first."},
            )
        self.assertEqual(update_response.status_code, 200)
        updated_payload = update_response.json()
        updated_item = (updated_payload.get("items") or [None])[0]
        self.assertEqual(updated_item.get("current_decision"), "approve")
        self.assertEqual(updated_item.get("approval_status"), "owner_approved")
        self.assertEqual(updated_item.get("publish_posture"), "approved")
        self.assertEqual(updated_item.get("current_notes"), "Ship this first.")
        self.assertEqual((updated_payload.get("workflow") or {}).get("status"), "queued")
        self.assertIn("Jean-Claude follow-up is queued", (updated_payload.get("workflow") or {}).get("message") or "")

        self.assertIn("Approval status: `owner_approved`", queue_path.read_text(encoding="utf-8"))
        updated_draft = draft_path.read_text(encoding="utf-8")
        self.assertIn("publish_posture: approved", updated_draft)
        self.assertIn("owner_decision: approve", updated_draft)
        updated_packet = packet_path.read_text(encoding="utf-8")
        self.assertIn("- [x] Approve for scheduling", updated_packet)
        self.assertIn("Ship this first.", updated_packet)

    def test_pm_owner_review_sync_and_card_action_route(self) -> None:
        drafts_dir = self.fixture_root / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        queue_path = drafts_dir / "queue_01.md"
        draft_path = drafts_dir / "feezie-002_quiet-inefficiency-is-still-failure.md"
        packet_path = drafts_dir / "feezie_owner_review_packet_20260409_b.md"

        queue_path.write_text(
            """# FEEZIE Draft Queue 01

## Queue

### FEEZIE-002 - Quiet inefficiency is still failure
- Lane: `ops-pm`
- Format: long-form LinkedIn post
- Core angle: Quiet inefficiency is still a real operating cost.
- Proof anchors:
  - `../../knowledge/persona/feeze/history/story_bank.md`
- Why now: the operating signal is visible right now.
- Status: owner_review_draft (`drafts/feezie-002_quiet-inefficiency-is-still-failure.md`)
- Owner packet: latest `drafts/feezie_owner_review_packet_YYYYMMDD.md` entry for `FEEZIE-002`
- Approval status: `owner_review_required`
""",
            encoding="utf-8",
        )
        draft_path.write_text(
            """---
title: "Quiet inefficiency is still failure"
lane: ops-pm
publish_posture: owner_review_required
---

# Quiet inefficiency is still failure

## Why this draft exists
- Queue item: `FEEZIE-002`

## First-pass draft

This is the second first pass.

## Owner notes
- Keep the operating examples specific.
""",
            encoding="utf-8",
        )
        packet_path.write_text(
            """# FEEZIE Owner Review Packet

## FEEZIE-002 — Quiet inefficiency is still failure
- **Lane / Format:** `ops-pm` | long-form post
- **Recommended action:** **Approve for scheduling**

**Owner decision**
- [ ] Approve for scheduling
- [ ] Revise (note specifics below)
- [ ] Park for later

**Draft copy**
> This is the second first pass.

**Revision notes (if needed):**

---
""",
            encoding="utf-8",
        )

        pending_card = PMCard(
            id="11111111-1111-4111-8111-111111111112",
            title="Owner review - FEEZIE-002 - Quiet inefficiency is still failure",
            owner="Neo",
            status="review",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id="FEEZIE-002",
            payload={
                "workspace_key": "linkedin-os",
                "owner_review": {"queue_id": "FEEZIE-002"},
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        created_payloads = []

        def fake_create_pending_card(payload):
            owner_review = payload.payload.get("owner_review") or {}
            queue_id = owner_review.get("queue_id")
            created_payloads.append({"queue_id": queue_id, "title": payload.title})
            self.assertEqual(payload.status, "review")
            self.assertIsNone(payload.link_id)
            if queue_id == "FEEZIE-002":
                return pending_card
            return PMCard(
                id=f"owner-review-{len(created_payloads)}",
                title=payload.title,
                owner="Neo",
                status="review",
                source="openclaw:workspace-owner-review",
                link_type="owner_review",
                link_id=payload.link_id,
                payload=payload.payload,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        with (
            patch.object(linkedin_owner_review_module.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(linkedin_owner_review_module.pm_card_service, "create_card", side_effect=fake_create_pending_card),
        ):
            sync_response = self.client.post("/api/pm/owner-review/sync")
        self.assertEqual(sync_response.status_code, 200)
        sync_payload = sync_response.json()
        self.assertGreaterEqual(sync_payload.get("pending_count") or 0, 1)
        self.assertIn("FEEZIE-002", {entry["queue_id"] for entry in created_payloads})
        self.assertIn("11111111-1111-4111-8111-111111111112", sync_payload.get("created_card_ids") or [])

        def fake_update_card(_card_id, patch):
            return pending_card.model_copy(
                update={
                    "title": patch.title if patch.title is not None else pending_card.title,
                    "status": patch.status if patch.status is not None else pending_card.status,
                    "payload": patch.payload if patch.payload is not None else pending_card.payload,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        def fake_dispatch_card(card_id, payload):
            self.assertEqual(card_id, pending_card.id)
            self.assertEqual(payload.execution_state, "queued")
            dispatched_card = pending_card.model_copy(
                update={
                    "title": "Schedule approved FEEZIE draft - FEEZIE-002",
                    "status": "todo",
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            return SimpleNamespace(
                card=dispatched_card,
                queue_entry=SimpleNamespace(target_agent="Jean-Claude", execution_state="queued"),
            )

        with (
            patch.object(linkedin_owner_review_module.pm_card_service, "get_card", return_value=pending_card),
            patch.object(linkedin_owner_review_module.pm_card_service, "find_active_card_by_trigger_key", return_value=pending_card),
            patch.object(linkedin_owner_review_module.pm_card_service, "update_card", side_effect=fake_update_card),
            patch.object(linkedin_owner_review_module.pm_card_service, "dispatch_card", side_effect=fake_dispatch_card),
        ):
            action_response = self.client.post(
                f"/api/pm/cards/{pending_card.id}/owner-review",
                json={"decision": "approve", "notes": "Use this one next."},
            )
        self.assertEqual(action_response.status_code, 200)
        action_payload = action_response.json()
        self.assertEqual((action_payload.get("workflow") or {}).get("status"), "queued")
        self.assertEqual(action_payload.get("source_card_id"), pending_card.id)
        self.assertIn("Jean-Claude follow-up is queued", (action_payload.get("workflow") or {}).get("message") or "")

        self.assertIn("Approval status: `owner_approved`", queue_path.read_text(encoding="utf-8"))
        updated_draft = draft_path.read_text(encoding="utf-8")
        self.assertIn("publish_posture: approved", updated_draft)
        updated_packet = packet_path.read_text(encoding="utf-8")
        self.assertIn("- [x] Approve for scheduling", updated_packet)
        self.assertIn("Use this one next.", updated_packet)

    def test_linkedin_owner_review_route_reads_and_updates_latent_transform_drafts(self) -> None:
        drafts_dir = self.fixture_root / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        draft_path = drafts_dir / "2026-04-10_the-shape-of-the-thing-latent-transform.md"
        execution_log = self.fixture_root / "memory" / "execution_log.md"

        draft_path.write_text(
            """---
title: "The Shape of the Thing"
draft_kind: owner_review
source_kind: latent_transform
idea_id: idea-123
lane: ai
publish_posture: owner_review_required
source_url: https://example.com/the-shape-of-the-thing
source_path: workspaces/linkedin-content-os/research/source.md
latent_reason: needs_context_translation
transform_type: context_translation
---

# The Shape of the Thing

## Why this draft exists
- This source was preserved as `needs_context_translation` instead of discarded.
- Priority lane: `AI systems and operator clarity`

## Source signal
- Source file: `workspaces/linkedin-content-os/research/source.md`
- Source URL: https://example.com/the-shape-of-the-thing
- Source summary: Useful signal about AI workflow interfaces.
- Why it matters: AI workflow design, operator judgment, and implementation signals

## Transform brief
- Proposed angle: If the workflow is unclear, AI just scales confusion.
- Owner question: What concrete change should operators notice if this is true?
- Proof prompt: AI Clone / Brain System rebuild notes
- Promotion rule: Promote only after one lived proof line and one audience consequence.

## Revision goals
- add one lived proof line

## First-pass transformed draft

This is the latent first pass.

## Owner notes
- Add one proof line before approval.
""",
            encoding="utf-8",
        )

        response = self.client.get("/api/workspace/linkedin-os-owner-review")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        items = payload.get("items") or []
        latent_item = next(
            item
            for item in items
            if item.get("entry_kind") == "supplemental" and item.get("title") == "The Shape of the Thing"
        )
        self.assertTrue((latent_item.get("queue_id") or "").startswith("LATENT-"))
        self.assertEqual(latent_item.get("source_kind"), "latent_transform")
        self.assertEqual(latent_item.get("entry_kind"), "supplemental")
        self.assertIn("This is the latent first pass.", latent_item.get("first_pass_draft") or "")
        self.assertEqual((latent_item.get("system_assessment") or {}).get("suggested_decision"), "revise")

        created_card = PMCard(
            id="owner-review-card-latent-1",
            title="Revise FEEZIE draft - latent",
            owner="Neo",
            status="todo",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id=str(latent_item.get("queue_id")),
            payload={"workspace_key": "linkedin-os"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        def fake_create_card(payload):
            owner_review = payload.payload.get("owner_review") or {}
            self.assertEqual(payload.payload.get("workspace_key"), "linkedin-os")
            self.assertEqual(owner_review.get("decision"), "revise")
            self.assertEqual(owner_review.get("source_kind"), "latent_transform")
            self.assertEqual((owner_review.get("system_assessment") or {}).get("suggested_decision"), "revise")
            self.assertIsNone(payload.link_id)
            return created_card

        def fake_dispatch_card(card_id, payload):
            self.assertEqual(card_id, created_card.id)
            self.assertEqual(payload.execution_state, "queued")
            return SimpleNamespace(
                card=created_card,
                queue_entry=SimpleNamespace(target_agent="Jean-Claude", execution_state="queued"),
            )

        with (
            patch.object(linkedin_owner_review_module.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(linkedin_owner_review_module.pm_card_service, "create_card", side_effect=fake_create_card),
            patch.object(linkedin_owner_review_module.pm_card_service, "dispatch_card", side_effect=fake_dispatch_card),
        ):
            update_response = self.client.post(
                f"/api/workspace/linkedin-os-owner-review/{latent_item['queue_id']}",
                json={"decision": "revise", "notes": "Add one lived proof line before approval."},
            )
        self.assertEqual(update_response.status_code, 200)
        updated_payload = update_response.json()
        updated_items = updated_payload.get("items") or []
        updated_item = next(item for item in updated_items if item.get("queue_id") == latent_item.get("queue_id"))
        self.assertEqual(updated_item.get("current_decision"), "revise")
        self.assertEqual(updated_item.get("current_notes"), "Add one lived proof line before approval.")
        self.assertEqual(updated_item.get("publish_posture"), "owner_review_required")
        self.assertEqual((updated_payload.get("workflow") or {}).get("status"), "queued")

        updated_draft = draft_path.read_text(encoding="utf-8")
        self.assertIn("owner_decision: revise", updated_draft)
        self.assertIn("owner_review_notes: \"Add one lived proof line before approval.\"", updated_draft)
        self.assertIn("publish_posture: owner_review_required", updated_draft)
        self.assertIn(str(latent_item.get("queue_id")), execution_log.read_text(encoding="utf-8"))

    def test_pm_owner_review_sync_includes_latent_transform_drafts(self) -> None:
        drafts_dir = self.fixture_root / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        draft_path = drafts_dir / "2026-04-10_claude-dispatch-and-the-power-of-interfaces-latent-transform.md"

        draft_path.write_text(
            """---
title: "Claude Dispatch and the Power of Interfaces"
draft_kind: owner_review
source_kind: latent_transform
idea_id: idea-456
lane: ai
publish_posture: owner_review_required
source_url: https://example.com/claude-dispatch
source_path: workspaces/linkedin-content-os/research/claude-dispatch.md
latent_reason: needs_context_translation
transform_type: context_translation
---

# Claude Dispatch and the Power of Interfaces

## Source signal
- Source file: `workspaces/linkedin-content-os/research/claude-dispatch.md`
- Source URL: https://example.com/claude-dispatch
- Source summary: Interface quality changes whether AI is actually useful.
- Why it matters: AI workflow design and operator judgment signals

## Transform brief
- Proposed angle: Interface quality decides whether capability becomes leverage.
- Owner question: What concrete change should operators notice if this is true?
- Proof prompt: AI Clone / Brain System rebuild notes
- Promotion rule: Promote only after one lived proof line and one audience consequence.

## First-pass transformed draft

This is another latent first pass.
""",
            encoding="utf-8",
        )

        pending_card = PMCard(
            id="22222222-2222-4222-8222-222222222222",
            title="Owner review - latent",
            owner="Neo",
            status="review",
            source="openclaw:workspace-owner-review",
            link_type="owner_review",
            link_id="LATENT-DUMMY",
            payload={"workspace_key": "linkedin-os"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        created_payloads = []

        def fake_create_pending_card(payload):
            owner_review = payload.payload.get("owner_review") or {}
            queue_id = owner_review.get("queue_id")
            created_payloads.append(
                {
                    "queue_id": queue_id,
                    "title": payload.title,
                    "source_kind": owner_review.get("source_kind"),
                    "entry_kind": owner_review.get("entry_kind"),
                    "draft_path": owner_review.get("draft_path"),
                }
            )
            self.assertEqual(payload.status, "review")
            self.assertIsNone(payload.link_id)
            if owner_review.get("draft_path") == "drafts/2026-04-10_claude-dispatch-and-the-power-of-interfaces-latent-transform.md":
                self.assertEqual(payload.title, "Owner review - Latent transform - Claude Dispatch and the Power of Interfaces")
                self.assertEqual(owner_review.get("source_kind"), "latent_transform")
                self.assertEqual(owner_review.get("entry_kind"), "supplemental")
                self.assertEqual(owner_review.get("draft_path"), "drafts/2026-04-10_claude-dispatch-and-the-power-of-interfaces-latent-transform.md")
                self.assertEqual((owner_review.get("system_assessment") or {}).get("suggested_decision"), "revise")
                return pending_card.model_copy(update={"link_id": payload.link_id})
            return PMCard(
                id=f"owner-review-{len(created_payloads)}",
                title=payload.title,
                owner="Neo",
                status="review",
                source="openclaw:workspace-owner-review",
                link_type="owner_review",
                link_id=payload.link_id,
                payload=payload.payload,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        with (
            patch.object(linkedin_owner_review_module.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(linkedin_owner_review_module.pm_card_service, "create_card", side_effect=fake_create_pending_card),
        ):
            sync_response = self.client.post("/api/pm/owner-review/sync")
        self.assertEqual(sync_response.status_code, 200)
        sync_payload = sync_response.json()
        self.assertGreaterEqual(sync_payload.get("pending_count") or 0, 1)
        self.assertTrue(
            any(
                entry["source_kind"] == "latent_transform"
                and entry["entry_kind"] == "supplemental"
                and entry["draft_path"]
                == "drafts/2026-04-10_claude-dispatch-and-the-power-of-interfaces-latent-transform.md"
                for entry in created_payloads
            )
        )
        self.assertIn(pending_card.id, sync_payload.get("created_card_ids") or [])

    def test_pm_auto_progress_route(self) -> None:
        expected = {
            "processed_count": 1,
            "closed_count": 0,
            "continued_count": 1,
            "processed": [
                {
                    "card_id": "card-123",
                    "title": "Seed FEEZIE backlog from canonical persona and lived work",
                    "workspace_key": "linkedin-os",
                    "resolution_mode": "close_and_spawn_next",
                    "rule": "workspace_policy_accept_and_continue",
                    "reason": "Codex review worker accepted this routine review result and opened the next PM lane under the workspace review policy.",
                    "successor_card_id": "card-124",
                    "successor_card_title": "Turn seeded FEEZIE backlog into first draft batch",
                }
            ],
        }

        with patch.object(pm_card_service_module, "auto_progress_review_cards", return_value=expected) as auto_progress_mock:
            response = self.client.post("/api/pm/review-hygiene/auto-progress")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        auto_progress_mock.assert_called_once_with(limit=250)

    def test_daily_briefs_attach_live_source_intelligence_to_latest_brief(self) -> None:
        fake_payloads = {
            "weekly_plan": {
                "generated_at": "2026-03-28T12:00:00+00:00",
                "base_generated_at": "2026-03-27 19:21",
                "source_counts": {"drafts": 1, "media": 3, "brief_only": 1, "belief_evidence": 2, "route_to_pm": 0},
                "brief_awareness_candidates": [
                    {
                        "title": "Awareness item one",
                        "priority_lane": "program-leadership",
                        "source_kind": "long_form_brief_awareness",
                        "route_reason": "Useful situational awareness without strong posting pressure",
                        "handoff_lane": "brief_only",
                        "handoff_reason": "cycle awareness",
                    }
                ],
                "media_post_seeds": [
                    {
                        "title": "Media seed one",
                        "priority_lane": "ai",
                        "source_kind": "long_form_post_seed",
                        "route_reason": "Strong original-post angle",
                        "handoff_lane": "post_candidate",
                        "handoff_reason": "public expression",
                    }
                ],
                "belief_evidence_candidates": [
                    {
                        "title": "Belief candidate one",
                        "priority_lane": "ai",
                        "source_kind": "long_form_belief_evidence",
                        "route_reason": "Durable worldview evidence",
                        "handoff_lane": "persona_candidate",
                        "handoff_reason": "durable worldview evidence",
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
        self.assertEqual(overlay.get("brief_awareness_count"), 1)
        self.assertEqual(overlay.get("belief_evidence_candidate_count"), 1)
        self.assertEqual((overlay.get("belief_relation_counts") or {}).get("qualified_agreement"), 3)
        self.assertEqual(((overlay.get("top_brief_awareness") or [{}])[0]).get("handoff_lane"), "brief_only")
        self.assertEqual(((overlay.get("top_media_post_seeds") or [{}])[0]).get("title"), "Media seed one")
        self.assertEqual(((overlay.get("top_media_post_seeds") or [{}])[0]).get("handoff_lane"), "post_candidate")
        self.assertFalse(older.metadata.get("source_intelligence_live"))
        self.assertIsNone(older.metadata.get("source_intelligence"))

    def test_daily_briefs_prefer_newer_local_brief_over_stale_db_row(self) -> None:
        stale_db_brief = daily_brief_module.DailyBrief(
            id="db-2026-03-20",
            brief_date=datetime(2026, 3, 20, tzinfo=timezone.utc).date(),
            title="Morning Daily Brief — 2026-03-20",
            summary="Stale DB brief",
            content_markdown="Morning Daily Brief — 2026-03-20\n\nOld database content.",
            source="cron_history",
            source_ref="db://daily_briefs/2026-03-20",
            metadata={},
            created_at=datetime(2026, 3, 20, 15, 30, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 20, 15, 30, tzinfo=timezone.utc),
        )
        fresh_local_brief = daily_brief_module.DailyBrief(
            id="local-2026-04-01",
            brief_date=datetime(2026, 4, 1, tzinfo=timezone.utc).date(),
            title="Morning Daily Brief — 2026-04-01",
            summary="Fresh local brief",
            content_markdown="Morning Daily Brief — 2026-04-01\n\nFresh local content.",
            source="workspace_markdown",
            source_ref="/workspace/memory/daily-briefs.md",
            metadata={},
            created_at=datetime(2026, 4, 1, 11, 30, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 1, 11, 30, tzinfo=timezone.utc),
        )

        with patch.object(daily_brief_module, "_load_from_db", return_value=[stale_db_brief]), patch.object(
            daily_brief_module,
            "_load_from_local_files",
            return_value=[fresh_local_brief],
        ), patch.object(
            daily_brief_module,
            "_snapshot_payloads",
            return_value={},
        ):
            briefs = daily_brief_module.list_daily_briefs(limit=5)

        self.assertEqual(len(briefs), 2)
        self.assertEqual(briefs[0].brief_date.isoformat(), "2026-04-01")
        self.assertEqual(briefs[0].source, "workspace_markdown")
        self.assertEqual(briefs[1].brief_date.isoformat(), "2026-03-20")

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

    def test_daily_briefs_attach_brief_stream_with_reactions_and_related_persona_context(self) -> None:
        fake_payloads = {
            "weekly_plan": {
                "generated_at": "2026-03-28T12:00:00+00:00",
                "source_counts": {"media": 1, "belief_evidence": 1},
                "media_post_seeds": [
                    {
                        "title": "Education AI thread",
                        "priority_lane": "education",
                        "source_kind": "market_signal",
                        "route_reason": "Good visibility post angle",
                        "source_url": "https://example.com/thread",
                        "hook": "Comment on this for visibility",
                        "response_modes": ["comment", "post_seed"],
                    }
                ],
                "belief_evidence_candidates": [],
                "media_summary": {
                    "generated_at": "2026-03-28T12:00:00+00:00",
                    "route_counts": {"post_seed": 1},
                    "primary_route_counts": {"post_seed": 1},
                },
            },
            "long_form_routes": {},
            "source_assets": {"counts": {"total": 2}},
            "persona_review_summary": {"belief_relation_counts": {}, "recent": []},
        }

        def fake_list_reactions_by_item_key(*, brief_id=None, item_keys, limit=200):
            item_key = item_keys[0]
            return {
                item_key: [
                    brief_reaction_module.BriefReaction(
                        id="reaction-1",
                        brief_id=brief_id or "brief-1",
                        item_key=item_key,
                        item_title="Education AI thread",
                        reaction_kind="nuance",
                        text="The headline is right, but the real issue is workflow clarity.",
                        source_kind="market_signal",
                        source_url="https://example.com/thread",
                        source_path=None,
                        linked_delta_id="delta-1",
                        linked_capture_id="capture-1",
                        metadata={},
                        created_at=datetime(2026, 3, 28, 12, 5, tzinfo=timezone.utc),
                        updated_at=datetime(2026, 3, 28, 12, 5, tzinfo=timezone.utc),
                    )
                ]
            }

        def fake_related_persona_context_for_items(items, *, limit_per_item=2, delta_limit=250):
            item_key = str(items[0].get("item_key") or "")
            return {
                item_key: [
                    brief_reaction_module.BriefReactionPersonaContext(
                        delta_id="delta-1",
                        trait="Workflow clarity is a leadership discipline, not an ops accessory.",
                        response_kind="story",
                        excerpt="I saw this when unclear reporting made it harder to know who to contact next.",
                        target_file="history/story_bank.md",
                        review_source="brain.persona.ui",
                        created_at=datetime(2026, 3, 28, 12, 10, tzinfo=timezone.utc),
                    )
                ]
            }

        with patch.object(daily_brief_module, "_load_from_db", return_value=[]), patch.object(
            daily_brief_module,
            "_snapshot_payloads",
            return_value=fake_payloads,
        ), patch.object(
            brief_reaction_module,
            "list_reactions_by_item_key",
            side_effect=fake_list_reactions_by_item_key,
        ), patch.object(
            brief_reaction_module,
            "related_persona_context_for_items",
            side_effect=fake_related_persona_context_for_items,
        ):
            briefs = daily_brief_module.list_daily_briefs(limit=5)

        stream = ((briefs[0].metadata.get("source_intelligence") or {}).get("brief_stream") or [])
        self.assertEqual(len(stream), 1)
        self.assertEqual(stream[0].get("title"), "Education AI thread")
        self.assertEqual(stream[0].get("hook"), "Comment on this for visibility")
        self.assertEqual((stream[0].get("existing_reactions") or [{}])[0].get("reaction_kind"), "nuance")
        self.assertEqual((stream[0].get("related_persona_context") or [{}])[0].get("delta_id"), "delta-1")

    def test_brief_reaction_story_creates_linked_persona_story_delta(self) -> None:
        fake_pool = _FakeBriefReactionPool()
        created_delta_payload = {}

        def fake_create_delta(payload):
            created_delta_payload["payload"] = payload
            return PersonaDelta(
                id="delta-story",
                capture_id=payload.capture_id,
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
                committed_at=None,
            )

        def fake_update_delta(delta_id, payload):
            metadata = created_delta_payload["payload"].metadata
            return PersonaDelta(
                id=delta_id,
                capture_id=created_delta_payload["payload"].capture_id,
                persona_target="worldview",
                trait=created_delta_payload["payload"].trait,
                notes=created_delta_payload["payload"].notes,
                status=payload.status or "in_review",
                metadata=metadata,
                created_at=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
                committed_at=None,
            )

        payload = brief_reaction_module.BriefReactionCreate(
            brief_id="brief-1",
            item_key="item-1",
            item_title="Education AI thread",
            item_summary="Teachers need clearer workflow support before more tools.",
            item_hook="Comment on this for visibility",
            source_kind="market_signal",
            source_url="https://example.com/thread",
            priority_lane="education",
            route_reason="Useful for a story-led post",
            reaction_kind="story",
            text="At Fusion, I learned fast that clarity changed who we reached and how we followed up.",
        )

        with patch.object(
            brief_reaction_module.capture_service,
            "create_capture",
            return_value=SimpleNamespace(capture_id="capture-1", chunk_ids=["chunk-1"], chunk_count=1, expires_at=None),
        ), patch.object(
            brief_reaction_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ), patch.object(
            brief_reaction_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update_delta,
        ), patch.object(
            brief_reaction_module,
            "annotate_for_brain_queue",
            side_effect=lambda delta: delta,
        ), patch.object(
            brief_reaction_module,
            "get_pool",
            return_value=fake_pool,
        ):
            response = brief_reaction_module.create_reaction(payload)

        delta_metadata = created_delta_payload["payload"].metadata
        self.assertEqual(delta_metadata.get("review_source"), "brain.daily_brief.stream")
        self.assertEqual(delta_metadata.get("target_file"), "history/story_bank.md")
        self.assertEqual((delta_metadata.get("anecdotes") or [{}])[0].get("summary"), payload.text)
        self.assertEqual(response.reaction.linked_delta_id, "delta-story")
        self.assertEqual(response.reaction.metadata.get("target_file"), "history/story_bank.md")

    def test_brief_reaction_agreement_defaults_to_claims_target(self) -> None:
        fake_pool = _FakeBriefReactionPool()
        created_delta_payload = {}

        def fake_create_delta(payload):
            created_delta_payload["payload"] = payload
            return PersonaDelta(
                id="delta-claim",
                capture_id=payload.capture_id,
                persona_target=payload.persona_target,
                trait=payload.trait,
                notes=payload.notes,
                status="draft",
                metadata=payload.metadata,
                created_at=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
                committed_at=None,
            )

        def fake_update_delta(delta_id, payload):
            metadata = created_delta_payload["payload"].metadata
            return PersonaDelta(
                id=delta_id,
                capture_id=created_delta_payload["payload"].capture_id,
                persona_target="worldview",
                trait=created_delta_payload["payload"].trait,
                notes=created_delta_payload["payload"].notes,
                status=payload.status or "in_review",
                metadata=metadata,
                created_at=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
                committed_at=None,
            )

        payload = brief_reaction_module.BriefReactionCreate(
            brief_id="brief-1",
            item_key="item-claim",
            item_title="Prompting alone is not enough",
            item_summary="The article nails the adoption gap.",
            source_kind="market_signal",
            source_url="https://example.com/prompting",
            priority_lane="tech_ai",
            route_reason="Strong thesis reinforcement",
            reaction_kind="agree",
            text="Prompting alone is not an AI strategy.",
        )

        with patch.object(
            brief_reaction_module.capture_service,
            "create_capture",
            return_value=SimpleNamespace(capture_id="capture-2", chunk_ids=["chunk-1"], chunk_count=1, expires_at=None),
        ), patch.object(
            brief_reaction_module.persona_delta_service,
            "create_delta",
            side_effect=fake_create_delta,
        ), patch.object(
            brief_reaction_module.persona_delta_service,
            "update_delta",
            side_effect=fake_update_delta,
        ), patch.object(
            brief_reaction_module,
            "annotate_for_brain_queue",
            side_effect=lambda delta: delta,
        ), patch.object(
            brief_reaction_module,
            "get_pool",
            return_value=fake_pool,
        ):
            response = brief_reaction_module.create_reaction(payload)

        delta_metadata = created_delta_payload["payload"].metadata
        self.assertEqual(delta_metadata.get("target_file"), "identity/claims.md")
        self.assertEqual(delta_metadata.get("owner_response_kind"), "agree")
        self.assertIn("Prompting alone is not an AI strategy.", delta_metadata.get("talking_points") or [])
        self.assertEqual(response.reaction.metadata.get("target_file"), "identity/claims.md")

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
            "assets_considered": 3,
            "segments_total": 3,
            "route_counts": {"comment": 0, "repost": 0, "post_seed": 2, "belief_evidence": 1},
            "primary_route_counts": {"comment": 0, "repost": 0, "post_seed": 2, "belief_evidence": 1},
            "handoff_lane_counts": {"source_only": 0, "brief_only": 1, "post_candidate": 1, "persona_candidate": 1, "route_to_pm": 0},
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
                    "response_modes": ["comment", "post_seed"],
                    "handoff_lane": "post_candidate",
                    "handoff_reason": "expression-ready",
                    "belief_summary": "people, process, and culture as the main levers of leadership",
                },
                {
                    "title": "Awareness source",
                    "segment": "A new transcript landed overnight and needs human eyes before promotion.",
                    "primary_route": "post_seed",
                    "route_reason": "segment is useful situational awareness for the current cycle",
                    "route_score": 8,
                    "lane_hint": "program-leadership",
                    "source_path": "knowledge/ingestions/example/normalized.md",
                    "source_url": "https://example.com/awareness",
                    "target_file": "identity/claims.md",
                    "response_modes": ["post_seed"],
                    "handoff_lane": "brief_only",
                    "handoff_reason": "cycle awareness",
                    "belief_summary": "",
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
                    "handoff_lane": "persona_candidate",
                    "handoff_reason": "durable worldview evidence",
                    "belief_summary": "an AI practitioner, not just a passive user",
                },
            ],
        }

        augmented = workspace_snapshot_module._augment_weekly_plan_payload(weekly_plan, long_form_routes)

        self.assertEqual(augmented.get("generated_at"), "2026-03-28T01:30:00+00:00")
        self.assertEqual(augmented.get("base_generated_at"), "2026-03-28T00:00:00+00:00")
        self.assertEqual(augmented.get("source_counts", {}).get("media"), 1)
        self.assertEqual(augmented.get("source_counts", {}).get("brief_only"), 1)
        self.assertEqual(augmented.get("source_counts", {}).get("belief_evidence"), 1)
        self.assertEqual(len(augmented.get("media_post_seeds") or []), 1)
        self.assertEqual(len(augmented.get("brief_awareness_candidates") or []), 1)
        self.assertEqual(len(augmented.get("belief_evidence_candidates") or []), 1)
        self.assertEqual((augmented.get("media_post_seeds") or [{}])[0].get("source_kind"), "long_form_post_seed")
        self.assertEqual((augmented.get("brief_awareness_candidates") or [{}])[0].get("source_kind"), "long_form_brief_awareness")
        self.assertEqual((augmented.get("belief_evidence_candidates") or [{}])[0].get("source_kind"), "long_form_belief_evidence")
        self.assertEqual((augmented.get("media_summary") or {}).get("assets_considered"), 3)
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
            "handoff_lane_counts": {"source_only": 0, "brief_only": 0, "post_candidate": 1, "persona_candidate": 1, "route_to_pm": 0},
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
                    "response_modes": ["comment", "post_seed"],
                    "handoff_lane": "post_candidate",
                    "handoff_reason": "expression-ready",
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
                    "handoff_lane": "persona_candidate",
                    "handoff_reason": "durable worldview evidence",
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

    def test_long_form_candidate_cleanup_strips_inline_caption_rollups_and_keeps_post_seed_out_of_persona_queue(self) -> None:
        caption_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "04" / "caption_rollup_asset"
        caption_dir.mkdir(parents=True, exist_ok=True)
        (caption_dir / "normalized.md").write_text(
            """---
id: caption_rollup_asset
title: Stop Shifting Blame and Start Taking Power
source_type: youtube_transcript
captured_at: '2026-04-01T04:30:03Z'
topics:
- transcript
- youtube
- video
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=caption123
author: Champion Leadership
raw_files:
- raw/transcript.txt
word_count: 239
summary: This video emphasizes the need for accountability over excuses.
---

# Clean Transcript / Document
So,<00:00:00.240><c> I</c><00:00:00.480><c> think</c><00:00:00.640><c> one</c><00:00:00.960><c> reason</c><00:00:01.280><c> people</c><00:00:01.680><c> make</c> So, I think one reason people make excuses,<00:00:02.720><c> it</c><00:00:02.960><c> takes</c><00:00:03.280><c> the</c><00:00:03.520><c> pressure</c><00:00:03.919><c> off</c><00:00:04.160><c> of</c> excuses, it takes the pressure off of them.<00:00:04.640><c> Here's</c><00:00:04.960><c> why.</c><00:00:05.200><c> If</c><00:00:05.440><c> they</c><00:00:05.680><c> can</c><00:00:06.000><c> blame</c> them. Here's why. If they can blame something<00:00:06.960><c> outside</c><00:00:07.520><c> of</c><00:00:07.759><c> them</c><00:00:08.240><c> for</c><00:00:08.400><c> the</c><00:00:08.720><c> reason</c> something outside of them for the reason that<00:00:09.200><c> they're</c><00:00:09.440><c> not</c><00:00:09.679><c> performing</c><00:00:10.160><c> at</c><00:00:10.400><c> their</c> that they're not performing at their best,<00:00:11.120><c> takes</c><00:00:11.360><c> the</c><00:00:11.599><c> pressure</c><00:00:11.920><c> off.</c><00:00:12.320><c> It</c> best, takes the pressure off. It relieves<00:00:12.960><c> them</c><00:00:13.120><c> of</c><00:00:13.360><c> accountability.</c>
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=1,
            max_segments_per_asset=1,
        )
        candidates = extracted.get("candidates") or []
        self.assertGreater(len(candidates), 0)
        segment = str(candidates[0].get("segment") or "")
        self.assertNotIn("<00:", segment)
        self.assertNotIn("<c>", segment)
        self.assertNotIn("something outside of them for the reason something outside of them", segment.lower())
        self.assertEqual(candidates[0].get("primary_route"), "post_seed")
        self.assertIn("pressure off", str(candidates[0].get("source_context_excerpt") or "").lower())
        self.assertIsInstance(candidates[0].get("source_context_before"), list)
        self.assertIsInstance(candidates[0].get("source_context_after"), list)

        with patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[]), patch.object(
            social_persona_review_module.persona_delta_service,
            "get_delta_by_review_key",
            return_value=None,
        ), patch.object(social_persona_review_module.persona_delta_service, "create_delta") as create_delta:
            result = social_persona_review_module.social_persona_review_service.sync_long_form_worldview_reviews(
                repo_root=Path(self.temp_dir.name),
                source_assets={"items": [item for item in (inventory.get("items") or []) if item.get("asset_id") == "caption_rollup_asset"]},
                max_assets=1,
                max_segments_per_asset=1,
            )

        self.assertEqual(result.get("created_count"), 0)
        create_delta.assert_not_called()

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

    def test_long_form_persona_review_sync_resolves_stale_missing_source_assets(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        stale_delta = PersonaDelta(
            id="missing-asset-delta",
            persona_target="feeze.core",
            trait="Orphaned autogenerated segment",
            notes="Old segment from removed asset",
            status="draft",
            metadata={
                "review_key": "long-form:missing-asset",
                "review_source": "long_form_media.segment",
                "source_asset_id": "missing_asset_id",
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
                source_assets=inventory,
                max_assets=12,
                max_segments_per_asset=1,
            )

        self.assertEqual(result.get("resolved_stale"), 1)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0], "missing-asset-delta")
        self.assertEqual(update_calls[0][1].status, "resolved")
        self.assertEqual(update_calls[0][1].metadata.get("sync_state"), "stale_source_asset")

    def test_long_form_persona_review_sync_resolves_route_downgraded_segments(self) -> None:
        downgrade_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "route_downgrade_transcript"
        downgrade_dir.mkdir(parents=True, exist_ok=True)
        (downgrade_dir / "normalized.md").write_text(
            """---
id: route_downgrade_transcript
title: Route Downgrade Transcript
source_type: youtube_transcript
captured_at: '2026-03-28T00:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=routedowngrade
author: unknown
raw_files:
- raw/transcript.txt
word_count: 9000
summary: Weak deictic story fragments should not stay in persona canon review.
---

# Clean Transcript / Document
If you are where they see the results, you're moving toward being a platform.
Move number two, become that system of record.
Remember that the hill that I showed you, the system of record hill?
So here's an example of what I mean by owning the data.
If you're a scheduling tool, don't facilitate bookings, store the history of every booking.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        candidates = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=12,
            max_segments_per_asset=2,
        ).get("candidates") or []
        downgraded = next(
            item
            for item in candidates
            if item.get("asset_id") == "route_downgrade_transcript" and item.get("weak_source_fragment") is True and item.get("primary_route") == "post_seed"
        )
        stale_delta = PersonaDelta(
            id="route-downgrade-delta",
            persona_target="feeze.core",
            trait=str(downgraded.get("segment") or "Downgraded segment"),
            notes="Old canon-oriented review",
            status="draft",
            metadata={
                "review_key": downgraded.get("candidate_id"),
                "review_source": "long_form_media.segment",
                "source_asset_id": downgraded.get("asset_id"),
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
                source_assets=inventory,
                max_assets=12,
                max_segments_per_asset=2,
            )

        self.assertEqual(result.get("resolved_stale"), 1)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0], "route-downgrade-delta")
        self.assertEqual(update_calls[0][1].status, "resolved")
        self.assertEqual(update_calls[0][1].metadata.get("sync_state"), "stale_route_downgrade")

    def test_brain_queue_does_not_mark_non_belief_long_form_drafts_as_active_review(self) -> None:
        delta = PersonaDelta(
            id="queue-post-seed",
            persona_target="feeze.core",
            trait="This should stay a post seed.",
            notes="Legacy draft row that should no longer show as active review.",
            status="draft",
            metadata={
                "review_source": "long_form_media.segment",
                "primary_route": "post_seed",
                "target_file": "identity/claims.md",
                "talking_points": ["This should stay a post seed."],
            },
            created_at=datetime.now(timezone.utc),
        )

        annotated = persona_queue_module.annotate_for_brain_queue(delta)

        self.assertEqual((annotated.metadata or {}).get("queue_stage"), "draft")
        self.assertFalse(persona_queue_module.is_brain_pending_review(annotated.status, annotated.metadata))

    def test_long_form_persona_review_sync_resolves_handoff_downgraded_segments(self) -> None:
        stale_delta = PersonaDelta(
            id="handoff-downgrade-delta",
            persona_target="feeze.core",
            trait="Workflow clarity should force an ops review before canon.",
            notes="Old persona-oriented review",
            status="draft",
            metadata={
                "review_key": "handoff-review-key",
                "review_source": "long_form_media.segment",
                "source_asset_id": "handoff-asset",
                "primary_route": "belief_evidence",
            },
            created_at=datetime.now(timezone.utc),
        )

        extracted = {
            "assets_considered": 1,
            "skipped_no_segments": 0,
            "considered_asset_ids": ["handoff-asset"],
            "assets": [{"asset_id": "handoff-asset"}],
            "candidates": [
                {
                    "candidate_id": "handoff-review-key",
                    "asset_id": "handoff-asset",
                    "primary_route": "belief_evidence",
                    "handoff_lane": "route_to_pm",
                }
            ],
        }

        update_calls = []

        def fake_update_delta(delta_id, payload):
            update_calls.append((delta_id, payload))
            return stale_delta

        with patch.object(
            social_persona_review_module,
            "extract_long_form_candidates",
            return_value=extracted,
        ), patch.object(social_persona_review_module.persona_delta_service, "list_deltas", return_value=[stale_delta]), patch.object(
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
                source_assets={"items": [{"asset_id": "handoff-asset"}]},
                max_assets=12,
                max_segments_per_asset=2,
            )

        self.assertEqual(result.get("resolved_stale"), 1)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0], "handoff-downgrade-delta")
        self.assertEqual(update_calls[0][1].status, "resolved")
        self.assertEqual(update_calls[0][1].metadata.get("sync_state"), "stale_handoff_downgrade")

    def test_long_form_persona_review_sync_refreshes_existing_draft_metadata(self) -> None:
        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        candidates = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=12,
            max_segments_per_asset=1,
        ).get("candidates") or []
        candidate = next(item for item in candidates if item.get("primary_route") == "belief_evidence")
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
                max_assets=12,
                max_segments_per_asset=1,
            )

        self.assertEqual(result.get("created_count"), 0)
        self.assertEqual(result.get("refreshed_existing"), 1)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0][0], "existing-delta")
        self.assertIn("belief_relation", update_calls[0][1].metadata)
        self.assertIn("System hypothesis:", update_calls[0][1].notes or "")

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

    def test_extract_long_form_candidates_skips_pending_watchlist_placeholders(self) -> None:
        pending_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "pending_watchlist_video"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "normalized.md").write_text(
            """---
id: pending_watchlist_video
title: Pending Watchlist Video
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
- youtube
tags:
- brain_ingest
- needs_review
source_url: https://www.youtube.com/watch?v=pendingwatchlist
author: unknown
raw_files:
- raw/source.url
word_count:
summary: Pending transcript or notes for Pending Watchlist Video.
---

# Source Notes
Selected from YouTube watchlist: Selected AI YouTube Channel.

Registered from link. Transcript capture still pending.

## Owner Notes
- **Resonance:** Pending owner review.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )

        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=4,
            max_segments_per_asset=2,
        )

        asset_ids = {social_long_form_signal_module._clean_text(item.get("asset_id")) for item in (extracted.get("assets") or [])}
        candidate_asset_ids = {social_long_form_signal_module._clean_text(item.get("asset_id")) for item in (extracted.get("candidates") or [])}
        self.assertNotIn("pending_watchlist_video", asset_ids)
        self.assertNotIn("pending_watchlist_video", candidate_asset_ids)
        self.assertIn("pending_watchlist_video", extracted.get("considered_asset_ids") or [])
        self.assertGreaterEqual(int(extracted.get("skipped_no_segments") or 0), 1)

    def test_extract_long_form_candidates_skips_validation_noise_assets(self) -> None:
        pending_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "queue_test_transcript_2"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "normalized.md").write_text(
            """---
id: queue_test_transcript_2
title: queue test transcript 2
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=queuetesttwo
author: unknown
raw_files:
- raw/queue_test_transcript_2.txt
word_count: 31
summary: "Transcript Host: This is a short validation transcript for the media background queue."
---

# Clean Transcript / Document
Transcript Host: This is a short validation transcript for the media background queue.
The key point is that background execution should return immediately while the actual normalization finishes on its own.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )

        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=10,
            max_segments_per_asset=2,
        )

        candidate_asset_ids = {social_long_form_signal_module._clean_text(item.get("asset_id")) for item in (extracted.get("candidates") or [])}
        self.assertNotIn("queue_test_transcript_2", candidate_asset_ids)

    def test_extract_long_form_candidates_demotes_hype_question_to_non_canon_route(self) -> None:
        hype_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "hype_question_transcript"
        hype_dir.mkdir(parents=True, exist_ok=True)
        (hype_dir / "normalized.md").write_text(
            """---
id: hype_question_transcript
title: Hype Question Transcript
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=hypequestion
author: unknown
raw_files:
- raw/transcript.txt
word_count: 900
summary: Contrarian question frames should stay outside canon review.
---

# Clean Transcript / Document
Everyone thinks that Apple lost the AI race, but what if they've been playing a different game all along?
Notice I didn't talk about Mac minis.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=10,
            max_segments_per_asset=2,
        )

        candidate = next(item for item in (extracted.get("candidates") or []) if item.get("asset_id") == "hype_question_transcript")
        self.assertNotEqual(candidate.get("primary_route"), "belief_evidence")

    def test_extract_long_form_candidates_demotes_reference_batch_meta_guidance(self) -> None:
        ref_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "reference_batch_transcript"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "normalized.md").write_text(
            """---
id: reference_batch_transcript
title: External Reference Batch – AI, Entrepreneurship, and Media Voice
source_type: transcript_note
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
tags:
- persona
- reference
source_url:
author:
raw_files:
- raw/reference_batch.txt
word_count: 900
summary: Reference-batch guidance should stay source intelligence unless it becomes lived proof.
---

# Clean Transcript / Document
This batch contains three high-signal external references.
The batch is not safe to treat as Johnnie's own lived proof and should remain style-reference-only inside the persona system.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=10,
            max_segments_per_asset=2,
        )

        candidate = next(item for item in (extracted.get("candidates") or []) if item.get("asset_id") == "reference_batch_transcript")
        self.assertNotEqual(candidate.get("primary_route"), "belief_evidence")

    def test_extract_long_form_candidates_does_not_treat_generic_we_line_as_story_bank_evidence(self) -> None:
        generic_story_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "generic_we_story_transcript"
        generic_story_dir.mkdir(parents=True, exist_ok=True)
        (generic_story_dir / "normalized.md").write_text(
            """---
id: generic_we_story_transcript
title: Generic We Story Transcript
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=genericwestory
author: unknown
raw_files:
- raw/transcript.txt
word_count: 900
summary: Generic we-lines should not be treated as story-bank proof.
---

# Clean Transcript / Document
Humans don't retrieve consistently.
In the advertisements, we do that, but we don't really do that.
We do respond to what shows up in front of us.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=10,
            max_segments_per_asset=2,
        )

        candidate = next(item for item in (extracted.get("candidates") or []) if item.get("asset_id") == "generic_we_story_transcript")
        self.assertNotEqual(candidate.get("target_file"), "history/story_bank.md")

    def test_extract_long_form_candidates_demotes_manual_non_lived_segment_without_exceptional_value(self) -> None:
        transcript_path = Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts" / "2026-04-01_manual_non_lived_note.md"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(
            """---
title: Manual Non Lived Note
received: 2026-04-01
tags:
- persona
- strategy
---

## Summary
- Reference-only strategic phrasing to validate demotion behavior.

## Transcript
Prompting alone is not an AI strategy.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=10,
            max_segments_per_asset=2,
        )

        candidates = [item for item in (extracted.get("candidates") or []) if item.get("asset_id") == "2026-04-01_manual_non_lived_note"]
        self.assertTrue(candidates)
        self.assertTrue(all(item.get("primary_route") != "belief_evidence" for item in candidates))
        self.assertTrue(all("belief_evidence" not in (item.get("response_modes") or []) for item in candidates))

    def test_extract_long_form_candidates_keeps_manual_non_lived_segment_when_exceptional_value_is_clear(self) -> None:
        transcript_path = Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts" / "2026-04-01_manual_high_value_note.md"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(
            """---
title: Manual High Value Note
received: 2026-04-01
tags:
- persona
- strategy
---

## Summary
- High-value strategic guidance that should still be reviewable for canon.

## Transcript
Improve Experience Relevance by preferring stories around operational cleanup, AI system-building under constraint, dashboards, admissions trust, and leadership voice instead of isolated prompting.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        extracted = social_persona_review_module.extract_long_form_candidates(
            repo_root=Path(self.temp_dir.name),
            source_assets=inventory,
            max_assets=10,
            max_segments_per_asset=2,
        )

        candidates = [item for item in (extracted.get("candidates") or []) if item.get("asset_id") == "2026-04-01_manual_high_value_note"]
        self.assertTrue(candidates)
        self.assertTrue(any(item.get("high_value_non_lived") for item in candidates))
        self.assertTrue(any(item.get("primary_route") == "belief_evidence" for item in candidates))

    def test_long_form_persona_review_sync_avoids_link_and_follow_boilerplate(self) -> None:
        promo_dir = Path(self.temp_dir.name) / "knowledge" / "ingestions" / "2026" / "03" / "promo_heavy_transcript"
        promo_dir.mkdir(parents=True, exist_ok=True)
        (promo_dir / "normalized.md").write_text(
            """---
id: promo_heavy_transcript
title: Promo Heavy Transcript
source_type: youtube_transcript
captured_at: '2026-03-31T00:00:00Z'
topics:
- transcript
- youtube
tags:
- auto_ingested
- needs_review
source_url: https://www.youtube.com/watch?v=promoheavy
author: unknown
raw_files:
- raw/transcript.txt
word_count: 2400
summary: The real work is designing systems that reduce coordination overhead before you scale.
---

# Clean Transcript / Document
My site: https://example.com Full story w/ prompts: https://example.com/story
Follow the besties: https://x.com/a https://x.com/b https://x.com/c
Subscribe for more breakdowns and join my newsletter for the full write-up.
The real work is designing systems that reduce coordination overhead before you scale a team.
Teams create fragility when they stack tools before they define ownership and handoffs.
""",
            encoding="utf-8",
        )

        inventory = build_source_asset_inventory(
            transcripts_root=Path(self.temp_dir.name) / "knowledge" / "aiclone" / "transcripts",
            ingestions_root=Path(self.temp_dir.name) / "knowledge" / "ingestions",
            repo_root=Path(self.temp_dir.name),
        )
        items = [item for item in (inventory.get("items") or []) if item.get("asset_id") == "promo_heavy_transcript"]
        created_payloads = []
        now = datetime.now(timezone.utc)

        def fake_create_delta(payload):
            created_payloads.append(payload)
            return PersonaDelta(
                id=f"promo-{len(created_payloads)}",
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
        self.assertIn("reduce coordination overhead before you scale a team", combined_text)
        self.assertIn("define ownership and handoffs", combined_text)
        self.assertNotIn("my site:", combined_text)
        self.assertNotIn("follow the besties", combined_text)
        self.assertNotIn("subscribe for more breakdowns", combined_text)

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

    def test_normalize_selected_promotion_items_keeps_review_voice_out_of_proof_by_default(self) -> None:
        delta = PersonaDelta(
            id="delta-semantic-proof-clean",
            capture_id=None,
            persona_target="feeze.core",
            trait="Proof cleanup delta",
            notes="Original review note that should not become proof.",
            status="committed",
            metadata={
                "owner_response_kind": "nuance",
                "owner_response_excerpt": "This is an incredible video.",
                "selected_promotion_items": [
                    {
                        "id": "initiative-stat-1",
                        "kind": "stat",
                        "label": "Proof point",
                        "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                        "targetFile": "history/initiatives.md",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=datetime.now(timezone.utc),
        )

        normalized = persona_promotion_utils_module.normalize_selected_promotion_items(delta)
        extracted = persona_promotion_extractor_module.extract_canonical_promotion_items(normalized)

        self.assertEqual(len(normalized), 1)
        self.assertIsNone(normalized[0]["evidence"])
        self.assertIsNone(normalized[0]["proof_signal"])
        self.assertEqual(
            normalized[0]["review_interpretation"],
            "This is an incredible video.",
        )
        self.assertEqual(len(extracted), 1)
        self.assertEqual(
            extracted[0]["canon_proof"],
            "CEO prompting plus agent usage makes AI success 5.2x more likely.",
        )
        self.assertNotIn(
            "incredible video",
            (extracted[0]["canon_proof"] or "").lower(),
        )

    def test_normalize_selected_promotion_items_prefers_committed_semantic_items(self) -> None:
        delta = PersonaDelta(
            id="delta-semantic-committed",
            capture_id=None,
            persona_target="feeze.core",
            trait="Committed semantic delta",
            notes="Original note",
            status="committed",
            metadata={
                "selected_promotion_items": [
                    {
                        "id": "stat-1",
                        "kind": "stat",
                        "label": "Proof point",
                        "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                        "targetFile": "history/initiatives.md",
                    }
                ],
                "committed_promotion_items": [
                    {
                        "id": "initiative-1",
                        "kind": "talking_point",
                        "label": "AI Clone / Brain System",
                        "content": "Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution.",
                        "target_file": "history/initiatives.md",
                        "artifact_summary": "Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution.",
                        "artifact_kind": "artifact_signal",
                        "artifact_ref": "workspace:brain",
                        "capability_signal": "Builds and translates AI execution patterns into clear operator guidance.",
                        "positioning_signal": "Strengthens Johnnie's positioning as an AI systems operator grounded in real execution.",
                        "leverage_signal": "Creates reusable proof for future writing, planning, and persona claims about AI execution and workflow clarity.",
                        "proof_signal": "Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot.",
                        "proof_strength": "strong",
                        "gate_decision": "allow",
                        "gate_reason": "Artifact-backed proof is present.",
                        "canon_purpose": "Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution.",
                        "canon_value": "Builds and translates AI execution patterns into clear operator guidance.",
                        "canon_proof": "Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot.",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=datetime.now(timezone.utc),
        )

        normalized = persona_promotion_utils_module.normalize_selected_promotion_items(delta)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["label"], "AI Clone / Brain System")
        self.assertEqual(normalized[0]["artifact_kind"], "artifact_signal")
        self.assertEqual(normalized[0]["canon_purpose"], "Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution.")
        self.assertEqual(
            normalized[0]["proof_signal"],
            "Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot.",
        )

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
            examples_path = bundle_root / "prompts" / "content_examples.md"
            claims_path.parent.mkdir(parents=True, exist_ok=True)
            initiatives_path.parent.mkdir(parents=True, exist_ok=True)
            stories_path.parent.mkdir(parents=True, exist_ok=True)
            examples_path.parent.mkdir(parents=True, exist_ok=True)

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
            examples_path.write_text(
                """## Good Examples
- Operator reframe with strategy first. Prompting alone is not an AI strategy. Use when: workflow clarity, agent orchestration, AI adoption.
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

        example_meta = by_path["prompts/content_examples.md"]["metadata"]
        self.assertEqual(example_meta.get("memory_role"), "example")
        self.assertEqual(example_meta.get("proof_kind"), "style_example")
        self.assertEqual(example_meta.get("persona_tag"), "LINKEDIN_EXAMPLES")
        self.assertIn("style_reference", example_meta.get("usage_modes", []))

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
                            "label": "AI Clone / Brain System",
                            "canon_purpose": "Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance.",
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
        self.assertIn("AI Clone / Brain System", chunks[0].get("chunk", ""))
        self.assertIn("Build a durable system for restart-safe memory", chunks[0].get("chunk", ""))
        self.assertIn("Proof: Brain, Ops, planner, and briefs now share the same routed workspace state", chunks[0].get("chunk", ""))
        metadata = chunks[0].get("metadata", {})
        self.assertEqual(metadata.get("memory_role"), "proof")
        self.assertEqual(metadata.get("proof_kind"), "initiative")
        self.assertEqual(metadata.get("proof_strength"), "strong")
        self.assertTrue(metadata.get("artifact_backed"))
        self.assertIn("proof_anchor", metadata.get("usage_modes", []))

    def test_persona_bundle_context_balances_core_and_proof_retrieval(self) -> None:
        items = [
            {
                "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                "metadata": {"memory_role": "core"},
                "persona_tag": "BIO_FACTS",
            },
            {
                "chunk": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                "metadata": {"memory_role": "proof"},
                "persona_tag": "VENTURES",
            },
            {
                "chunk": "65% of executives trust AI outputs, versus far fewer frontline employees.",
                "metadata": {"memory_role": "proof"},
                "persona_tag": "VENTURES",
            },
            {
                "chunk": "A story about operator clarity in practice.",
                "metadata": {"memory_role": "story"},
                "persona_tag": "EXPERIENCES",
            },
        ]

        with patch.object(persona_bundle_context_module, "load_committed_overlay_chunks", return_value=[]), patch.object(
            persona_bundle_context_module,
            "load_bundle_persona_chunks",
            return_value=items,
        ), patch.object(
            persona_bundle_context_module,
            "embed_texts",
            return_value=[[0.1], [0.2], [0.3], [0.4]],
        ), patch.object(
            persona_bundle_context_module,
            "cosine_similarity",
            return_value=[[0.4, 0.95, 0.9, 0.7]],
        ), patch.object(
            persona_bundle_context_module,
            "get_combined_weights",
            return_value={item["persona_tag"]: 1.0 for item in items},
        ):
            chunks = persona_bundle_context_module.retrieve_bundle_persona_chunks(
                query_text="agent orchestration",
                query_embedding=[0.1],
                top_k=3,
            )

        combined = " ".join(chunk.get("chunk", "") for chunk in chunks)
        self.assertEqual(len(chunks), 3)
        self.assertIn("prompting plus agent orchestration", combined)
        self.assertIn("5.2x more likely", combined)

    def test_persona_bundle_context_prefers_semantic_initiative_overlay_fields(self) -> None:
        with patch.object(
            persona_bundle_context_module,
            "build_committed_persona_overlay",
            return_value={
                "by_target_file": {
                    "history/initiatives.md": [
                        {
                            "label": "AI Clone / Brain System",
                            "canon_purpose": "Use quantified AI execution proof to ground initiative-level canon.",
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
        self.assertIn("Use quantified AI execution proof to ground initiative-level canon", (chunks[0].get("chunk") or ""))
        self.assertIn("5.2x success signal tied to visible prompting and agent usage", (chunks[0].get("chunk") or ""))
        self.assertNotIn("Raw review-shaped content", (chunks[0].get("chunk") or ""))

    def test_persona_bundle_context_skips_metric_only_legacy_initiative_overlay(self) -> None:
        with patch.object(
            persona_bundle_context_module,
            "build_committed_persona_overlay",
            return_value={
                "by_target_file": {
                    "history/initiatives.md": [
                        {
                            "label": "Proof point",
                            "content": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                            "target_file": "history/initiatives.md",
                            "artifact_kind": "metric_or_proof_point",
                            "proof_strength": "strong",
                            "gate_decision": "allow",
                            "canon_purpose": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                            "canon_value": "Builds and translates AI execution patterns into clear operator guidance.",
                            "canon_proof": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                        }
                    ]
                }
            },
        ), patch.object(persona_bundle_context_module, "resolve_persona_bundle_root", return_value=Path("/tmp/does-not-exist")):
            chunks = persona_bundle_context_module.load_committed_overlay_chunks()

        self.assertEqual(chunks, [])

    def test_content_generation_context_extracts_primary_claim_from_initiative_purpose(self) -> None:
        claims = content_context_service_module._extract_primary_claims(
            core_topic_chunks=[],
            topic_anchor_chunks=[],
            proof_anchor_chunks=[
                {
                    "chunk": (
                        "AI Clone / Brain System. Build a durable system for restart-safe memory, evidence capture, "
                        "persona development, and content assistance. Value: Strengthens Johnnie's positioning as an AI "
                        "systems operator grounded in real execution. Proof: Brain, Ops, planner, and briefs now share the same routed workspace state."
                    )
                }
            ],
            grounding_mode="proof_ready",
        )

        self.assertEqual(
            claims,
            ["Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance."],
        )

    def test_content_generation_context_drops_generic_proof_point_prefixes(self) -> None:
        claims = content_context_service_module._extract_primary_claims(
            core_topic_chunks=[],
            topic_anchor_chunks=[],
            proof_anchor_chunks=[
                {
                    "chunk": (
                        "Proof point. CEO prompting plus agent usage makes AI success 5.2x more likely. "
                        "Value: Builds and translates AI execution patterns into clear operator guidance. "
                        "Proof: CEO prompting plus agent usage makes AI success 5.2x more likely."
                    )
                }
            ],
            grounding_mode="proof_ready",
        )
        packets = content_context_service_module._extract_proof_packets(
            [
                {
                    "chunk": (
                        "Proof point. CEO prompting plus agent usage makes AI success 5.2x more likely. "
                        "Value: Builds and translates AI execution patterns into clear operator guidance. "
                        "Proof: CEO prompting plus agent usage makes AI success 5.2x more likely."
                    )
                }
            ]
        )

        self.assertEqual(claims, ["CEO prompting plus agent usage makes AI success 5.2x more likely."])
        self.assertEqual(packets, ["CEO prompting plus agent usage makes AI success 5.2x more likely."])

    def test_content_generation_context_strips_use_when_from_proof_packets(self) -> None:
        packets = content_context_service_module._extract_proof_packets(
            [
                {
                    "chunk": (
                        "Grounded Content Generation System. Purpose: Make the content engine read persona canon through typed "
                        "core, proof, story, and example lanes. Public-facing proof: The content route now uses typed retrieval, "
                        "domain gates, grounding modes, structured proof briefs, and proof-packet enforcement before final drafts. "
                        "Use when: AI writing systems and context engineering."
                    )
                }
            ]
        )

        self.assertEqual(
            packets,
            [
                "Grounded Content Generation System -> The content route now uses typed retrieval, domain gates, grounding modes, structured proof briefs, and proof-packet enforcement before final drafts.",
            ],
        )

    def test_content_generation_context_strips_generic_claim_prefixes(self) -> None:
        claims = content_context_service_module._extract_primary_claims(
            core_topic_chunks=[
                {
                    "chunk": "Guardrails: Keep writing specific, credible, and grounded in lived experience.",
                    "metadata": {"memory_role": "core"},
                },
                {
                    "chunk": "Wins: Content generation now reads persona through typed core, proof, story, and example lanes.",
                    "metadata": {"memory_role": "core"},
                },
            ],
            topic_anchor_chunks=[],
            proof_anchor_chunks=[],
            grounding_mode="principle_only",
        )

        self.assertIn("Keep writing specific, credible, and grounded in lived experience.", claims)
        self.assertIn("Content generation now reads persona through typed core, proof, story, and example lanes.", claims)

    def test_content_generation_context_prefers_claim_like_topic_anchor_over_metric_proof(self) -> None:
        claims = content_context_service_module._extract_primary_claims(
            core_topic_chunks=[
                {
                    "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. Evidence: Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
                    "metadata": {"memory_role": "core"},
                }
            ],
            topic_anchor_chunks=[
                {
                    "chunk": "Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution. Proof: Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
                    "metadata": {"memory_role": "proof"},
                }
            ],
            proof_anchor_chunks=[
                {
                    "chunk": "CEO prompting plus agent usage makes AI success 5.2x more likely.",
                    "metadata": {"memory_role": "proof"},
                }
            ],
            grounding_mode="proof_ready",
        )

        self.assertGreaterEqual(len(claims), 2)
        self.assertEqual(
            claims[0],
            "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
        )
        self.assertIn(
            claims[1],
            {
                "Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution.",
                "CEO prompting plus agent usage makes AI success 5.2x more likely.",
            },
        )

    def test_content_generation_context_prefers_tech_ai_specific_claim_over_generic_leadership_claim(self) -> None:
        claims = content_context_service_module._extract_primary_claims(
            core_topic_chunks=[
                {
                    "chunk": "Johnnie values people, process, and culture as the main levers of leadership. Evidence: Recurring philosophy across persona docs and operating decisions.",
                    "metadata": {"memory_role": "core"},
                },
                {
                    "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. Evidence: Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
                    "metadata": {
                        "memory_role": "core",
                        "domain_tags": ["ai_systems", "operator_workflows"],
                    },
                },
            ],
            topic_anchor_chunks=[],
            proof_anchor_chunks=[],
            grounding_mode="principle_only",
            topic="agent orchestration",
            audience="tech_ai",
        )

        self.assertGreaterEqual(len(claims), 2)
        self.assertEqual(
            claims[0],
            "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
        )

    def test_extract_approved_reference_terms_prefers_labels_and_evidence_phrases(self) -> None:
        approved = content_generation_module._extract_approved_reference_terms(
            primary_claims=[
                "AI Clone / Brain System. Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance."
            ],
            proof_packets=[
                "AI Clone / Brain System -> CEO prompting plus agent usage makes AI success 5.2x more likely."
            ],
            story_beats=[],
        )

        approved_text = " | ".join(approved)
        self.assertIn("AI Clone / Brain System", approved_text)
        self.assertIn("CEO prompting plus agent usage makes AI success 5.2x more likely", approved_text)
        self.assertNotIn("Builds", approved_text)

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
        self.assertIn(
            "Teams fail when they chase tools before workflow clarity.\n\nThe workflow still has to hold.",
            payload.get("options") or [],
        )
        diagnostics = payload.get("diagnostics") or {}
        self.assertEqual(diagnostics.get("grounding_mode"), "proof_ready")
        self.assertEqual(diagnostics.get("generation_strategy"), "planner_writer_critic")
        self.assertGreaterEqual(len(diagnostics.get("taste_scores") or []), 1)
        self.assertGreaterEqual((diagnostics.get("taste_scores") or [{}])[0].get("overall", 0), 60)
        self.assertEqual(
            diagnostics.get("primary_claims"),
            ["Teams fail when they chase tools before workflow clarity."],
        )
        self.assertEqual(
            diagnostics.get("proof_packets"),
            ["Workflow clarity -> Teams fail when they chase tools before workflow clarity."],
        )
        approved_references_text = " ".join(diagnostics.get("approved_references") or []).lower()
        self.assertIn("workflow clarity", approved_references_text)

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
        bundle_example = {
            "chunk": "Good Examples: Prompting alone is not an AI strategy. Why it works: strategic claim first. Use when: workflow clarity, agent orchestration, AI adoption.",
            "persona_tag": "LINKEDIN_EXAMPLES",
            "metadata": {
                "source": "canonical persona bundle",
                "source_kind": "canonical_bundle",
                "bundle_path": "prompts/content_examples.md",
                "file_name": "prompts/content_examples.md",
                "memory_role": "example",
                "usage_modes": ["style_reference"],
            },
        }
        canonical_claim = {
            "chunk": (
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. "
                "Evidence: Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared "
                "workspace state, and proof-aware prompts instead of isolated prompting."
            ),
            "persona_tag": "CLAIMS",
            "metadata": {
                "source": "canonical persona bundle",
                "source_kind": "canonical_bundle",
                "bundle_path": "identity/claims.md",
                "file_name": "identity/claims.md",
                "memory_role": "core",
                "claim_type": "positioning",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "proof_strength": "medium",
                "artifact_backed": True,
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
            "load_bundle_persona_chunks",
            return_value=[bundle_example, canonical_claim],
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
        self.assertEqual(context_pack.framing_modes[0], "contrarian_reframe")
        self.assertIn("contrarian_reframe", context_pack.framing_modes)
        self.assertIn("drama_tension", context_pack.framing_modes)
        self.assertGreaterEqual(len(context_pack.primary_claims), 1)
        self.assertEqual(
            context_pack.primary_claims[0],
            "AI helps when the workflow is coordinated, not improvised.",
        )
        self.assertEqual(
            context_pack.raw_primary_claims[0],
            "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
        )
        self.assertGreaterEqual(len(context_pack.proof_packets), 1)
        self.assertTrue(all("daily briefs" not in item.lower() for item in context_pack.proof_packets))
        self.assertEqual(len(context_pack.example_chunks), 2)
        self.assertEqual(
            context_pack.example_chunks[0].get("metadata", {}).get("bundle_path"),
            "prompts/content_examples.md",
        )
        self.assertEqual(
            context_pack.example_chunks[1].get("metadata", {}).get("source"),
            "JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md",
        )

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
            "load_bundle_persona_chunks",
            return_value=[],
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
            {
                "chunk": "Lead with clarity, not hype.\nTell you what tho\nAvoid opener formulas like \"X is essential\".",
                "persona_tag": "VOICE_PATTERNS",
                "metadata": {
                    "prompt_section": "CORE CANON",
                    "memory_role": "core",
                    "bundle_path": "identity/VOICE_PATTERNS.md",
                },
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
        self.assertIn("## OPTION FRAMING PLAN", prompt)
        self.assertIn("`contrarian_reframe`", prompt)
        self.assertIn("`drama_tension`", prompt)
        self.assertIn("## PRIMARY CLAIMS YOU MAY MAKE:", prompt)
        self.assertIn("## APPROVED PROOF PACKETS:", prompt)
        self.assertIn("## ONLY THESE NAMED REFERENCES MAY APPEAR:", prompt)
        self.assertIn("## VOICE SHAPING RULES:", prompt)
        self.assertIn("Lead with clarity, not hype.", prompt)
        self.assertIn("Tell you what tho", prompt)
        self.assertIn("AI Clone / Brain System", prompt)
        self.assertNotIn("Use Georgetown, Salesforce, Fusion, or Easy Outfit", prompt)

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
        self.assertFalse(
            content_generation_module.option_mentions_approved_proof(
                "Builds and translates AI execution patterns into clear operator guidance.",
                proof_packets,
            )
        )

    def test_parse_content_options_strips_option_labels_from_final_copy(self) -> None:
        options = content_generation_module.parse_content_options(
            "**Option 1: `operator_lesson`**  \nAgent orchestration starts with explicit handoffs."
            "\n---OPTION---\n"
            "**Option 2: `contrarian_reframe`**  \nPrompting alone is not the strategy."
        )

        self.assertEqual(
            options,
            [
                "Agent orchestration starts with explicit handoffs.",
                "Prompting alone is not the strategy.",
            ],
        )

    def test_option_uses_unapproved_reference_flags_stray_named_entities_and_placeholders(self) -> None:
        approved_reference_terms = [
            "AI Clone / Brain System",
            "Brain",
            "Ops",
            "daily briefs",
            "long-form routing",
            "routed workspace state",
        ]

        self.assertFalse(
            content_generation_module.option_uses_unapproved_reference(
                "Brain and Ops now read from the same routed workspace state.",
                approved_reference_terms=approved_reference_terms,
                audience="tech_ai",
            )
        )
        self.assertTrue(
            content_generation_module.option_uses_unapproved_reference(
                "That incredible video on AI execution patterns changed how I think about orchestration.",
                approved_reference_terms=approved_reference_terms,
                audience="tech_ai",
            )
        )
        self.assertTrue(
            content_generation_module.option_uses_unapproved_reference(
                "Big shout-out to Georgetown for showing what workflow clarity looks like.",
                approved_reference_terms=approved_reference_terms,
                audience="tech_ai",
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
            story_beats=[],
            framing_modes=["operator_lesson", "contrarian_reframe", "drama_tension"],
        )

        self.assertEqual(len(repaired), 3)
        self.assertTrue(all("workspace state" in option.lower() or "brain" in option.lower() for option in repaired))

    def test_enforce_grounding_on_options_repairs_stray_named_references(self) -> None:
        class _FakeResponse:
            def __init__(self, content: str) -> None:
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResponse(
                    "Brain and Ops now depend on explicit handoffs instead of isolated prompts.\n---OPTION---\n"
                    "Daily briefs and long-form routing now share the same routed workspace state.\n---OPTION---\n"
                    "Planner and content generation now inherit proof-aware prompts from the same system."
                )

        class _FakeChat:
            def __init__(self) -> None:
                self.completions = _FakeCompletions()

        class _FakeClient:
            def __init__(self) -> None:
                self.chat = _FakeChat()

        repaired = content_generation_module.enforce_grounding_on_options(
            client=_FakeClient(),
            topic="workflow clarity",
            audience="tech_ai",
            content_type="linkedin_post",
            grounding_mode="proof_ready",
            rough_options=[
                "That incredible video on AI execution patterns made workflow clarity click for me.",
                "Big shout-out to Georgetown for showing me that clear handoffs matter.",
                "Agent orchestration works better when the system is clear.",
            ],
            primary_claims=["Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone."],
            proof_packets=[
                "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting."
            ],
            story_beats=[],
            framing_modes=["operator_lesson", "contrarian_reframe", "drama_tension"],
        )

        self.assertEqual(len(repaired), 3)
        self.assertTrue(all("Georgetown" not in option for option in repaired))
        self.assertTrue(all("video" not in option.lower() for option in repaired))

    def test_options_need_voice_sharpening_flags_flat_generic_openers(self) -> None:
        self.assertTrue(
            content_generation_module._options_need_voice_sharpening(
                [
                    "Workflow clarity is essential if you want better AI outcomes.",
                    "Workflow clarity is important for good teams.",
                    "Workflow clarity is critical for modern operators.",
                ]
            )
        )
        self.assertTrue(
            content_generation_module._options_need_voice_sharpening(
                [
                    "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nWe are moving in the right direction.",
                    "Prompting alone is not an AI strategy.\n\nLet's keep pushing forward.",
                    "If there is no artifact, stay at the level of principle.\n\nThis isn't just a shift. It's a transformation.",
                ]
            )
        )
        self.assertFalse(
            content_generation_module._options_need_voice_sharpening(
                [
                    "Prompting alone is not an AI strategy.\n\nTell you what tho: orchestration is where the operating model actually shows up.",
                    "Most teams do not have an AI problem.\nThey have a handoff problem.",
                    "Big shout-out to explicit workflows.\nThey keep the system honest.",
                ]
            )
        )

    def test_score_option_taste_prefers_claim_led_operator_copy_over_generic_copy(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        grounded = content_generation_module.score_option_taste(
            "Prompting alone is not an AI strategy.\n\nBrain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.\n\nThat is the operating model.",
            brief=brief,
        )
        generic = content_generation_module.score_option_taste(
            "Agent orchestration is critical for driving results.\n\nThis gives teams a cohesive system and a comprehensive view of their work.\n\nWe're moving in the right direction.",
            brief=brief,
        )

        self.assertGreater(grounded.get("overall", 0), generic.get("overall", 0))
        self.assertIn("claim_led_opening", grounded.get("strengths", []))
        self.assertIn("proof_grounded", grounded.get("strengths", []))
        self.assertIn("taste_negative", generic.get("warnings", []))
        self.assertIn("human_paragraph_cadence", grounded.get("strengths", []))

    def test_score_option_taste_flags_weak_operator_closer_and_soft_pronoun(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        scored = content_generation_module.score_option_taste(
            "Prompting plus agent orchestration? That's the winning combo.\n\nNow, we rely on explicit handoffs, shared workspace state, and proof-aware prompts.\n\nEverything's interconnected, and it's making a tangible impact.",
            brief=brief,
        )

        self.assertIn("weak_closer", scored.get("warnings", []))
        self.assertIn("soft_operator_pronoun", scored.get("warnings", []))

    def test_finalize_planned_options_drops_filler_fragments_from_opening_sequence(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting in isolation isn't enough.\n\nWhy?\n\nNot prompting in isolation.\n\nBrain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertEqual(len(finalized), 1)
        self.assertIn("Prompting alone is not the strategy.", finalized[0])
        self.assertNotIn("Why?", finalized[0])
        self.assertNotIn("Not prompting in isolation.", finalized[0])

    def test_critique_planned_options_falls_back_when_model_returns_too_few_options(self) -> None:
        class _FakeResponse:
            def __init__(self, content: str) -> None:
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResponse("Only one option came back.")

        class _FakeChat:
            def __init__(self) -> None:
                self.completions = _FakeCompletions()

        class _FakeClient:
            def __init__(self) -> None:
                self.chat = _FakeChat()

        rough_options = [
            "Prompting alone is not an AI strategy.\n\nBrain and Ops now depend on explicit handoffs.",
            "Agent orchestration starts with shared state.\n\nThat is the operating model.",
            "Context has to travel.\n\nNot isolated prompts.",
        ]
        briefs = [
            content_generation_module.ContentOptionBrief(
                option_number=index + 1,
                framing_mode="operator_lesson",
                primary_claim="Prompting alone is not an AI strategy.",
                proof_packet="AI Clone / Brain System -> Brain and Ops now depend on explicit handoffs.",
                story_beat="",
            )
            for index in range(3)
        ]

        critiqued = content_generation_module.critique_planned_options(
            client=_FakeClient(),
            topic="agent orchestration",
            audience="tech_ai",
            grounding_mode="proof_ready",
            briefs=briefs,
            rough_options=rough_options,
            avoid_examples=[],
            voice_directives=["Lead with the thesis."],
            approved_references=["explicit handoffs"],
        )

        self.assertEqual(critiqued, rough_options)

    def test_recover_missing_planned_options_synthesizes_missing_slots(self) -> None:
        briefs = [
            content_generation_module.ContentOptionBrief(
                option_number=1,
                framing_mode="contrarian_reframe",
                primary_claim="Prompting alone is not an AI strategy.",
                proof_packet="AI Clone / Brain System -> Brain and Ops now depend on explicit handoffs and shared workspace state instead of isolated prompting.",
                story_beat="",
            ),
            content_generation_module.ContentOptionBrief(
                option_number=2,
                framing_mode="operator_lesson",
                primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs and proof-aware prompts.",
                story_beat="",
            ),
            content_generation_module.ContentOptionBrief(
                option_number=3,
                framing_mode="warning",
                primary_claim="Without explicit handoffs and shared state, it breaks.",
                proof_packet="Wins: Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.",
                story_beat="",
            ),
        ]

        recovered = content_generation_module._recover_missing_planned_options(
            [
                "Prompting alone is not an AI strategy.",
                "",
            ],
            briefs,
        )

        self.assertEqual(len(recovered), 3)
        self.assertTrue(recovered[0].startswith("Prompting alone is not an AI strategy."))
        self.assertIn("explicit handoffs", recovered[1].lower())
        self.assertIn("without that, it breaks", recovered[2].lower())
        self.assertIn("routed workspace snapshot", recovered[2].lower())

    def test_finalize_planned_options_drops_it_just_isnt_restatement(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain and Ops now depend on explicit handoffs and shared workspace state instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nIt just isn't.\n\nBrain and Ops now depend on explicit handoffs and shared workspace state instead of isolated prompting."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertEqual(len(finalized), 1)
        self.assertNotIn("It just isn't.", finalized[0])
        self.assertTrue(
            "clear handoffs" in finalized[0].lower()
            or "handoff explicit" in finalized[0].lower()
        )

    def test_default_content_provider_order_prefers_ollama_locally_and_gemini_in_production(self) -> None:
        with patch.dict(content_generation_module.os.environ, {}, clear=True):
            self.assertEqual(
                content_generation_module._default_content_provider_order(),
                ["ollama", "openai"],
            )
        with patch.dict(content_generation_module.os.environ, {"RAILWAY_PROJECT_ID": "railway-project"}, clear=True):
            self.assertEqual(
                content_generation_module._default_content_provider_order(),
                ["gemini", "openai"],
            )

    def test_resolve_provider_model_maps_fast_and_editor_models(self) -> None:
        gemini_provider = content_generation_module.ContentLLMProvider(
            name="gemini",
            client=object(),
            fast_model="gemini-2.5-flash",
            editor_model="gemini-2.5-pro",
        )
        ollama_provider = content_generation_module.ContentLLMProvider(
            name="ollama",
            client=object(),
            fast_model="llama3.1",
            editor_model="qwen2.5:14b",
        )

        self.assertEqual(
            content_generation_module._resolve_provider_model(gemini_provider, "gpt-4o-mini"),
            "gemini-2.5-flash",
        )
        self.assertEqual(
            content_generation_module._resolve_provider_model(gemini_provider, "gpt-4o"),
            "gemini-2.5-pro",
        )
        self.assertEqual(
            content_generation_module._resolve_provider_model(ollama_provider, "gpt-4o"),
            "qwen2.5:14b",
        )

    def test_content_llm_router_client_falls_back_on_quota_or_connection_error(self) -> None:
        class _ProviderError(Exception):
            def __init__(self, message: str, status_code: int | None = None) -> None:
                super().__init__(message)
                self.status_code = status_code

        class _FakeCompletions:
            def __init__(self, *, response=None, exc: Exception | None = None) -> None:
                self.response = response
                self.exc = exc
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                if self.exc:
                    raise self.exc
                return self.response

        class _FakeChat:
            def __init__(self, completions) -> None:
                self.completions = completions

        class _FakeClient:
            def __init__(self, completions) -> None:
                self.chat = _FakeChat(completions)

        success_response = type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {"message": type("Message", (), {"content": "ok"})()},
                    )()
                ]
            },
        )()
        primary_completions = _FakeCompletions(exc=_ProviderError("RESOURCE_EXHAUSTED", status_code=429))
        fallback_completions = _FakeCompletions(response=success_response)
        router = content_generation_module.ContentLLMRouterClient(
            [
                content_generation_module.ContentLLMProvider(
                    name="gemini",
                    client=_FakeClient(primary_completions),
                    fast_model="gemini-2.5-flash",
                    editor_model="gemini-2.5-pro",
                ),
                content_generation_module.ContentLLMProvider(
                    name="openai",
                    client=_FakeClient(fallback_completions),
                    fast_model="gpt-4o-mini",
                    editor_model="gpt-4o",
                ),
            ]
        )

        response = router.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.2,
        )

        self.assertIs(response, success_response)
        self.assertEqual(primary_completions.calls[0]["model"], "gemini-2.5-flash")
        self.assertEqual(fallback_completions.calls[0]["model"], "gpt-4o-mini")
        self.assertEqual(router.provider_trace[0]["provider"], "gemini")
        self.assertEqual(router.provider_trace[0]["status"], "failed")
        self.assertEqual(router.provider_trace[1]["provider"], "gemini")
        self.assertEqual(router.provider_trace[1]["status"], "failed")
        self.assertEqual(router.provider_trace[2]["provider"], "openai")
        self.assertEqual(router.provider_trace[2]["status"], "success")

    def test_score_option_taste_flags_missing_named_reference_for_operator_warning(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="warning",
            primary_claim="Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.",
            proof_packet="Wins: Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.",
            story_beat="",
        )

        scored = content_generation_module.score_option_taste(
            "Without that, it breaks.\n\nNot living in isolated tools.\n\nNow, operator context flows seamlessly across the system instead of getting trapped in isolated tools.",
            brief=brief,
        )

        self.assertIn("named_reference_missing", scored.get("warnings", []))
        self.assertIn("taste_negative", scored.get("warnings", []))

    def test_rank_options_by_taste_surfaces_best_option_first(self) -> None:
        options = [
            "Prompting alone is not the strategy.",
            "Prompting alone is not an AI strategy.",
            "Without that, it breaks.",
        ]
        briefs = [
            content_generation_module.ContentOptionBrief(
                option_number=1,
                framing_mode="contrarian_reframe",
                primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                proof_packet="",
                story_beat="",
            ),
            content_generation_module.ContentOptionBrief(
                option_number=2,
                framing_mode="operator_lesson",
                primary_claim="Prompting alone is not an AI strategy.",
                proof_packet="",
                story_beat="",
            ),
            content_generation_module.ContentOptionBrief(
                option_number=3,
                framing_mode="warning",
                primary_claim="Without that, it breaks.",
                proof_packet="",
                story_beat="",
            ),
        ]
        taste_scores = [
            {"overall": 77},
            {"overall": 95},
            {"overall": 97},
        ]

        ranked_options, ranked_briefs, ranked_scores = content_generation_module._rank_options_by_taste(
            options=options,
            briefs=briefs,
            taste_scores=taste_scores,
        )

        self.assertEqual(ranked_options[0], "Without that, it breaks.")
        self.assertEqual(ranked_briefs[0].framing_mode, "warning")
        self.assertEqual(ranked_scores[0].get("overall"), 97)

    def test_sharpen_editorial_options_rewrites_flat_openers_without_losing_proof(self) -> None:
        class _FakeResponse:
            def __init__(self, content: str) -> None:
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResponse(
                    "Most teams do not have an orchestration problem.\nBrain and Ops now read from the same workspace state instead of isolated views.\n---OPTION---\n"
                    "Most orchestration advice is too loose.\nDaily briefs and planner now share the same routed workspace state.\n---OPTION---\n"
                    "Tell you what tho: workflow clarity shows up in the handoff.\nLong-form routing now moves through the same shared workspace state."
                )

        class _FakeChat:
            def __init__(self) -> None:
                self.completions = _FakeCompletions()

        class _FakeClient:
            def __init__(self) -> None:
                self.chat = _FakeChat()

        persona_chunks = [
            {
                "chunk": "Lead with clarity, not hype.\nTell you what tho\nUse short, punchy lines when the point needs force.",
                "persona_tag": "VOICE_PATTERNS",
                "metadata": {
                    "prompt_section": "CORE CANON",
                    "memory_role": "core",
                    "bundle_path": "identity/VOICE_PATTERNS.md",
                },
            }
        ]
        sharpened = content_generation_module.sharpen_editorial_options(
            client=_FakeClient(),
            topic="agent orchestration",
            audience="tech_ai",
            content_type="linkedin_post",
            grounding_mode="principle_only",
            persona_chunks=persona_chunks,
            rough_options=[
                "Workflow clarity is essential for AI systems.",
                "Agent orchestration is critical for teams.",
                "Workflow clarity is important for operators.",
            ],
            primary_claims=["Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone."],
            proof_packets=[
                "AI Clone / Brain System -> Brain and Ops now read from the same workspace state instead of isolated views.",
                "Daily briefs / Planner -> Daily briefs and planner now share the same routed workspace state.",
                "Long-form routing -> Long-form routing now moves through the same shared workspace state.",
            ],
            story_beats=[],
            framing_modes=["operator_lesson", "contrarian_reframe", "drama_tension"],
        )

        self.assertEqual(len(sharpened), 3)
        self.assertTrue(any("brain and ops" in option.lower() for option in sharpened))
        self.assertTrue(any("daily briefs" in option.lower() for option in sharpened))
        self.assertTrue(any("long-form routing" in option.lower() for option in sharpened))
        self.assertTrue(all("is essential" not in option.lower() for option in sharpened))

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

    def test_build_content_prompt_separates_good_and_avoid_example_references(self) -> None:
        persona_chunks = [
            {
                "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                "persona_tag": "PHILOSOPHY",
                "metadata": {"prompt_section": "CORE CANON"},
            }
        ]
        example_chunks = [
            {
                "chunk": "Good Examples: Prompting alone is not an AI strategy. Why it works: strategic claim first. Use when: workflow clarity, agent orchestration, AI adoption.",
                "persona_tag": "LINKEDIN_EXAMPLES",
                "metadata": {"source": "canonical persona bundle"},
            },
            {
                "chunk": "Avoid Patterns: Agent orchestration is critical for driving results. Why it fails: vague, corporate, generic.",
                "persona_tag": "LINKEDIN_EXAMPLES",
                "metadata": {"source": "canonical persona bundle"},
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
            example_chunks=example_chunks,
            audience="tech_ai",
        )

        self.assertIn("## GOOD STYLE REFERENCES:", prompt)
        self.assertIn("Prompting alone is not an AI strategy", prompt)
        self.assertIn("## AVOID PATTERN REFERENCES:", prompt)
        self.assertIn("Agent orchestration is critical for driving results", prompt)
        self.assertIn("Do not borrow facts or named stories", prompt)

    def test_plan_content_option_briefs_preserves_claim_and_proof_pairs(self) -> None:
        briefs = content_generation_module.plan_content_option_briefs(
            primary_claims=[
                "Prompting alone is not an AI strategy.",
                "If there is no artifact, keep the writing at the level of principle or hypothesis.",
            ],
            proof_packets=[
                "AI Clone / Brain System -> Brain, Ops, planner, and briefs now share the same routed workspace state.",
            ],
            story_beats=[],
            framing_modes=["contrarian_reframe", "operator_lesson", "agree_and_extend"],
            option_count=3,
        )

        self.assertEqual(len(briefs), 3)
        self.assertEqual(briefs[0].primary_claim, "Prompting alone is not an AI strategy.")
        self.assertEqual(briefs[0].proof_packet, "AI Clone / Brain System -> Brain, Ops, planner, and briefs now share the same routed workspace state.")
        self.assertEqual(briefs[1].framing_mode, "operator_lesson")

    def test_build_planned_writer_prompt_uses_good_examples_without_avoid_patterns(self) -> None:
        prompt = content_generation_module.build_planned_writer_prompt(
            topic="agent orchestration",
            context="",
            audience="tech_ai",
            grounding_mode="proof_ready",
            grounding_reason="Artifact-backed proof is available.",
            topic_anchor_chunks=[],
            proof_anchor_chunks=[],
            story_anchor_chunks=[],
            briefs=[
                content_generation_module.ContentOptionBrief(
                    option_number=1,
                    framing_mode="contrarian_reframe",
                    primary_claim="Prompting alone is not an AI strategy.",
                    proof_packet="AI Clone / Brain System -> Brain, Ops, planner, and briefs now share the same routed workspace state.",
                    story_beat="",
                )
            ],
            good_examples=[
                "Good Examples: Prompting alone is not an AI strategy. Why it works: strategic claim first.",
            ],
            voice_directives=["Lead with clarity, not hype."],
            approved_references=["AI Clone / Brain System"],
            disallowed_moves=["Do not invent metrics."],
        )

        self.assertIn("GOOD STYLE REFERENCES", prompt)
        self.assertIn("Prompting alone is not an AI strategy", prompt)
        self.assertNotIn("AVOID PATTERN REFERENCES", prompt)

    def test_finalize_planned_options_replaces_flat_opening_with_claim(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, planner, and briefs now share the same routed workspace state.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=["Agent orchestration is critical for driving results.\n\nTeams need more clarity."],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("Prompting alone is not an AI strategy.", finalized[0])
        self.assertIn("Operator context has to travel.", finalized[0])

    def test_finalize_planned_options_drops_generic_closer_lines(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nBrain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.\n\nWe're breaking down silos and fostering collaboration at every step. Let's keep pushing forward."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("shared state keeps context alive across the handoff.", finalized[0].lower())
        self.assertNotIn("breaking down silos", finalized[0].lower())
        self.assertNotIn("let's keep pushing", finalized[0].lower())

    def test_finalize_planned_options_shapes_contrarian_opening(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nBrain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertTrue(finalized[0].startswith("Prompting alone is not the strategy."))
        self.assertIn("shared state keeps context alive across the handoff.", finalized[0].lower())

    def test_finalize_planned_options_inserts_contrast_and_punch_line_when_missing(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nBrain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("ai only helps when the workflow is coordinated.", finalized[0].lower())
        self.assertIn("shared state keeps context alive across the handoff.", finalized[0].lower())
        self.assertGreaterEqual(finalized[0].count("\n\n"), 2)

    def test_finalize_planned_options_rewrites_soft_operator_closer(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting plus agent orchestration? That's the winning combo.\n\nJohnnie treats this approach as a stronger AI operating pattern than just prompting alone.\n\nNow, we rely on explicit handoffs, shared workspace state, and proof-aware prompts across Brain, Ops, daily briefs, planner, and long-form routing.\n\nIsolated prompting is a thing of the past. Everything's interconnected, and it's making a tangible impact."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("shared state keeps context alive across the handoff.", finalized[0].lower())
        self.assertNotIn("tangible impact", finalized[0].lower())
        self.assertNotIn("everything's interconnected", finalized[0].lower())
        self.assertNotIn("\n\nNow, we rely on", finalized[0])
        self.assertRegex(
            finalized[0].rstrip(),
            r"(The workflow has to carry the load\.|Isolated prompting is a thing of the past\.)$",
        )

    def test_finalize_planned_options_compresses_abstract_operator_middle_and_drops_label_tail(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nNow, Brain, Ops, daily briefs, planner, long-form routing, and content generation depend on explicit handoffs, shared workspace state, and proof-aware prompts.\n\nThis approach ensures context travels across the system instead of getting lost in isolated prompts.\n\nAgent orchestration is where AI truly excels.\n\nAgent orchestration."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("Context travels.", finalized[0])
        self.assertIn("Not isolated prompts.", finalized[0])
        self.assertNotIn("This approach ensures", finalized[0])
        self.assertFalse(finalized[0].rstrip().endswith("Agent orchestration."))

    def test_finalize_planned_options_rewrites_soft_operator_body_lines(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not the strategy.\n\nJohnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nOur system now integrates Brain, Ops, daily briefs, planner, and long-form routing into a unified approach.\n\nThis means we rely on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.\n\nIt's not just about asking the right questions; it's about orchestrating the entire process for superior AI outcomes."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("Now it runs on clear handoffs, context survives the handoff, and prompts tied to proof.", finalized[0])
        self.assertRegex(finalized[0].rstrip(), r"Not isolated prompts\.$")
        self.assertNotIn("unified approach", finalized[0].lower())
        self.assertNotIn("it's not just about", finalized[0].lower())

    def test_finalize_planned_options_inserts_mid_punch_line_when_no_short_sentence_exists(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nJohnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nBrain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts.\n\nIsolated prompting just doesn't cut it anymore."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertRegex(
            finalized[0],
            r"\n\n(Explicit handoffs\.|Shared state\.|Proof-aware prompts\.|Not prompting in isolation\.)\n\n",
        )

    def test_finalize_planned_options_rewrites_generic_warning_body_and_strips_label_prefix(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="warning",
            primary_claim="Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.",
            proof_packet="Wins: Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Without that, it breaks.\n\nFor effective AI, all components of the operation must be interconnected.\n\nThis integration is crucial; without it, the system breaks.\n\nWins: Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertIn("context survives the handoff.", finalized[0].lower())
        self.assertNotIn("For effective AI", finalized[0])
        self.assertNotIn("interconnected", finalized[0].lower())
        self.assertNotIn("Wins:", finalized[0])

    def test_finalize_planned_options_rewrites_brain_reliability_body_lines(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing operate from a single routed workspace snapshot. Previously, we dealt with malformed JSON and inconsistent schema discipline. We're enhancing output handling and validation, even as we continue to improve reliability.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nThe AI Clone / Brain System illustrates this clearly. Now, Brain, Ops, daily briefs, planner, persona review, and long-form routing operate from a single routed workspace snapshot. Previously, we dealt with malformed JSON and inconsistent schema discipline. Daily briefs. We're enhancing output handling and validation, even as we continue to improve reliability. That is the operating model."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertNotIn("Daily briefs.", finalized[0])
        self.assertIn("Malformed JSON kept breaking the flow.", finalized[0])
        self.assertIn("Output handling is stricter now.", finalized[0])
        self.assertIn("Reliability is better, but not done.", finalized[0])

    def test_finalize_planned_options_drops_opening_echo_and_generic_outcomes_closer(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not the strategy.\n\nThat's not a viable AI strategy. Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. Our Brain, Ops, daily briefs, planner, and long-form routing now depend on explicit handoffs, shared workspace state, and proof-aware prompts. Isolated prompting is a thing of the past. It's all about connecting the dots for better outcomes."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized)
        self.assertNotIn("That's not a viable AI strategy.", finalized[0])
        self.assertNotIn("It's all about", finalized[0])
        self.assertNotIn("better outcomes", finalized[0].lower())
        self.assertIn("Johnnie treats prompting plus coordinated workflow", finalized[0])
        self.assertRegex(finalized[0].rstrip(), r"Isolated prompting is a thing of the past\.$")

    def test_parse_content_options_strips_markdown_option_headings(self) -> None:
        options = content_generation_module.parse_content_options(
            "### OPTION 1\nPrompting alone is not an AI strategy.\n---OPTION---\n### OPTION 2\nIf there is no artifact, stay at the level of principle."
        )

        self.assertEqual(
            options,
            [
                "Prompting alone is not an AI strategy.",
                "If there is no artifact, stay at the level of principle.",
            ],
        )

        bold_options = content_generation_module.parse_content_options(
            "**OPTION 1**  \nPrompting alone is not an AI strategy.\n---OPTION---\n**OPTION 2**  \nIf there is no artifact, stay at the level of principle."
        )

        self.assertEqual(
            bold_options,
            [
                "Prompting alone is not an AI strategy.",
                "If there is no artifact, stay at the level of principle.",
            ],
        )

    def test_parse_content_options_splits_numbered_option_headings_without_delimiters(self) -> None:
        options = content_generation_module.parse_content_options(
            "Option 1: `contrarian_reframe`\nPrompting alone is not an AI strategy.\n\n"
            "Option 2: `operator_lesson`\nAgent orchestration starts with explicit handoffs.\n\n"
            "Option 3: `warning`\nWithout shared state, the workflow breaks."
        )

        self.assertEqual(
            options,
            [
                "Prompting alone is not an AI strategy.",
                "Agent orchestration starts with explicit handoffs.",
                "Without shared state, the workflow breaks.",
            ],
        )

    def test_parse_content_options_splits_markdown_option_headings_without_delimiters(self) -> None:
        options = content_generation_module.parse_content_options(
            "### OPTION 1\nPrompting alone is not an AI strategy.\n\n"
            "### OPTION 2\nAgent orchestration starts with explicit handoffs.\n\n"
            "### OPTION 3\nWithout shared state, the workflow breaks."
        )

        self.assertEqual(
            options,
            [
                "Prompting alone is not an AI strategy.",
                "Agent orchestration starts with explicit handoffs.",
                "Without shared state, the workflow breaks.",
            ],
        )

    def test_finalize_planned_options_rewrites_soft_operator_pronouns(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes; output handling and validation are stricter now.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nNow, we’ve tightened output handling and validation.\n\nWe began building the AI Clone / Brain System as a persistent operator platform."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("soft_operator_pronoun", scored.get("warnings", []))
        self.assertNotIn("Now, we", finalized[0])
        self.assertNotIn("We began", finalized[0])

    def test_finalize_planned_options_inserts_short_sentence_when_missing(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="warning",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nThe system only holds when context moves across shared state and explicit handoffs instead of disappearing into isolated prompts."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("no_short_sentence", scored.get("warnings", []))

    def test_finalize_planned_options_rewrites_with_weve_unified_operator_sentence(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nWith the AI Clone / Brain System, we’ve unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("soft_operator_pronoun", scored.get("warnings", []))
        self.assertNotIn("we’ve unified", finalized[0].lower())
        self.assertIn("context survives the handoff.", finalized[0].lower())

    def test_finalize_planned_options_rewrites_seamless_operator_setup_sentence(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="If the workflow is unclear, AI just scales confusion.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Isolation stifles progress.\n\nAI Clone / Brain System made the handoff visible.\n\nWith this setup, context flows seamlessly, enhancing content generation and decision-making."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertNotIn("seamlessly", lowered)
        self.assertNotIn("enhancing content generation", lowered)
        self.assertIn("context survives the handoff.", lowered)
        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("taste_negative", scored.get("warnings", []))

    def test_finalize_planned_options_compresses_internal_operator_catalog_lines(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nUnified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.\n\nBrain, Ops, daily briefs, planner, persona review, and long-form routing now run on one routed workspace snapshot."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertNotIn("brain, ops, daily briefs", lowered)
        self.assertIn("context survives the handoff.", lowered)
        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("taste_negative", scored.get("warnings", []))

    def test_finalize_planned_options_drops_operator_catalog_essential_sentence(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="Agent orchestration proof -> Daily briefs, long-form routing, proof-aware prompts, shared workspace state, and explicit handoffs now anchor the workflow.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not the strategy.\n\nIt’s just noise without context.\n\nDaily briefs, long-form routing, and proof-aware prompts are now essential to our content generation."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertNotIn("are now essential", lowered)
        self.assertIn("shared state keeps context alive across the handoff.", lowered)
        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("genericity:2", scored.get("warnings", []))

    def test_finalize_planned_options_restores_named_reference_specificity_for_operator_copy(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="If the workflow is unclear, AI just scales confusion.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Unified systems drive real results.\n\nOne routed workspace snapshot now keeps context alive. Previously, we struggled with malformed JSON and weak schema discipline. Now, stricter output handling is embedded in the architecture."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertIn("context survives the handoff.", lowered)
        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("named_reference_missing", scored.get("warnings", []))

    def test_finalize_planned_options_replaces_unified_approach_opening_with_claim(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="If the workflow is unclear, AI just scales confusion.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "A unified approach is essential for maintaining operator context across systems.\n\nAI Clone / Brain System made the handoff visible.\n\nOne routed workspace snapshot now keeps context alive. No more fragmented tools. Content generation now reads canon through typed lanes, ensuring everything flows smoothly."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        self.assertTrue(finalized[0].startswith("If the workflow is unclear, AI just scales confusion."))
        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("taste_negative", scored.get("warnings", []))
        self.assertNotIn("claim_not_leading", scored.get("warnings", []))

    def test_rank_options_by_taste_prefers_topic_aligned_ai_adoption_option(self) -> None:
        generic_brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> shared workspace state and explicit handoffs make operator context visible.",
            story_beat="",
        )
        adoption_brief = content_generation_module.ContentOptionBrief(
            option_number=2,
            framing_mode="operator_lesson",
            primary_claim="AI adoption gets real when the workflow gets easier for the operator.",
            proof_packet="Fusion Academy Dashboard Transformation -> people adopted the dashboard because clear next actions made the workflow easier to use.",
            story_beat="",
        )

        ordered_options, ordered_briefs, _ = content_generation_module._rank_options_by_taste(
            options=[
                "Prompting alone is not an AI strategy.\n\nShared state keeps context alive across the handoff.\n\nThat is the operating model.",
                "AI adoption gets real when the workflow gets easier for the operator.\n\nPeople adopt what makes their life easier, not what leadership tells them to use.\n\nThe Fusion Academy Dashboard Transformation made the next action clear.",
            ],
            briefs=[generic_brief, adoption_brief],
            taste_scores=[{"overall": 92}, {"overall": 89}],
            topic="AI adoption",
            audience="tech_ai",
        )

        self.assertIn("AI adoption gets real", ordered_options[0])
        self.assertEqual(ordered_briefs[0].primary_claim, adoption_brief.primary_claim)

    def test_rank_options_by_taste_penalizes_education_option_that_drops_policy_signal(self) -> None:
        drifted_brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Admissions is not just enrollment; it is translation.",
            proof_packet="Fusion Academy Market Development -> Coffee and Convo events help families understand the process.",
            story_beat="",
        )
        policy_brief = content_generation_module.ContentOptionBrief(
            option_number=2,
            framing_mode="operator_lesson",
            primary_claim="Admissions is not just enrollment; it is translation.",
            proof_packet="Fusion Academy Dashboard Transformation -> the policy signal was translated into clearer next actions for school teams and families.",
            story_beat="",
        )

        ordered_options, _, _ = content_generation_module._rank_options_by_taste(
            options=[
                "Admissions isn’t just enrollment; it’s translation.\n\nCoffee and Convo events make the family experience feel more personal.",
                "Admissions isn’t just enrollment; it’s translation.\n\nWhen faculty-cut bills hit, school teams need language families can trust.\n\nThe dashboard made the next action clear.",
            ],
            briefs=[drifted_brief, policy_brief],
            taste_scores=[{"overall": 92}, {"overall": 89}],
            topic="Kentucky Senate passes bill making it easier to cut faculty",
            audience="education_admissions",
        )

        self.assertIn("faculty-cut bills", ordered_options[0].lower())

    def test_rank_options_by_taste_prefers_thesis_led_agent_orchestration_option(self) -> None:
        proof_led_brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="One routed workspace snapshot now keeps context alive.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )
        thesis_led_brief = content_generation_module.ContentOptionBrief(
            option_number=2,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        ordered_options, ordered_briefs, _ = content_generation_module._rank_options_by_taste(
            options=[
                "One routed workspace snapshot now keeps context alive.\n\nAI Clone / Brain System made the handoff visible.\n\nShared state keeps context alive across the handoff.",
                "Prompting alone is not an AI strategy.\n\nAI Clone / Brain System made the handoff visible.\n\nOne routed workspace snapshot now keeps context alive.",
            ],
            briefs=[proof_led_brief, thesis_led_brief],
            taste_scores=[{"overall": 93}, {"overall": 90}],
            topic="agent orchestration",
            audience="tech_ai",
        )

        self.assertIn("prompting alone is not an ai strategy", ordered_options[0].lower())
        self.assertEqual(ordered_briefs[0].primary_claim, thesis_led_brief.primary_claim)

    def test_score_option_taste_flags_internal_public_leak_and_proof_overload(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=3,
            framing_mode="operator_lesson",
            primary_claim="We finally stopped sending raw context to the writer.",
            proof_packet="Content generation now reads persona through typed core, proof, story, and example lanes; applies domain gates; and enforces approved proof packets before final drafts; meetings rose by more than 20%; referrals rose by more than 50%.",
            story_beat="",
            public_lane="build_in_public",
        )

        scored = content_generation_module.score_option_taste(
            "We finally stopped sending persona soup to the writer.\n\nContent generation now reads persona through typed core, proof, story, and example lanes, applies domain gates, and enforces approved proof packets before final drafts; meetings rose by more than 20%, referrals rose by more than 50%, and leadership engagement increased.",
            brief=brief,
        )

        self.assertIn("internal_public_leak", scored.get("warnings", []))
        self.assertIn("proof_overloaded", scored.get("warnings", []))

    def test_score_option_taste_flags_operator_catalog_public_leak(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="AI does not create the edge by itself. Clear operating context does.",
            proof_packet="Workflow clarity proof -> clearer handoffs and clearer proof rules made the workflow more reliable.",
            story_beat="",
            public_lane="operator_lesson",
        )

        scored = content_generation_module.score_option_taste(
            "Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot.",
            brief=brief,
        )

        self.assertIn("internal_public_leak", scored.get("warnings", []))

    def test_rank_options_by_taste_prefers_public_safe_option_over_internal_jargon(self) -> None:
        internal_brief = content_generation_module.ContentOptionBrief(
            option_number=3,
            framing_mode="operator_lesson",
            primary_claim="We finally stopped sending raw context to the writer.",
            proof_packet="Content generation now reads persona through typed core, proof, story, and example lanes; applies domain gates; and enforces approved proof packets before final drafts.",
            story_beat="",
            public_lane="build_in_public",
        )
        public_brief = content_generation_module.ContentOptionBrief(
            option_number=2,
            framing_mode="operator_lesson",
            primary_claim="We stopped making the writer do infrastructure work.",
            proof_packet="The workflow now blocks weak drafts before they ship and leaves tone work for the final pass.",
            story_beat="",
            public_lane="build_in_public",
        )

        ordered_options, ordered_briefs, _ = content_generation_module._rank_options_by_taste(
            options=[
                "We finally stopped sending persona soup to the writer.\n\nContent generation now reads persona through typed core, proof, story, and example lanes, applies domain gates, and enforces approved proof packets before final drafts.",
                "We stopped making the writer do infrastructure work.\n\nThe workflow now blocks weak drafts before they ship, so editing can stay focused on tone and judgment.\n\nThat is what the build taught us.",
            ],
            briefs=[internal_brief, public_brief],
            taste_scores=[{"overall": 95}, {"overall": 90}],
            topic="workflow clarity",
            audience="tech_ai",
        )

        self.assertIn("infrastructure work", ordered_options[0].lower())
        self.assertEqual(ordered_briefs[0].primary_claim, public_brief.primary_claim)

    def test_build_planned_writer_prompt_adds_education_policy_guardrail(self) -> None:
        prompt = content_generation_module.build_planned_writer_prompt(
            topic="Kentucky Senate passes bill making it easier to cut faculty",
            context="",
            audience="education_admissions",
            grounding_mode="proof_ready",
            grounding_reason="proof ready",
            topic_anchor_chunks=[],
            proof_anchor_chunks=[],
            story_anchor_chunks=[],
            briefs=[
                content_generation_module.ContentOptionBrief(
                    option_number=1,
                    framing_mode="operator_lesson",
                    primary_claim="Admissions is not just enrollment; it is translation.",
                    proof_packet="Fusion Academy Dashboard Transformation -> clearer next actions for school teams.",
                    story_beat="",
                )
            ],
            good_examples=[],
            voice_directives=[],
            approved_references=[],
            disallowed_moves=[],
        )

        self.assertIn("Keep the policy / school / faculty signal visible.", prompt)

    def test_build_planned_writer_prompt_bans_third_person_persona_framing_and_internal_shorthand(self) -> None:
        prompt = content_generation_module.build_planned_writer_prompt(
            topic="AI is not making every market meaner",
            context="Use the operator systems angle.",
            audience="tech_ai",
            grounding_mode="proof_ready",
            grounding_reason="proof ready",
            topic_anchor_chunks=[],
            proof_anchor_chunks=[],
            story_anchor_chunks=[],
            briefs=[
                content_generation_module.ContentOptionBrief(
                    option_number=1,
                    framing_mode="contrarian_reframe",
                    primary_claim="AI is not making every market meaner.",
                    proof_packet="Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                    story_beat="",
                    public_lane="market_insight",
                )
            ],
            good_examples=[],
            voice_directives=[],
            approved_references=[],
            disallowed_moves=[],
        )

        self.assertIn("Never write about the author in third person", prompt)
        self.assertIn("Do not use public-facing shorthand like `shared workspace state`", prompt)
        self.assertIn("keep the opener on that claim", prompt.lower())

    def test_focus_terms_support_leadership_management_alias(self) -> None:
        route_terms = content_generation_module._focus_terms("change management", "leadership_management")
        service_terms = content_context_service_module._focus_terms("change management", "leadership_management")

        self.assertIn("people", route_terms)
        self.assertIn("behavior", route_terms)
        self.assertIn("leadership", service_terms)
        self.assertIn("change", service_terms)

    def test_content_generation_benchmark_stability_mode_lowers_temperatures(self) -> None:
        with patch.dict("os.environ", {"CONTENT_GENERATION_STABILITY_MODE": "benchmark"}, clear=False):
            self.assertEqual(content_generation_module._writer_temperature("tech_ai"), 0.2)
            self.assertEqual(content_generation_module._writer_temperature("education_admissions"), 0.28)
            self.assertEqual(content_generation_module._critic_temperature(), 0.15)
            self.assertEqual(content_generation_module._refinement_temperature(), 0.12)
            self.assertEqual(content_generation_module._final_editor_temperature(), 0.12)
            self.assertEqual(content_generation_module._proof_enforcement_temperature(), 0.1)
            self.assertEqual(content_generation_module._legacy_generation_temperature("tech_ai"), 0.25)
            self.assertEqual(content_generation_module._legacy_generation_temperature("education_admissions"), 0.35)

        with patch.dict("os.environ", {}, clear=False):
            content_generation_module.os.environ.pop("CONTENT_GENERATION_STABILITY_MODE", None)
            self.assertEqual(content_generation_module._writer_temperature("tech_ai"), 0.55)
            self.assertEqual(content_generation_module._writer_temperature("education_admissions"), 0.72)
            self.assertEqual(content_generation_module._critic_temperature(), 0.25)
            self.assertEqual(content_generation_module._refinement_temperature(), 0.35)
            self.assertEqual(content_generation_module._final_editor_temperature(), 0.35)
            self.assertEqual(content_generation_module._proof_enforcement_temperature(), 0.2)
            self.assertEqual(content_generation_module._legacy_generation_temperature("tech_ai"), 0.68)
            self.assertEqual(content_generation_module._legacy_generation_temperature("education_admissions"), 0.85)

    def test_finalize_planned_options_warning_mode_keeps_claim_led_opening(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="warning",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="AI adoption proof -> shared workspace state, typed retrieval, and explicit handoffs now anchor the workflow instead of isolated prompting.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.\n\nOperator context has to travel.\n\nWithout that, it breaks."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        first_line = finalized[0].splitlines()[0].strip().lower()
        self.assertIn("prompting plus agent orchestration", first_line)
        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("claim_not_leading", scored.get("warnings", []))

    def test_score_option_taste_accepts_prompting_alone_contrarian_opener_for_agent_orchestration(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        scored = content_generation_module.score_option_taste(
            "Prompting alone is not the strategy.\n\nShared state keeps context alive across the handoff.\n\nAI Clone / Brain System made the handoff visible.",
            brief=brief,
        )

        self.assertNotIn("claim_not_leading", scored.get("warnings", []))
        self.assertIn("claim_led_opening", scored.get("strengths", []))

    def test_clean_generic_sentences_drops_cohesive_system_filler(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        cleaned = content_generation_module._clean_generic_sentences(
            "Prompting alone is not the strategy.\n\nShared state keeps context alive across the handoff. This shift fundamentally changes our approach to AI, creating a cohesive system that operates in concert rather than in isolation.",
            brief,
        )

        lowered = cleaned.lower()
        self.assertIn("shared state keeps context alive across the handoff.", lowered)
        self.assertNotIn("cohesive system", lowered)
        self.assertNotIn("operates in concert", lowered)

    def test_ensure_paragraph_cadence_dedupes_and_splits_benchmark_agent_orchestration_output(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        with patch.dict("os.environ", {"CONTENT_GENERATION_STABILITY_MODE": "benchmark"}, clear=False):
            revised = content_generation_module._ensure_paragraph_cadence(
                "Prompting alone is not the strategy. Shared state keeps context alive across the handoff. Shared state keeps context alive across the handoff.",
                brief,
            )

        self.assertEqual(
            revised,
            "Prompting alone is not the strategy.\n\nShared state keeps context alive across the handoff.",
        )

    def test_finalize_planned_options_rewrites_generic_named_reference_sentence(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="Prompting alone is not an AI strategy.",
            proof_packet="AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Prompting alone is not an AI strategy.\n\nThe AI Clone / Brain System illustrates this clearly.\n\nOne routed workspace snapshot now keeps context alive."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertIn("ai clone / brain system made the handoff visible.", lowered)
        self.assertNotIn("illustrates this clearly", lowered)

    def test_option_named_reference_specificity_rejects_routed_workspace_snapshot_fragment(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            proof_packet="Agent orchestration proof -> one routed workspace snapshot now keeps context alive across the handoff instead of isolated prompting.",
            story_beat="",
        )

        self.assertFalse(
            content_generation_module._option_has_named_reference_specificity(
                "One routed workspace snapshot now keeps context alive.\n\nIsolated prompting just doesn't cut it anymore.",
                brief,
            )
        )

    def test_sanitize_public_output_drops_meta_scaffold_and_dedupes_bridge(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="AI is not making every market meaner.",
            proof_packet="Agent orchestration proof -> shared workspace state and explicit handoffs matter more than isolated prompting.",
            story_beat="",
            public_lane="market_insight",
        )

        sanitized = content_generation_module._sanitize_public_output(
            "The key insight is that AI is not uniformly intensifying competition everywhere.\n\nAI isn't making every market meaner.\n\nNot prompting in isolation.\n\nShared state keeps context alive across the handoff.\n\nShared state keeps context alive across the handoff.",
            brief,
        )

        lowered = sanitized.lower()
        self.assertNotIn("the key insight is that", lowered)
        self.assertNotIn("shared state keeps context alive across the handoff.", lowered)
        self.assertEqual(sanitized.strip(), "AI isn't making every market meaner.")

    def test_finalize_planned_options_rewrites_third_person_persona_opening(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="AI is not making every market meaner.",
            proof_packet="Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
            story_beat="",
            public_lane="market_insight",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.\n\nThe same tooling lands very differently when the operating playbook is clear."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertFalse(lowered.startswith("johnnie is"))
        self.assertIn("ai is not making every market meaner.", lowered)

    def test_score_option_taste_flags_persona_bio_opening(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="AI is not making every market meaner.",
            proof_packet="Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
            story_beat="",
            public_lane="market_insight",
        )

        scored = content_generation_module.score_option_taste(
            "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.\n\nThe same tooling lands very differently when the operating playbook is clear.",
            brief=brief,
        )

        self.assertIn("persona_bio_opening", scored.get("warnings", []))

    def test_topic_alignment_penalizes_market_topic_that_opens_on_prompting(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="AI is not making every market meaner.",
            proof_packet="Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
            story_beat="",
            public_lane="market_insight",
        )

        score = content_generation_module._topic_alignment_score(
            option="Prompting alone is not the strategy.\n\nThe workflow only holds when ownership is clear.",
            brief=brief,
            topic="AI is not making every market meaner",
            audience="tech_ai",
        )

        self.assertLess(score, 0)

    def test_contrast_line_rewrites_isolated_tools_fragment(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="warning",
            primary_claim="If the workflow is unclear, AI just scales confusion.",
            proof_packet="Wins -> operator context travels across the system instead of living in isolated tools.",
            story_beat="",
            public_lane="build_in_public",
        )

        self.assertEqual(content_generation_module._contrast_line_from_brief(brief), "Not fragmented tools.")

    def test_finalize_planned_options_adds_contrast_line_for_dashboard_proof(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Technology can help close gaps in education access and equity, but only if adoption is real.",
            proof_packet="Fusion Academy Dashboard Transformation -> Daily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard; high-priority, active-pipeline, and gray-area outreach became clearer; leadership engagement increased because execution was easier to see.",
            story_beat="",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "The Kentucky Senate's recent bill easing faculty cuts is a stark reminder of the pressure education teams are under.\n\nJohnnie is building at the intersection of education, AI systems, entrepreneurship, and style.\n\nWith the Fusion Academy Dashboard Transformation, we unified metrics into one Salesforce dashboard, clarifying outreach and execution."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        scored = content_generation_module.score_option_taste(finalized[0], brief=brief)
        self.assertNotIn("low_contrast", scored.get("warnings", []))
        self.assertIn("Visibility should change the next move.", finalized[0])

    def test_finalize_planned_options_market_lane_drops_stock_operator_house_lines(self) -> None:
        brief = content_generation_module.ContentOptionBrief(
            option_number=1,
            framing_mode="contrarian_reframe",
            primary_claim="AI is not making every market meaner.",
            proof_packet="Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
            story_beat="",
            public_lane="market_insight",
        )

        finalized = content_generation_module.finalize_planned_options(
            options=[
                "The key insight is that AI is not uniformly intensifying competition everywhere.\n\nai is not making every market meaner.\n\nNot more reporting.\n\nClearer action.\n\nTeams with clear buyer ownership get more out of the same tooling.\n\nThat is the operating model."
            ],
            briefs=[brief],
            grounding_mode="proof_ready",
        )

        lowered = finalized[0].lower()
        self.assertNotIn("not more reporting.", lowered)
        self.assertNotIn("clearer action.", lowered)
        self.assertNotIn("that is the operating model.", lowered)
        self.assertIn("AI is not making every market meaner.", finalized[0])

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
