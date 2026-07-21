from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SPEC = importlib.util.spec_from_file_location("brain_canonical_memory_sync_script", SCRIPTS_ROOT / "brain_canonical_memory_sync.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BrainCanonicalMemorySyncTests(unittest.TestCase):
    def test_patch_outage_retries_reconcile_metadata_without_duplicate_local_effects(self) -> None:
        route_id = "brain-route-v1-0123456789abcdef0123456789abcdef"
        route = {
            "route_id": route_id,
            "queued_at": "2026-07-20T12:00:00Z",
            "workspace_key": "shared_ops",
            "targets": ["persistent_state", "learnings", "chronicle"],
            "summary": "Persist this canonical route exactly once.",
            "source_delta_id": "delta-retry",
            "state": "queued",
        }
        delta = {
            "id": "delta-retry",
            "trait": "Retry-safe canonical memory",
            "persona_target": "feeze.core",
            "metadata": {"pending_canonical_memory_routes": [route, dict(route)]},
        }
        brain_context = {
            "brain_signals": [],
            "portfolio_snapshot": {"workspaces": []},
            "source_intelligence": {"available": False, "counts": {}},
            "source_paths": [],
        }
        patch_payloads: list[dict] = []
        patch_attempt = 0

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            nonlocal patch_attempt
            if method == "GET":
                return [delta]
            patch_attempt += 1
            patch_payloads.append(payload or {})
            if patch_attempt == 1:
                raise RuntimeError("Railway PATCH unavailable")
            return {"id": "delta-retry", "metadata": (payload or {}).get("metadata") or {}}

        def fake_append_markdown(path: Path, heading: str, body: str) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            path.write_text(existing + heading + "\n" + body + "\n", encoding="utf-8")

        def fake_append_chronicle(_item: dict, marker: str) -> None:
            path = MODULE._runtime_memory_path("memory/codex_session_handoff.jsonl")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"tags": [marker]}) + "\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            memory_root = Path(temp_dir) / "memory"

            def runtime_path(relative_path: str) -> Path:
                return memory_root / "runtime" / Path(relative_path).name

            with (
                patch.object(MODULE, "MEMORY_ROOT", memory_root),
                patch.object(MODULE, "_runtime_memory_path", side_effect=runtime_path),
                patch.object(MODULE, "build_brain_automation_context", return_value=brain_context),
                patch.object(MODULE, "_fetch_json", side_effect=fake_fetch_json),
                patch.object(MODULE, "_append_markdown", side_effect=fake_append_markdown),
                patch.object(MODULE, "_append_chronicle", side_effect=fake_append_chronicle),
            ):
                with self.assertRaisesRegex(RuntimeError, "PATCH unavailable"):
                    MODULE.build_report("https://example.test", limit=25, sync_live=True)

                second = MODULE.build_report("https://example.test", limit=25, sync_live=True)

            target_files = {
                "persistent_state": memory_root / "runtime" / "persistent_state.md",
                "learnings": memory_root / "runtime" / "LEARNINGS.md",
                "chronicle": memory_root / "runtime" / "codex_session_handoff.jsonl",
                "daily_log": next(memory_root.glob("20??-??-??.md")),
            }
            for target, path in target_files.items():
                marker = f"brain-canonical-route:{route_id}:{target}"
                self.assertEqual(path.read_text(encoding="utf-8").count(marker), 1)

        self.assertEqual(second["queued_route_count"], 1)
        self.assertEqual(second["processed_count"], 1)
        self.assertTrue(all(effect["reused"] for effect in second["processed_items"][0]["effects"]))
        reconciled = patch_payloads[-1]["metadata"]
        self.assertEqual(reconciled["pending_canonical_memory_routes"], [])
        self.assertEqual(len(reconciled["brain_memory_sync_history"]), 1)
        self.assertEqual(reconciled["brain_memory_sync_history"][0]["route_id"], route_id)

    def test_report_carries_brain_context_sources(self) -> None:
        brain_context = {
            "brain_signals": [
                {
                    "id": "signal-1",
                    "source_workspace_key": "shared_ops",
                    "summary": "Memory sync should cite Brain context.",
                    "review_status": "reviewed",
                }
            ],
            "portfolio_snapshot": {"workspaces": []},
            "source_intelligence": {
                "available": True,
                "counts": {"total": 1, "digested": 1, "reviewed": 0, "routed": 0},
            },
            "source_paths": ["/tmp/brain_signals.jsonl"],
        }

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith("/api/persona/deltas?limit=25"))
            return []

        with patch.object(MODULE, "build_brain_automation_context", return_value=brain_context), patch.object(
            MODULE,
            "_fetch_json",
            side_effect=fake_fetch_json,
        ):
            report = MODULE.build_report("https://example.test", limit=25, sync_live=False)

        self.assertEqual(report["processed_count"], 0)
        self.assertIn("/tmp/brain_signals.jsonl", report["source_paths"])
        self.assertTrue(any("Brain Signal" in item for item in report["brain_context_lines"]))
        self.assertIn("## Brain Context", MODULE._markdown_report(report))


if __name__ == "__main__":
    unittest.main()
