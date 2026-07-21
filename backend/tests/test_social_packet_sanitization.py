from __future__ import annotations

import unittest

from app.services.social_johnnie_perspective_service import SocialJohnniePerspectiveService
from app.services.social_reaction_brief_service import SocialReactionBriefService


class SocialPacketSanitizationTests(unittest.TestCase):
    def test_johnnie_perspective_strips_packet_metadata_from_pushback_and_lived_addition(self) -> None:
        service = SocialJohnniePerspectiveService()
        packet = service.build(
            signal={},
            lane_id="ai",
            article_understanding={
                "thesis": "Teams are over-indexing on model choice.",
                "world_stakes": "This matters because the work breaks in execution.",
                "article_kind": "trend",
            },
            persona_retrieval={
                "selected_belief": {
                    "title": "Prompting alone is not an AI strategy",
                    "summary_text": (
                        "Prompting alone is not an AI strategy. "
                        "Evidence: Johnnie keeps moving work from isolated prompting into structured workflows. "
                        "Usage: Use as a thesis line when the topic is AI adoption."
                    ),
                },
                "selected_experience": {
                    "title": "AI Clone / Brain System",
                    "summary_text": (
                        "AI Clone / Brain System. "
                        "Evidence: Built as a restart-safe AI operating system for memory and planning. "
                        "Usage: Use for posts about AI systems."
                    ),
                },
            },
            belief_assessment={
                "stance": "nuance",
                "agreement_level": "medium",
                "belief_relation": "qualified_agreement",
                "belief_used": "Prompting alone is not an AI strategy",
            },
        )

        self.assertNotIn("Evidence:", packet["pushback"])
        self.assertNotIn("Usage:", packet["pushback"])
        self.assertNotIn("Evidence:", packet["lived_addition"])
        self.assertNotIn("Usage:", packet["lived_addition"])
        self.assertIn("Prompting alone is not an AI strategy", packet["pushback"])
        self.assertIn("AI Clone / Brain System", packet["lived_addition"])

    def test_reaction_brief_strips_packet_metadata_from_supporting_proof(self) -> None:
        service = SocialReactionBriefService()
        packet = service.build(
            lane_id="ai",
            article_understanding={
                "article_view": "This article is about AI workflow maturity.",
                "thesis": "Teams are treating model choice like strategy.",
                "world_stakes": "The real break happens in workflow design.",
                "article_kind": "trend",
            },
            persona_retrieval={
                "relevant_claims": [
                    {
                        "summary_text": (
                            "Prompting alone is not an AI strategy. "
                            "Evidence: Johnnie keeps moving work into typed retrieval and shared state. "
                            "Usage: Use when the topic is orchestration."
                        )
                    }
                ],
                "relevant_stories": [],
                "relevant_initiatives": [],
                "relevant_deltas": [],
            },
            johnnie_perspective={
                "personal_reaction": "I agree with the direction, but the real gap shows up in execution.",
                "pushback": "Prompting alone is not an AI strategy.",
                "lived_addition": "AI Clone / Brain System.",
                "what_matters_most": "The real break happens in workflow design.",
                "stance_rationale": "The lane is ai and the stance is nuance.",
                "audience_posture": "builder_operator",
                "role_posture": "ai_practitioner",
                "agree_with": "The article is pointing at something real.",
            },
        )

        supporting_proof = packet["draft_guidance"]["supporting_proof"]
        self.assertEqual(supporting_proof, "Prompting alone is not an AI strategy.")
        self.assertNotIn("Evidence:", supporting_proof)
        self.assertNotIn("Usage:", supporting_proof)


if __name__ == "__main__":
    unittest.main()
