from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PostSyncDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.dispatch = _load_module("post_sync_dispatch", SCRIPTS_ROOT / "post_sync_dispatch.py")

    def test_build_card_payload_autostarts_and_includes_execution_contract(self) -> None:
        payload = self.dispatch._build_card_payload(
            {
                "id": "standup-xyz",
                "workspace_key": "shared_ops",
                "payload": {"participants": ["Jean-Claude", "Neo"]},
            },
            "Advance a post-sync commitment",
        )

        execution = dict(payload.get("execution") or {})
        self.assertEqual(execution.get("state"), "queued")
        self.assertTrue(str(execution.get("queued_at") or "").strip())
        self.assertEqual(payload.get("completion_contract", {}).get("source"), "post_sync_dispatch")
        self.assertTrue(payload.get("completion_contract", {}).get("autostart"))
        self.assertGreaterEqual(len(payload.get("instructions") or []), 1)
        self.assertGreaterEqual(len(payload.get("acceptance_criteria") or []), 1)


if __name__ == "__main__":
    unittest.main()
