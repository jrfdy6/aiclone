from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
BACKEND_ROOT = ROOT / "backend"
for import_root in (SCRIPTS_ROOT, BACKEND_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import build_content_safe_operator_lessons as content_safe_builder  # noqa: E402
import build_morning_daily_brief as morning_brief_builder  # noqa: E402
import build_operator_story_signals as operator_story_builder  # noqa: E402
from app.services import brain_signal_intake_service  # noqa: E402
from app.services import operator_story_signal_service  # noqa: E402
from app.services import workspace_snapshot_service  # noqa: E402


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


launchd_audit = _load_script(
    "active_job_launchd_audit",
    SCRIPTS_ROOT / "ops" / "audit_launchd_jobs.py",
)
portfolio_standups = _load_script(
    "active_job_portfolio_standups",
    SCRIPTS_ROOT / "ops" / "build_portfolio_standups.py",
)


def test_automation_report_reader_prefers_private_state_and_keeps_logical_ref(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "state"
    logical_ref = "memory/reports/operator_story_signals_latest.json"
    project_report = project_root / logical_ref
    state_report = state_root / logical_ref
    project_report.parent.mkdir(parents=True)
    state_report.parent.mkdir(parents=True)
    project_report.write_text('{"origin":"project"}\n', encoding="utf-8")
    state_report.write_text('{"origin":"state"}\n', encoding="utf-8")
    spec = {
        "automation_id": "operator_story_signals",
        "logical_ref": logical_ref,
        "path": project_report,
    }

    with patch.object(brain_signal_intake_service, "ROOT", project_root), patch.object(
        brain_signal_intake_service,
        "PRIVATE_STATE_ROOT",
        state_root,
    ):
        resolved = brain_signal_intake_service._automation_report_path(spec)
        source_ref = brain_signal_intake_service._automation_report_ref(spec, resolved)

    assert resolved == state_report
    assert json.loads(resolved.read_text(encoding="utf-8"))["origin"] == "state"
    assert source_ref == logical_ref
    assert not Path(source_ref).is_absolute()


def test_workspace_snapshot_report_reader_prefers_private_state(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "state"
    logical_ref = workspace_snapshot_service.OPERATOR_STORY_SIGNALS_LOGICAL_REF
    project_report = project_root / logical_ref
    state_report = state_root / logical_ref
    project_report.parent.mkdir(parents=True)
    state_report.parent.mkdir(parents=True)
    project_report.write_text(
        json.dumps({"counts": {"total": 1}, "signals": [{"id": "project"}]}),
        encoding="utf-8",
    )
    state_report.write_text(
        json.dumps({"counts": {"total": 1}, "signals": [{"id": "state"}]}),
        encoding="utf-8",
    )

    with patch.object(workspace_snapshot_service, "ROOT", project_root), patch.object(
        workspace_snapshot_service,
        "PRIVATE_STATE_ROOT",
        state_root,
    ), patch.object(
        workspace_snapshot_service,
        "OPERATOR_STORY_SIGNALS_PATH",
        project_report,
    ):
        payload = workspace_snapshot_service._load_operator_story_signals_payload()

    assert payload is not None
    assert payload["signals"][0]["id"] == "state"


def test_operator_story_memory_reads_private_state_before_legacy_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_memory = project_root / "memory"
    state_root = tmp_path / "state"
    state_memory = state_root / "memory"
    project_memory.mkdir(parents=True)
    state_memory.mkdir(parents=True)
    project_memory.joinpath("daily-briefs.md").write_text(
        "# Morning Daily Brief — 2026-07-25\n\n## Summary\n- Project-only signal.\n",
        encoding="utf-8",
    )
    state_memory.joinpath("daily-briefs.md").write_text(
        "# Morning Daily Brief — 2026-07-25\n\n## Summary\n- State-only signal.\n",
        encoding="utf-8",
    )

    with patch.object(operator_story_signal_service, "ROOT", project_root), patch.object(
        operator_story_signal_service,
        "MEMORY_ROOT",
        project_memory,
    ), patch.object(
        operator_story_signal_service,
        "PRIVATE_STATE_ROOT",
        state_root,
    ):
        payload = operator_story_signal_service.build_operator_story_signals_payload()

    serialized = json.dumps(payload)
    assert "State-only signal" in serialized
    assert "Project-only signal" not in serialized
    assert payload["source_paths"]["daily-briefs.md"] == "memory/daily-briefs.md"
    assert all(
        not Path(str(signal.get("source_ref") or "")).is_absolute()
        for signal in payload["signals"]
    )


def test_operator_story_code_root_stays_with_own_checkout(monkeypatch) -> None:
    monkeypatch.delenv("AI_CLONE_ROOT", raising=False)
    assert operator_story_signal_service.resolve_workspace_root() == Path(
        operator_story_signal_service.__file__
    ).resolve().parents[3]


def test_active_job_default_writers_leave_project_bytes_unchanged(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    state_root = tmp_path / "state"
    project_reports = project_root / "memory" / "reports"
    state_reports = state_root / "memory" / "reports"
    project_reports.mkdir(parents=True)

    daily_project = project_root / "memory" / "daily-briefs.md"
    daily_project.write_text("legacy daily bytes\n", encoding="utf-8")
    with patch.object(morning_brief_builder, "WORKSPACE_ROOT", project_root), patch.object(
        morning_brief_builder,
        "STATE_ROOT",
        state_root,
    ):
        daily_state = morning_brief_builder._daily_briefs_write_path()
        morning_brief_builder._upsert_brief(
            daily_state,
            "# Morning Daily Brief — 2026-07-25\n\nState brief.",
            "2026-07-25",
        )
    assert daily_project.read_bytes() == b"legacy daily bytes\n"
    assert daily_state == state_root / "memory" / "daily-briefs.md"
    assert b"State brief" in daily_state.read_bytes()

    cases = [
        (
            operator_story_builder,
            "operator_story_signals_latest.json",
            {
                "ROOT": project_root,
                "PRIVATE_STATE_ROOT": state_root,
                "REPORT_ROOT": state_reports,
            },
        ),
        (
            content_safe_builder,
            "content_safe_operator_lessons_latest.json",
            {
                "ROOT": project_root,
                "PRIVATE_STATE_ROOT": state_root,
                "REPORT_ROOT": state_reports,
            },
        ),
        (
            launchd_audit,
            "launchd_health_audit_latest.json",
            {
                "WORKSPACE_ROOT": project_root,
                "STATE_ROOT": state_root,
                "DEFAULT_REPORT_PATH": state_reports / "launchd_health_audit_latest.json",
            },
        ),
        (
            portfolio_standups,
            "portfolio_standup_prep_latest.json",
            {
                "WORKSPACE_ROOT": project_root,
                "STATE_ROOT": state_root,
                "REPORT_PATH": state_reports / "portfolio_standup_prep_latest.json",
            },
        ),
    ]
    for module, filename, replacements in cases:
        project_path = project_reports / filename
        project_path.write_text(f"legacy {filename}\n", encoding="utf-8")
        patchers = [patch.object(module, name, value) for name, value in replacements.items()]
        for patcher in patchers:
            patcher.start()
        try:
            if module in {operator_story_builder, content_safe_builder}:
                state_path = module._report_write_path(state_reports, filename)
            else:
                state_path = module._report_write_path(state_reports / filename)
            module._write_json(state_path, {"origin": "state"}) if hasattr(module, "_write_json") else module._write_report(
                {"origin": "state"},
                state_path,
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

        assert project_path.read_text(encoding="utf-8") == f"legacy {filename}\n"
        assert json.loads((state_reports / filename).read_text(encoding="utf-8"))["origin"] == "state"


def test_portfolio_remote_payload_replaces_absolute_state_paths(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    prep_path = state_root / "memory" / "standups" / "prep.json"
    with patch.object(portfolio_standups, "STATE_ROOT", state_root):
        sanitized = portfolio_standups._logical_remote_value(
            {
                "prep_json_path": str(prep_path),
                "source_paths": [str(state_root / "memory" / "brain_signals.jsonl")],
            }
        )

    assert sanitized["prep_json_path"] == "memory/standups/prep.json"
    assert sanitized["source_paths"] == ["memory/brain_signals.jsonl"]


def test_operator_story_remote_payload_replaces_absolute_state_paths(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    with patch.object(operator_story_builder, "PRIVATE_STATE_ROOT", state_root):
        sanitized = operator_story_builder._logical_remote_value(
            [
                {
                    "source_ref": str(state_root / "memory" / "daily-briefs.md"),
                    "artifact_paths": [str(state_root / "workspaces" / "feezie-os" / "proof.md")],
                }
            ]
        )

    serialized = json.dumps(sanitized)
    assert str(state_root) not in serialized
    assert sanitized[0]["source_ref"] == "memory/daily-briefs.md"
    assert sanitized[0]["artifact_paths"] == ["workspaces/feezie-os/proof.md"]
