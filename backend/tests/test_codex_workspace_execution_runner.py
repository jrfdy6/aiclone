from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(os.getenv("AI_CLONE_ROOT") or Path(__file__).resolve().parents[2])
SCRIPTS_ROOT = ROOT / "scripts"
RUNNER_PATH = Path(
    os.getenv("AI_CLONE_CODEX_RUNNER_UNDER_TEST")
    or SCRIPTS_ROOT / "runners" / "run_codex_workspace_execution.py"
)
RUNNABLE_GATE_FIELDS = {
    "execution_gate_decision": "AUTO_EXECUTE",
    "execution_gate_approval_state": "not_required",
    "execution_gate_intent_hash": "sha256:" + ("0" * 64),
    "execution_gate_authorization_current": True,
}


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
        cls.runner = _load_module("run_codex_workspace_execution", RUNNER_PATH)

    def test_load_card_uses_raw_execution_source_endpoint(self) -> None:
        expected = {"id": "card-raw-1", "payload": {"execution": {"state": "running"}}}
        with mock.patch.object(self.runner, "_fetch_json", return_value=expected) as fetch:
            card = self.runner._load_card({"mode": "api"}, "https://control.example", "card-raw-1")

        self.assertEqual(card, expected)
        fetch.assert_called_once_with(
            "https://control.example/api/pm/cards/card-raw-1/execution-source"
        )

    def test_fetch_json_rejects_untrusted_host_before_loading_authorization(self) -> None:
        with mock.patch.object(self.runner, "control_plane_headers") as headers:
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                self.runner._fetch_json("https://evil.example/api/pm/execution-queue")

        headers.assert_not_called()

    def test_fetch_json_rejects_redirect_without_forwarding_authorization(self) -> None:
        opened_requests = []
        installed_handlers = []
        runtime_globals = self.runner.open_control_plane_request.__globals__
        runner_module = self.runner

        class RedirectingOpener:
            def open(self, request, *, timeout):
                opened_requests.append(request)
                raise runner_module.urllib.error.HTTPError(
                    request.full_url,
                    302,
                    "Found",
                    {"Location": "https://evil.example/collect"},
                    None,
                )

        def build_opener(*handlers):
            installed_handlers.extend(handlers)
            return RedirectingOpener()

        with (
            mock.patch.object(
                self.runner,
                "control_plane_headers",
                side_effect=lambda value: {**value, "Authorization": "Bearer must-not-leave-production-host"},
            ),
            mock.patch.object(runtime_globals["urllib"].request, "build_opener", side_effect=build_opener),
        ):
            with self.assertRaisesRegex(self.runner.urllib.error.HTTPError, "HTTP Error 302"):
                self.runner._fetch_json(
                    "https://aiclone-production-32dc.up.railway.app/api/pm/execution-queue"
                )

        self.assertEqual(len(opened_requests), 1)
        self.assertTrue(opened_requests[0].full_url.startswith("https://aiclone-production-32dc.up.railway.app"))
        self.assertEqual(opened_requests[0].get_header("Authorization"), "Bearer must-not-leave-production-host")
        self.assertEqual(len(installed_handlers), 1)
        handler = installed_handlers[0]
        self.assertIsInstance(handler, runtime_globals["_NoRedirectHandler"])
        self.assertIsNone(
            handler.redirect_request(
                opened_requests[0],
                None,
                302,
                "Found",
                {"Location": "https://evil.example/collect"},
                "https://evil.example/collect",
            )
        )

    def test_select_entry_requires_packet_and_queued_executor(self) -> None:
        entries = [
            {
                **RUNNABLE_GATE_FIELDS,
                "card_id": "skip-no-packet",
                "workspace_key": "fusion-os",
                "execution_state": "running",
                "executor_status": "queued",
                "last_transition_at": "2026-04-06T12:00:00+00:00",
            },
            {
                **RUNNABLE_GATE_FIELDS,
                "card_id": "skip-already-running",
                "workspace_key": "fusion-os",
                "execution_state": "running",
                "executor_status": "running",
                "execution_packet_path": "/tmp/running.json",
                "last_transition_at": "2026-04-06T11:00:00+00:00",
            },
            {
                **RUNNABLE_GATE_FIELDS,
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

    def test_build_entry_from_card_recovers_direct_queued_card_without_packet(self) -> None:
        imports = self.runner._optional_backend_imports("api")
        card = {
            "id": "direct-queued-card",
            "title": "Execute the direct queued card",
            "owner": "Jean-Claude",
            "status": "todo",
            "source": "post-sync-dispatch:test",
            "link_type": "standup",
            "link_id": "standup-1",
            "payload": {
                "workspace_key": "shared_ops",
                "reason": "Advance the direct queued lane.",
                "instructions": ["Advance only the bounded internal direct lane."],
                "acceptance_criteria": ["Return one concrete internal outcome."],
                "artifacts_expected": ["bounded internal result"],
                "completion_contract": {
                    "source": "post_sync_dispatch",
                    "autostart": True,
                    "done_when": ["The bounded internal result is written back."],
                },
                "execution": {
                    "lane": "codex",
                    "state": "queued",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Jean-Claude",
                    "execution_mode": "direct",
                    "assigned_runner": "codex",
                    "queued_at": "2026-04-06T10:00:00+00:00",
                    "last_transition_at": "2026-04-06T10:00:00+00:00",
                },
            },
            "created_at": "2026-04-06T10:00:00+00:00",
            "updated_at": "2026-04-06T10:00:00+00:00",
        }

        with mock.patch.dict(
            os.environ,
            {"CONTROL_PLANE_JOB_SIGNING_SECRET": "runner-test-secret"},
        ):
            from app.security.execution_authorization import sign_execution_payload
            from app.services.execution_gate_service import apply_execution_gate

            card["payload"] = apply_execution_gate(
                card_id=card["id"],
                title=card["title"],
                source=card["source"],
                workspace_key="shared_ops",
                payload=card["payload"],
            )
            card["payload"] = sign_execution_payload(card["id"], card["payload"])
            entry = self.runner._build_entry_from_card(imports, card)

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["card_id"], "direct-queued-card")
        self.assertEqual(entry["execution_mode"], "direct")
        self.assertEqual(entry["target_agent"], "Jean-Claude")
        self.assertEqual(entry["execution_state"], "queued")
        self.assertIsNone(entry.get("execution_packet_path"))

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

    def test_select_runnable_host_action_automation_card_autostarts_standup_prep_card(self) -> None:
        cards = [
            {
                "id": "standup-prep-card",
                "status": "todo",
                "updated_at": "2026-04-20T09:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "standup_prep_writeback",
                        "state": "ready",
                        "autostart": True,
                        "requires_host_confirmation": False,
                    }
                },
            }
        ]

        selected = self.runner._select_runnable_host_action_automation_card(cards)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "standup-prep-card")

    def test_select_runnable_host_action_automation_card_autostarts_writer_proof_card(self) -> None:
        cards = [
            {
                "id": "writer-proof-card",
                "status": "todo",
                "updated_at": "2026-04-20T09:00:00Z",
                "payload": {
                    "host_action_automation": {
                        "automation_id": "execution_result_writeback_proof",
                        "state": "ready",
                        "autostart": True,
                        "requires_host_confirmation": False,
                    }
                },
            }
        ]

        selected = self.runner._select_runnable_host_action_automation_card(cards)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "writer-proof-card")

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

    def test_select_runnable_host_action_automation_card_autostarts_linkedin_ready_card_when_confirmation_exists(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            confirmation_path = (
                temp_root
                / "workspaces"
                / "linkedin-content-os"
                / "analytics"
                / "2026-04-27_feezie-008"
                / "confirmation.png"
            )
            confirmation_path.parent.mkdir(parents=True, exist_ok=True)
            confirmation_path.write_text("proof", encoding="utf-8")
            cards = [
                {
                    "id": "linkedin-ready-card",
                    "title": "Host action required - Schedule FEEZIE-008",
                    "status": "todo",
                    "updated_at": "2026-04-20T07:00:00Z",
                    "payload": {
                        "host_action_required": {
                            "summary": "Queue FEEZIE-008 in LinkedIn's native scheduler for Monday, April 27, 2026 at 09:35 ET.",
                            "steps": ["Queue FEEZIE-008 in LinkedIn's native scheduler."],
                        },
                        "host_action_automation": {
                            "automation_id": "linkedin_scheduled_writeback",
                            "state": "ready",
                            "queue_id": "FEEZIE-008",
                        },
                    },
                }
            ]

            with mock.patch.object(self.runner, "WORKSPACE_ROOT", temp_root):
                selected = self.runner._select_runnable_host_action_automation_card(cards)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["id"], "linkedin-ready-card")

    def test_select_entry_accepts_direct_queued_card_without_packet_as_fallback(self) -> None:
        entries = [
            {
                **RUNNABLE_GATE_FIELDS,
                "card_id": "skip-delegated-no-packet",
                "workspace_key": "fusion-os",
                "execution_mode": "delegated",
                "target_agent": "Fusion Systems Operator",
                "execution_state": "queued",
                "last_transition_at": "2026-04-06T11:00:00+00:00",
            },
            {
                **RUNNABLE_GATE_FIELDS,
                "card_id": "direct-bootstrap",
                "workspace_key": "shared_ops",
                "execution_mode": "direct",
                "target_agent": "Jean-Claude",
                "execution_state": "queued",
                "executor_status": "queued",
                "last_transition_at": "2026-04-06T10:00:00+00:00",
            },
        ]

        selected = self.runner._select_entry(entries, card_id=None, workspace_key="shared_ops")

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["card_id"], "direct-bootstrap")

    def test_select_entry_rejects_missing_stale_or_malformed_execution_gates(self) -> None:
        base = {
            "card_id": "candidate",
            "workspace_key": "shared_ops",
            "execution_mode": "direct",
            "target_agent": "Jean-Claude",
            "execution_state": "queued",
            "executor_status": "queued",
        }
        invalid_entries = [
            {**base, **RUNNABLE_GATE_FIELDS, "execution_gate_authorization_current": False},
            {**base, **RUNNABLE_GATE_FIELDS, "execution_gate_intent_hash": ""},
            {**base, **RUNNABLE_GATE_FIELDS, "execution_gate_intent_hash": "sha256:not-a-hash"},
            {**base, **RUNNABLE_GATE_FIELDS, "execution_gate_approval_state": "stale"},
            {
                **base,
                **RUNNABLE_GATE_FIELDS,
                "execution_gate_decision": "REQUIRE_APPROVAL",
                "execution_gate_approval_state": "missing",
            },
        ]

        for entry in invalid_entries:
            with self.subTest(entry=entry):
                self.assertIsNone(
                    self.runner._select_entry([entry], card_id=None, workspace_key="shared_ops")
                )

        self.assertEqual(
            self.runner._select_entry(
                [{**base, **RUNNABLE_GATE_FIELDS}],
                card_id=None,
                workspace_key="shared_ops",
            )["card_id"],
            "candidate",
        )

    def test_claim_execution_promotes_todo_card_to_in_progress_and_running(self) -> None:
        card = {
            "id": "queued-direct-card",
            "status": "todo",
            "payload": {
                "execution": {
                    "state": "queued",
                    "executor_status": "queued",
                    "execution_mode": "direct",
                    "target_agent": "Jean-Claude",
                    "history": [],
                }
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            packet_path = Path(temp_dir) / "packet.json"
            packet_path.write_text("{}", encoding="utf-8")
            claimed_card = {
                **card,
                "status": "in_progress",
                "payload": {
                    "execution": {
                        **card["payload"]["execution"],
                        "state": "running",
                        "executor_status": "running",
                        "executor_worker_id": "worker-1",
                        "claim_id": "4c06b94d-d139-4b32-b89b-d775265d15fd",
                        "execution_packet_path": str(packet_path),
                    }
                },
            }
            with mock.patch.object(
                self.runner,
                "_fetch_json",
                return_value={"card": claimed_card, "disposition": "claimed"},
            ) as fetch:
                result = self.runner._claim_execution(
                    {"mode": "api"},
                    "https://api.example.test",
                    card,
                    worker_id="worker-1",
                    claim_id="4c06b94d-d139-4b32-b89b-d775265d15fd",
                    packet_path=packet_path,
                    workspace_key="shared_ops",
                    execution_mode="direct",
                    target_agent="Jean-Claude",
                    dry_run=False,
                )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "in_progress")
        execution = dict((result["payload"] or {}).get("execution") or {})
        self.assertEqual(execution.get("state"), "running")
        self.assertEqual(execution.get("executor_status"), "running")
        self.assertEqual(execution.get("claim_id"), "4c06b94d-d139-4b32-b89b-d775265d15fd")
        self.assertEqual(execution.get("execution_packet_path"), str(packet_path))
        request_payload = fetch.call_args.kwargs["payload"]
        self.assertEqual(request_payload["workspace_key"], "shared_ops")
        self.assertEqual(request_payload["execution_mode"], "direct")
        self.assertEqual(request_payload["target_agent"], "Jean-Claude")

    def test_claim_execution_service_mode_uses_atomic_service_operation(self) -> None:
        from app.models import PMCard, PMExecutionClaimRequest

        now = self.runner._now()
        card = {
            "id": "01234567-89ab-4def-8123-456789abcdef",
            "title": "Service claim",
            "status": "todo",
            "payload": {"workspace_key": "shared_ops", "execution": {"state": "queued"}},
            "created_at": now,
            "updated_at": now,
        }
        claimed = PMCard.model_validate({**card, "status": "in_progress"})
        claim_service = mock.Mock(return_value=(claimed, "claimed"))
        imports = {
            "mode": "service",
            "PMExecutionClaimRequest": PMExecutionClaimRequest,
            "claim_execution": claim_service,
        }

        result = self.runner._claim_execution(
            imports,
            "https://api.example.test",
            card,
            worker_id="worker-1",
            claim_id="4c06b94d-d139-4b32-b89b-d775265d15fd",
            packet_path=Path("/private/work-order.json"),
            workspace_key="shared_ops",
            execution_mode="direct",
            target_agent="Jean-Claude",
            dry_run=False,
        )

        self.assertEqual(result["id"], card["id"])
        request = claim_service.call_args.args[1]
        self.assertEqual(str(request.claim_id), "4c06b94d-d139-4b32-b89b-d775265d15fd")
        self.assertEqual(request.worker_id, "worker-1")

    def test_stable_claim_id_reuses_queue_generation_and_changes_with_worker(self) -> None:
        card = {
            "id": "card-1",
            "payload": {"execution": {"last_transition_at": "2026-07-20T18:00:00Z"}},
        }

        first = self.runner._stable_claim_id(card, worker_id="worker-a")
        retry = self.runner._stable_claim_id(card, worker_id="worker-a")
        competing_worker = self.runner._stable_claim_id(card, worker_id="worker-b")

        self.assertEqual(first, retry)
        self.assertNotEqual(first, competing_worker)

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

    def test_standup_prep_writeback_generates_fresh_prep_and_closes_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            memory_root = temp_root / "memory"
            prep_path = memory_root / "standup-prep" / "executive_ops" / "20260421T112533Z.json"
            prep_path.parent.mkdir(parents=True)
            source_card = {
                "id": "source-card",
                "status": "done",
                "payload": {
                    "latest_execution_result": {
                        "status": "review",
                        "result_path": "/tmp/runner-results/source.json",
                        "memo_path": "/tmp/runner-memos/source_execution_result.md",
                        "artifacts": [
                            "/tmp/runner-results/source.json",
                            "/tmp/runner-memos/source_execution_result.md",
                            "/tmp/workspaces/shared-ops/docs/chronicle_standup_pm_flow_wire_2026-04-21.md",
                        ],
                    }
                },
            }
            close_payloads: list[dict] = []

            def fake_run(command, **_kwargs):
                script_name = Path(command[1]).name
                if script_name != "build_standup_prep.py":
                    raise AssertionError(f"Unexpected command: {command}")
                prep_path.write_text(
                    json.dumps(
                        {
                            "generated_at": "2026-04-21T11:25:33Z",
                            "decision_loop": {
                                "active": True,
                                "routing_targets": [
                                    "canonical_memory",
                                    "standup_interpretation",
                                    "pm_execution",
                                    "workspace_handoff",
                                    "no_action",
                                ],
                            },
                            "standup_payload": {
                                "payload": {
                                    "decision_loop": {
                                        "active": True,
                                        "routing_targets": [
                                            "canonical_memory",
                                            "standup_interpretation",
                                            "pm_execution",
                                            "workspace_handoff",
                                            "no_action",
                                        ],
                                    }
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return self.runner.subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=f"summary\nJSON: {prep_path}\nMarkdown: {prep_path.with_suffix('.md')}\n",
                    stderr="",
                )

            def fake_fetch(_url, *, method="GET", payload=None):
                if method == "POST":
                    close_payloads.append(payload or {})
                    return {"card": {"id": "host-card", "status": "done", "payload": {}}}
                raise AssertionError("Only the close action should use _fetch_json in this test.")

            card = {
                "id": "host-card",
                "title": "Host action required - Run standup prep proof",
                "payload": {
                    "workspace_key": "shared_ops",
                    "host_action_required": {"source_card_id": "source-card"},
                    "host_action_automation": {
                        "automation_id": "standup_prep_writeback",
                        "source_card_id": "source-card",
                        "standup_workspace_key": "shared_ops",
                        "standup_kind": "executive_ops",
                    },
                },
            }

            with mock.patch.object(self.runner, "WORKSPACE_ROOT", temp_root):
                with mock.patch.object(self.runner, "MEMORY_ROOT", memory_root):
                    with mock.patch.object(self.runner, "SCRIPTS_ROOT", temp_root / "scripts"):
                        with mock.patch.object(self.runner, "_run_command", side_effect=fake_run):
                            with mock.patch.object(self.runner, "_load_card", return_value=source_card):
                                with mock.patch.object(self.runner, "_fetch_json", side_effect=fake_fetch):
                                    with mock.patch.object(self.runner, "_patch_host_action_automation", side_effect=lambda *_args, **_kwargs: card):
                                        result = self.runner._run_standup_prep_writeback_automation(
                                            {},
                                            "https://api.example.test",
                                            card,
                                            worker_id="worker-1",
                                            dry_run=False,
                                        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metadata"]["prep_json_path"], str(prep_path))
        self.assertEqual(close_payloads[0]["action"], "approve")
        self.assertEqual(close_payloads[0]["resolution_mode"], "close_only")
        proof = "\n".join(close_payloads[0]["proof_items"])
        self.assertIn("decision_loop.active=true", proof)
        self.assertIn("canonical_memory, standup_interpretation, pm_execution, workspace_handoff, no_action", proof)

    def test_execution_result_writeback_proof_closes_card_when_writer_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            memo_path = temp_root / "memory" / "runner-memos" / "jean-claude" / "20260421T044428Z_execution_result.md"
            result_path = temp_root / "memory" / "runner-results" / "jean-claude" / "20260421T044428Z.json"
            artifact_path = temp_root / "workspaces" / "shared-ops" / "docs" / "codex_chronicle_durable_memory_promotion_2026-04-21.md"
            memo_path.parent.mkdir(parents=True)
            result_path.parent.mkdir(parents=True)
            artifact_path.parent.mkdir(parents=True)
            memo_path.write_text(f"Memo cites {artifact_path}\n", encoding="utf-8")
            result_path.write_text("{}", encoding="utf-8")
            artifact_path.write_text("# Durable promotion\n", encoding="utf-8")
            source_card = {
                "id": "source-card",
                "status": "done",
                "payload": {
                    "latest_execution_result": {
                        "status": "review",
                        "result_path": str(result_path),
                        "memo_path": str(memo_path),
                        "artifacts": [
                            str(result_path),
                            str(memo_path),
                            str(artifact_path),
                        ],
                        "learnings": [
                            "When Chronicle emits a standup-shaping signal, shared_ops should package a bounded promotion."
                        ],
                    }
                },
            }
            close_payloads: list[dict] = []

            def fake_fetch(_url, *, method="GET", payload=None):
                if method == "POST":
                    close_payloads.append(payload or {})
                    return {"card": {"id": "host-card", "status": "done", "payload": {}}}
                raise AssertionError("Only the close action should use _fetch_json in this test.")

            card = {
                "id": "host-card",
                "title": "Host action required - Run execution-result writer",
                "payload": {
                    "workspace_key": "shared_ops",
                    "host_action_required": {
                        "source_card_id": "source-card",
                        "steps": [
                            "Run the normal authorized execution-result writer for PM card source-card.",
                            f"Include {artifact_path} in the writer artifacts.",
                        ],
                        "proof_required": [
                            f"Execution-result memo or runner result cites {artifact_path}."
                        ],
                    },
                    "host_action_automation": {
                        "automation_id": "execution_result_writeback_proof",
                        "source_card_id": "source-card",
                    },
                },
            }

            with mock.patch.object(self.runner, "WORKSPACE_ROOT", temp_root):
                with mock.patch.object(self.runner, "_load_card", return_value=source_card):
                    with mock.patch.object(self.runner, "_fetch_json", side_effect=fake_fetch):
                        with mock.patch.object(self.runner, "_patch_host_action_automation", side_effect=lambda *_args, **_kwargs: card):
                            result = self.runner._run_execution_result_writeback_proof_automation(
                                {},
                                "https://api.example.test",
                                card,
                                worker_id="worker-1",
                                dry_run=False,
                            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(close_payloads[0]["action"], "approve")
        self.assertEqual(close_payloads[0]["resolution_mode"], "close_only")
        proof = "\n".join(close_payloads[0]["proof_items"])
        self.assertIn("Execution-result proof:", proof)
        self.assertIn("Required artifact proof:", proof)
        self.assertIn("Learning proof:", proof)

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

    def test_linkedin_scheduled_writeback_records_artifact_detected_confirmation_method(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            linkedin_root = temp_root / "workspaces" / "linkedin-content-os"
            schedule_path = linkedin_root / "docs" / "publishing_schedule_2026-04-11.md"
            queue_path = linkedin_root / "drafts" / "queue_01.md"
            analytics_dir = linkedin_root / "analytics" / "2026-04-27_feezie-008"
            analytics_log = analytics_dir / "log_template.md"
            confirmation_path = analytics_dir / "confirmation.png"
            release_packet = linkedin_root / "docs" / "release_packets" / "feezie-008_schedule_packet_20260419.md"
            schedule_path.parent.mkdir(parents=True)
            queue_path.parent.mkdir(parents=True)
            analytics_log.parent.mkdir(parents=True)
            release_packet.parent.mkdir(parents=True)
            confirmation_path.write_text("proof", encoding="utf-8")
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
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            analytics_log.write_text(
                "\n".join(
                    [
                        "# FEEZIE-008 Analytics Log - Template (Slot 8)",
                        "- Scheduled timestamp: __________________ (ET)",
                        "- LinkedIn confirmation saved to: `workspaces/linkedin-content-os/analytics/2026-04-27_feezie-008/confirmation.png`",
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
                        "| Field | Value |",
                        "| --- | --- |",
                        "| Scheduled timestamp | _e.g., 2026-04-27 09:35 ET_ |",
                        "| Asset decision | _Text only / approved leadership or planning media path_ |",
                        "| LinkedIn confirmation file | _analytics/2026-04-27_feezie-008/confirmation.png_ |",
                        "| Analytics note | _analytics/2026-04-27_feezie-008/log_template.md_ |",
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
                        "state": "ready",
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
                    ):
                        self.runner._run_linkedin_scheduled_writeback_automation(
                            {},
                            "https://api.example.test",
                            card,
                            worker_id="worker-1",
                            dry_run=False,
                        )

            receipt_path = analytics_dir / "scheduled_receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["confirmation_method"], "host_artifact_detected")
            self.assertTrue(receipt["screenshot_present"])
            self.assertIn("confirmation artifact", receipt["note"].lower())

    def test_parse_work_order_supports_direct_and_workspace_packets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-clone-runner-test-") as project_dir:
            project_root = Path(project_dir)
            temp_root = project_root / "workspaces" / "shared-ops-test"
            packet_path = temp_root / "dispatch" / "packet.json"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text(
                json.dumps(
                    {
                        "schema_version": "codex_execution_work_order/v1",
                        "workspace_key": "shared_ops",
                        "workspace_root": str(temp_root),
                        "repo_path": str(project_root),
                        "front_door_agent": "Neo",
                        "manager_agent": "Jean-Claude",
                        "owner_agent": "Jean-Claude",
                        "target_agent": "Jean-Claude",
                        "pm_card_id": "card-1",
                        "execution_gate_intent_hash": RUNNABLE_GATE_FIELDS["execution_gate_intent_hash"],
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
                        "local_artifact_context": {
                            "manager_briefing_path": str(temp_root / "briefings" / "manager.md"),
                            "latest_workspace_briefing_path": str(temp_root / "briefings" / "workspace.md"),
                            "execution_log_path": str(temp_root / "memory" / "execution_log.md"),
                        },
                        "context_policy": {
                            "manager_scope": "Manager can use whole-system context before direct execution.",
                            "workspace_scope": "Stay inside shared_ops.",
                            "relevance_rule": "Explain why broader context matters here now.",
                        },
                        "write_back_contract": {
                            "pm_card_id": "card-1",
                            "preferred_runner_id": "jean-claude",
                            "preferred_author_agent": "Jean-Claude",
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(self.runner, "WORKSPACE_ROOT", project_root):
                parsed = self.runner._parse_work_order(packet_path)

        self.assertEqual(parsed["workspace_key"], "shared_ops")
        self.assertEqual(parsed["pm_card_id"], "card-1")
        self.assertEqual(
            parsed["execution_gate_intent_hash"],
            RUNNABLE_GATE_FIELDS["execution_gate_intent_hash"],
        )
        self.assertEqual(parsed["preferred_runner_id"], "jean-claude")
        self.assertEqual(parsed["preferred_author_agent"], "Jean-Claude")
        self.assertEqual(parsed["front_door_agent"], "Neo")
        self.assertEqual(parsed["instructions"], ["Read the SOP first."])
        self.assertEqual(parsed["acceptance_criteria"], ["Return a bounded result with at least one concrete outcome."])
        self.assertEqual(parsed["artifacts_expected"], ["updated PM execution result"])
        self.assertEqual(parsed["completion_contract"], {"source": "standup_promotion", "autostart": True})
        self.assertEqual(parsed["local_artifact_context"]["execution_log_path"], str(temp_root / "memory" / "execution_log.md"))
        self.assertEqual(parsed["context_policy"]["relevance_rule"], "Explain why broader context matters here now.")

    def test_build_prompt_surfaces_local_artifact_context_and_result_contract(self) -> None:
        packet = {
            "owner_agent": "Fusion Systems Operator",
            "front_door_agent": "Neo",
            "manager_agent": "Jean-Claude",
            "target_agent": "Fusion Systems Operator",
            "workspace_key": "fusion-os",
            "repo_path": str(ROOT),
            "path": "/tmp/work-order.json",
            "pm_card_id": "card-1",
            "execution_gate_intent_hash": RUNNABLE_GATE_FIELDS["execution_gate_intent_hash"],
            "title": "Advance the next Fusion artifact",
            "objective": "Execute a bounded Fusion lane.",
            "reason": "Standup resolved the next move.",
            "sop_path": "/tmp/fusion_sop.json",
            "briefing_path": "/tmp/manager_briefing.md",
            "read_order": ["Packet", "Briefing", "PM card"],
            "instructions": ["Stay inside fusion-os."],
            "acceptance_criteria": ["Return a bounded result."],
            "artifacts_expected": ["Update the next Fusion artifact."],
            "completion_contract": {
                "result_requirements": {
                    "summary_min_length": 24,
                    "require_outcome_or_artifact": True,
                    "require_briefing_citation": True,
                    "require_execution_log_citation": True,
                    "require_lane_constraint": True,
                    "require_relevance_explanation_for_global_context": True,
                    "require_exact_next_artifact_or_blocker": True,
                },
                "done_when": ["Advance the next Fusion artifact without widening scope."],
            },
            "local_artifact_context": {
                "manager_briefing_path": "/tmp/manager_briefing.md",
                "latest_workspace_briefing_path": "/tmp/workspace_briefing.md",
                "execution_log_path": "/tmp/execution_log.md",
            },
            "context_policy": {
                "manager_scope": "Jean-Claude may use whole-system context before delegation.",
                "workspace_scope": "Fusion stays inside fusion-os.",
                "relevance_rule": "Explain why broader context matters to fusion-os now.",
            },
            "recent_chronicle_entries": [],
            "durable_memory_context": {},
            "memory_context": {},
            "source_paths": [],
        }

        prompt = self.runner._build_prompt(packet)

        self.assertIn("Local artifact context:", prompt)
        self.assertIn("/tmp/workspace_briefing.md", prompt)
        self.assertIn("Result contract:", prompt)
        self.assertIn("If no files changed, include the reviewed local artifact paths in `artifact_paths` anyway.", prompt)
        self.assertIn("Context policy:", prompt)

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

    def test_sanitize_result_adds_local_artifact_paths_from_workspace_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manager_briefing = temp_root / "briefings" / "manager.md"
            workspace_briefing = temp_root / "briefings" / "workspace.md"
            execution_log = temp_root / "memory" / "execution_log.md"
            manager_briefing.parent.mkdir(parents=True, exist_ok=True)
            execution_log.parent.mkdir(parents=True, exist_ok=True)
            manager_briefing.write_text("manager", encoding="utf-8")
            workspace_briefing.write_text("workspace", encoding="utf-8")
            execution_log.write_text("log", encoding="utf-8")
            packet = {
                "title": "Advance Fusion next move",
                "workspace_key": "fusion-os",
                "owner_agent": "Fusion Systems Operator",
                "sop_path": "",
                "briefing_path": str(manager_briefing),
                "local_artifact_context": {
                    "manager_briefing_path": str(manager_briefing),
                    "latest_workspace_briefing_path": str(workspace_briefing),
                    "execution_log_path": str(execution_log),
                },
            }
            result = {
                "status": "review",
                "summary": "Reviewed the latest workspace briefing and execution log, then narrowed the next Fusion artifact to ship.",
                "blockers": [],
                "decisions": [],
                "learnings": [],
                "outcomes": [],
                "follow_ups": [],
                "host_actions": [],
                "host_action_proof": [],
                "project_updates": [],
                "memory_promotions": [],
                "persistent_state": [],
                "artifact_paths": [],
            }

            sanitized, changed = self.runner._sanitize_result_for_wrapper_success(
                result,
                "https://example.test",
                packet,
            )

        self.assertTrue(changed)
        self.assertIn(str(manager_briefing), sanitized["artifact_paths"])
        self.assertIn(str(workspace_briefing), sanitized["artifact_paths"])
        self.assertIn(str(execution_log), sanitized["artifact_paths"])

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
            "execution_gate_intent_hash": RUNNABLE_GATE_FIELDS["execution_gate_intent_hash"],
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
            self.runner._write_result(
                packet,
                result,
                api_url="https://example.com",
                claim_id="4c06b94d-d139-4b32-b89b-d775265d15fd",
                worker_id="worker-1",
                dry_run=False,
            )

        command = mocked_run.call_args.args[0]
        self.assertIn("--host-action", command)
        self.assertIn("Schedule the approved draft in LinkedIn's native scheduler.", command)
        self.assertIn("--host-action-proof", command)
        self.assertIn("Capture a confirmation screenshot and store it under analytics.", command)
        self.assertEqual(command[command.index("--claim-id") + 1], "4c06b94d-d139-4b32-b89b-d775265d15fd")
        self.assertEqual(command[command.index("--worker-id") + 1], "worker-1")

    def test_reconcile_pending_results_uses_writer_without_database_credentials(self) -> None:
        completed = mock.Mock(returncode=0, stdout="{}", stderr="")

        with mock.patch.object(self.runner.subprocess, "run", return_value=completed) as mocked_run:
            self.runner._reconcile_pending_results("https://example.com")

        command = mocked_run.call_args.args[0]
        env = mocked_run.call_args.kwargs["env"]
        self.assertIn("--reconcile-outbox", command)
        self.assertEqual(command[command.index("--api-url") + 1], "https://example.com")
        self.assertEqual(env["OPEN_BRAIN_DATABASE_URL"], "")
        self.assertEqual(env["BRAIN_VECTOR_DATABASE_URL"], "")
        self.assertEqual(env["DATABASE_URL"], "")

    def test_recover_stale_claims_calls_server_scoped_worker_endpoint(self) -> None:
        response = {
            "schema_version": "pm_stale_execution_claim_recovery_result/v1",
            "worker_id": "mac-runner",
            "stale_after_seconds": 1800,
            "cutoff_at": "2026-07-20T17:30:00Z",
            "examined_count": 0,
            "requeued_count": 0,
            "surfaced_count": 0,
            "quarantined_count": 0,
            "cas_miss_count": 0,
            "items": [],
        }
        with mock.patch.object(self.runner, "_fetch_json", return_value=response) as fetch:
            result = self.runner._recover_stale_claims(
                {"mode": "api"},
                "https://aiclone-production-32dc.up.railway.app",
                worker_id="mac-runner",
                stale_after_seconds=1800,
            )

        self.assertEqual(result, response)
        fetch.assert_called_once_with(
            "https://aiclone-production-32dc.up.railway.app/api/pm/execution-claims/recover-stale",
            method="POST",
            payload={
                "schema_version": "pm_stale_execution_claim_recovery/v1",
                "worker_id": "mac-runner",
                "stale_after_seconds": 1800,
                "limit": 50,
            },
        )

    def test_main_recovers_stale_claims_before_loading_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = mock.Mock(
                api_url="https://aiclone-production-32dc.up.railway.app",
                dry_run=False,
                output_root=temp_dir,
                mode="api",
                worker_id="mac-runner",
                stale_claim_seconds=1800,
                card_id=None,
                workspace_key=None,
                limit=50,
                model="gpt-5.4",
            )
            events: list[str] = []
            reconciliation = self.runner.subprocess.CompletedProcess(
                ["write_execution_result.py", "--reconcile-outbox"],
                0,
                stdout='{"pending": 0}',
                stderr="",
            )

            def recover(*_args, **_kwargs):
                events.append("recover")
                return {"requeued_count": 0, "surfaced_count": 0}

            def load_queue(*_args, **_kwargs):
                events.append("queue")
                return "api", []

            with (
                mock.patch.object(self.runner, "parse_args", return_value=args),
                mock.patch.object(self.runner, "_reconcile_pending_results", return_value=reconciliation),
                mock.patch.object(self.runner, "_optional_backend_imports", return_value={"mode": "api"}),
                mock.patch.object(self.runner, "_recover_stale_claims", side_effect=recover),
                mock.patch.object(self.runner, "_load_host_action_automation_cards", return_value=[]),
                mock.patch.object(self.runner, "_load_queue", side_effect=load_queue),
            ):
                returncode = self.runner.main()

        self.assertEqual(returncode, 0)
        self.assertEqual(events, ["recover", "queue"])

    def test_main_stops_before_queue_work_when_writeback_reconciliation_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = mock.Mock(
                api_url="https://example.com",
                dry_run=False,
                output_root=temp_dir,
                mode="api",
            )
            pending = self.runner.subprocess.CompletedProcess(
                ["write_execution_result.py", "--reconcile-outbox"],
                self.runner.WRITEBACK_PENDING_EXIT,
                stdout='{"pending": 1}',
                stderr="",
            )
            with (
                mock.patch.object(self.runner, "parse_args", return_value=args),
                mock.patch.object(self.runner, "_reconcile_pending_results", return_value=pending),
                mock.patch.object(self.runner, "_optional_backend_imports") as backend_imports,
            ):
                returncode = self.runner.main()

        self.assertEqual(returncode, self.runner.WRITEBACK_PENDING_EXIT)
        backend_imports.assert_not_called()

    def test_main_stops_before_claim_or_execution_when_outbox_configuration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = mock.Mock(
                api_url="https://evil.example",
                dry_run=False,
                output_root=temp_dir,
                mode="api",
            )
            rejected = self.runner.subprocess.CompletedProcess(
                ["write_execution_result.py", "--reconcile-outbox"],
                1,
                stdout="",
                stderr="Control-plane URL host is not allowlisted.",
            )
            with (
                mock.patch.object(self.runner, "parse_args", return_value=args),
                mock.patch.object(self.runner, "_reconcile_pending_results", return_value=rejected),
                mock.patch.object(self.runner, "_optional_backend_imports") as backend_imports,
                mock.patch.object(self.runner, "_claim_execution") as claim_execution,
                mock.patch.object(self.runner, "_run_codex") as run_codex,
            ):
                returncode = self.runner.main()

        self.assertEqual(returncode, 1)
        backend_imports.assert_not_called()
        claim_execution.assert_not_called()
        run_codex.assert_not_called()


if __name__ == "__main__":
    unittest.main()
