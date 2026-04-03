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
from app.services.generated_fragment_promotion_service import promote_generated_fragment


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
    def test_metric_fragment_routes_to_wins_and_commits(self) -> None:
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=None,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.create_delta",
            return_value=_delta(),
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=_delta(status="approved"),
        ) as update_delta_mock, patch(
            "app.services.generated_fragment_promotion_service.promote_delta_to_canon",
            return_value=_delta(status="committed", metadata={"bundle_written_files": ["history/wins.md"]}),
        ):
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
        self.assertEqual(result["written_files"], ["history/wins.md"])
        update_call = update_delta_mock.call_args
        self.assertEqual(
            update_call.args[1].metadata["selected_promotion_items"][0]["targetFile"],
            "history/wins.md",
        )

    def test_story_like_fragment_routes_to_story_bank(self) -> None:
        with patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.get_delta_by_review_key",
            return_value=None,
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.create_delta",
            return_value=_delta(),
        ), patch(
            "app.services.generated_fragment_promotion_service.persona_delta_service.update_delta",
            return_value=_delta(status="approved"),
        ), patch(
            "app.services.generated_fragment_promotion_service.promote_delta_to_canon",
            return_value=_delta(status="committed", metadata={"bundle_written_files": ["history/story_bank.md"]}),
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
        self.assertIn("Story Bank", result["message"])

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


if __name__ == "__main__":
    unittest.main()
