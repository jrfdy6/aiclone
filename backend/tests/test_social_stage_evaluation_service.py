from __future__ import annotations

import unittest

from app.services.social_stage_evaluation_service import SocialStageEvaluationService


class SocialStageEvaluationServiceTests(unittest.TestCase):
    def test_article_stance_scores_higher_when_reason_and_counterweight_exist(self) -> None:
        service = SocialStageEvaluationService()
        strong = service.evaluate_variant(
            article_understanding={
                "thesis": "x",
                "world_context": "y",
                "article_stance": "speculate",
                "article_stance_confidence": 8.4,
                "article_stance_reason": "The article is reading a live signal as part of a bigger shift.",
                "article_stance_counterweight": "The article is separating the visible product race from the deeper compounding layer underneath it.",
                "article_stance_evidence": ["what compounds is", "distribution"],
                "source_expression_family": "trend",
            },
            persona_retrieval={"top_candidates": [{"text": "x"}]},
            johnnie_perspective={"personal_reaction": "x", "agree_with": "x", "pushback": "y", "what_matters_most": "z"},
            reaction_brief={"content_angle": "lived_translation", "article_view": "x", "johnnie_view": "y", "tension": "z"},
            composition_traces={"comment": {"selected_parts": ["x"]}, "repost": {"selected_parts": ["y"]}},
            response_type_packet={"response_type": "contrarian", "eligible_types": ["agree", "contrarian"], "type_confidence": 8.0},
        )
        weak = service.evaluate_variant(
            article_understanding={
                "thesis": "x",
                "world_context": "y",
                "article_stance": "speculate",
                "article_stance_confidence": 7.2,
            },
            persona_retrieval={"top_candidates": [{"text": "x"}]},
            johnnie_perspective={"personal_reaction": "x", "agree_with": "x", "pushback": "y", "what_matters_most": "z"},
            reaction_brief={"content_angle": "lived_translation", "article_view": "x", "johnnie_view": "y", "tension": "z"},
            composition_traces={"comment": {"selected_parts": ["x"]}, "repost": {"selected_parts": ["y"]}},
            response_type_packet={"response_type": "contrarian", "eligible_types": ["agree", "contrarian"], "type_confidence": 8.0},
        )

        self.assertGreater(strong["article_stance_score"], weak["article_stance_score"])

    def test_belief_relevance_uses_fit_and_claim_type(self) -> None:
        service = SocialStageEvaluationService()
        strong = service.evaluate_variant(
            article_understanding={"thesis": "x", "world_context": "y", "article_stance": "advocate"},
            persona_retrieval={
                "top_candidates": [{"text": "x"}],
                "selected_belief": {
                    "text": "Technology can help close gaps in education access and equity, but only if adoption is real.",
                    "selection_fit_score": 18.0,
                    "reference_alignment_score": 2.0,
                    "claim_type": "mission",
                },
            },
            johnnie_perspective={"personal_reaction": "x", "agree_with": "x", "pushback": "y", "what_matters_most": "z"},
            reaction_brief={"content_angle": "qualified_disagreement", "article_view": "x", "johnnie_view": "y", "tension": "z"},
            composition_traces={"comment": {"selected_parts": ["x"]}, "repost": {"selected_parts": ["y"]}},
            response_type_packet={"response_type": "contrarian", "eligible_types": ["agree", "contrarian"], "type_confidence": 8.0},
        )
        weak = service.evaluate_variant(
            article_understanding={"thesis": "x", "world_context": "y", "article_stance": "advocate"},
            persona_retrieval={
                "top_candidates": [{"text": "x"}],
                "selected_belief": {
                    "text": "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.",
                    "selection_fit_score": 10.0,
                    "reference_alignment_score": 0.0,
                    "claim_type": "positioning",
                },
            },
            johnnie_perspective={"personal_reaction": "x", "agree_with": "x", "pushback": "y", "what_matters_most": "z"},
            reaction_brief={"content_angle": "qualified_disagreement", "article_view": "x", "johnnie_view": "y", "tension": "z"},
            composition_traces={"comment": {"selected_parts": ["x"]}, "repost": {"selected_parts": ["y"]}},
            response_type_packet={"response_type": "contrarian", "eligible_types": ["agree", "contrarian"], "type_confidence": 8.0},
        )

        self.assertGreater(strong["belief_relevance_score"], weak["belief_relevance_score"])
        self.assertIn("belief relevance is still thin", weak["warnings"])

    def test_experience_relevance_uses_fit_and_proof_strength(self) -> None:
        service = SocialStageEvaluationService()
        strong = service.evaluate_variant(
            article_understanding={"thesis": "x", "world_context": "y", "article_stance": "advocate"},
            persona_retrieval={
                "top_candidates": [{"text": "x"}],
                "selected_experience": {
                    "text": "Cheap Models, Better Systems. Johnnie learned AI by building on weaker and cheaper models first.",
                    "selection_fit_score": 20.0,
                    "artifact_backed": True,
                    "proof_strength": "strong",
                    "candidate_type": "story",
                },
            },
            johnnie_perspective={"personal_reaction": "x", "agree_with": "x", "pushback": "y", "lived_addition": "z", "what_matters_most": "z"},
            reaction_brief={"content_angle": "lived_translation", "article_view": "x", "johnnie_view": "y", "tension": "z"},
            composition_traces={"comment": {"selected_parts": ["x"]}, "repost": {"selected_parts": ["y"]}},
            response_type_packet={"response_type": "personal_story", "eligible_types": ["agree", "personal_story"], "type_confidence": 8.0},
        )
        weak = service.evaluate_variant(
            article_understanding={"thesis": "x", "world_context": "y", "article_stance": "advocate"},
            persona_retrieval={
                "top_candidates": [{"text": "x"}],
                "selected_experience": {
                    "text": "AI Clone / Brain System. Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution.",
                    "selection_fit_score": 10.0,
                    "artifact_backed": True,
                    "proof_strength": "strong",
                    "candidate_type": "initiative",
                },
            },
            johnnie_perspective={"personal_reaction": "x", "agree_with": "x", "pushback": "y", "lived_addition": "z", "what_matters_most": "z"},
            reaction_brief={"content_angle": "lived_translation", "article_view": "x", "johnnie_view": "y", "tension": "z"},
            composition_traces={"comment": {"selected_parts": ["x"]}, "repost": {"selected_parts": ["y"]}},
            response_type_packet={"response_type": "personal_story", "eligible_types": ["agree", "personal_story"], "type_confidence": 8.0},
        )

        self.assertGreater(strong["experience_relevance_score"], weak["experience_relevance_score"])
        self.assertIn("experience relevance is still thin", weak["warnings"])


if __name__ == "__main__":
    unittest.main()
