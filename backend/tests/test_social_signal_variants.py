from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_evaluation_engine import social_evaluation_engine
from app.services.social_signal_utils import _variation_seed, build_variants, normalize_saved_signal
import app.services.social_signal_utils as social_signal_utils_module


class SocialSignalVariantTests(unittest.TestCase):
    def test_admissions_variant_drops_abstract_bridge_fragment(self) -> None:
        signal = normalize_saved_signal(
            {
                "title": "Kentucky Senate passes bill making it easier to cut faculty",
                "summary": "Higher-ed operations, enrollment shifts, and student-journey execution signals",
                "source_platform": "rss",
                "source_type": "article",
                "source_url": "https://example.com/kentucky-faculty",
                "author": "Natalie Schwartz",
                "priority_lane": "admissions",
                "headline_candidates": [
                    "Kentucky Senate passes bill making it easier to cut faculty",
                    "The frontline signal usually shows up first in the questions people keep asking.",
                ],
            },
            raw_text=(
                "Kentucky Senate passes bill making it easier to cut faculty. "
                "The frontline signal usually shows up first in the questions people keep asking."
            ),
        )

        with patch.object(
            social_signal_utils_module.social_belief_engine,
            "assess_signal",
            return_value={
                "stance": "translate",
                "agreement_level": "medium",
                "belief_relation": "translation",
                "belief_used": "people, process, and culture as the main levers of leadership",
                "belief_summary": "people, process, and culture as the main levers of leadership",
                "experience_anchor": "Fusion Academy Market Development",
                "experience_summary": "Keeps leadership, trust-building, and community-facing execution grounded in a live operating role rather than abstract commentary.",
                "role_safety": "safe",
                "stance_comment_open": "I keep translating this into the real work on the ground.",
                "stance_repost_open": "This changes once it touches the real work.",
                "bridge_line": "Keeps leadership, trust-building, and community-facing execution grounded in a live operating role rather than abstract commentary.",
            },
        ):
            variants = build_variants(signal)

        admissions = variants["admissions"]
        comment = admissions["comment"]
        repost = admissions["repost"]

        self.assertIn("The frontline signal usually shows up first in the questions people keep asking.", comment)
        self.assertIn("Those repeated questions usually tell you what the market is trying to say", comment)
        self.assertNotIn("Keeps leadership", comment)
        self.assertNotIn("abstract commentary", comment.lower())
        self.assertNotIn("community-facing execution", comment.lower())
        self.assertTrue(
            any(
                marker in repost
                for marker in [
                    "Admissions teams usually hear the market first",
                    "Admissions usually hears the friction early",
                    "Admissions teams often spot the gap first",
                ]
            )
        )

    def test_variation_seed_is_stable_but_title_sensitive(self) -> None:
        ctx_a = {
            "title": "Kentucky Senate passes bill making it easier to cut faculty",
            "priority_lane": "admissions",
            "stance": "counter",
            "source_takeaway_origin": "The frontline signal usually shows up first in the questions people keep asking.",
        }
        ctx_b = {
            **ctx_a,
            "title": "Faculty cuts usually expose the message gap before leadership names it",
        }

        self.assertEqual(_variation_seed(ctx_a, "comment-open"), _variation_seed(ctx_a, "comment-open"))
        self.assertNotEqual(_variation_seed(ctx_a, "comment-open"), _variation_seed(ctx_b, "comment-open"))

    def test_counter_stance_variant_uses_contrast_language(self) -> None:
        signal = normalize_saved_signal(
            {
                "title": "Faculty cuts usually expose the message gap before leadership names it",
                "summary": "Higher-ed operations, enrollment shifts, and student-journey execution signals",
                "source_platform": "rss",
                "source_type": "article",
                "source_url": "https://example.com/faculty-cuts",
                "author": "Natalie Schwartz",
                "priority_lane": "admissions",
                "headline_candidates": [
                    "Kentucky Senate passes bill making it easier to cut faculty",
                    "The frontline signal usually shows up first in the questions people keep asking.",
                ],
            },
            raw_text=(
                "Kentucky Senate passes bill making it easier to cut faculty. "
                "The frontline signal usually shows up first in the questions people keep asking."
            ),
        )

        with patch.object(
            social_signal_utils_module.social_belief_engine,
            "assess_signal",
            return_value={
                "stance": "counter",
                "agreement_level": "low",
                "belief_relation": "contrast",
                "belief_used": "people, process, and culture as the main levers of leadership",
                "belief_summary": "people, process, and culture as the main levers of leadership",
                "experience_anchor": "Fusion Academy Market Development",
                "experience_summary": "The work is to strengthen referral relationships, enrollment outcomes, and family trust.",
                "role_safety": "safe",
                "stance_comment_open": "I would frame this a little differently.",
                "stance_repost_open": "The headline is directionally right, but the real issue sits one layer lower.",
                "bridge_line": "",
            },
        ):
            variants = build_variants(signal)
            variants_repeat = build_variants(signal)

        self.assertEqual(variants["admissions"]["comment"], variants_repeat["admissions"]["comment"])

        combined = " ".join(
            [
                variants["admissions"]["comment"].lower(),
                variants["admissions"]["repost"].lower(),
            ]
        )
        self.assertTrue(
            any(
                marker in combined
                for marker in [
                    "the post is not wrong",
                    "the visible issue is one thing",
                    "one layer lower",
                    "stops too early",
                    "the real issue is not the headline",
                    "one layer deeper than this framing",
                ]
            )
        )

    def test_evaluator_penalizes_abstract_meta_phrase_without_crashing(self) -> None:
        evaluation = social_evaluation_engine.evaluate_variant(
            lane_id="program-leadership",
            signal={"standout_lines": ["signal"]},
            belief={
                "belief_summary": "people, process, and culture as the main levers of leadership",
                "stance": "nuance",
                "agreement_level": "medium",
                "experience_summary": "Some lived operator context.",
                "role_safety": "safe",
            },
            technique={"techniques": ["specificity-injection"]},
            expression=None,
            comment="Keeps leadership, trust-building, and community-facing execution grounded in a live operating role rather than abstract commentary.",
            repost="",
            short_comment="",
        )

        self.assertGreater(evaluation["genericity_penalty"], 0.0)
        self.assertIn("copy still contains abstract meta phrasing", evaluation["warnings"])


if __name__ == "__main__":
    unittest.main()
