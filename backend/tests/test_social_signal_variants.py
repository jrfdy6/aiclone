from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_signal_utils import build_variants, normalize_saved_signal
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
        self.assertIn("Admissions teams usually hear the market first", repost)


if __name__ == "__main__":
    unittest.main()
