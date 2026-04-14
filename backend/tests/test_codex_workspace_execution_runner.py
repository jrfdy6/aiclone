from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexWorkspaceExecutionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.runner = _load_module("run_codex_workspace_execution", SCRIPTS_ROOT / "runners" / "run_codex_workspace_execution.py")

    def test_select_entry_requires_packet_and_queued_executor(self) -> None:
        entries = [
            {
                "card_id": "skip-no-packet",
                "workspace_key": "fusion-os",
                "execution_state": "running",
                "executor_status": "queued",
                "last_transition_at": "2026-04-06T12:00:00+00:00",
            },
            {
                "card_id": "skip-already-running",
                "workspace_key": "fusion-os",
                "execution_state": "running",
                "executor_status": "running",
                "execution_packet_path": "/tmp/running.json",
                "last_transition_at": "2026-04-06T11:00:00+00:00",
            },
            {
                "card_id": "pick-me",
                "workspace_key": "fusion-os",
                "execution_state": "running",
                "executor_status": "queued",
                "execution_packet_path": "/tmp/pick-me.json",
                "last_transition_at": "2026-04-06T10:00:00+00:00",
            },
        ]

        selected = self.runner._select_entry(entries, card_id=None, workspace_key="fusion-os")

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["card_id"], "pick-me")

    def test_build_entry_from_card_recovers_target_when_queue_window_misses_it(self) -> None:
        imports = self.runner._optional_backend_imports("api")
        card = {
            "id": "target-card",
            "title": "Execute the target card",
            "owner": "Jean-Claude",
            "status": "in_progress",
            "source": "openclaw:thin-trigger",
            "link_type": None,
            "link_id": None,
            "payload": {
                "workspace_key": "fusion-os",
                "execution": {
                    "lane": "codex",
                    "state": "running",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "assigned_runner": "codex",
                    "executor_status": "queued",
                    "execution_packet_path": "/tmp/target-card.json",
                    "queued_at": "2026-04-06T10:00:00+00:00",
                    "last_transition_at": "2026-04-06T10:00:00+00:00",
                },
            },
            "created_at": "2026-04-06T10:00:00+00:00",
            "updated_at": "2026-04-06T10:00:00+00:00",
        }

        entry = self.runner._build_entry_from_card(imports, card)

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["card_id"], "target-card")
        self.assertEqual(entry["execution_packet_path"], "/tmp/target-card.json")
        self.assertEqual(entry["executor_status"], "queued")

    def test_parse_work_order_supports_direct_and_workspace_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            packet_path = temp_root / "dispatch" / "packet.json"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text(
                json.dumps(
                    {
                        "schema_version": "codex_execution_work_order/v1",
                        "workspace_key": "shared_ops",
                        "workspace_root": str(temp_root),
                        "repo_path": str(ROOT),
                        "front_door_agent": "Neo",
                        "manager_agent": "Jean-Claude",
                        "owner_agent": "Jean-Claude",
                        "target_agent": "Jean-Claude",
                        "pm_card_id": "card-1",
                        "title": "Direct packet",
                        "objective": "Implement the bounded change.",
                        "reason": "Test the direct execution packet.",
                        "instructions": ["Read the SOP first."],
                        "acceptance_criteria": ["Return a bounded result with at least one concrete outcome."],
                        "artifacts_expected": ["updated PM execution result"],
                        "completion_contract": {"source": "standup_promotion", "autostart": True},
                        "read_order": ["Work packet", "SOP", "PM card"],
                        "sop_path": str(temp_root / "dispatch" / "sop.json"),
                        "briefing_path": str(temp_root / "briefings" / "brief.md"),
                        "write_back_contract": {
                            "pm_card_id": "card-1",
                            "preferred_runner_id": "jean-claude",
                            "preferred_author_agent": "Jean-Claude",
                        },
                    }
                ),
                encoding="utf-8",
            )

            parsed = self.runner._parse_work_order(packet_path)

        self.assertEqual(parsed["workspace_key"], "shared_ops")
        self.assertEqual(parsed["pm_card_id"], "card-1")
        self.assertEqual(parsed["preferred_runner_id"], "jean-claude")
        self.assertEqual(parsed["preferred_author_agent"], "Jean-Claude")
        self.assertEqual(parsed["front_door_agent"], "Neo")
        self.assertEqual(parsed["instructions"], ["Read the SOP first."])
        self.assertEqual(parsed["acceptance_criteria"], ["Return a bounded result with at least one concrete outcome."])
        self.assertEqual(parsed["artifacts_expected"], ["updated PM execution result"])
        self.assertEqual(parsed["completion_contract"], {"source": "standup_promotion", "autostart": True})

    def test_sanitize_result_strips_wrapper_owned_failures(self) -> None:
        packet = {
            "title": "Review Fusion OS delegated lane proof and either close it or return it to execution",
            "workspace_key": "fusion-os",
            "owner_agent": "Jean-Claude",
        }
        result = {
            "status": "review",
            "summary": (
                "Reviewed the March 31 Fusion OS delegated handoff proof, documented the decision, "
                "and logged the outcome so the PM card now has traceable artifacts, but the automatic "
                "write-back to the PM API is still pending because the writer CLI could not reach Railway."
            ),
            "blockers": [
                "write_execution_result.py failed with Failed to reach PM API at https://aiclone-production-32dc.up.railway.app"
            ],
            "follow_ups": [
                "Rerun the writer once network access to Railway is restored.",
                "Schedule and capture the first Fusion OS workspace standup.",
            ],
            "project_updates": [],
            "outcomes": [
                "Created workspaces/fusion-os/docs/delegated_lane_proof_review.md with the review decision."
            ],
            "memory_promotions": [],
            "persistent_state": [],
            "artifact_paths": [],
        }

        sanitized, changed = self.runner._sanitize_result_for_wrapper_success(
            result,
            "https://aiclone-production-32dc.up.railway.app",
            packet,
        )

        self.assertTrue(changed)
        self.assertEqual(
            sanitized["summary"],
            "Reviewed the March 31 Fusion OS delegated handoff proof, documented the decision, and logged the outcome so the PM card now has traceable artifacts.",
        )
        self.assertEqual(sanitized["blockers"], [])
        self.assertEqual(sanitized["follow_ups"], ["Schedule and capture the first Fusion OS workspace standup."])

    def test_schema_requires_host_action_fields(self) -> None:
        schema = self.runner._build_schema()

        self.assertIn("host_actions", schema["properties"])
        self.assertIn("host_action_proof", schema["properties"])
        self.assertIn("host_actions", schema["required"])
        self.assertIn("host_action_proof", schema["required"])

    def test_sanitize_result_strips_wrapper_owned_host_action_noise(self) -> None:
        packet = {
            "title": "Package accepted FEEZIE draft into scheduling lane",
            "workspace_key": "feezie-os",
            "owner_agent": "Jean-Claude",
        }
        result = {
            "status": "review",
            "summary": "Packaged the approved FEEZIE draft into a scheduling lane and documented the host-only next steps.",
            "blockers": [],
            "decisions": [],
            "learnings": [],
            "outcomes": ["Updated the scheduling packet and status memo."],
            "follow_ups": [],
            "host_actions": [
                "Schedule the approved draft in LinkedIn's native scheduler.",
                "Rerun the writer once PM API access is restored.",
            ],
            "host_action_proof": [
                "Confirmation screenshot stored under analytics/2026-04-13_feezie-002/confirmation.png.",
                "Document that write_execution_result.py completed successfully.",
            ],
            "project_updates": [],
            "memory_promotions": [],
            "persistent_state": [],
            "artifact_paths": [],
        }

        sanitized, changed = self.runner._sanitize_result_for_wrapper_success(
            result,
            "https://aiclone-production-32dc.up.railway.app",
            packet,
        )

        self.assertTrue(changed)
        self.assertEqual(
            sanitized["host_actions"],
            ["Schedule the approved draft in LinkedIn's native scheduler."],
        )
        self.assertEqual(
            sanitized["host_action_proof"],
            ["Confirmation screenshot stored under analytics/2026-04-13_feezie-002/confirmation.png."],
        )

    def test_write_result_passes_host_action_flags_to_writer(self) -> None:
        packet = {
            "path": "/tmp/work-order.json",
            "preferred_runner_id": "jean-claude",
            "preferred_author_agent": "Jean-Claude",
        }
        result = {
            "status": "review",
            "summary": "Packaged the approved draft and left only the host scheduling step.",
            "decisions": [],
            "blockers": [],
            "learnings": [],
            "outcomes": ["Updated the release packet and scheduling memo."],
            "follow_ups": [],
            "host_actions": ["Schedule the approved draft in LinkedIn's native scheduler."],
            "host_action_proof": ["Capture a confirmation screenshot and store it under analytics."],
            "project_updates": [],
            "memory_promotions": [],
            "persistent_state": [],
            "artifact_paths": ["/tmp/release-packet.md"],
        }

        completed = mock.Mock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""

        with mock.patch.object(self.runner.subprocess, "run", return_value=completed) as mocked_run:
            self.runner._write_result(packet, result, api_url="https://example.com", dry_run=False)

        command = mocked_run.call_args.args[0]
        self.assertIn("--host-action", command)
        self.assertIn("Schedule the approved draft in LinkedIn's native scheduler.", command)
        self.assertIn("--host-action-proof", command)
        self.assertIn("Capture a confirmation screenshot and store it under analytics.", command)


if __name__ == "__main__":
    unittest.main()
