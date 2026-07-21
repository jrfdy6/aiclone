from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_codex_memory_sync


def test_run_records_success_even_when_remote_mirror_is_deferred() -> None:
    report = {
        "status": "ok",
        "backend": "sqlite_fts5",
        "files": 12,
        "probe_result_count": 3,
    }
    with (
        patch.object(run_codex_memory_sync, "build_report", return_value=report),
        patch.object(run_codex_memory_sync, "mirror_runs", return_value=False) as mirror,
    ):
        output, ok = run_codex_memory_sync.run(api_url="https://example.invalid")

    assert ok is True
    assert output["remote_mirror"] == "deferred"
    payload = mirror.call_args.args[1][0]
    assert payload["automation_id"] == "codex_memory_sync"
    assert payload["status"] == "success"
