from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import decision_snapshot_service as service  # noqa: E402
from app.services.persona_bundle_writer import resolve_persona_bundle_root  # noqa: E402
from app.services.persona_profile_coverage_service import build_persona_profile_coverage  # noqa: E402
from app.routes.brain import router as brain_router  # noqa: E402


class DecisionSnapshotServiceTests(unittest.TestCase):
    def test_snapshot_is_content_minimized_and_keeps_actionable_facts(self) -> None:
        portfolio = {
            "generated_at": "2026-07-25T12:00:00Z",
            "counts": {"workspaces": 1, "active_pm_cards": 1},
            "workspaces": [
                {
                    "workspace_key": "future-workspace",
                    "display_name": "Future Workspace",
                    "short_label": "Future",
                    "kind": "workspace",
                    "status": "planned",
                    "priority_order": 99,
                    "capability_keys": ["system_health", "custom_future_capability"],
                    "capabilities": [
                        {"key": "system_health", "label": "System health"},
                        {"key": "custom_future_capability", "label": "Future capability"},
                    ],
                    "attention": {
                        "status": "needs_owner",
                        "label": "Needs your decision",
                        "needs_operator": True,
                        "has_system_issue": False,
                        "reasons": ["Private blocker detail"],
                    },
                    "readiness": {
                        "state": "watch",
                        "label": "Check soon",
                        "reasons": ["Private readiness detail"],
                        "latest_standup_freshness": "fresh",
                        "latest_standup_quality": "decision_ready",
                    },
                    "counts": {"active_pm_cards": 1, "standup_blockers": 1},
                    "active_pm_cards": [
                        {
                            "id": "card-1",
                            "title": "Approve launch boundary",
                            "status": "review",
                            "owner": "Feeze",
                            "attention_kind": "needs_owner",
                            "updated_at": "2026-07-25T11:00:00Z",
                            "payload": {"private_source": "must not escape"},
                        }
                    ],
                    "latest_standups": [
                        {
                            "id": "standup-1",
                            "status": "complete",
                            "summary": "Private standup summary",
                            "blockers": ["Private blocker detail"],
                            "created_at": "2026-07-25T10:00:00Z",
                            "truth": {"freshness": "fresh", "quality": "decision_ready"},
                        }
                    ],
                }
            ],
        }
        persona = {
            "schema_version": "persona_profile_coverage/v1",
            "private_content_included": False,
            "ready": True,
            "dimensions": {"favorite_language": True},
            "coverage": {"reusable_phrase_patterns": 12},
            "supported_intake_lanes": ["phrase_candidate"],
        }

        with patch.object(service, "build_portfolio_workspace_snapshot", return_value=portfolio), patch.object(
            service,
            "build_persona_profile_coverage",
            return_value=persona,
        ):
            snapshot = service.build_decision_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["capability_keys"][-1], "custom_future_capability")
        self.assertEqual(workspace["top_priorities"][0]["action_ref"]["id"], "card-1")
        self.assertNotIn("reasons", workspace["attention"])
        self.assertNotIn("summary", workspace["latest_standup"])
        self.assertNotIn("payload", workspace["top_priorities"][0])
        self.assertFalse(snapshot["data_policy"]["private_content_included"])

    def test_persona_coverage_reports_dimensions_without_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "identity").mkdir()
            (root / "prompts").mkdir()
            (root / "history").mkdir()
            (root / "identity" / "VOICE_PATTERNS.md").write_text(
                "# Voice\n\n## Reusable Phrases\n- phrase one\n\n## Sentence Rhythm\n- rhythm one\n",
                encoding="utf-8",
            )
            (root / "identity" / "audience_communication.md").write_text(
                "# Communication\n\n## Patterns\n- pattern one\n",
                encoding="utf-8",
            )
            (root / "prompts" / "content_examples.md").write_text(
                "# Examples\n\n## Good Examples\n- example one\n",
                encoding="utf-8",
            )
            (root / "prompts" / "taste_examples.md").write_text(
                "# Taste\n\n## Taste Anchors\n- anchor one\n",
                encoding="utf-8",
            )
            (root / "history" / "story_bank.md").write_text(
                "# Stories\n\n## Story One\n- private detail\n",
                encoding="utf-8",
            )

            coverage = build_persona_profile_coverage(bundle_root=root)

        self.assertTrue(coverage["ready"])
        self.assertEqual(coverage["coverage"]["personal_stories"], 1)
        self.assertFalse(coverage["private_content_included"])
        self.assertNotIn("phrase one", str(coverage))

    def test_runtime_persona_resolution_prefers_the_complete_bundle(self) -> None:
        bundle_root = resolve_persona_bundle_root()
        self.assertTrue((bundle_root / "identity" / "VOICE_PATTERNS.md").is_file())
        self.assertTrue((bundle_root / "identity" / "audience_communication.md").is_file())
        self.assertTrue((bundle_root / "history" / "story_bank.md").is_file())

    def test_shadow_snapshot_route_is_registered(self) -> None:
        paths = {getattr(route, "path", "") for route in brain_router.routes}
        self.assertIn("/api/brain/decision-snapshot", paths)


if __name__ == "__main__":
    unittest.main()
