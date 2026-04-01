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

    def test_generic_store_language_does_not_false_positive_into_ai_swag_store(self) -> None:
        delta = _delta(
            trait="Remember that the hill that I showed you, the system of record hill?",
            notes=(
                "If you're a scheduling tool, don't facilitate bookings, store the history of every booking, "
                "customer preferences, cancellation patterns, and lifetime value."
            ),
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(result["workspace_keys"], ["shared_ops", "linkedin-os"])
        self.assertNotIn("ai-swag-store", result["workspace_keys"])

    def test_fashion_signal_prefers_feezie_and_easy_outfit(self) -> None:
        delta = _delta(
            trait="Closet organization and outfit recommendation quality are still broken for users.",
            notes="This is about personal style, wardrobe logic, and better digital closet behavior.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(result["workspace_keys"], ["linkedin-os", "easyoutfitapp"])

    def test_agc_signal_prefers_feezie_and_agc(self) -> None:
        delta = _delta(
            trait="AGC initiatives need cleaner mission boundaries and traceable execution.",
            notes="This should stay inside AGC work instead of getting lost in general ops.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(result["workspace_keys"], ["linkedin-os", "agc"])

    def test_ambiguous_non_domain_signal_stays_feezie_and_executive(self) -> None:
        delta = _delta(
            trait="We need better follow-through and less confusion in how work moves.",
            notes="This feels important, but it does not clearly belong to one product or workspace yet.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(result["workspace_keys"], ["shared_ops", "linkedin-os"])

    def test_ai_plus_education_signal_keeps_portfolio_fanout(self) -> None:
        delta = _delta(
            trait="AI could help twice exceptional families navigate admissions more clearly.",
            notes="This combines AI systems with education, referrals, and family trust.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(
            result["workspace_keys"],
            ["shared_ops", "linkedin-os", "fusion-os", "easyoutfitapp", "ai-swag-store", "agc"],
        )

    def test_ai_plus_fashion_signal_keeps_portfolio_fanout(self) -> None:
        delta = _delta(
            trait="AI styling systems should improve digital closet recommendations.",
            notes="This is AI plus fashion, wardrobe context, and outfit logic.",
        )

        result = recommend_brain_workspaces(delta)

        self.assertEqual(
            result["workspace_keys"],
            ["shared_ops", "linkedin-os", "fusion-os", "easyoutfitapp", "ai-swag-store", "agc"],
        )


if __name__ == "__main__":
    unittest.main()
