from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

source_lifecycle_module = importlib.import_module("app.services.linkedin_source_lifecycle_service")


class LinkedinSourceLifecycleServiceTests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        workspace = root / "workspaces" / "linkedin-content-os"
        (workspace / "drafts").mkdir(parents=True, exist_ok=True)
        (workspace / "research" / "market_signals").mkdir(parents=True, exist_ok=True)
        (workspace / "docs" / "release_packets").mkdir(parents=True, exist_ok=True)
        return workspace

    def test_owner_review_draft_wins_over_post_seed_and_path_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(Path(tmp))
            source_path = "workspaces/linkedin-content-os/research/market_signals/admissions.md"
            (workspace / "drafts" / "2026-04-01_admissions.md").write_text(
                """---
title: "Admissions teams are a content goldmine"
draft_kind: owner_review
source_kind: reaction_seed
publish_posture: owner_review_required
source_url: https://www.linkedin.com/posts/example
source_path: workspaces/linkedin-content-os/research/market_signals/admissions.md
---

# Admissions teams are a content goldmine

## First-pass draft

Draft body.
""",
                encoding="utf-8",
            )

            payload = source_lifecycle_module.build_source_lifecycle(
                linkedin_root=workspace,
                social_feed={
                    "items": [
                        {
                            "id": "feed-1",
                            "platform": "linkedin",
                            "title": "Admissions teams are a content goldmine",
                            "author": "Marc Zarefsky",
                            "source_url": "https://www.linkedin.com/posts/example",
                            "source_path": "research/market_signals/admissions.md",
                            "ranking": {"total": 174},
                        }
                    ]
                },
                reaction_queue={
                    "post_seeds": [
                        {
                            "title": "Admissions teams are a content goldmine",
                            "source_url": "https://www.linkedin.com/posts/example",
                            "source_path": source_path,
                            "qualification_route": "pass",
                            "publish_posture": "owner_review_required",
                        }
                    ]
                },
                weekly_plan={
                    "recommendations": [
                        {
                            "title": "Admissions teams are a content goldmine",
                            "source_kind": "draft",
                            "publish_posture": "owner_review_required",
                            "source_path": "workspaces/linkedin-content-os/drafts/2026-04-01_admissions.md",
                        }
                    ]
                },
            )

            items = payload["items"]
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["stage"], "owner_review")
            self.assertEqual(item["visibility"], "owner_review")
            self.assertIn("path:research/market_signals/admissions.md", item["match_keys"])
            self.assertIn("path:workspaces/linkedin-content-os/research/market_signals/admissions.md", item["match_keys"])
            self.assertEqual(payload["counts"]["by_stage"]["owner_review"], 1)

    def test_scheduled_receipt_wins_over_banked_queue_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(Path(tmp))
            (workspace / "drafts" / "queue_01.md").write_text(
                """# FEEZIE Draft Queue 01

## Queue

### FEEZIE-001 - Cheap models, better systems
- Lane: `ai`
- Format: long-form LinkedIn post
- Core angle: Better systems beat model worship.
- Proof anchors:
  - `knowledge/persona/feeze/history/story_bank.md`
- Why now: The system is active.
- Status: approved (`drafts/feezie-001_cheap-models-better-systems.md`)
- Owner packet: `drafts/feezie_owner_review_packet_20260410.md#feezie-001`
- Approval status: `owner_approved`
- Banked copy: `docs/release_packets/feezie-001_schedule_packet_20260419.md`
""",
                encoding="utf-8",
            )
            (workspace / "docs" / "release_packets" / "feezie-001_schedule_packet_20260419.md").write_text(
                "# FEEZIE-001 Schedule Packet\n",
                encoding="utf-8",
            )
            receipt_dir = workspace / "analytics" / "2026-04-22_feezie-001"
            receipt_dir.mkdir(parents=True, exist_ok=True)
            (receipt_dir / "scheduled_receipt.json").write_text(
                json.dumps(
                    {
                        "schema_version": "linkedin_scheduled_writeback/v1",
                        "queue_id": "FEEZIE-001",
                        "scheduled_at_et": "Wed Apr 22, 2026 09:35 ET",
                        "asset_decision": "text-only",
                    }
                ),
                encoding="utf-8",
            )

            payload = source_lifecycle_module.build_source_lifecycle(linkedin_root=workspace)
            item = next(entry for entry in payload["items"] if entry.get("queue_id") == "FEEZIE-001")
            self.assertEqual(item["stage"], "scheduled")
            self.assertEqual(item["visibility"], "scheduled")
            self.assertEqual(item["scheduled_at"], "Wed Apr 22, 2026 09:35 ET")
            self.assertIn("queue:FEEZIE-001", item["match_keys"])

    def test_rejected_feedback_wins_over_seed_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(Path(tmp))
            analytics_dir = workspace / "analytics"
            analytics_dir.mkdir(parents=True, exist_ok=True)
            source_path = "workspaces/linkedin-content-os/research/market_signals/noisy-reddit.md"
            (analytics_dir / "feed_feedback.jsonl").write_text(
                json.dumps(
                    {
                        "recorded_at": "2026-04-21T12:00:00+00:00",
                        "feed_item_id": "reddit-noisy",
                        "title": "Attention DEVS and SALES PERSONS",
                        "platform": "reddit",
                        "decision": "reject",
                        "lens": "current-role",
                        "source_url": "https://reddit.com/r/example/comments/123",
                        "source_path": source_path,
                        "notes": "Owner marked this source Not for FEEZIE.",
                        "evaluation_overall": 6.7,
                        "source_expression_quality": 5.3,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = source_lifecycle_module.build_source_lifecycle(
                linkedin_root=workspace,
                social_feed={
                    "items": [
                        {
                            "id": "reddit-noisy",
                            "platform": "reddit",
                            "title": "Attention DEVS and SALES PERSONS",
                            "author": "/u/mybrotherhasabbgun",
                            "source_url": "https://reddit.com/r/example/comments/123",
                            "source_path": "research/market_signals/noisy-reddit.md",
                            "ranking": {"total": 170},
                        }
                    ]
                },
                reaction_queue={
                    "post_seeds": [
                        {
                            "title": "Attention DEVS and SALES PERSONS",
                            "source_url": "https://reddit.com/r/example/comments/123",
                            "source_path": source_path,
                            "qualification_route": "pass",
                            "publish_posture": "owner_review_required",
                        }
                    ]
                },
            )

            item = payload["items"][0]
            self.assertEqual(item["stage"], "rejected")
            self.assertEqual(item["visibility"], "rejected")
            self.assertEqual(payload["counts"]["by_stage"]["rejected"], 1)
            self.assertEqual(payload["counts"]["needs_decision"], 0)
            self.assertEqual(payload["counts"]["in_workflow"], 0)


if __name__ == "__main__":
    unittest.main()
