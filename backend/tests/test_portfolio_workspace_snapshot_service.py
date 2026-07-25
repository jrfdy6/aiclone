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
                created_at=datetime.now(timezone.utc),
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
                created_at=datetime.now(timezone.utc),
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
                created_at=datetime.now(timezone.utc),
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

    def test_build_snapshot_filters_workspace_status_ui_noise_from_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "shared-ops"
            workspace_root.mkdir(parents=True)

            entry = {
                "key": "shared_ops",
                "kind": "executive",
                "display_name": "Executive",
                "workspace_root": "shared-ops",
                "status": "live",
                "priority_order": 0,
                "portfolio_visible": False,
            }
            standup = SimpleNamespace(
                id="standup-ui-noise",
                status="queued",
                workspace_key="shared_ops",
                blockers=[
                    "Recent Standups workspace_sync · Apr 19, 4:49 PM · 2 commitments · 0 blockers "
                    "AI Swag Store Standup · Apr 19, 4:47 PM · 2 commitments · 0 blockers "
                    "Open PM Lane No open PM cards in this workspace.",
                ],
                needs=[],
                payload={"standup_kind": "executive_ops", "summary": "Executive is current."},
                created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="shared-ops"), patch.object(
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
        self.assertEqual(workspace["active_blockers"], [])
        self.assertEqual(workspace["counts"]["standup_blockers"], 0)
        self.assertEqual(workspace["attention"]["label"], "Healthy")

    def test_build_snapshot_filters_brain_debug_ui_text_from_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = repo_root / "workspaces" / "shared-ops"
            workspace_root.mkdir(parents=True)

            entry = {
                "key": "shared_ops",
                "kind": "executive",
                "display_name": "Executive",
                "workspace_root": "shared-ops",
                "status": "live",
                "priority_order": 0,
                "portfolio_visible": False,
            }
            standup = SimpleNamespace(
                id="standup-debug-ui-noise",
                status="queued",
                workspace_key="shared_ops",
                blockers=[
                    "why does it say needs brain: FEEZIE OS Direct · live Needs Brain Pack 0/5 "
                    "Identity files PM 3 Active cards Blockers 6 Standup blockers Latest State.",
                    "Fallback watchdog found 1 active fallback condition(s) … Last Execution Result No execution result visible yet.",
                    "Active Blockers Automation drift remains: mismatch_count=1, action_required_count=1.",
                    "Automation drift remains: mismatch_count=1, action_required_count=1.",
                ],
                needs=[],
                payload={"standup_kind": "executive_ops", "summary": "Executive is current."},
                created_at=datetime.now(timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="shared-ops"), patch.object(
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
        self.assertEqual(workspace["active_blockers"], ["Automation drift remains: mismatch_count=1, action_required_count=1."])
        self.assertEqual(workspace["counts"]["standup_blockers"], 1)

    def test_build_snapshot_treats_observational_automation_drift_as_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "workspaces" / "shared-ops"
            workspace_root.mkdir(parents=True)
            entry = {
                "key": "shared_ops",
                "kind": "executive",
                "display_name": "Executive",
                "workspace_root": "shared-ops",
                "status": "live",
                "priority_order": 0,
                "portfolio_visible": False,
            }
            standup = SimpleNamespace(
                id="standup-observational-drift",
                status="queued",
                workspace_key="shared_ops",
                blockers=["Automation drift remains: mismatch_count=21, action_required_count=0."],
                commitments=[],
                needs=[],
                payload={"standup_kind": "executive_ops", "summary": "No action is required."},
                created_at=datetime.now(timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="shared-ops"), patch.object(
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
        self.assertEqual(workspace["active_blockers"], [])
        self.assertEqual(workspace["counts"]["standup_blockers"], 0)
        self.assertEqual(workspace["readiness"]["state"], "healthy")
        self.assertFalse(workspace["has_system_issue"])

    def test_build_snapshot_keeps_stale_failed_recovery_visible_without_degrading_current_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "workspaces" / "easy-outfit-app"
            workspace_root.mkdir(parents=True)
            entry = {
                "key": "easy-outfit-app",
                "kind": "workspace",
                "display_name": "Easy Outfit App",
                "workspace_root": "easy-outfit-app",
                "status": "live",
                "priority_order": 3,
                "portfolio_visible": True,
            }
            card = SimpleNamespace(
                id="historical-recovery-card",
                title="Capture the first Easy Outfit App traffic baseline proof",
                status="failed",
                owner="Easy Outfit App Operator",
                source="test",
                link_type="execution",
                payload={
                    "workspace_key": "easy-outfit-app",
                    "execution": {
                        "state": "failed",
                        "last_transition_at": "2025-04-29T17:19:00Z",
                    },
                },
                created_at=datetime(2025, 4, 29, tzinfo=timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            standup = SimpleNamespace(
                id="current-easy-outfit-standup",
                status="queued",
                workspace_key="easy-outfit-app",
                blockers=[],
                commitments=[],
                needs=[],
                payload={"standup_kind": "workspace_sync", "summary": "Current Easy Outfit state."},
                created_at=datetime.now(timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="easy-outfit-app"), patch.object(
                service.pm_card_service,
                "list_cards",
                return_value=[card],
            ), patch.object(
                service.pm_card_service,
                "decorate_card_for_client",
                return_value=card,
            ), patch.object(service.standup_service, "list_standups", return_value=[standup]), patch.object(
                service,
                "list_snapshot_payloads",
                return_value={},
            ):
                snapshot = service.build_portfolio_workspace_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["counts"]["active_pm_cards"], 1)
        self.assertEqual(workspace["counts"]["system_issue_pm_cards"], 0)
        self.assertEqual(workspace["counts"]["historical_recovery_pm_cards"], 1)
        self.assertEqual(workspace["active_pm_cards"][0]["truth"]["freshness"], "stale")
        self.assertEqual(workspace["attention"]["failed_pm_cards"], 0)
        self.assertEqual(workspace["attention"]["historical_failed_pm_cards"], 1)
        self.assertEqual(workspace["readiness"]["failed_executions"], 0)
        self.assertEqual(workspace["readiness"]["historical_failed_executions"], 1)
        self.assertEqual(workspace["readiness"]["state"], "healthy")
        self.assertFalse(workspace["has_system_issue"])

    def test_stale_execution_state_mismatch_stays_in_historical_recovery(self) -> None:
        card = {
            "truth": {
                "execution_class": "failed",
                "freshness": "stale",
                "state_mismatch": True,
            }
        }

        attention = service._attention_summary(
            operator_cards=[],
            system_issue_cards=[card],
            active_blockers=[],
        )
        readiness = service._readiness_summary(
            latest_standups=[],
            system_issue_cards=[card],
            active_blockers=[],
        )

        self.assertEqual(attention["failed_pm_cards"], 0)
        self.assertEqual(attention["historical_failed_pm_cards"], 1)
        self.assertEqual(attention["state_mismatch_pm_cards"], 0)
        self.assertFalse(attention["has_system_issue"])
        self.assertEqual(readiness["failed_executions"], 0)
        self.assertEqual(readiness["historical_failed_executions"], 1)
        self.assertEqual(readiness["state_mismatches"], 0)
        self.assertNotEqual(readiness["state"], "degraded")

    def test_current_execution_state_mismatch_remains_a_system_issue(self) -> None:
        card = {
            "truth": {
                "execution_class": "failed",
                "freshness": "current",
                "state_mismatch": True,
            }
        }

        attention = service._attention_summary(
            operator_cards=[],
            system_issue_cards=[card],
            active_blockers=[],
        )
        readiness = service._readiness_summary(
            latest_standups=[],
            system_issue_cards=[card],
            active_blockers=[],
        )

        self.assertEqual(attention["failed_pm_cards"], 1)
        self.assertEqual(attention["state_mismatch_pm_cards"], 1)
        self.assertTrue(attention["has_system_issue"])
        self.assertEqual(readiness["failed_executions"], 1)
        self.assertEqual(readiness["state_mismatches"], 1)
        self.assertEqual(readiness["state"], "degraded")

    def test_legacy_path_only_affects_readiness_while_its_card_is_current(self) -> None:
        current_standup = [{"truth": {"freshness": "current", "quality": "actionable"}}]
        stale_card = {
            "truth": {
                "execution_class": "unverified",
                "freshness": "stale",
                "state_mismatch": False,
                "legacy_instruction": True,
            }
        }
        current_card = {
            "truth": {
                "execution_class": "unverified",
                "freshness": "current",
                "state_mismatch": False,
                "legacy_instruction": True,
            }
        }

        stale_readiness = service._readiness_summary(
            latest_standups=current_standup,
            system_issue_cards=[stale_card],
            active_blockers=[],
        )
        current_readiness = service._readiness_summary(
            latest_standups=current_standup,
            system_issue_cards=[current_card],
            active_blockers=[],
        )

        self.assertEqual(stale_readiness["state"], "healthy")
        self.assertEqual(stale_readiness["legacy_instructions"], 0)
        self.assertEqual(stale_readiness["historical_system_issues"], 1)
        self.assertEqual(current_readiness["state"], "watch")
        self.assertEqual(current_readiness["legacy_instructions"], 1)

    def test_build_snapshot_treats_stale_standup_blocker_as_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "workspaces" / "agc"
            workspace_root.mkdir(parents=True)
            entry = {
                "key": "agc",
                "kind": "workspace",
                "display_name": "AGC",
                "workspace_root": "agc",
                "status": "live",
                "priority_order": 4,
                "portfolio_visible": True,
            }
            standup = SimpleNamespace(
                id="historical-standup",
                status="queued",
                workspace_key="agc",
                blockers=["An old blocker remains in the historical record."],
                commitments=[],
                needs=[],
                payload={"standup_kind": "workspace_sync", "summary": "Historical AGC state."},
                created_at=datetime(2025, 4, 29, tzinfo=timezone.utc),
            )

            with patch.object(service, "workspace_registry_entries", return_value=(entry,)), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="agc"), patch.object(
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
        self.assertEqual(workspace["active_blockers"], [])
        self.assertEqual(workspace["counts"]["standup_blockers"], 0)
        self.assertEqual(workspace["readiness"]["state"], "watch")
        self.assertFalse(workspace["has_system_issue"])

    def test_alias_aware_services_are_queried_once_per_workspace(self) -> None:
        with patch.object(service.pm_card_service, "list_cards", return_value=[]) as list_cards, patch.object(
            service.standup_service,
            "list_standups",
            return_value=[],
        ) as list_standups:
            service._safe_pm_cards("feezie-os", limit=8)
            service._safe_standups("feezie-os", limit=5)

        list_cards.assert_called_once_with(workspace_key="feezie-os", limit=8)
        list_standups.assert_called_once_with(workspace_key="feezie-os", limit=5)

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
        self.assertEqual(workspace["attention"]["status"], "needs_owner")
        self.assertEqual(workspace["attention"]["label"], "Needs your decision")
        self.assertEqual(workspace["counts"]["needs_owner_pm_cards"], 1)

    def test_build_snapshot_reads_private_activity_first_and_keeps_legacy_fallback_for_future_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "project"
            state_root = Path(temp_dir) / "private-state"
            workspace_root = repo_root / "workspaces" / "future-project-root"
            private_root = state_root / "workspaces" / "future-capability"
            (workspace_root / "analytics").mkdir(parents=True)
            (workspace_root / "memory").mkdir(parents=True)
            (private_root / "briefings").mkdir(parents=True)
            (private_root / "dispatch").mkdir(parents=True)
            (workspace_root / "CHARTER.md").write_text(
                "# Charter\n\nCanonical project contract.\n",
                encoding="utf-8",
            )
            (private_root / "CHARTER.md").write_text(
                "# Charter\n\nGenerated state must not replace the project contract.\n",
                encoding="utf-8",
            )
            (private_root / "briefings" / "20260725T120000Z_status.md").write_text(
                "# Status\n\nNewest private-state briefing.\n",
                encoding="utf-8",
            )
            (private_root / "dispatch" / "20260725T120000Z_run.json").write_text(
                '{"source": "private"}\n',
                encoding="utf-8",
            )
            (workspace_root / "analytics" / "20260724_report.md").write_text(
                "# Analytics\n\nLegacy analytics fallback.\n",
                encoding="utf-8",
            )
            (workspace_root / "memory" / "execution_log.md").write_text(
                "# Execution\n\nLegacy execution fallback.\n",
                encoding="utf-8",
            )

            entry = {
                "key": "future-capability",
                "kind": "workspace",
                "display_name": "Future Capability",
                "workspace_root": "future-project-root",
                "status": "standing_up",
                "priority_order": 10,
                "portfolio_visible": True,
            }

            with patch.object(service, "PRIVATE_STATE_ROOT", state_root), patch.object(
                service,
                "workspace_registry_entries",
                return_value=(entry,),
            ), patch.object(
                service,
                "workspace_root_path",
                return_value=workspace_root,
            ), patch.object(service, "workspace_root_slug", return_value="future-project-root"), patch.object(
                service.pm_card_service,
                "list_cards",
                return_value=[],
            ), patch.object(service.standup_service, "list_standups", return_value=[]), patch.object(
                service,
                "list_snapshot_payloads",
                return_value={},
            ):
                snapshot = service.build_portfolio_workspace_snapshot()

        workspace = snapshot["workspaces"][0]
        self.assertEqual(workspace["workspace_key"], "future-capability")
        self.assertEqual(workspace["latest_briefing"]["source"], "private_state")
        self.assertIn("Newest private-state briefing", workspace["latest_briefing"]["tail"])
        self.assertEqual(workspace["latest_dispatch"]["source"], "private_state")
        self.assertEqual(workspace["latest_analytics"]["source"], "legacy_project")
        self.assertIn("Legacy analytics fallback", workspace["latest_analytics"]["tail"])
        self.assertEqual(workspace["execution_log"]["source"], "legacy_project")
        self.assertEqual(workspace["pack_status"][0]["snippet"], "Canonical project contract.")


if __name__ == "__main__":
    unittest.main()
