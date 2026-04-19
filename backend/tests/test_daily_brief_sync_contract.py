from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services import daily_brief_service  # noqa: E402

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "sync_daily_briefs.py"
SPEC = importlib.util.spec_from_file_location("sync_daily_briefs_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SYNC_SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC_SCRIPT)


class DailyBriefSyncContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_sync_daily_briefs_from_markdown_rejects_stale_latest_date(self) -> None:
        raw_markdown = """# Morning Daily Brief - 2026-04-15

### Highlights:
- Daily log input processing completed without errors.
"""

        with self.assertRaisesRegex(
            ValueError,
            "Latest brief date 2026-04-15 does not match expected 2026-04-16",
        ):
            daily_brief_service.sync_daily_briefs_from_markdown(
                raw_markdown,
                expected_latest_brief_date=date(2026, 4, 16),
            )

    def test_sync_daily_briefs_route_returns_400_for_stale_markdown(self) -> None:
        response = self.client.post(
            "/api/briefs/sync",
            json={
                "raw_markdown": "# Morning Daily Brief - 2026-04-15\n\n- stale brief\n",
                "expected_latest_brief_date": "2026-04-16",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Latest brief date 2026-04-15 does not match expected 2026-04-16", response.json().get("detail", ""))

    def test_sync_script_uses_memory_resolver_for_workspace_memory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            live_path = workspace_root / "memory" / "daily-briefs.md"
            runtime_path = workspace_root / "memory" / "runtime" / "daily-briefs.md"
            live_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            live_path.write_text("live\n", encoding="utf-8")
            runtime_path.write_text("runtime\n", encoding="utf-8")

            with patch.object(SYNC_SCRIPT, "WORKSPACE_ROOT", workspace_root), patch.object(
                SYNC_SCRIPT,
                "resolve_memory_read_target",
                return_value={"resolved_path": str(runtime_path), "resolved_mode": "runtime"},
            ) as resolver_mock:
                resolved = SYNC_SCRIPT._resolve_brief_path(str(live_path))

        self.assertEqual(resolved, runtime_path)
        resolver_mock.assert_called_once_with(workspace_root, "memory/daily-briefs.md")


if __name__ == "__main__":
    unittest.main()
