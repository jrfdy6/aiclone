from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts" / "personal-brand"
QUALIFICATION_MODULE_PATH = SCRIPTS_ROOT / "linkedin_idea_qualification.py"
MATERIALIZE_MODULE_PATH = SCRIPTS_ROOT / "materialize_latent_transform_drafts.py"


def load_module(path: Path, name: str):
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LatentTransformDraftMaterializationTests(unittest.TestCase):
    def test_context_translation_plan_keeps_source_signal_visible(self) -> None:
        module = load_module(QUALIFICATION_MODULE_PATH, "linkedin_idea_qualification")

        plan = module._latent_transform_plan(
            {
                "content_lane": "ai",
                "title": "Claude Dispatch and the Power of Interfaces",
                "raw_angle": "If the workflow is unclear, AI just scales confusion",
                "delta": "",
                "audience": "AI builders and operators",
                "proof_summary": "AI Clone / Brain System. Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution",
                "source_summary": "We often lack the tools for the job, even if the AI is capable enough",
                "source_supporting_claim": "We often lack the tools for the job, even if the AI is capable enough",
                "current_belief": "Claude Dispatch and the Power of Interfaces.",
            },
            {"latent_reason": "needs_context_translation"},
        )

        self.assertEqual(
            plan.get("source_signal"),
            "We often lack the tools for the job, even if the AI is capable enough",
        )
        self.assertIn("Anchor it in the source signal:", plan.get("proposed_angle") or "")
        self.assertIn("We often lack the tools for the job, even if the AI is capable enough", plan.get("proposed_angle") or "")

    def test_draft_body_grounds_first_pass_in_source_signal(self) -> None:
        module = load_module(MATERIALIZE_MODULE_PATH, "materialize_latent_transform_drafts")

        body = module._draft_body(
            {
                "idea_id": "idea-claude-dispatch",
                "title": "Claude Dispatch and the Power of Interfaces",
                "content_lane": "ai",
                "latent_reason": "needs_context_translation",
                "source_path": "workspaces/linkedin-content-os/research/market_signals/claude-dispatch.md",
                "source_url": "https://www.oneusefulthing.org/p/claude-dispatch-and-the-power-of",
                "source_summary": "We often lack the tools for the job, even if the AI is capable enough",
                "source_supporting_claim": "We often lack the tools for the job, even if the AI is capable enough",
                "suggested_fix": "AI workflow design, operator judgment, and education implementation signals",
                "transform_plan": {
                    "transform_type": "context_translation",
                    "autotransform_ready": True,
                    "source_signal": "We often lack the tools for the job, even if the AI is capable enough",
                    "proposed_angle": "If the workflow is unclear, AI just scales confusion. Anchor it in the source signal: We often lack the tools for the job, even if the AI is capable enough. The part worth saying publicly is whether the workflow, interface, and surrounding context make better judgment easier or just scale confusion.",
                    "owner_question": "What concrete change should ai builders and operators notice if this is true?",
                    "proof_prompt": "AI Clone / Brain System. Build a restart-safe AI operating system for memory, persona review, source routing, planning, and content execution",
                    "promotion_rule": "Promote only after the angle names a concrete audience consequence and one lived proof line.",
                    "revision_goals": [
                        "replace generic relevance with a concrete audience consequence",
                    ],
                },
            },
            {
                "summary": "We often lack the tools for the job, even if the AI is capable enough",
                "supporting_claims": [
                    "We often lack the tools for the job, even if the AI is capable enough",
                ],
                "why_it_matters": "AI workflow design, operator judgment, and education implementation signals",
            },
        )

        self.assertIn(
            '"Claude Dispatch and the Power of Interfaces" is useful because the source signal is We often lack the tools for the job, even if the AI is capable enough.',
            body,
        )
        self.assertIn(
            "Anchor it in the source signal: We often lack the tools for the job, even if the AI is capable enough.",
            body,
        )
        self.assertIn(
            "The operator consequence still needs to answer this clearly: What concrete change should ai builders and operators notice if this is true.",
            body,
        )


if __name__ == "__main__":
    unittest.main()
