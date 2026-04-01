from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_article_understanding_service import SocialArticleUnderstandingService


class SocialArticleUnderstandingServiceTests(unittest.TestCase):
    def test_article_stance_packet_adds_reason_counterweight_and_evidence(self) -> None:
        service = SocialArticleUnderstandingService()
        packet = service.analyze(
            {
                "title": "Distribution Is Becoming the Moat for Small AI Products",
                "summary": (
                    "Small AI products can ship features quickly now, which means feature speed alone stops being the moat. "
                    "What compounds is distribution, user trust, and the operational system that keeps insight close to the product."
                ),
                "raw_text": (
                    "Small AI products can ship features quickly now, which means feature speed alone stops being the moat. "
                    "What compounds is distribution, user trust, and the operational system that keeps insight close to the product."
                ),
            },
            "entrepreneurship",
        )

        self.assertEqual(packet["article_stance"], "nuance")
        self.assertTrue(packet["article_stance_reason"])
        self.assertIn("compounding layer", packet["article_stance_counterweight"].lower())
        self.assertGreaterEqual(packet["article_stance_confidence"], 8.0)
        self.assertTrue(packet["article_stance_evidence"])


if __name__ == "__main__":
    unittest.main()
