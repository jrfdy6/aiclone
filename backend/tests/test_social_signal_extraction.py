from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_signal_extraction import social_signal_extraction_service


class SocialSignalExtractionTests(unittest.TestCase):
    def test_extract_article_payload_prefers_richer_body_text_over_short_meta_description(self) -> None:
        html = """
        <html>
          <head>
            <title>Claude Dispatch and the Power of Interfaces</title>
            <meta property="og:title" content="Claude Dispatch and the Power of Interfaces" />
            <meta property="og:description" content="A short teaser about AI interfaces." />
            <meta name="author" content="Ethan Mollick" />
          </head>
          <body>
            <article>
              <p>We often lack the tools for the job, even if the AI is capable enough.</p>
              <p>Interfaces decide whether that capability becomes leverage for the operator or just stays trapped behind friction.</p>
              <p>The real constraint is often workflow quality, not raw model intelligence.</p>
            </article>
          </body>
        </html>
        """

        payload = social_signal_extraction_service.extract_article_payload(html)

        self.assertEqual(payload["title"], "Claude Dispatch and the Power of Interfaces")
        self.assertEqual(payload["author"], "Ethan Mollick")
        self.assertIn("We often lack the tools for the job, even if the AI is capable enough.", payload["text"])
        self.assertIn("workflow quality, not raw model intelligence", payload["text"])
        self.assertNotEqual(payload["text"], "A short teaser about AI interfaces.")


if __name__ == "__main__":
    unittest.main()
