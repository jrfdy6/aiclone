from __future__ import annotations

import importlib.util
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
RUNNERS = SCRIPTS / "runners"
for path in (SCRIPTS, RUNNERS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load_runner():
    path = RUNNERS / "run_codex_maintenance_job.py"
    spec = importlib.util.spec_from_file_location("run_codex_maintenance_job", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load maintenance runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _payload():
    return {
        "summary": "Material execution state was synthesized.",
        "findings": ["One bounded finding."],
        "actions": ["Advance the signed PM job."],
        "durable_memory": ["Railway is the remote control plane."],
        "evidence": ["SOURCE_OF_TRUTH.md"],
    }


def test_write_result_upserts_same_daily_section() -> None:
    runner = _load_runner()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
        with mock.patch.object(runner, "PROJECT_ROOT", root):
            first = runner.write_result(runner.JOBS["daily-memory-flush"], _payload(), now=now)
            second_payload = _payload()
            second_payload["summary"] = "Updated synthesis."
            runner.write_result(runner.JOBS["daily-memory-flush"], second_payload, now=now)
        content = (root / "memory" / "2026-07-17.md").read_text(encoding="utf-8")

    assert first[0] == "memory/2026-07-17.md"
    assert content.count("## Daily Memory Flush — 2026-07-17") == 1
    assert "Updated synthesis." in content


def test_minimum_age_gate_skips_without_invoking_codex() -> None:
    runner = _load_runner()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    with mock.patch.object(runner, "latest_successful_run_ms", return_value=now_ms), mock.patch.object(
        runner, "run_codex"
    ) as run_codex, mock.patch.object(runner, "_record", return_value=False):
        result, ok = runner.execute_job("rolling-docs", minimum_success_age_hours=47)

    assert ok is True
    assert result == {"status": "skipped", "remote_mirror": "deferred"}
    run_codex.assert_not_called()


def test_validate_payload_rejects_unexpected_fields() -> None:
    runner = _load_runner()
    payload = _payload()
    payload["secret"] = "must not pass"
    try:
        runner._validate_payload(payload)
    except ValueError as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("unexpected field was accepted")
