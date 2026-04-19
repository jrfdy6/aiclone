from __future__ import annotations

import importlib.util
import sys
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
