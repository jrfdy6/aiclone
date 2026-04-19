from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.automations import AutomationRun
from app.services import automation_mismatch_service
from app.services import automation_service
from app.services.automation_service import automation_source_of_truth, list_automation_runs, list_automations
from app.services import automation_run_service


class AutomationRegistryTests(unittest.TestCase):
    def test_source_of_truth_reports_static_plus_launchd_when_jobs_missing(self) -> None:
        missing_jobs_path = Path("/tmp/nonexistent-openclaw-jobs.json")
        with patch.object(automation_service, "OPENCLAW_JOBS_PATH", missing_jobs_path):
            self.assertEqual(automation_source_of_truth(), "static_registry+local_launchd_registry")

    def test_includes_local_launchd_execution_and_accountability_jobs(self) -> None:
        automations = list_automations()
        expected_ids = {
            "brain_canonical_memory_sync",
            "codex_chronicle_sync",
            "operator_story_signals",
            "content_safe_operator_lessons",
            "meeting_watchdog",
            "fallback_watchdog",
            "post_sync_dispatch",
            "accountability_sweep",
            "jean_claude_execution_dispatch",
            "workspace_agent_dispatch",
            "codex_workspace_execution",
            "pm_review_resolution",
            "feezie_codex_bridge",
        }

        seen = {item.id for item in automations}
        self.assertTrue(expected_ids.issubset(seen))

        jean_claude = next((item for item in automations if item.id == "jean_claude_execution_dispatch"), None)
        self.assertIsNotNone(jean_claude)
        assert jean_claude is not None
        self.assertEqual(jean_claude.source, automation_service.LOCAL_LAUNCHD_SOURCE)
        self.assertEqual(jean_claude.runtime, "launchd")
        self.assertEqual(jean_claude.owner_agent, "Jean-Claude")
        self.assertEqual(jean_claude.cron, "*/5 * * * *")

        codex_bridge = next((item for item in automations if item.id == "feezie_codex_bridge"), None)
        self.assertIsNotNone(codex_bridge)
        assert codex_bridge is not None
        self.assertEqual(codex_bridge.runtime, "launchd")
        self.assertEqual(codex_bridge.schedule, "Always on")
        self.assertEqual(codex_bridge.workspace_key, "linkedin-content-os")

        codex_executor = next((item for item in automations if item.id == "codex_workspace_execution"), None)
        self.assertIsNotNone(codex_executor)
        assert codex_executor is not None
        self.assertEqual(codex_executor.runtime, "launchd")
        self.assertEqual(codex_executor.owner_agent, None)
        self.assertEqual(codex_executor.cron, "*/5 * * * *")

        review_worker = next((item for item in automations if item.id == "pm_review_resolution"), None)
        self.assertIsNotNone(review_worker)
        assert review_worker is not None
        self.assertEqual(review_worker.runtime, "launchd")
        self.assertEqual(review_worker.owner_agent, "Codex Review Worker")
        self.assertEqual(review_worker.cron, "*/5 * * * *")

    def test_includes_local_youtube_watchlist_auto_ingest(self) -> None:
        automations = list_automations()
        youtube_automation = next((item for item in automations if item.id == "youtube_watchlist_auto_ingest"), None)
        self.assertIsNotNone(youtube_automation)
        assert youtube_automation is not None
        self.assertEqual(youtube_automation.schedule, "Every 2 hours")
        self.assertEqual(youtube_automation.cron, "0 */2 * * *")
        self.assertEqual(youtube_automation.channel, "brain/youtube-watchlist")
        self.assertIn("openclaw", youtube_automation.metrics.get("framework", ""))
        self.assertIn("ollama -> gemini flash -> openai", youtube_automation.metrics.get("cheap_task_defaults", ""))

    def test_augments_youtube_watchlist_with_pending_transcript_runtime_metrics(self) -> None:
        runtime_status = {
            "runtime": {
                "yt_dlp": True,
                "whisper": False,
                "can_transcribe": False,
                "whisper_model": "base",
            },
            "pending_transcript_backfill": 3,
            "pending_transcript_assets": [],
        }

        fake_module = types.ModuleType("app.services.youtube_watchlist_service")
        fake_module.youtube_watchlist_runtime_status = lambda: runtime_status

        with patch.dict(sys.modules, {"app.services.youtube_watchlist_service": fake_module}):
            automations = list_automations()

        youtube_automation = next((item for item in automations if item.id == "youtube_watchlist_auto_ingest"), None)
        self.assertIsNotNone(youtube_automation)
        assert youtube_automation is not None
        self.assertEqual(youtube_automation.metrics.get("pending_transcript_backfill"), "3")
        self.assertEqual(youtube_automation.metrics.get("transcription_runtime_ready"), "false")
        self.assertEqual(youtube_automation.metrics.get("caption_runtime_available"), "true")
        self.assertEqual(youtube_automation.metrics.get("whisper_runtime_available"), "false")
        self.assertEqual(youtube_automation.metrics.get("whisper_model"), "base")

    def test_prefers_openclaw_jobs_json_when_available(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": "job-1",
                    "agentId": "main",
                    "name": "Mirror Test Job",
                    "enabled": True,
                    "schedule": {"kind": "cron", "expr": "*/15 * * * *"},
                    "sessionTarget": "isolated",
                    "wakeMode": "now",
                    "payload": {"kind": "agentTurn", "model": "openai/gpt-4o-mini", "message": "mirror me"},
                    "delivery": {"mode": "announce", "channel": "discord", "to": "chan-1"},
                    "state": {
                        "lastRunAtMs": 1774864800040,
                        "nextRunAtMs": 1774865700040,
                        "lastStatus": "ok",
                        "lastDelivered": True,
                        "lastDurationMs": 1200,
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"
            jobs_path.write_text(json.dumps(payload))
            with patch.object(automation_service, "OPENCLAW_JOBS_PATH", jobs_path):
                automations = list_automations()
                self.assertEqual(automation_source_of_truth(), "openclaw_jobs_json+local_launchd_registry")

        mirrored = next((item for item in automations if item.name == "Mirror Test Job"), None)
        self.assertIsNotNone(mirrored)
        assert mirrored is not None
        self.assertEqual(mirrored.source, "openclaw_jobs_json")
        self.assertEqual(mirrored.runtime, "openclaw_agent_turn")
        self.assertEqual(mirrored.delivery_channel, "discord")
        self.assertEqual(mirrored.delivery_target, "chan-1")
        self.assertTrue(any(item.id == "youtube_watchlist_auto_ingest" for item in automations))

    def test_lists_mirrored_runs_from_openclaw_jobs_json(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": "job-2",
                    "agentId": "main",
                    "name": "Run Mirror Job",
                    "enabled": True,
                    "schedule": {"kind": "every", "everyMs": 1800000},
                    "sessionTarget": "isolated",
                    "wakeMode": "now",
                    "payload": {"kind": "agentTurn", "model": "openai/gpt-4o-mini", "message": "run me"},
                    "delivery": {"mode": "announce", "channel": "webchat", "to": "control-ui"},
                    "state": {
                        "lastRunAtMs": 1774864800040,
                        "nextRunAtMs": 1774866600040,
                        "lastStatus": "ok",
                        "lastDelivered": False,
                        "lastDurationMs": 5000,
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"
            jobs_path.write_text(json.dumps(payload))
            with patch.object(automation_service, "OPENCLAW_JOBS_PATH", jobs_path):
                runs = list_automation_runs()

        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run.automation_name, "Run Mirror Job")
        self.assertEqual(run.delivery_channel, "webchat")
        self.assertEqual(run.delivery_target, "control-ui")
        self.assertTrue(run.action_required)

    def test_prefers_openclaw_run_log_and_suppresses_no_reply_delivery(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": "job-4",
                    "agentId": "main",
                    "name": "Context Guard",
                    "enabled": True,
                    "schedule": {"kind": "cron", "expr": "*/20 * * * *"},
                    "sessionTarget": "isolated",
                    "wakeMode": "now",
                    "payload": {"kind": "agentTurn", "model": "openai/gpt-4o-mini", "message": "guard me"},
                    "delivery": {"mode": "announce", "channel": "discord", "to": "chan-3"},
                    "state": {
                        "lastRunAtMs": 1774864800040,
                        "nextRunAtMs": 1774866600040,
                        "lastStatus": "ok",
                        "lastDelivered": True,
                        "lastDurationMs": 5000,
                    },
                }
            ]
        }
        run_record = {
            "jobId": "job-4",
            "status": "ok",
            "summary": "Context usage is low. NO_REPLY",
            "delivered": False,
            "deliveryStatus": "not-delivered",
            "runAtMs": 1774864801040,
            "durationMs": 1250,
            "ts": 1774864802290,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"
            runs_dir = Path(tmpdir) / "runs"
            runs_dir.mkdir()
            jobs_path.write_text(json.dumps(payload))
            (runs_dir / "job-4.jsonl").write_text(json.dumps(run_record) + "\n")
            with (
                patch.object(automation_service, "OPENCLAW_JOBS_PATH", jobs_path),
                patch.object(automation_service, "OPENCLAW_RUNS_DIR", runs_dir),
            ):
                automations = list_automations()
                runs = list_automation_runs()

        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertFalse(run.action_required)
        self.assertEqual(run.metadata.get("run_source"), "cron_runs_jsonl")
        self.assertTrue(run.metadata.get("no_reply"))
        mirrored = next((item for item in automations if item.id == "job-4"), None)
        self.assertIsNotNone(mirrored)
        assert mirrored is not None
        self.assertFalse(mirrored.last_delivered)

    def test_infers_no_reply_when_run_log_omits_summary_for_no_reply_job(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": "job-4",
                    "agentId": "main",
                    "name": "Context Guard",
                    "enabled": True,
                    "schedule": {"kind": "cron", "expr": "*/20 * * * *"},
                    "sessionTarget": "isolated",
                    "wakeMode": "now",
                    "payload": {
                        "kind": "agentTurn",
                        "model": "openai/gpt-4o-mini",
                        "message": "If below threshold, return EXACTLY NO_REPLY.",
                    },
                    "delivery": {"mode": "announce", "channel": "discord", "to": "chan-3"},
                    "state": {
                        "lastRunAtMs": 1774864800040,
                        "nextRunAtMs": 1774866600040,
                        "lastStatus": "ok",
                        "lastDelivered": False,
                        "lastDurationMs": 5000,
                    },
                }
            ]
        }
        run_record = {
            "jobId": "job-4",
            "status": "ok",
            "delivered": False,
            "deliveryStatus": "not-delivered",
            "runAtMs": 1774864801040,
            "durationMs": 1250,
            "ts": 1774864802290,
            "usage": {"output_tokens": 39},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"
            runs_dir = Path(tmpdir) / "runs"
            runs_dir.mkdir()
            jobs_path.write_text(json.dumps(payload))
            (runs_dir / "job-4.jsonl").write_text(json.dumps(run_record) + "\n")
            with (
                patch.object(automation_service, "OPENCLAW_JOBS_PATH", jobs_path),
                patch.object(automation_service, "OPENCLAW_RUNS_DIR", runs_dir),
            ):
                runs = list_automation_runs()

        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertFalse(run.action_required)
        self.assertTrue(run.metadata.get("no_reply"))
        self.assertTrue(run.metadata.get("no_reply_inferred"))
        self.assertTrue(run.metadata.get("no_reply_contract"))

    def test_run_sync_uses_upsert_contract_against_pool(self) -> None:
        run = AutomationRun(
            id="job-3::1774864800040",
            automation_id="job-3",
            automation_name="Persist Me",
            source="openclaw_jobs_json",
            runtime="openclaw_agent_turn",
            status="ok",
            delivered=True,
            delivery_channel="discord",
            delivery_target="chan-2",
            action_required=False,
            metadata={"model": "openai/gpt-4o-mini"},
        )

        executed: list[tuple[str, tuple]] = []

        class FakeCursor:
            def execute(self, query, params=None):
                executed.append((query, params))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConnection:
            def cursor(self, row_factory=None):
                return FakeCursor()

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakePool:
            def connection(self):
                return FakeConnection()

        with (
            patch.object(automation_run_service, "automation_source_of_truth", return_value="openclaw_jobs_json"),
            patch.object(automation_run_service, "list_automation_runs", return_value=[run]),
            patch.object(automation_run_service, "_get_pool", return_value=FakePool()),
        ):
            count = automation_run_service.sync_openclaw_run_mirror()

        self.assertEqual(count, 1)
        self.assertEqual(len(executed), 1)
        self.assertIn("INSERT INTO automation_runs", executed[0][0])

    def test_run_sync_accepts_mixed_openclaw_and_launchd_source_label(self) -> None:
        run = AutomationRun(
            id="job-5::1774864800040",
            automation_id="job-5",
            automation_name="Hybrid Source Job",
            source="openclaw_jobs_json",
            runtime="openclaw_agent_turn",
            status="ok",
            run_at=datetime.now(timezone.utc),
        )

        class FakeCursor:
            def __init__(self):
                self.calls = 0

            def execute(self, query, params=None):
                self.calls += 1

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConnection:
            def __init__(self):
                self.cursor_impl = FakeCursor()

            def cursor(self, row_factory=None):
                return self.cursor_impl

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakePool:
            def __init__(self):
                self.connection_impl = FakeConnection()

            def connection(self):
                return self.connection_impl

        pool = FakePool()
        with (
            patch.object(automation_run_service, "automation_source_of_truth", return_value="openclaw_jobs_json+local_launchd_registry"),
            patch.object(automation_run_service, "list_automation_runs", return_value=[run]),
            patch.object(automation_run_service, "_get_pool", return_value=pool),
        ):
            count = automation_run_service.sync_openclaw_run_mirror()

        self.assertEqual(count, 1)
        self.assertEqual(pool.connection_impl.cursor_impl.calls, 1)

    def test_mismatch_report_flags_delivery_failure_and_run_error(self) -> None:
        mirrored = [
            automation_service.Automation(
                id="job-1",
                name="Context Guard",
                description="Mirrored",
                schedule="*/20 * * * *",
                cron="*/20 * * * *",
                source="openclaw_jobs_json",
            ),
            automation_service.Automation(
                id="job-2",
                name="Progress Pulse",
                description="Mirrored",
                schedule="Every 30 minutes",
                cron="every:1800000",
                source="openclaw_jobs_json",
            ),
        ]
        runs = [
            AutomationRun(
                id="job-1::1",
                automation_id="job-1",
                automation_name="Context Guard",
                status="ok",
                delivered=False,
                delivery_channel="webchat",
                delivery_target="openclaw-control-ui",
                run_at=datetime.now(timezone.utc),
                action_required=True,
            ),
            AutomationRun(
                id="job-2::1",
                automation_id="job-2",
                automation_name="Progress Pulse",
                status="error",
                delivered=True,
                error="edit failed",
                run_at=datetime.now(timezone.utc),
                action_required=True,
            ),
        ]
        jobs = [{"id": "job-1"}, {"id": "job-2"}]

        with (
            patch.object(automation_mismatch_service, "automation_source_of_truth", return_value="openclaw_jobs_json"),
            patch.object(automation_mismatch_service, "openclaw_jobs_snapshot", return_value=jobs),
            patch.object(automation_mismatch_service, "list_automations", return_value=mirrored),
            patch.object(automation_mismatch_service, "list_runs", return_value=runs),
        ):
            report = automation_mismatch_service.build_mismatch_report()

        self.assertEqual(report.openclaw_job_count, 2)
        self.assertEqual(report.mirrored_openclaw_automation_count, 2)
        self.assertEqual(report.action_required_count, 2)
        kinds = [item.kind for item in report.mismatches]
        self.assertIn("delivery_failure", kinds)
        self.assertIn("run_error", kinds)

    def test_mismatch_report_ignores_no_reply_non_delivery(self) -> None:
        mirrored = [
            automation_service.Automation(
                id="job-1",
                name="Context Guard",
                description="Mirrored",
                schedule="*/20 * * * *",
                cron="*/20 * * * *",
                source="openclaw_jobs_json",
            )
        ]
        runs = [
            AutomationRun(
                id="job-1::1",
                automation_id="job-1",
                automation_name="Context Guard",
                status="ok",
                delivered=False,
                delivery_channel="discord",
                delivery_target="chan-1",
                run_at=datetime.now(timezone.utc),
                action_required=False,
                metadata={"no_reply": True},
            )
        ]
        jobs = [{"id": "job-1"}]

        with (
            patch.object(automation_mismatch_service, "automation_source_of_truth", return_value="openclaw_jobs_json"),
            patch.object(automation_mismatch_service, "openclaw_jobs_snapshot", return_value=jobs),
            patch.object(automation_mismatch_service, "list_automations", return_value=mirrored),
            patch.object(automation_mismatch_service, "list_runs", return_value=runs),
        ):
            report = automation_mismatch_service.build_mismatch_report()

        kinds = [item.kind for item in report.mismatches]
        self.assertNotIn("delivery_failure", kinds)

    def test_mismatch_report_ignores_intentional_no_delivery(self) -> None:
        mirrored = [
            automation_service.Automation(
                id="job-1",
                name="Memory Archive Sweep",
                description="Mirrored",
                schedule="0 4 1 * *",
                cron="0 4 1 * *",
                source="openclaw_jobs_json",
            )
        ]
        runs = [
            AutomationRun(
                id="job-1::1",
                automation_id="job-1",
                automation_name="Memory Archive Sweep",
                status="ok",
                delivered=False,
                delivery_channel=None,
                delivery_target=None,
                run_at=datetime.now(timezone.utc),
                action_required=False,
                metadata={"delivery_mode": "none", "no_delivery": True},
            )
        ]
        jobs = [{"id": "job-1"}]

        with (
            patch.object(automation_mismatch_service, "automation_source_of_truth", return_value="openclaw_jobs_json"),
            patch.object(automation_mismatch_service, "openclaw_jobs_snapshot", return_value=jobs),
            patch.object(automation_mismatch_service, "list_automations", return_value=mirrored),
            patch.object(automation_mismatch_service, "list_runs", return_value=runs),
        ):
            report = automation_mismatch_service.build_mismatch_report()

        kinds = [item.kind for item in report.mismatches]
        self.assertNotIn("delivery_failure", kinds)


if __name__ == "__main__":
    unittest.main()
