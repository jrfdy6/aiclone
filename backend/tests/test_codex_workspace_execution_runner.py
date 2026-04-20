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

    def test_select_runnable_host_action_automation_card_picks_oldest_queued_card_first(self) -> None:
        cards = [
            {
                "id": "ready-autostart-card",
                "status": "todo",
                "updated_at": "2026-04-20T07:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "ready",
                        "autostart": True,
                        "requires_host_confirmation": False,
                    }
                },
            },
            {
                "id": "newer-queued-card",
                "status": "in_progress",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "queued",
                        "queued_at": "2026-04-20T10:00:00Z",
                    }
                },
            },
            {
                "id": "oldest-queued-card",
                "status": "in_progress",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "queued",
                        "queued_at": "2026-04-20T08:00:00Z",
                    }
                },
            },
            {
                "id": "closed-card",
                "status": "done",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "queued",
                        "queued_at": "2026-04-20T07:00:00Z",
                    }
                },
            },
        ]

        selected = self.runner._select_runnable_host_action_automation_card(cards)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "oldest-queued-card")

    def test_select_runnable_host_action_automation_card_autostarts_ready_card(self) -> None:
        cards = [
            {
                "id": "manual-ready-card",
                "status": "todo",
                "updated_at": "2026-04-20T07:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "ready",
                        "autostart": False,
                    }
                },
            },
            {
                "id": "confirmation-required-card",
                "status": "todo",
                "updated_at": "2026-04-20T08:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "ready",
                        "autostart": True,
                        "requires_host_confirmation": True,
                    }
                },
            },
            {
                "id": "autostart-card",
                "status": "todo",
                "updated_at": "2026-04-20T09:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "state": "ready",
                        "autostart": True,
                        "requires_host_confirmation": False,
                    }
                },
            },
        ]

        selected = self.runner._select_runnable_host_action_automation_card(cards)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "autostart-card")

    def test_select_runnable_host_action_automation_card_requires_linkedin_queue(self) -> None:
        cards = [
            {
                "id": "linkedin-ready-card",
                "status": "todo",
                "updated_at": "2026-04-20T07:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "linkedin_scheduled_writeback",
                        "state": "ready",
                    }
                },
            },
            {
                "id": "linkedin-queued-card",
                "status": "in_progress",
                "updated_at": "2026-04-20T08:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "linkedin_scheduled_writeback",
                        "state": "queued",
                        "queued_at": "2026-04-20T08:00:00Z",
                    }
                },
            },
        ]

        selected = self.runner._select_runnable_host_action_automation_card(cards)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "linkedin-queued-card")

    def test_source_work_order_path_uses_latest_result_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            work_order = temp_root / "dispatch" / "20260420T102400Z_jean_claude_work_order.json"
            work_order.parent.mkdir(parents=True, exist_ok=True)
            work_order.write_text("{}", encoding="utf-8")
            source_card = {
                "id": "source-card",
                "payload": {
                    "latest_execution_result": {
                        "artifacts": [
                            str(temp_root / "runner-result.json"),
                            str(work_order),
                        ]
                    }
                },
            }

            resolved = self.runner._source_work_order_path(source_card)

        self.assertEqual(resolved, work_order)

    def test_latest_result_artifact_prefers_explicit_result_paths(self) -> None:
        source_card = {
            "id": "source-card",
            "payload": {
                "latest_execution_result": {
                    "result_path": "/tmp/new-result.json",
                    "memo_path": "/tmp/new-result_execution_result.md",
                    "artifacts": [
                        "/tmp/source-work-order.json",
                        "/tmp/older-result_execution_result.md",
                    ],
                }
            },
        }

        self.assertEqual(self.runner._latest_result_artifact(source_card, ".json"), "/tmp/new-result.json")
        self.assertEqual(
            self.runner._latest_result_artifact(source_card, "_execution_result.md"),
            "/tmp/new-result_execution_result.md",
        )

    def test_fallback_watchdog_automation_records_blocked_then_retries_to_done(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            memory_root = temp_root / "memory"
            report_path = memory_root / "reports" / "fallback_watchdog_latest.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-20T21:27:47Z",
                        "status": "action_required",
                        "active_count": 1,
                        "memory_alert_count": 1,
                        "durable_retrieval_alert_count": 0,
                        "delivery_alert_count": 0,
                        "runtime_alert_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            work_order = temp_root / "dispatch" / "20260420T072334Z_jean_claude_work_order.json"
            work_order.parent.mkdir(parents=True)
            work_order.write_text("{}", encoding="utf-8")
            writer_statuses: list[str] = []
            watchdog_runs = 0

            def fake_run(command, **_kwargs):
                nonlocal watchdog_runs
                script_name = Path(command[1]).name
                if script_name == "fallback_watchdog.py":
                    watchdog_runs += 1
                    if watchdog_runs == 2:
                        report_path.write_text(
                            json.dumps(
                                {
                                    "generated_at": "2026-04-20T21:30:29Z",
                                    "status": "ok",
                                    "active_count": 0,
                                    "memory_alert_count": 0,
                                    "durable_retrieval_alert_count": 0,
                                    "delivery_alert_count": 0,
                                    "runtime_alert_count": 0,
                                }
                            ),
                            encoding="utf-8",
                        )
                    return self.runner.subprocess.CompletedProcess(command, 0, stdout=f"watchdog {watchdog_runs}", stderr="")
                if script_name == "write_execution_result.py":
                    writer_statuses.append(command[command.index("--status") + 1])
                    return self.runner.subprocess.CompletedProcess(command, 0, stdout="writer ok", stderr="")
                raise AssertionError(f"Unexpected command: {command}")

            def fake_load_card(_imports, _api_url, _card_id):
                return {
                    "id": "source-card",
                    "payload": {
                        "latest_execution_result": {
                            "result_path": "/tmp/final-result.json",
                            "memo_path": "/tmp/final-result_execution_result.md",
                            "artifacts": [str(work_order)],
                        }
                    },
                }

            card = {
                "id": "host-card",
                "payload": {
                    "workspace_key": "shared_ops",
                    "host_action_required": {"source_card_id": "source-card"},
                    "host_action_automation": {
                        "automation_id": "fallback_watchdog_writeback",
                        "source_card_id": "source-card",
                    },
                },
            }

            with mock.patch.object(self.runner, "WORKSPACE_ROOT", temp_root):
                with mock.patch.object(self.runner, "MEMORY_ROOT", memory_root):
                    with mock.patch.object(self.runner, "SCRIPTS_ROOT", temp_root / "scripts"):
                        with mock.patch.object(self.runner, "_run_command", side_effect=fake_run):
                            with mock.patch.object(self.runner, "_load_card", side_effect=fake_load_card):
                                with mock.patch.object(self.runner, "_patch_host_action_automation", side_effect=lambda *_args, **_kwargs: card):
                                    with mock.patch.object(
                                        self.runner,
                                        "_fetch_json",
                                        return_value={"card": {"id": "host-card", "status": "done", "payload": {}}},
                                    ):
                                        result = self.runner._run_fallback_watchdog_writeback_automation(
                                            {},
                                            "https://api.example.test",
                                            card,
                                            worker_id="worker-1",
                                            dry_run=False,
                                        )

        self.assertEqual(writer_statuses, ["blocked", "done"])
        self.assertEqual(watchdog_runs, 2)
        self.assertEqual(result["status"], "ok")

    def test_linkedin_scheduled_writeback_records_receipt_docs_and_closes_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            linkedin_root = temp_root / "workspaces" / "linkedin-content-os"
            schedule_path = linkedin_root / "docs" / "publishing_schedule_2026-04-11.md"
            queue_path = linkedin_root / "drafts" / "queue_01.md"
            analytics_log = linkedin_root / "analytics" / "2026-04-27_feezie-008" / "log_template.md"
            release_packet = linkedin_root / "docs" / "release_packets" / "feezie-008_schedule_packet_20260419.md"
            schedule_path.parent.mkdir(parents=True)
            queue_path.parent.mkdir(parents=True)
            analytics_log.parent.mkdir(parents=True)
            release_packet.parent.mkdir(parents=True)
            schedule_path.write_text(
                "\n".join(
                    [
                        "### Slot 8 - FEEZIE-008 - Saying the plan breaks in execution",
                        "#### Slot 8 run log (fill when scheduled)",
                        "- Scheduled timestamp: __________________ (ET)",
                        "- Asset decision: __________________ (text-only / approved leadership or planning media path)",
                        "- LinkedIn confirmation saved to: `workspaces/linkedin-content-os/analytics/2026-04-27_feezie-008/confirmation.png`",
                        "- Analytics note path: `workspaces/linkedin-content-os/analytics/2026-04-27_feezie-008/log_template.md`",
                        "- Notes / drift: ______________________________________",
                        "### Slot 9 - Next",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            queue_path.write_text(
                "\n".join(
                    [
                        "### FEEZIE-008 - Saying the plan breaks in execution",
                        "- Release packet: `docs/release_packets/feezie-008_schedule_packet_20260419.md`",
                        "- Scheduling status: Packaged for scheduling; host should queue the LinkedIn post.",
                        "- Prep checklist:",
                        "  - Default to text-only.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            analytics_log.write_text(
                "\n".join(
                    [
                        "# FEEZIE-008 Analytics Log - Template (Slot 8)",
                        "",
                        "## Publish details",
                        "- Scheduled timestamp: __________________ (ET)",
                        "- Actual go-live timestamp: __________________ (ET)",
                        "- Asset decision: __________________ (text-only / approved leadership or planning media path)",
                        "- Metric/proof decision: __________________ (copy unchanged / verified metric added / media added)",
                        "- LinkedIn URL: ______________________________________________",
                        "- Confirmation artifact: `workspaces/linkedin-content-os/analytics/2026-04-27_feezie-008/confirmation.png`",
                        "",
                        "## Hand-off checklist",
                        "- [ ] Update `docs/publishing_schedule_2026-04-11.md` with the real timestamp + asset note.",
                        "- [ ] Update `drafts/queue_01.md#feezie-008` with the same information.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            release_packet.write_text(
                "\n".join(
                    [
                        "# FEEZIE-008 Scheduling Packet - Slot 8 (Mon 27 Apr 2026 - 09:35 ET)",
                        "",
                        "## Run-log placeholder (fill after scheduling)",
                        "| Field | Value |",
                        "| --- | --- |",
                        "| Scheduled timestamp | _e.g., 2026-04-27 09:35 ET_ |",
                        "| Asset decision | _Text only / approved leadership or planning media path_ |",
                        "| LinkedIn confirmation file | _analytics/2026-04-27_feezie-008/confirmation.png_ |",
                        "| Analytics note | _analytics/2026-04-27_feezie-008/log_template.md_ |",
                        "| Notes | _Any slot drift, metric decision, or media decision_ |",
                        "",
                        "## Checklist",
                        "- [ ] Asset decision recorded (text-only or approved leadership/planning media path).",
                        "- [ ] Publishing schedule + queue entry updated with exact timestamp and asset note after scheduling.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            card = {
                "id": "host-card",
                "title": "Host action required - Schedule FEEZIE-008",
                "payload": {
                    "workspace_key": "linkedin-os",
                    "host_action_required": {
                        "summary": "Queue FEEZIE-008 in LinkedIn's native scheduler for Monday, April 27, 2026 at 09:35 ET.",
                        "steps": ["After scheduling, update the publishing schedule and queue entry."],
                        "source_card_id": "source-card",
                    },
                    "host_action_automation": {
                        "automation_id": "linkedin_scheduled_writeback",
                        "queue_id": "FEEZIE-008",
                        "source_card_id": "source-card",
                        "asset_decision": "text-only",
                    },
                },
            }

            with mock.patch.object(self.runner, "WORKSPACE_ROOT", temp_root):
                with mock.patch.object(self.runner, "_patch_host_action_automation", side_effect=lambda *_args, **_kwargs: card):
                    with mock.patch.object(
                        self.runner,
                        "_fetch_json",
                        return_value={"card": {"id": "host-card", "status": "done", "payload": card["payload"]}},
                    ) as fetch_mock:
                        result = self.runner._run_linkedin_scheduled_writeback_automation(
                            {},
                            "https://api.example.test",
                            card,
                            worker_id="worker-1",
                            dry_run=False,
                        )

            receipt_path = temp_root / "workspaces" / "linkedin-content-os" / "analytics" / "2026-04-27_feezie-008" / "scheduled_receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(receipt["queue_id"], "FEEZIE-008")
            self.assertEqual(receipt["scheduled_at_et"], "2026-04-27 09:35 ET")
            self.assertFalse(receipt["screenshot_present"])
            self.assertIn("2026-04-27 09:35 ET", schedule_path.read_text(encoding="utf-8"))
            self.assertIn("Scheduled in LinkedIn for 2026-04-27 09:35 ET", queue_path.read_text(encoding="utf-8"))
            self.assertIn("- [x] Update `docs/publishing_schedule_2026-04-11.md`", analytics_log.read_text(encoding="utf-8"))
            self.assertIn("| Scheduled timestamp | 2026-04-27 09:35 ET |", release_packet.read_text(encoding="utf-8"))
            self.assertTrue(fetch_mock.called)

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

    def test_resolve_codex_cli_model_falls_back_from_unsupported_labels(self) -> None:
        self.assertEqual(self.runner._resolve_codex_cli_model("gpt-5.1-codex"), "gpt-5.4")
        self.assertEqual(self.runner._resolve_codex_cli_model("openai/gpt-5.3-codex"), "gpt-5.4")
        self.assertEqual(self.runner._resolve_codex_cli_model("openai/gpt-5.4"), "gpt-5.4")

    def test_run_codex_uses_resolved_model_in_command(self) -> None:
        packet = {
            "repo_path": str(ROOT),
            "path": "/tmp/work-order.json",
            "pm_card_id": "pm-card-1",
            "title": "Resolve model fallback",
            "workspace_key": "shared_ops",
            "owner_agent": "Jean-Claude",
            "front_door_agent": "Jean-Claude",
            "manager_agent": "Jean-Claude",
            "target_agent": "Jean-Claude",
            "objective": "Return structured output.",
            "reason": "Exercise the Codex command builder.",
            "sop_path": "",
            "briefing_path": "",
            "read_order": [],
            "instructions": [],
            "acceptance_criteria": [],
            "artifacts_expected": [],
        }

        def fake_run(command, **kwargs):
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "status": "review",
                        "summary": "Returned structured output.",
                        "decisions": [],
                        "blockers": [],
                        "learnings": [],
                        "outcomes": ["Model fallback resolved."],
                        "follow_ups": [],
                        "host_actions": [],
                        "host_action_proof": [],
                        "project_updates": [],
                        "memory_promotions": [],
                        "persistent_state": [],
                        "artifact_paths": [],
                    }
                ),
                encoding="utf-8",
            )
            return self.runner.subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with mock.patch.object(self.runner.subprocess, "run", side_effect=fake_run) as mocked_run:
            self.runner._run_codex(packet, model="gpt-5.1-codex", reasoning_effort="high", timeout_seconds=30)

        command = mocked_run.call_args.args[0]
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.4")

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
