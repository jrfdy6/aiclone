from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.models import PMCard
from app.services import linkedin_owner_review_service


class LinkedInGeneratedOwnerReviewTest(unittest.TestCase):
    def _request_payload(self) -> dict:
        return {
            "user_id": "johnnie_fields",
            "topic": "judgment literacy",
            "content_type": "linkedin_post",
            "audience": "tech_ai",
            "source_card": {
                "item_key": "brief-item-1",
                "brief_id": "brief-1",
                "origin_type": "daily_brief_item",
                "origin_id": "brief-item-1",
                "owner_reaction": "This is the point I want to make in public.",
                "title": "AI literacy is judgment literacy",
                "summary": "Better judgment matters more than adding another tool.",
                "source_url": "https://example.com/judgment",
                "source_path": "knowledge/ingestions/private-source.md",
                "priority_lane": "ai",
                "source_kind": "daily_brief",
            },
        }

    def test_generated_option_creates_one_durable_owner_review_card_and_dedupes(self) -> None:
        cards: list[PMCard] = []

        def create_card(payload):
            now = datetime.now(timezone.utc)
            card = PMCard(
                id="generated-review-card-1",
                title=payload.title,
                owner=payload.owner,
                status=payload.status,
                source=payload.source,
                link_type=payload.link_type,
                link_id=payload.link_id,
                payload=payload.payload,
                created_at=now,
                updated_at=now,
            )
            cards.append(card)
            return card

        with patch.object(linkedin_owner_review_service.pm_card_service, "list_cards", side_effect=lambda limit=250: list(cards)), patch.object(
            linkedin_owner_review_service.pm_card_service,
            "create_card",
            side_effect=create_card,
        ) as create:
            first = linkedin_owner_review_service.ensure_generated_owner_review_item(
                job_id="job-123",
                option_index=1,
                option_text="Judgment is the real AI literacy. Tools only amplify the operating choices already being made.",
                request_payload=self._request_payload(),
                context_packet={"proof_packets": ["A public-safe proof anchor."]},
            )
            second = linkedin_owner_review_service.ensure_generated_owner_review_item(
                job_id="job-123",
                option_index=1,
                option_text="Judgment is the real AI literacy. Tools only amplify the operating choices already being made.",
                request_payload=self._request_payload(),
                context_packet={"proof_packets": ["A public-safe proof anchor."]},
            )

        self.assertEqual(create.call_count, 1)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["card_id"], second["card_id"])
        self.assertEqual(first["queue_id"], second["queue_id"])
        owner_review = cards[0].payload["owner_review"]
        self.assertEqual(cards[0].status, "review")
        self.assertEqual(owner_review["sync_state"], "pending_owner_review")
        self.assertEqual(owner_review["approval_status"], "owner_review_required")
        self.assertEqual(owner_review["publish_posture"], "owner_review_required")
        self.assertEqual(owner_review["entry_kind"], "generated")
        self.assertEqual(owner_review["source_kind"], "codex_generation")
        self.assertEqual(owner_review["generation_job_id"], "job-123")
        self.assertEqual(owner_review["generation_option_index"], 1)
        self.assertEqual(owner_review["source_card"]["brief_id"], "brief-1")
        self.assertNotIn("execution", cards[0].payload)
        self.assertIsNone(owner_review.get("decision"))
        self.assertIn(
            "do not publish automatically",
            linkedin_owner_review_service._owner_review_reason(first["item"], "approve"),
        )

    def test_listing_keeps_pm_generated_review_when_file_queue_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            drafts_root = root / "drafts"
            drafts_root.mkdir(parents=True)
            (drafts_root / "queue_01.md").write_text(
                """# FEEZIE Draft Queue

## Queue

### FEEZIE-001 - Existing queue draft
- Lane: ai
- Format: linkedin_post
- Core angle: Existing queue angle
- Why now: Existing timing reason
- Status: owner_review_draft (`drafts/existing.md`)
- Approval status: `owner_review_required`
- Proof anchors:
  - Existing public proof
""",
                encoding="utf-8",
            )
            (drafts_root / "existing.md").write_text(
                """---
title: Existing queue draft
publish_posture: owner_review_required
created_at: 2026-07-19T12:00:00+00:00
source_kind: feezie_queue
---

## First-pass draft

This existing file-backed draft is still waiting for owner review.
""",
                encoding="utf-8",
            )

            generated_item = linkedin_owner_review_service._generated_owner_review_item(
                job_id="job-456",
                option_index=0,
                option_text="This generated draft must also remain visible when the file-backed queue is healthy.",
                request_payload=self._request_payload(),
                context_packet={"proof_packets": ["A second public-safe proof anchor."]},
            )
            generated_payload = linkedin_owner_review_service._build_pending_owner_review_card_payload(generated_item)
            now = datetime.now(timezone.utc)
            generated_card = PMCard(
                id="generated-review-card-2",
                title="Generated owner review",
                owner="Neo",
                status="review",
                source=linkedin_owner_review_service.OWNER_REVIEW_CARD_SOURCE,
                link_type=linkedin_owner_review_service.OWNER_REVIEW_LINK_TYPE,
                link_id=None,
                payload=generated_payload,
                created_at=now,
                updated_at=now,
            )

            with patch.object(linkedin_owner_review_service, "_linkedin_root", return_value=root), patch.object(
                linkedin_owner_review_service.pm_card_service,
                "list_cards",
                return_value=[generated_card],
            ):
                result = linkedin_owner_review_service.list_owner_review_items()

        queue_ids = {item["queue_id"] for item in result["items"]}
        self.assertIn("FEEZIE-001", queue_ids)
        self.assertIn(generated_item["queue_id"], queue_ids)
        generated_result = next(item for item in result["items"] if item["queue_id"] == generated_item["queue_id"])
        self.assertEqual(generated_result["approval_status"], "owner_review_required")
        self.assertEqual(generated_result["publish_posture"], "owner_review_required")


if __name__ == "__main__":
    unittest.main()
