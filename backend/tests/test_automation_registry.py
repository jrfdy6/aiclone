from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.automations import Automation, AutomationRun
from app.routes import automations as automation_routes
from app.services import automation_mismatch_service, automation_run_service, automation_service
from app.services.automation_service import automation_source_of_truth, list_automation_runs, list_automations


EXPECTED_AUTOMATION_IDS = {
    "accountability_sweep",
    "brain_canonical_memory_sync",
    "codex_chronicle_sync",
    "codex_daily_memory_flush",
    "codex_memory_sync",
    "codex_nightly_self_improvement",
    "codex_rolling_docs",
    "codex_workspace_execution",
    "content_safe_operator_lessons",
    "dream_cycle",
    "email_codex_bridge",
    "external_service_health",
    "fallback_watchdog",
    "feezie_codex_bridge",
    "feezie_content_pipeline",
    "fusion_feedback_refresh",
    "jean_claude_execution_dispatch",
    "launchd_health_audit",
    "meeting_watchdog",
    "memory_archive_sweep",
    "memory_health_check",
    "morning_daily_brief",
    "neo_guest",
    "operator_story_signals",
    "persona_bundle_sync",
    "pm_review_resolution",
    "portfolio_standup_prep",
    "post_sync_dispatch",
    "progress_pulse",
    "project_snapshot",
    "secure_config_backup",
    "watchtranscripts",
    "weekly_memory_hygiene",
    "workspace_agent_dispatch",
    "youtube_watchlist_auto_ingest",
}


def _automation(automation_id: str, name: str | None = None) -> Automation:
    return Automation(
        id=automation_id,
        name=name or automation_id.replace("_", " ").title(),
        description="Registered launchd worker",
        schedule="Every 5 minutes",
        cron="every:300",
        source=automation_service.CODEX_REGISTRY_SOURCE,
        runtime="launchd",
    )


