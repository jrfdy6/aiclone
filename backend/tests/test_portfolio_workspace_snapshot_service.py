from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import portfolio_workspace_snapshot_service as service  # noqa: E402


class PortfolioWorkspaceSnapshotServiceTests(unittest.TestCase):
    def test_build_snapshot_reuses_registry_pm_standup_and_local_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "fusion-os"
            (workspace_root / "docs").mkdir(parents=True)
            (workspace_root / "briefings").mkdir(parents=True)
            (workspace_root / "memory").mkdir(parents=True)
            (workspace_root / "dispatch").mkdir(parents=True)
            (workspace_root / "CHARTER.md").write_text("# Charter\n\nFusion local mission.\n", encoding="utf-8")
            (workspace_root / "docs" / "operating_model.md").write_text("# Operating Model\n\nLocal operating proof.\n", encoding="utf-8")
            (workspace_root / "briefings" / "20260419T120000Z_status.md").write_text("# Status\n\nLatest briefing body.\n", encoding="utf-8")
            (workspace_root / "memory" / "execution_log.md").write_text("# Log\n\nLatest execution proof.\n", encoding="utf-8")
            (workspace_root / "dispatch" / "20260419T120000Z_sop.json").write_text('{"ok": true}\n', encoding="utf-8")

            entry = {
                "key": "fusion-os",
                "kind": "workspace",
                "display_name": "Fusion OS",
                "short_label": "Fusion",
                "workspace_root": "fusion-os",
                "status": "standing_up",
                "priority_order": 2,
                "portfolio_visible": True,
                "manager_agent": "Jean-Claude",
                "target_agent": "Fusion Systems Operator",
                "workspace_agent": "Fusion Systems Operator",
                "execution_mode": "delegated",
                "default_standup_kind": "workspace_sync",
                "workspace_sync_participants": ["Jean-Claude", "Fusion Systems Operator"],
            }
            card = SimpleNamespace(
                id="card-1",
                title="Validate Fusion proof",
                status="review",
                owner="Jean-Claude",
                source="test",
                payload={"workspace_key": "fusion-os"},
                updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            )
            standup = SimpleNamespace(
                id="standup-1",
                status="queued",
                workspace_key="fusion-os",
                blockers=["Needs owner proof"],
                needs=[],
                payload={"standup_kind": "workspace_sync", "summary": "Check delegated proof."},
                created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="fusion-os"), patch.object(
                service.pm_card_service,
                "list_cards",
                return_value=[card],
            ), patch.object(service.standup_service, "list_standups", return_value=[standup]), patch.object(
                service,
                "list_snapshot_payloads",
                return_value={"local_signal": {"ok": True}},
            ):
                snapshot = service.build_portfolio_workspace_snapshot()

        self.assertEqual(snapshot["counts"]["workspaces"], 1)
        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["workspace_key"], "fusion-os")
        self.assertTrue(workspace["needs_brain_attention"])
        self.assertEqual(workspace["counts"]["pack_files_present"], 1)
        self.assertEqual(workspace["counts"]["active_pm_cards"], 1)
        self.assertEqual(workspace["counts"]["standup_blockers"], 1)
        self.assertEqual(workspace["local_contracts"][0]["name"], "operating_model.md")
        self.assertIn("fusion-os", workspace["persisted_snapshot_types"])

    def test_build_snapshot_filters_resolved_workspace_root_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "linkedin-content-os"
            workspace_root.mkdir(parents=True)

            entry = {
                "key": "feezie-os",
                "kind": "workspace",
                "display_name": "FEEZIE OS",
                "workspace_root": "linkedin-content-os",
                "status": "live",
                "priority_order": 1,
                "portfolio_visible": True,
            }
            standup = SimpleNamespace(
                id="standup-legacy-root-blocker",
                status="queued",
                workspace_key="linkedin-os",
                blockers=[
                    "`linkedin-os` has no local artifact root yet.",
                    "Automation drift remains: mismatch_count=1, action_required_count=1.",
                ],
                needs=[],
                payload={"standup_kind": "workspace_sync", "summary": "Check FEEZIE proof."},
                created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="linkedin-content-os"), patch.object(
                service.pm_card_service,
                "list_cards",
                return_value=[],
            ), patch.object(service.standup_service, "list_standups", return_value=[standup]), patch.object(
                service,
                "list_snapshot_payloads",
                return_value={},
            ):
                snapshot = service.build_portfolio_workspace_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["counts"]["standup_blockers"], 1)
        self.assertEqual(workspace["latest_standups"][0]["workspace_key"], "feezie-os")
        self.assertEqual(
            workspace["latest_standups"][0]["blockers"],
            ["Automation drift remains: mismatch_count=1, action_required_count=1."],
        )
        self.assertTrue(workspace["needs_brain_attention"])

    def test_build_snapshot_prefers_existing_staged_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            missing_root = repo_root / "missing" / "workspaces" / "linkedin-content-os"
            staged_root = repo_root / "backend" / "workspaces" / "linkedin-content-os"
            staged_root.mkdir(parents=True)
            (staged_root / "CHARTER.md").write_text("# Charter\n\nFEEZIE staged proof.\n", encoding="utf-8")
            (staged_root / "IDENTITY.md").write_text("# Identity\n\nFEEZIE identity.\n", encoding="utf-8")

            entry = {
                "key": "feezie-os",
                "kind": "workspace",
                "display_name": "FEEZIE OS",
                "workspace_root": "linkedin-content-os",
                "status": "live",
                "priority_order": 1,
                "portfolio_visible": True,
            }

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=missing_root,
            ), patch.object(
                service,
                "_workspace_root_candidates",
                return_value=[missing_root, staged_root],
            ), patch.object(service.pm_card_service, "list_cards", return_value=[]), patch.object(
                service.standup_service,
                "list_standups",
                return_value=[],
            ), patch.object(service, "list_snapshot_payloads", return_value={}):
                snapshot = service.build_portfolio_workspace_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["workspace_root"], "workspaces/linkedin-content-os")
        self.assertEqual(workspace["counts"]["pack_files_present"], 2)
        self.assertFalse(workspace["needs_brain_attention"])

    def test_build_snapshot_counts_only_latest_standup_blockers_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "feezie-os"
            workspace_root.mkdir(parents=True)

            entry = {
                "key": "feezie-os",
                "kind": "workspace",
                "display_name": "FEEZIE OS",
                "workspace_root": "feezie-os",
                "status": "live",
                "priority_order": 1,
                "portfolio_visible": True,
            }
            newest = SimpleNamespace(
                id="standup-new",
                status="queued",
                workspace_key="feezie-os",
                blockers=[],
                needs=[],
                payload={"standup_kind": "workspace_sync", "summary": "FEEZIE is current."},
                created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            )
            older = SimpleNamespace(
                id="standup-old",
                status="queued",
                workspace_key="feezie-os",
                blockers=["Old blocker that was resolved by a newer standup."],
                needs=[],
                payload={"standup_kind": "workspace_sync", "summary": "Old FEEZIE state."},
                created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="feezie-os"), patch.object(
                service.pm_card_service,
                "list_cards",
                return_value=[],
            ), patch.object(service.standup_service, "list_standups", return_value=[newest, older]), patch.object(
                service,
                "list_snapshot_payloads",
                return_value={},
            ):
                snapshot = service.build_portfolio_workspace_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["active_blockers"], [])
        self.assertEqual(workspace["counts"]["standup_blockers"], 0)
        self.assertFalse(workspace["needs_brain_attention"])

    def test_build_snapshot_labels_owner_review_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "linkedin-content-os"
            workspace_root.mkdir(parents=True)

            entry = {
                "key": "feezie-os",
                "kind": "workspace",
                "display_name": "FEEZIE OS",
                "workspace_root": "linkedin-content-os",
                "status": "live",
                "priority_order": 1,
                "portfolio_visible": True,
            }
            card = SimpleNamespace(
                id="owner-review-card",
                title="Owner review - FEEZIE-001 - Cheap models, better systems",
                status="review",
                owner="Feeze",
                source="openclaw:workspace-owner-review",
                link_type="owner_review",
                payload={
                    "workspace_key": "feezie-os",
                    "owner_review": {"queue_id": "FEEZIE-001", "sync_state": "pending_owner_review"},
                },
                updated_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="linkedin-content-os"), patch.object(
                service.pm_card_service,
                "list_cards",
                return_value=[card],
            ), patch.object(service.standup_service, "list_standups", return_value=[]), patch.object(
                service,
                "list_snapshot_payloads",
                return_value={},
            ):
                snapshot = service.build_portfolio_workspace_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertTrue(workspace["needs_brain_attention"])
        self.assertEqual(workspace["attention"]["status"], "owner_review")
        self.assertEqual(workspace["attention"]["label"], "Owner Review")
        self.assertEqual(workspace["counts"]["owner_review_pm_cards"], 1)


if __name__ == "__main__":
    unittest.main()
