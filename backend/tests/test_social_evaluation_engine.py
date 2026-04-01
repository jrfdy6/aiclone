from __future__ import annotations

import unittest

from app.services.social_evaluation_engine import SocialEvaluationEngine


class SocialEvaluationEngineTests(unittest.TestCase):
    def test_new_owned_voice_markers_raise_voice_match(self) -> None:
        engine = SocialEvaluationEngine()
        strong = engine.evaluate_variant(
            lane_id="ai",
            signal={"standout_lines": ["x"]},
            belief={
                "belief_summary": "x",
                "experience_summary": "y",
                "stance": "nuance",
                "agreement_level": "medium",
                "role_safety": "safe",
            },
            technique={"techniques": ["contrarian-reframe"]},
            expression=None,
            comment=(
                "Look, people get this wrong all the time. They're not wrong, but that's incomplete. "
                "If you cannot rely on the output, you cannot really build with it."
            ),
            repost="AI is changing what competence looks like faster than most teams are ready to admit.",
            short_comment="Automate friction, not judgment.",
            article_understanding={"article_stance": "warn"},
            persona_retrieval={"top_candidates": [{"text": "x"}], "relevant_claims": [{"text": "x"}]},
            johnnie_perspective={"personal_reaction": "x", "pushback": "y"},
            reaction_brief={"content_angle": "qualified_disagreement"},
            composition_traces={"comment": {"selected_parts": ["open", "main"]}, "repost": {"selected_parts": ["open", "main"]}},
            response_type_packet={"response_type": "contrarian"},
            stage_evaluation={},
        )
        weak = engine.evaluate_variant(
            lane_id="ai",
            signal={"standout_lines": ["x"]},
            belief={
                "belief_summary": "x",
                "experience_summary": "y",
                "stance": "nuance",
                "agreement_level": "medium",
                "role_safety": "safe",
            },
            technique={"techniques": ["contrarian-reframe"]},
            expression=None,
            comment="I agree with the direction and think this matters in practice.",
            repost="This is a useful point for teams.",
            short_comment="Important point.",
            article_understanding={"article_stance": "warn"},
            persona_retrieval={"top_candidates": [{"text": "x"}], "relevant_claims": [{"text": "x"}]},
            johnnie_perspective={"personal_reaction": "x", "pushback": "y"},
            reaction_brief={"content_angle": "qualified_disagreement"},
            composition_traces={"comment": {"selected_parts": ["open", "main"]}, "repost": {"selected_parts": ["open", "main"]}},
            response_type_packet={"response_type": "contrarian"},
            stage_evaluation={},
        )

        self.assertGreater(strong["voice_match"], weak["voice_match"])

    def test_leadership_distance_and_inside_work_lines_count_as_voice(self) -> None:
        engine = SocialEvaluationEngine()
        strong = engine.evaluate_variant(
            lane_id="program-leadership",
            signal={"standout_lines": ["x"]},
            belief={
                "belief_summary": "Visibility changes behavior more than pressure does",
                "experience_summary": "Fusion Dashboard Transformation. Johnnie replaced scattered reporting with one actionable dashboard.",
                "stance": "personal-anchor",
                "agreement_level": "medium",
                "role_safety": "safe",
            },
            technique={"techniques": ["lived-translation"]},
            expression=None,
            comment=(
                "I have seen some version of this up close. It reads one way from a distance and another way from inside the work. "
                "The visible backlog is not the real system. The underlying operating system is where the break usually lives."
            ),
            repost="This feels familiar for a reason. Leadership matters in whether that gets translated into standards and follow-through.",
            short_comment="The visible backlog is not the real system.",
            article_understanding={"article_stance": "nuance"},
            persona_retrieval={"top_candidates": [{"text": "x"}], "relevant_claims": [{"text": "x"}]},
            johnnie_perspective={"personal_reaction": "x", "pushback": "y"},
            reaction_brief={"content_angle": "lived_translation"},
            composition_traces={"comment": {"selected_parts": ["open", "main"]}, "repost": {"selected_parts": ["open", "main"]}},
            response_type_packet={"response_type": "lived_translation"},
            stage_evaluation={},
        )
        weak = engine.evaluate_variant(
            lane_id="program-leadership",
            signal={"standout_lines": ["x"]},
            belief={
                "belief_summary": "Visibility changes behavior more than pressure does",
                "experience_summary": "Fusion Dashboard Transformation. Johnnie replaced scattered reporting with one actionable dashboard.",
                "stance": "personal-anchor",
                "agreement_level": "medium",
                "role_safety": "safe",
            },
            technique={"techniques": ["lived-translation"]},
            expression=None,
            comment="This is a leadership issue that affects follow-through.",
            repost="Teams need more clarity and better standards.",
            short_comment="Leadership matters.",
            article_understanding={"article_stance": "nuance"},
            persona_retrieval={"top_candidates": [{"text": "x"}], "relevant_claims": [{"text": "x"}]},
            johnnie_perspective={"personal_reaction": "x", "pushback": "y"},
            reaction_brief={"content_angle": "lived_translation"},
            composition_traces={"comment": {"selected_parts": ["open", "main"]}, "repost": {"selected_parts": ["open", "main"]}},
            response_type_packet={"response_type": "lived_translation"},
            stage_evaluation={},
        )

        self.assertGreater(strong["voice_match"], weak["voice_match"])
        self.assertGreaterEqual(strong["voice_match"], 7.0)


if __name__ == "__main__":
    unittest.main()