class AutomationRegistryTests(unittest.TestCase):
    def test_source_of_truth_is_codex_registry_plus_local_ledger(self) -> None:
        self.assertEqual(automation_source_of_truth(), "codex_launchd_registry+codex_run_ledger")

    def test_registry_contains_only_actual_codex_launchd_definitions(self) -> None:
        automations = list_automations(runs=[])
        self.assertEqual({item.id for item in automations}, EXPECTED_AUTOMATION_IDS)
        self.assertTrue(all(item.source == automation_service.CODEX_REGISTRY_SOURCE for item in automations))
        self.assertTrue(all(item.runtime == "launchd" for item in automations))
        self.assertTrue(all(item.last_run_at is None and item.last_status == "unknown" for item in automations))

        memory_sync = next(item for item in automations if item.id == "codex_memory_sync")
        self.assertEqual(memory_sync.cron, "every:300")
        self.assertEqual(memory_sync.metrics.get("script"), "scripts/run_codex_memory_sync.py")

        codex_execution = next(item for item in automations if item.id == "codex_workspace_execution")
        self.assertEqual(codex_execution.cron, "* * * * *")
        self.assertEqual(codex_execution.metrics.get("cadence_seconds"), "60")

        neo_guest = next(item for item in automations if item.id == "neo_guest")
        self.assertEqual(neo_guest.type, "daemon")
        self.assertEqual(neo_guest.schedule, "Always on")
        self.assertEqual(neo_guest.cron, "launchd.keepalive")
        self.assertIsNone(neo_guest.next_run_at)
        self.assertEqual(neo_guest.metrics.get("script"), "scripts/runners/run_neo_guest.py")
        self.assertEqual(neo_guest.metrics.get("launch_agent"), "automations/launchd/com.neo.neo_guest.plist")
        self.assertEqual(neo_guest.metrics.get("execution_mode"), "persistent_serial_queue_worker")
        self.assertEqual(neo_guest.metrics.get("idle_poll_seconds"), "0.5-2.0")
        self.assertEqual(neo_guest.metrics.get("model_residency"), "preloaded_keep_alive")
        self.assertEqual(neo_guest.metrics.get("streaming_progress"), "throttled")
        self.assertEqual(neo_guest.metrics.get("default_max_predict_tokens"), "160")
        self.assertEqual(neo_guest.metrics.get("knowledge_pack_contract"), "neo_public_knowledge_pack/v1")
        self.assertEqual(neo_guest.metrics.get("local_ledger_content"), "metadata_only")
        self.assertEqual(neo_guest.metrics.get("capability"), "write_capable_guest_response")
        self.assertNotIn("cadence_seconds", neo_guest.metrics)

        for intentionally_uninstalled_id in ("email_codex_bridge", "watchtranscripts"):
            item = next(entry for entry in automations if entry.id == intentionally_uninstalled_id)
            self.assertEqual(item.status, "paused")
            self.assertEqual(item.cron, "disabled")
            self.assertEqual(item.metrics.get("installation_state"), "intentionally_uninstalled")

        self.assertNotIn("workspace_backup", EXPECTED_AUTOMATION_IDS)
        self.assertNotIn("self_improvement", EXPECTED_AUTOMATION_IDS)

    def test_youtube_registry_listing_never_scans_runtime_source_inventory(self) -> None:
        with patch(
            "app.services.youtube_watchlist_service.youtube_watchlist_runtime_status",
        ) as runtime_status:
            automations = list_automations(runs=[])

        runtime_status.assert_not_called()
        item = next(entry for entry in automations if entry.id == "youtube_watchlist_auto_ingest")
        self.assertEqual(item.metrics.get("framework"), "Codex project automation + launchd")
        self.assertNotIn("pending_transcript_backfill", item.metrics)

    def test_generic_automation_index_never_scans_runtime_source_inventory(self) -> None:
        with patch.object(
            automation_routes.automation_run_service,
            "list_runs",
            return_value=[],
        ), patch(
            "app.services.youtube_watchlist_service.youtube_watchlist_runtime_status",
        ) as runtime_status:
            payload = automation_routes._build_automations_index()

        runtime_status.assert_not_called()
        self.assertEqual(payload["count"], len(EXPECTED_AUTOMATION_IDS))

    def test_local_ledger_is_validated_deduplicated_and_sorted(self) -> None:
        older = {
            "id": "memory::1",
            "automation_id": "codex_memory_sync",
            "automation_name": "Codex Durable Memory Sync",
            "source": "local_launchd_registry",
            "runtime": "launchd",
            "status": "error",
            "run_at": "2026-07-17T10:00:00Z",
        }
        replacement = {**older, "status": "success", "run_at": "2026-07-17T11:00:00Z"}
        newest = {
            "id": "audit::1",
            "automation_id": "launchd_health_audit",
            "automation_name": "Launchd Health Audit",
            "source": "codex_launchd_registry",
            "runtime": "launchd",
            "status": "success",
            "run_at": "2026-07-17T12:00:00Z",
        }
        retired_runtime = {
            "id": "retired::1",
            "automation_id": "retired_job",
            "automation_name": "Retired Job",
            "source": "retired_registry",
            "runtime": "agent_turn",
            "status": "success",
            "run_at": "2026-07-17T13:00:00Z",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "all.jsonl"
            ledger.write_text(
                "\n".join(
                    [json.dumps(older), "not-json", json.dumps(newest), json.dumps(replacement), json.dumps(retired_runtime)]
                )
                + "\n",
                encoding="utf-8",
            )
            with patch.object(automation_service, "CODEX_RUN_LEDGER_PATH", ledger):
                runs = list_automation_runs()

        self.assertEqual([run.id for run in runs], ["audit::1", "memory::1"])
        self.assertEqual(runs[1].status, "success")

    def test_registry_uses_latest_observed_ledger_state(self) -> None:
        now = datetime.now(timezone.utc)
        old = AutomationRun(
            id="memory::old",
            automation_id="codex_memory_sync",
            automation_name="Codex Durable Memory Sync",
            runtime="launchd",
            status="error",
            run_at=now - timedelta(minutes=5),
            error="old failure",
        )
        latest = AutomationRun(
            id="memory::latest",
            automation_id="codex_memory_sync",
            automation_name="Codex Durable Memory Sync",
            runtime="launchd",
            status="success",
            run_at=now,
        )

        item = next(entry for entry in list_automations(runs=[old, latest]) if entry.id == "codex_memory_sync")
        self.assertEqual(item.last_run_at, now)
        self.assertEqual(item.last_status, "success")
        self.assertIsNone(item.last_error)

    def test_ledger_sync_uses_database_upsert_contract(self) -> None:
        run = AutomationRun(
            id="memory::1",
            automation_id="codex_memory_sync",
            automation_name="Codex Durable Memory Sync",
            source="codex_launchd_registry",
            runtime="launchd",
            status="success",
            run_at=datetime.now(timezone.utc),
        )
        executed: list[tuple[str, tuple | None]] = []

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
            patch.object(automation_run_service, "list_automation_runs", return_value=[run]),
            patch.object(automation_run_service, "_get_pool", return_value=FakePool()),
        ):
            count = automation_run_service.sync_codex_run_ledger()

        self.assertEqual(count, 1)
        self.assertEqual(len(executed), 1)
        self.assertIn("INSERT INTO automation_runs", executed[0][0])

    def test_list_runs_fallback_honors_automation_filter(self) -> None:
        runs = [
            AutomationRun(
                id="memory::1",
                automation_id="codex_memory_sync",
                automation_name="Memory",
                runtime="launchd",
            ),
            AutomationRun(
                id="audit::1",
                automation_id="launchd_health_audit",
                automation_name="Audit",
                runtime="launchd",
            ),
        ]
        with (
            patch.object(automation_run_service, "_get_pool", side_effect=RuntimeError("database unavailable")),
            patch.object(automation_run_service, "list_automation_runs", return_value=runs),
        ):
            result = automation_run_service.list_runs(limit=10, automation_id="codex_memory_sync")
        self.assertEqual([run.id for run in result], ["memory::1"])

    def test_mismatch_report_compares_registry_to_latest_ledger_runs(self) -> None:
        registry = [_automation("worker_a"), _automation("worker_b"), _automation("worker_c")]
        runs = [
            AutomationRun(
                id="a::1",
                automation_id="worker_a",
                automation_name="Worker A",
                runtime="launchd",
                status="success",
                delivered=False,
                delivery_channel="control_plane",
                delivery_target="ops",
                run_at=datetime.now(timezone.utc),
                action_required=True,
            ),
            AutomationRun(
                id="b::1",
                automation_id="worker_b",
                automation_name="Worker B",
                runtime="launchd",
                status="error",
                error="execution failed",
                run_at=datetime.now(timezone.utc),
                action_required=True,
            ),
            AutomationRun(
                id="orphan::1",
                automation_id="unregistered_worker",
                automation_name="Unregistered Worker",
                runtime="launchd",
                status="success",
                run_at=datetime.now(timezone.utc),
            ),
        ]

        report = automation_mismatch_service.build_mismatch_report(automations=registry, runs=runs)

        self.assertEqual(report.registry_count, 3)
        self.assertEqual(report.registered_launchd_count, 3)
        self.assertEqual(report.run_count, 3)
        self.assertEqual(report.action_required_count, 2)
        kinds = {item.kind for item in report.mismatches}
        self.assertEqual(kinds, {"delivery_failure", "run_error", "missing_run_record", "unregistered_run"})

    def test_mismatch_report_uses_latest_health_audit_only(self) -> None:
        now = datetime.now(timezone.utc)
        registry = [_automation("launchd_health_audit")]
        old = AutomationRun(
            id="audit::old",
            automation_id="launchd_health_audit",
            automation_name="Launchd Health Audit",
            runtime="launchd",
            status="error",
            run_at=now - timedelta(minutes=5),
            action_required=True,
            metadata={
                "launchd_issues": [
                    {
                        "kind": "local_launchd_missing_program",
                        "severity": "error",
                        "automation_id": "worker_a",
                        "message": "A configured program is missing.",
                    }
                ]
            },
        )
        latest = AutomationRun(
            id="audit::latest",
            automation_id="launchd_health_audit",
            automation_name="Launchd Health Audit",
            runtime="launchd",
            status="success",
            run_at=now,
            metadata={"launchd_issues": [], "has_observed_run": True},
        )

        report = automation_mismatch_service.build_mismatch_report(automations=registry, runs=[old, latest])
        self.assertEqual(report.mismatch_count, 0)
        self.assertEqual(report.action_required_count, 0)

    def test_mismatch_report_allows_intentional_no_delivery(self) -> None:
        registry = [_automation("worker_a")]
        run = AutomationRun(
            id="a::1",
            automation_id="worker_a",
            automation_name="Worker A",
            runtime="launchd",
            status="success",
            delivered=False,
            delivery_channel="control_plane",
            run_at=datetime.now(timezone.utc),
            metadata={"no_delivery": True},
        )
        report = automation_mismatch_service.build_mismatch_report(automations=registry, runs=[run])
        self.assertNotIn("delivery_failure", {item.kind for item in report.mismatches})


if __name__ == "__main__":
    unittest.main()
