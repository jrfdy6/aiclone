from __future__ import annotations

import json
import os
import plistlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import scheduled_automation_runtime as runtime  # noqa: E402
import scheduled_automation_tasks as tasks  # noqa: E402


def test_scheduled_subprocess_environment_excludes_provider_credentials() -> None:
    provider_key = "OPENAI" + "_API_KEY"
    with patch.object(runtime, "control_plane_token", return_value="service-token"):
        env = runtime.scheduled_subprocess_env(
            {
                "HOME": "/Users/neo",
                "PATH": "/usr/bin:/bin",
                provider_key: "must-not-pass",
            }
        )

    assert provider_key not in env
    assert env["CONTROL_PLANE_SERVICE_TOKEN"] == "service-token"
    assert env["AI_CLONE_SECRETS_ROOT"].endswith("scheduled-no-secret-files")


def test_scheduled_task_records_local_truth_before_deferred_mirror() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        ledger = root / "runs" / "all.jsonl"
        pending = root / "runs" / "pending.jsonl"

        result, ok = runtime.run_scheduled_task(
            automation_id="test_job",
            automation_name="Test Job",
            task=lambda: runtime.TaskOutcome(ok=True, summary="Local work complete."),
            api_url="https://example.invalid",
            ledger_path=ledger,
            pending_path=pending,
            mirror_attempts=0,
        )

        local_row = json.loads(ledger.read_text(encoding="utf-8").strip())
        pending_row = json.loads(pending.read_text(encoding="utf-8").strip())

    assert ok is True
    assert local_row["id"] == pending_row["id"] == result["run_id"]
    assert local_row["metadata"]["local_first"] is True
    assert result["railway_mirror"]["status"] == "deferred"
    assert result["railway_mirror"]["pending"] == 1


def test_pending_railway_mirror_retries_with_service_auth_and_clears_queue() -> None:
    requests = []

    def fake_urlopen(request, timeout):
        assert timeout == runtime.DEFAULT_MIRROR_TIMEOUT_SECONDS
        requests.append(request)
        return _FakeResponse()

    with tempfile.TemporaryDirectory() as temp_dir:
        pending = Path(temp_dir) / "pending.jsonl"
        runtime.enqueue_pending_run({"id": "run-1", "status": "success"}, pending_path=pending)
        with patch.object(runtime, "control_plane_token", return_value="service-token"), patch.object(
            runtime,
            "control_plane_headers",
            side_effect=lambda headers: {**headers, "Authorization": "Bearer service-token"},
        ), patch.object(runtime.urllib.request, "urlopen", side_effect=fake_urlopen):
            outcome = runtime.flush_pending_runs(
                "https://backend.example",
                pending_path=pending,
                attempts=1,
            )
        pending_text = pending.read_text(encoding="utf-8")

    assert outcome.status == "ok"
    assert outcome.mirrored == 1
    assert outcome.pending == 0
    assert pending_text == ""
    assert requests[0].get_header("Authorization") == "Bearer service-token"


