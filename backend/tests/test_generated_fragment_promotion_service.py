from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import PersonaDelta
from app.services.generated_fragment_promotion_service import promote_generated_fragment, undo_generated_fragment_promotion


def _delta(*, status: str = "draft", metadata: dict | None = None, delta_id: str = "delta-1") -> PersonaDelta:
    now = datetime.now(timezone.utc)
    return PersonaDelta(
        id=delta_id,
        persona_target="feeze.core",
        trait="Generated fragment",
        notes="note",
        status=status,
        metadata=metadata or {},
        created_at=now,
        committed_at=now if status == "committed" else None,
    )


class GeneratedFragmentPromotionServiceTests(unittest.TestCase):
    def test_metric_fragment_routes_to_wins_and_waits_for_owner_review(self) -> None:
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=None,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.create_delta",
            return_value=_delta(),
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=_delta(
                status="in_review",
                metadata={
                    "review_source": "linkedin_workspace.generated_fragment",
                    "review_state": "in_review",
                    "approval_state": "pending_owner_review",
                    "pending_promotion": False,
                    "stats": ["We improved adoption 42% after fixing the review handoff."],
                    "selected_promotion_items": [],
                },
            ),
        ) as update_delta_mock, patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta"
        ) as get_delta_mock:
            result = promote_generated_fragment(
                user_id="johnnie_fields",
                fragment_text="We improved adoption 42% after fixing the review handoff.",
                option_text="We improved adoption 42% after fixing the review handoff.\n\nThat changed the whole workflow.",
                option_index=0,
                topic="agent orchestration",
                audience="tech_ai",
                category="value",
                content_type="linkedin_post",
                source_mode="recent_signals",
                support_items=[{"reservoir_lane": "proof_point", "text": "Review handoffs create trust."}],
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["route_key"], "proof_support")
        self.assertEqual(result["target_file"], "history/wins.md")
        self.assertEqual(result["written_files"], [])
        self.assertEqual(result["delta"]["status"], "in_review")
        self.assertEqual(result["delta"]["metadata"]["approval_state"], "pending_owner_review")
        self.assertFalse(result["delta"]["metadata"]["pending_promotion"])
        self.assertIn("owner review", result["message"])
        update_call = update_delta_mock.call_args
        self.assertEqual(update_call.args[1].status, "in_review")
        self.assertEqual(
            update_call.args[1].metadata["proposed_promotion_items"][0]["targetFile"],
            "history/wins.md",
        )
        self.assertEqual(update_call.args[1].metadata["selected_promotion_items"], [])
        get_delta_mock.assert_not_called()

    def test_story_like_fragment_routes_to_story_bank(self) -> None:
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=None,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.create_delta",
            return_value=_delta(),
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=_delta(
                status="in_review",
                metadata={
                    "review_source": "linkedin_workspace.generated_fragment",
                    "anecdotes": [
                        {
                            "title": "Anecdote",
                            "summary": "When I stopped forcing the pitch, the family finally trusted the process.",
                        }
                    ],
                },
            ),
        ):
            result = promote_generated_fragment(
                user_id="johnnie_fields",
                fragment_text="When I stopped forcing the pitch, the family finally trusted the process.",
                option_text="When I stopped forcing the pitch, the family finally trusted the process.",
                option_index=1,
                topic="family trust",
                audience="education_admissions",
                category="personal",
                content_type="linkedin_post",
                source_mode="recent_signals",
                support_items=[{"reservoir_lane": "story_bank", "primary_type": "anecdote"}],
                option_brief={"framing_mode": "drama_tension", "story_beat": "Family trust opened after the pressure dropped."},
            )

        self.assertEqual(result["route_key"], "chronicle")
        self.assertEqual(result["target_file"], "history/story_bank.md")
        self.assertIn("owner review", result["message"])

    def test_story_brief_does_not_turn_generic_generated_line_into_personal_history(self) -> None:
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=None,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.create_delta",
            return_value=_delta(),
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=_delta(status="in_review"),
        ):
            result = promote_generated_fragment(
                user_id="johnnie_fields",
                fragment_text="Maybe the system can read the purchase order and check the terms.",
                option_text="Maybe the system can read the purchase order and check the terms.",
                option_index=1,
                topic="AI and future work",
                audience="tech_ai",
                category="value",
                content_type="linkedin_post",
                source_mode="recent_signals",
                support_items=[],
                option_brief={
                    "framing_mode": "story_first",
                    "story_beat": "Five years before everything changes.",
                },
            )

        self.assertNotEqual(result["target_file"], "history/story_bank.md")

    def test_claim_proposal_stays_selectable_when_fragment_is_the_whole_option(self) -> None:
        captured_update = None

        def fake_update(_delta_id, payload):
            nonlocal captured_update
            captured_update = payload
            return _delta(status="in_review", metadata=payload.metadata)

        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=None,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.create_delta",
            return_value=_delta(),
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            side_effect=fake_update,
        ):
            result = promote_generated_fragment(
                user_id="johnnie_fields",
                fragment_text="Shared context survives every workflow handoff.",
                option_text="Shared context survives every workflow handoff.",
                option_index=0,
                topic="agent orchestration",
                audience="tech_ai",
                category="value",
                content_type="linkedin_post",
                source_mode="canon_reservoir",
                support_items=[{"reservoir_lane": "canon_bridge", "text": "Context continuity is canonical."}],
            )

        self.assertEqual(result["route_key"], "core_canon")
        self.assertIsNotNone(captured_update)
        self.assertEqual(captured_update.metadata["talking_points"], ["Shared context survives every workflow handoff."])
        self.assertNotEqual(captured_update.metadata["source_excerpt_clean"], captured_update.metadata["talking_points"][0])
        self.assertEqual(captured_update.metadata["selected_promotion_items"], [])

    def test_existing_committed_delta_short_circuits_duplicate_write(self) -> None:
        existing = _delta(
            status="committed",
            metadata={"bundle_written_files": ["identity/VOICE_PATTERNS.md"]},
            delta_id="existing-delta",
        )
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=existing,
        ), patch("app.services.generated_fragment_promotion_service.persona_delta_service.create_delta") as create_delta_mock:
            result = promote_generated_fragment(
                user_id="johnnie_fields",
                fragment_text="That is the part people miss.",
                option_text="That is the part people miss.",
                option_index=2,
                topic="operator clarity",
                audience="tech_ai",
                category="value",
                content_type="linkedin_post",
                source_mode="recent_signals",
                support_items=[{"reservoir_lane": "voice_guidance", "primary_type": "voice"}],
            )

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["delta_id"], "existing-delta")
        self.assertEqual(result["target_file"], "identity/VOICE_PATTERNS.md")
        create_delta_mock.assert_not_called()

    def test_undo_generated_fragment_removes_canon_write(self) -> None:
        committed = _delta(
            status="committed",
            metadata={
                "review_source": "linkedin_workspace.generated_fragment",
                "committed_promotion_items": [
                    {
                        "id": "delta-undo:item-1",
                        "kind": "framework",
                        "label": "Framework",
                        "content": "Operator clarity beats dashboard sprawl.",
                        "target_file": "identity/decision_principles.md",
                    }
                ],
            },
            delta_id="delta-undo",
        )
        reverted = _delta(
            status="reverted",
            metadata={
                "review_source": "linkedin_workspace.generated_fragment",
                "reverted_target_files": ["identity/decision_principles.md"],
                "preserved_target_files": [],
            },
            delta_id="delta-undo",
        )
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta",
            return_value=committed,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.list_deltas",
            return_value=[],
        ), patch(
            "app.services.generated_fragment_promotion_service.remove_promotion_items_from_bundle",
            return_value={"written_files": ["identity/decision_principles.md"], "file_results": {}},
        ) as remove_mock, patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=reverted,
        ):
            result = undo_generated_fragment_promotion(delta_id="delta-undo")

        self.assertTrue(result["success"])
        self.assertFalse(result["already_reverted"])
        self.assertEqual(result["delta_id"], "delta-undo")
        self.assertEqual(result["removed_target_files"], ["identity/decision_principles.md"])
        remove_mock.assert_called_once()

    def test_undo_in_review_fragment_withdraws_proposal_without_touching_canon(self) -> None:
        proposal = _delta(
            status="in_review",
            metadata={
                "review_source": "linkedin_workspace.generated_fragment",
                "promotion_state": "awaiting_owner_review",
                "pending_promotion": False,
            },
            delta_id="delta-proposal",
        )
        reverted = _delta(
            status="reverted",
            metadata={
                "review_source": "linkedin_workspace.generated_fragment",
                "promotion_state": "reverted",
            },
            delta_id="delta-proposal",
        )
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta",
            return_value=proposal,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=reverted,
        ) as update_mock, patch(
            "app.services.generated_fragment_promotion_service.remove_promotion_items_from_bundle"
        ) as remove_mock:
            result = undo_generated_fragment_promotion(delta_id="delta-proposal")

        self.assertTrue(result["success"])
        self.assertEqual(result["removed_target_files"], [])
        self.assertIn("Canon was unchanged", result["message"])
        self.assertEqual(update_mock.call_args.args[1].status, "reverted")
        remove_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
