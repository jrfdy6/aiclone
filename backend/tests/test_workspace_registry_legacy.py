from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from workspace_registry_legacy import (  # type: ignore
    build_legacy_workspace_registry_payload,
    load_legacy_workspace_registry_map,
    write_legacy_workspace_registry,
)


class WorkspaceRegistryLegacyTests(unittest.TestCase):
    def test_feezie_and_fusion_statuses_match_canonical_registry(self) -> None:
        payload = build_legacy_workspace_registry_payload()
        workspaces = {item["workspace_key"]: item for item in payload["workspaces"]}

        feezie = workspaces["feezie-os"]
        fusion = workspaces["fusion-os"]

        self.assertEqual(feezie["status"], "live")
        self.assertEqual(feezie["display_name"], "FEEZIE OS")
        self.assertEqual(feezie["legacy_name"], "LinkedIn OS")
        self.assertIn("linkedin-content-os", feezie["filesystem_path"])

        self.assertEqual(fusion["status"], "standing_up")
        self.assertEqual(fusion["display_name"], "Fusion OS")
        self.assertIn("fusion-os", fusion["filesystem_path"])

    def test_written_legacy_registry_can_be_loaded_as_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "workspace_registry.json"
            write_legacy_workspace_registry(path)
            registry = load_legacy_workspace_registry_map(path, ensure_synced=False)

        self.assertIn("feezie-os", registry)
        self.assertIn("fusion-os", registry)
        self.assertEqual(registry["feezie-os"]["execution_mode"], "direct")
        self.assertEqual(registry["fusion-os"]["workspace_agent"], "Fusion Systems Operator")


if __name__ == "__main__":
    unittest.main()