def test_morning_daily_brief_syncs_current_date_before_reporting_success() -> None:
    brief_date = datetime.now(tasks.LOCAL_TZ).date().isoformat()
    calls: list[tuple[str, tuple[str, ...], int]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        artifact = root / "memory" / "daily-briefs.md"

        def fake_run(script_name, arguments=(), *, timeout_seconds, **_kwargs):
            calls.append((script_name, tuple(arguments), timeout_seconds))
            if script_name == "build_morning_daily_brief.py":
                artifact.parent.mkdir(parents=True)
                artifact.write_text(f"## Daily Brief — {brief_date}\n\nCurrent signal.\n", encoding="utf-8")
                return runtime.CommandOutput(
                    returncode=0,
                    stdout=json.dumps({"date": brief_date, "markdown": "# Current signal"}),
                    stderr="",
                )
            assert script_name == "sync_daily_briefs.py"
            assert tuple(arguments) == ("--expected-latest-date", brief_date)
            return runtime.CommandOutput(
                returncode=0,
                stdout=json.dumps({"success": True, "count": 1, "latest_brief_date": brief_date}),
                stderr="",
            )

        with (
            patch.object(tasks, "PROJECT_ROOT", root),
            patch.object(tasks, "_relative_project_path", return_value="memory/daily-briefs.md"),
            patch.object(tasks, "run_project_python", side_effect=fake_run),
        ):
            outcome = tasks.build_morning_daily_brief(timeout_seconds=180)

    assert [call[0] for call in calls] == ["build_morning_daily_brief.py", "sync_daily_briefs.py"]
    assert calls[1][2] == 60
    assert outcome.ok is True
    assert outcome.metadata["brief_date"] == brief_date
    assert outcome.metadata["railway_sync"] == "ok"
    assert outcome.metadata["railway_sync_count"] == 1


def test_morning_daily_brief_fails_when_railway_sync_fails() -> None:
    brief_date = datetime.now(tasks.LOCAL_TZ).date().isoformat()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        artifact = root / "memory" / "daily-briefs.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text(f"## Daily Brief — {brief_date}\n", encoding="utf-8")

        def fake_run(script_name, arguments=(), *, timeout_seconds, **_kwargs):
            if script_name == "build_morning_daily_brief.py":
                return runtime.CommandOutput(
                    returncode=0,
                    stdout=json.dumps({"date": brief_date, "markdown": "# Current signal"}),
                    stderr="",
                )
            raise runtime.ScheduledTaskError("Railway sync unavailable")

        with (
            patch.object(tasks, "PROJECT_ROOT", root),
            patch.object(tasks, "run_project_python", side_effect=fake_run),
            pytest.raises(runtime.ScheduledTaskError, match="Railway sync unavailable"),
        ):
            tasks.build_morning_daily_brief(timeout_seconds=180)


def test_memory_archive_moves_only_old_stable_daily_files() -> None:
    now = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        memory = root / "memory"
        memory.mkdir()
        old_file = memory / "2026-05-01.md"
        recent_file = memory / "2026-07-16.md"
        old_file.write_text("# Old durable note\n", encoding="utf-8")
        recent_file.write_text("# Recent durable note\n", encoding="utf-8")
        stable_mtime = (now - timedelta(days=4)).timestamp()
        os.utime(old_file, (stable_mtime, stable_mtime))

        outcome = tasks.archive_memory(project_root=root, now=now)

        archived = memory / "archive" / "2026" / "05" / old_file.name
        manifest = memory / "archive" / "manifests" / "2026-07.md"
        archived_text = archived.read_text(encoding="utf-8")
        recent_exists = recent_file.exists()
        manifest_text = manifest.read_text(encoding="utf-8")

    assert outcome.ok is True
    assert outcome.metadata["archived_count"] == 1
    assert outcome.metadata["purged_count"] == 0
    assert archived_text == "# Old durable note\n"
    assert recent_exists is True
    assert "sha256=" in manifest_text


def test_memory_archive_retains_symbolic_link_daily_files() -> None:
    now = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        memory = root / "memory"
        memory.mkdir()
        outside = root / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        linked = memory / "2026-05-01.md"
        linked.symlink_to(outside)

        outcome = tasks.archive_memory(project_root=root, now=now)
        link_still_exists = linked.is_symlink()
        archive_copy_exists = (memory / "archive" / "2026" / "05" / linked.name).exists()

    assert link_still_exists is True
    assert archive_copy_exists is False
    assert outcome.metadata["archived_count"] == 0
    assert outcome.metadata["anomaly_count"] == 1
    assert outcome.action_required is True


def test_memory_health_uses_sqlite_report_and_bounded_project_paths() -> None:
    now = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        memory = root / "memory"
        memory.mkdir()
        for name in tasks.CRITICAL_MEMORY_FILES:
            (root / name).write_text(f"# {name}\n", encoding="utf-8")
        (memory / "2026-07-17.md").write_text("# Today\n", encoding="utf-8")
        report, report_path = tasks.inspect_memory_health(
            {
                "status": "ok",
                "ready": True,
                "backend": "sqlite_fts5",
                "files": 42,
                "hours_since_update": 0.1,
                "probe_result_count": 3,
            },
            project_root=root,
            now=now,
        )
        report_text = report_path.read_text(encoding="utf-8")

    assert report["status"] == "ok"
    assert report["findings"] == []
    assert report_path == root / "memory" / "reports" / "memory_health_2026-07-17.md"
    assert "sqlite_fts5" in report_text


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return b'{"status":"ok"}'


def test_external_health_authenticates_only_the_backend_protected_probe() -> None:
    requests = []

    def fake_urlopen(request, timeout):
        assert timeout == 5
        requests.append(request)
        return _FakeResponse()

    with tempfile.TemporaryDirectory() as temp_dir, patch.object(
        tasks, "STATE_ROOT", Path(temp_dir)
    ), patch.object(tasks, "control_plane_token", return_value="service-token"), patch.object(
        tasks, "control_plane_headers", side_effect=lambda headers: {**headers, "Authorization": "Bearer service-token"}
    ), patch.object(tasks.urllib.request, "urlopen", side_effect=fake_urlopen):
        outcome = tasks.check_external_services(
            api_url="https://backend.example",
            frontend_url="https://frontend.example",
            timeout_seconds=5,
        )

    protected = next(request for request in requests if request.full_url.endswith("/api/open-brain/health"))
    frontend = next(request for request in requests if request.full_url.endswith("/login"))
    assert outcome.ok is True
    assert protected.get_header("Authorization") == "Bearer service-token"
    assert frontend.get_header("Authorization") is None


def test_launchd_plists_have_exact_parity_schedules_and_runtime_paths() -> None:
    expected = {
        "com.neo.morning_daily_brief": {"calendar": {"Hour": 11, "Minute": 30}},
        "com.neo.progress_pulse": {"interval": 3600},
        "com.neo.dream_cycle": {"calendar": {"Hour": 6, "Minute": 15}},
        "com.neo.memory_health_check": {"calendar": {"Hour": 3, "Minute": 10}},
        "com.neo.memory_archive_sweep": {"calendar": {"Day": 1, "Hour": 4, "Minute": 0}},
        "com.neo.external_service_health": {"calendar": {"Hour": 6, "Minute": 5}},
    }
    for label, schedule in expected.items():
        path = ROOT / "automations" / "launchd" / f"{label}.plist"
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
        assert payload["Label"] == label
        assert payload["ProgramArguments"][0] == "/Users/neo/.codex/ai-clone/venv/bin/python"
        assert payload["ProgramArguments"][1].startswith("/Users/neo/Documents/Codex/AI-Clone/scripts/")
        assert payload["WorkingDirectory"] == "/Users/neo/Documents/Codex/AI-Clone"
        assert payload["StandardOutPath"].startswith("/Users/neo/.codex/ai-clone/logs/")
        if "calendar" in schedule:
            assert payload["StartCalendarInterval"] == schedule["calendar"]
        else:
            assert payload["StartInterval"] == schedule["interval"]


def test_feezie_umbrella_refresh_reuses_existing_ingest_and_memory_sync_jobs() -> None:
    for relative_path in (
        "automations/com.neo.feezie_content_pipeline.plist",
        "automations/launchd/com.neo.feezie_content_pipeline.plist",
    ):
        with (ROOT / relative_path).open("rb") as handle:
            payload = plistlib.load(handle)
        arguments = payload["ProgramArguments"]
        assert arguments.count("--skip-fetch") == 1
        assert arguments.count("--skip-brain-context-sync") == 1
        assert arguments[arguments.index("--sources") + 1] == "safe"
