from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_expression_engine import analyze_expression, social_expression_engine


class SocialExpressionEngineTests(unittest.TestCase):
    def test_structured_source_is_not_overpenalized_for_length(self) -> None:
        packet = analyze_expression(
            "Product teams rarely miss work because the tasks are invisible. "
            "They miss because ownership, context, and decision rules break at the handoff. "
            "The visible backlog is usually cleaner than the underlying operating system."
        )

        self.assertEqual(packet["structure"], "contrast-causal")
        self.assertGreaterEqual(packet["overall"], 7.0)
        self.assertNotIn("sentence is long", packet["warnings"])

    def test_detects_and_preserves_cascade_warning_structure(self) -> None:
        source = (
            "Higher-ed budget pressure does not stay confined to staffing charts. "
            "Families start asking harder questions about stability, support, and whether the institution can still deliver on trust."
        )
        preserved = (
            "The pressure does not stay confined to staffing charts. "
            "It eventually shows up in the trust questions families start asking."
        )

        assessment = social_expression_engine.compare(source, preserved)

        self.assertEqual(assessment["source_structure"], "cascade-warning")
        self.assertTrue(assessment["structure_preserved"])
        self.assertGreaterEqual(assessment["expression_delta"], 0.0)

    def test_detects_and_preserves_timing_gap_structure(self) -> None:
        source = (
            "Executives usually communicate the change long before the team can repeat the new behavior. "
            "That leaves middle layers translating the same message over and over without shared standards. "
            "The problem is rarely urgency by itself. It is whether the change becomes coachable and repeatable."
        )
        preserved = (
            "The timing gap is the real issue. "
            "Leaders announce the change long before the team can repeat it."
        )

        assessment = social_expression_engine.compare(source, preserved)

        self.assertEqual(assessment["source_structure"], "timing-gap")
        self.assertTrue(assessment["structure_preserved"])
        self.assertGreaterEqual(assessment["output_expression_quality"], 7.4)

    def test_detects_and_preserves_trend_compounding_structure(self) -> None:
        source = (
            "Small AI products can ship features quickly now, which means feature speed alone stops being the moat. "
            "What compounds is distribution, user trust, and the operational system that keeps insight close to the product."
        )
        preserved = (
            "Feature speed is no longer the moat by itself. "
            "What compounds is distribution, user trust, and the operating system around the product."
        )

        assessment = social_expression_engine.compare(source, preserved)

        self.assertEqual(assessment["source_structure"], "trend-compounding")
        self.assertTrue(assessment["structure_preserved"])
        self.assertGreaterEqual(assessment["expression_delta"], 0.0)


if __name__ == "__main__":
    unittest.main()
