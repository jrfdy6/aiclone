from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workspace_registry_service import workspace_registry_entries, workspace_root_path

PACK_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md", "CHARTER.md")
LANE_DIRS = ("dispatch", "briefings", "docs", "memory", "agent-ledgers")


class WorkspaceLaneContractTests(unittest.TestCase):
    def _workspace_entries(self) -> list[dict[str, object]]:
        return [entry for entry in workspace_registry_entries() if entry.get("kind") == "workspace"]

    def test_shared_ops_has_full_identity_pack(self) -> None:
        root = workspace_root_path("shared_ops", repo_root=REPO_ROOT)
        self.assertTrue(root.exists(), "shared_ops root missing")
        for pack_name in PACK_FILES:
            self.assertTrue((root / pack_name).is_file(), f"shared_ops missing pack file {pack_name}")
        self.assertTrue((root / "docs").is_dir(), "shared_ops missing docs directory")
        self.assertTrue((root / "docs" / "README.md").is_file(), "shared_ops missing docs/README.md")
        self.assertTrue((root / "docs" / "execution_lane.md").is_file(), "shared_ops missing docs/execution_lane.md")
        self.assertTrue((root / "memory" / "execution_log.md").is_file(), "shared_ops missing execution log")

    def test_non_executive_workspaces_have_minimum_lane_shape(self) -> None:
        for entry in self._workspace_entries():
            key = str(entry["key"])
            root = workspace_root_path(key, repo_root=REPO_ROOT)
            self.assertTrue(root.exists(), f"{key} root missing: {root}")

            for pack_name in PACK_FILES:
                self.assertTrue((root / pack_name).is_file(), f"{key} missing pack file {pack_name}")

            for dirname in LANE_DIRS:
                self.assertTrue((root / dirname).is_dir(), f"{key} missing lane directory {dirname}/")

            self.assertTrue((root / "docs" / "README.md").is_file(), f"{key} missing docs/README.md")
            self.assertTrue((root / "docs" / "execution_lane.md").is_file(), f"{key} missing docs/execution_lane.md")
            self.assertTrue((root / "memory" / "README.md").is_file(), f"{key} missing memory/README.md")
            self.assertTrue((root / "memory" / "execution_log.md").is_file(), f"{key} missing memory/execution_log.md")

    def test_workspace_agents_reference_local_lane_anchors(self) -> None:
        for entry in self._workspace_entries():
            key = str(entry["key"])
            root = workspace_root_path(key, repo_root=REPO_ROOT)
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")

            self.assertIn("docs/README.md", agents_text, f"{key} AGENTS.md should anchor local docs")
            self.assertIn("memory/execution_log.md", agents_text, f"{key} AGENTS.md should anchor local memory")
            self.assertIn("dispatch", agents_text, f"{key} AGENTS.md should mention dispatch lane")
            self.assertIn("briefings", agents_text, f"{key} AGENTS.md should mention briefings lane")

    def test_shared_ops_remains_an_executive_exception(self) -> None:
        executive = next(entry for entry in workspace_registry_entries() if str(entry["key"]) == "shared_ops")
        self.assertEqual(executive["kind"], "executive")


if __name__ == "__main__":
    unittest.main()
