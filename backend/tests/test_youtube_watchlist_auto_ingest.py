from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "automations" / "youtube_watchlist_auto_ingest.py"
SPEC = importlib.util.spec_from_file_location("youtube_watchlist_auto_ingest_test_module", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def _args() -> SimpleNamespace:
    return SimpleNamespace(
        api_url="https://example.invalid",
        max_videos_per_run=None,
        per_channel_limit=None,
        skip_refresh=True,
        dry_run=False,
        snapshot_only=False,
        no_mirror=False,
    )


def _result() -> dict:
    return {
        "enabled": True,
        "ingested": [],
        "skipped": [],
        "warnings": [],
        "errors": [],
        "counts": {"discovered": 0, "ingested": 0, "skipped": 0, "warnings": 0, "errors": 0},
        "_watchlist_payload": {
            "schema_version": "youtube_watchlist/v1",
            "generated_at": "2026-07-20T00:00:00+00:00",
            "runtime": {},
            "channels": [],
            "counts": {"channels": 0, "videos": 0},
        },
    }


class YouTubeWatchlistAutomationTests(unittest.TestCase):
    def test_runtime_defaults_do_not_force_an_ollama_provider(self) -> None:
        with patch.dict(module.os.environ, {"PATH": "/usr/bin:/bin"}, clear=True):
            applied = module._apply_easy_task_defaults()

            self.assertEqual(applied, {})
            self.assertNotIn("CONTENT_GENERATION_PROVIDER_ORDER", module.os.environ)
            self.assertNotIn("CONTENT_GENERATION_OLLAMA_FAST_MODEL", module.os.environ)
            self.assertNotIn("CONTENT_GENERATION_OLLAMA_EDITOR_MODEL", module.os.environ)

    def test_normal_ingest_fails_when_required_snapshot_mirror_fails(self) -> None:
        with (
            patch.object(module, "parse_args", return_value=_args()),
            patch.object(module, "_apply_easy_task_defaults", return_value={}),
            patch.object(module, "sync_watchlist_auto_ingest", return_value=_result()),
            patch.object(module, "_mirror_watchlist_snapshot", return_value=False),
            patch.object(module, "_mirror_summary", return_value=True),
            patch.object(module, "_write_report", return_value=True),
        ):
            self.assertEqual(module.main(), 1)

    def test_normal_ingest_reuses_completed_watchlist_payload(self) -> None:
        expected = _result()["_watchlist_payload"]
        with (
            patch.object(module, "parse_args", return_value=_args()),
            patch.object(module, "_apply_easy_task_defaults", return_value={}),
            patch.object(module, "sync_watchlist_auto_ingest", return_value=_result()),
            patch.object(module, "build_youtube_watchlist_payload", side_effect=AssertionError("feed fetched twice")),
            patch.object(module, "_mirror_watchlist_snapshot", return_value=True) as mirror,
            patch.object(module, "_mirror_summary", return_value=True),
            patch.object(module, "_write_report", return_value=True),
        ):
            self.assertEqual(module.main(), 0)

        mirror.assert_called_once_with(expected, api_url="https://example.invalid")

    def test_ops_mirror_uses_logical_report_reference(self) -> None:
        started_at = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        with patch.object(module, "mirror_runs", return_value=True) as mirror:
            self.assertTrue(
                module._mirror_summary(
                    {"mode": "ingest", "result": _result()},
                    api_url="https://example.invalid",
                    started_at=started_at,
                    finished_at=started_at + timedelta(seconds=2),
                )
            )

        mirrored_run = mirror.call_args.args[1][0]
        metadata = mirrored_run.get("metadata") or {}
        self.assertEqual(metadata.get("report_ref"), module.REPORT_REFERENCE)
        self.assertNotIn("report_path", metadata)
        self.assertNotIn(str(module.REPORT_PATH), str(mirrored_run))


if __name__ == "__main__":
    unittest.main()
