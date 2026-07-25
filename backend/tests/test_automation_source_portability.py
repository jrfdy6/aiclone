from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PINNED_CHECKOUT = "/Users/neo/Documents/Codex/AI-Clone"

PORTABLE_PYTHON_SOURCES = (
    "automations/persona_bundle_sync.py",
    "automations/youtube_watchlist_auto_ingest.py",
    "scripts/backfill_long_form_structured_extraction.py",
    "scripts/build_core_memory_snapshot.py",
    "scripts/build_dream_cycle_snapshot.py",
    "scripts/build_morning_daily_brief.py",
    "scripts/context_flush.py",
    "scripts/doc_status_snapshot.py",
    "scripts/fallback_watchdog.py",
    "scripts/heartbeat_report.py",
    "scripts/heartbeat_touch.py",
    "scripts/load_context_pack.py",
    "scripts/meeting_watchdog.py",
    "scripts/post_sync_dispatch.py",
    "scripts/promote_standup_packet.py",
    "scripts/refresh_fusion_instagram_feedback.py",
    "scripts/restore_core_memory_snapshot.py",
    "scripts/sync_daily_briefs.py",
)

EXPECTED_PLIST_SOURCES = {
    "com.neo.brain_canonical_memory_sync": "automations/launchd/com.neo.brain_canonical_memory_sync.plist",
    "com.neo.codex_chronicle_sync": "automations/launchd/com.neo.codex_chronicle_sync.plist",
    "com.neo.codex_memory_sync": "automations/launchd/com.neo.codex_memory_sync.plist",
    "com.neo.codex_workspace_execution": "automations/launchd/com.neo.codex_workspace_execution.plist",
    "com.neo.content_safe_operator_lessons": "automations/launchd/com.neo.content_safe_operator_lessons.plist",
    "com.neo.feezie_codex_bridge": "automations/launchd/com.neo.feezie_codex_bridge.plist",
    "com.neo.feezie_content_pipeline": "automations/launchd/com.neo.feezie_content_pipeline.plist",
    "com.neo.jean_claude_execution": "automations/launchd/com.neo.jean_claude_execution.plist",
    "com.neo.launchd_health_audit": "automations/launchd/com.neo.launchd_health_audit.plist",
    "com.neo.meeting_watchdog": "automations/launchd/com.neo.meeting_watchdog.plist",
    "com.neo.morning_daily_brief": "automations/launchd/com.neo.morning_daily_brief.plist",
    "com.neo.neo_guest": "automations/launchd/com.neo.neo_guest.plist",
    "com.neo.operator_story_signals": "automations/launchd/com.neo.operator_story_signals.plist",
    "com.neo.pm_review_resolution": "automations/launchd/com.neo.pm_review_resolution.plist",
    "com.neo.persona_bundle_sync": "automations/com.neo.persona_bundle_sync.plist",
    "com.neo.portfolio_standup_prep": "automations/launchd/com.neo.portfolio_standup_prep.plist",
    "com.neo.post_sync_dispatch": "automations/launchd/com.neo.post_sync_dispatch.plist",
    "com.neo.workspace_agent_dispatch": "automations/launchd/com.neo.workspace_agent_dispatch.plist",
    "com.neo.youtube_watchlist_auto_ingest": "automations/com.neo.youtube_watchlist_auto_ingest.plist",
    "com.neo.project_snapshot": "automations/launchd/com.neo.project_snapshot.plist",
}


def test_python_automations_do_not_pin_the_operational_checkout() -> None:
    for relative in PORTABLE_PYTHON_SOURCES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert PINNED_CHECKOUT not in source, relative
        assert "PROJECT_ROOT" in source, relative


def test_runtime_root_override_controls_project_and_generated_report_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "alternate-project"
    state_root = tmp_path / "private-state"
    script = ROOT / "scripts" / "meeting_watchdog.py"
    code = (
        "import json, runpy; "
        f"scope = runpy.run_path({str(script)!r}); "
        "print(json.dumps({'project': str(scope['WORKSPACE_ROOT']), 'reports': str(scope['REPORT_ROOT'])}))"
    )
    env = os.environ.copy()
    env["AI_CLONE_ROOT"] = str(project_root)
    env["AI_CLONE_STATE_ROOT"] = str(state_root)

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["project"] == str(project_root)
    assert payload["reports"] == str(state_root / "memory" / "reports")


def test_repo_managed_launchd_sources_are_public_configuration_only() -> None:
    forbidden_environment_keys = {
        "API_KEY",
        "AUTHORIZATION",
        "CONTROL_PLANE_SERVICE_TOKEN",
        "PASSWORD",
        "SECRET",
        "TOKEN",
    }
    for expected_label, relative in EXPECTED_PLIST_SOURCES.items():
        path = ROOT / relative
        with path.open("rb") as handle:
            payload = plistlib.load(handle)

        assert payload["Label"] == expected_label
        environment = payload.get("EnvironmentVariables") or {}
        assert forbidden_environment_keys.isdisjoint(environment)
        if expected_label == "com.neo.youtube_watchlist_auto_ingest":
            assert not any(key.startswith("CONTENT_GENERATION_") for key in environment)
