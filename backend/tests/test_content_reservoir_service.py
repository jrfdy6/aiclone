from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_reservoir_service import build_content_reservoir_payload


class ContentReservoirServiceTests(unittest.TestCase):
    def test_build_content_reservoir_preserves_voice_story_and_proof_fragments(self) -> None:
        source_assets = {
            "items": [
                {
                    "asset_id": "asset-1",
                    "title": "Operator Lessons From A Broken AI Workflow",
                    "source_path": "knowledge/ingestions/2026/04/asset-1/normalized.md",
                    "source_url": "https://example.com/operator-lessons",
                    "source_channel": "youtube",
                    "source_type": "youtube_transcript",
                    "origin": "media_pipeline",
                    "summary": "AI systems fail when operators lose the review layer.",
                    "structured_summary": "AI systems fail when operators lose the review layer.",
                    "topics": ["ai", "workflow"],
                    "tags": ["operator", "automation"],
                    "deep_harvest_fragments": [
                        {
                            "text": "AI systems fail when operators lose the review layer.",
                            "primary_type": "worldview",
                            "labels": ["worldview", "lesson"],
                            "source_section": "summary",
                            "score": 8,
                            "likely_handoff_lane": "persona_candidate",
                            "promotion_recommendation": "persona_candidate",
                            "promotion_reason": "Durable lesson.",
                        },
                        {
                            "text": "The breakthrough was trust and clarity, not persuasion.",
                            "primary_type": "anecdote",
                            "labels": ["anecdote"],
                            "source_section": "key_anecdotes",
                            "score": 7,
                            "likely_handoff_lane": "source_only",
                            "promotion_recommendation": "source_only",
                            "promotion_reason": "Held back for now.",
                        },
                        {
                            "text": "That is the part people miss.",
                            "primary_type": "quote",
                            "labels": ["quote", "voice_pattern"],
                            "source_section": "reusable_quotes",
                            "score": 7,
                            "likely_handoff_lane": "post_candidate",
                            "promotion_recommendation": "voice_guidance_only",
                            "promotion_reason": "Useful phrasing.",
                        },
                        {
                            "text": "This generic sentence is too weak to store.",
                            "primary_type": "signal",
                            "labels": ["signal"],
                            "source_section": "clean_document",
                            "score": 3,
                            "likely_handoff_lane": "source_only",
                            "promotion_recommendation": "source_only",
                            "promotion_reason": "Too weak.",
                        },
                    ],
                }
            ]
        }

        payload = build_content_reservoir_payload(source_assets=source_assets)
        self.assertIsNotNone(payload)

        items = payload["items"]
        self.assertEqual(len(items), 3)
        by_text = {item["text"]: item for item in items}

        proof_point = by_text["AI systems fail when operators lose the review layer."]
        self.assertEqual(proof_point["reservoir_lane"], "proof_point")
        self.assertEqual(proof_point["metadata"]["memory_role"], "proof")
        self.assertEqual(proof_point["metadata"]["persona_tag"], "PHILOSOPHY")

        story_bank = by_text["The breakthrough was trust and clarity, not persuasion."]
        self.assertEqual(story_bank["reservoir_lane"], "story_bank")
        self.assertEqual(story_bank["metadata"]["memory_role"], "story")

        voice_guidance = by_text["That is the part people miss."]
        self.assertEqual(voice_guidance["reservoir_lane"], "voice_guidance")
        self.assertEqual(voice_guidance["metadata"]["persona_tag"], "VOICE_PATTERNS")

        counts = payload["counts"]["by_reservoir_lane"]
        self.assertEqual(counts["proof_point"], 1)
        self.assertEqual(counts["story_bank"], 1)
        self.assertEqual(counts["voice_guidance"], 1)


if __name__ == "__main__":
    unittest.main()
