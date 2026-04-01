from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.models.persona import PersonaDelta
from app.services.brain_workspace_contract_service import recommend_brain_workspaces


def _delta(*, trait: str, notes: str = "", persona_target: str = "feeze.core") -> PersonaDelta:
    return PersonaDelta(
        id="delta-test",
        capture_id=None,
        persona_target=persona_target,
        trait=trait,
        notes=notes,
        status="draft",
        metadata={},
        created_at=datetime.now(timezone.utc),
        committed_at=None,
    )


class BrainWorkspaceContractServiceTests(unittest.TestCase):
    def test_ai_signal_routes_across_project_portfolio(self) -> None:
        delta = _delta(
            trait="AI agents are changing how teams operate.",
            notes="This AI system should influence multiple active projects, not just one workspace.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(
            result["workspace_keys"],
            ["shared_ops", "linkedin-os", "fusion-os", "easyoutfitapp", "ai-swag-store", "agc"],
        )

    def test_education_signal_prefers_feezie_and_fusion(self) -> None:
        delta = _delta(
            trait="Twice exceptional students need schools with better admissions fit and trust.",
            notes="This is about education, families, and referral clarity.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(result["workspace_keys"], ["linkedin-os", "fusion-os"])

    def test_fusion_merch_signal_routes_to_both_relevant_workspaces(self) -> None:
        delta = _delta(
            trait="Fusion Academy accessory merchandise just arrived.",
            notes="This could matter for school identity and merch demand.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(result["workspace_keys"], ["shared_ops", "linkedin-os", "fusion-os", "ai-swag-store"])


if __name__ == "__main__":
    unittest.main()
