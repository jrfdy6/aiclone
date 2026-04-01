from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes.content_generation import ContentGenerationRequest, _generate_staged_options
from app.services.content_generation_context_service import ContentGenerationContext


class StagedPipelineCallReductionTests(unittest.TestCase):
    def test_staged_pipeline_uses_consolidated_refinement_instead_of_old_multi_pass_chain(self) -> None:
        req = ContentGenerationRequest(
            user_id="lab-test",
            topic="agent orchestration",
            content_type="linkedin_post",
            category="value",
            tone="expert_direct",
            audience="tech_ai",
        )
        context = ContentGenerationContext(
            persona_chunks=[],
            example_chunks=[],
            core_chunks=[],
            proof_chunks=[],
            story_chunks=[],
            ambient_chunks=[],
            topic_anchor_chunks=[],
            proof_anchor_chunks=[],
            story_anchor_chunks=[],
            grounding_mode="proof_ready",
            grounding_reason="proof available",
            framing_modes=["operator_lesson", "contrarian_reframe", "warning"],
            primary_claims=["Prompting plus orchestration beats prompting alone."],
            proof_packets=["AI Clone / Brain System -> one routed workspace snapshot."],
            story_beats=[],
            disallowed_moves=[],
            persona_context_summary=None,
        )

        with (
            patch("app.routes.content_generation.write_planned_options", return_value=["one", "two", "three"]) as write_mock,
            patch("app.routes.content_generation.refine_generated_options", return_value=["r1", "r2", "r3"]) as refine_mock,
            patch("app.routes.content_generation.finalize_planned_options", side_effect=lambda options, **_: options) as finalize_mock,
            patch("app.routes.content_generation.critique_planned_options", side_effect=AssertionError("old critic pass should not run")),
            patch("app.routes.content_generation.enforce_grounding_on_options", side_effect=AssertionError("old proof enforcement pass should not run")),
            patch("app.routes.content_generation.sharpen_editorial_options", side_effect=AssertionError("old sharpening pass should not run")),
        ):
            options, briefs, strategy, fallback_trace = _generate_staged_options(
                client=MagicMock(),
                req=req,
                content_context=context,
                persona_chunks=[],
                example_chunks=[],
            )

        self.assertEqual(strategy, "planner_writer_critic")
        self.assertEqual(options, ["r1", "r2", "r3"])
        self.assertEqual(len(briefs), 3)
        self.assertTrue(fallback_trace["used_consolidated_refinement"])
        write_mock.assert_called_once()
        refine_mock.assert_called_once()
        self.assertGreaterEqual(finalize_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
