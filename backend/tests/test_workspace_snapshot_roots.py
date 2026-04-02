from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import workspace_snapshot_service as workspace_snapshot_module


class WorkspaceSnapshotRootSelectionTests(unittest.TestCase):
    def test_ingestions_and_transcripts_roots_prefer_richer_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            app_root = temp_root / "app"
            backend_root = app_root / "backend"
            rich_ingestions = app_root / "knowledge" / "ingestions" / "2026" / "04" / "rich-asset"
            thin_ingestions = backend_root / "knowledge" / "ingestions" / "2026" / "04" / "thin-asset"
            rich_transcripts = app_root / "knowledge" / "aiclone" / "transcripts"
            thin_transcripts = backend_root / "knowledge" / "aiclone" / "transcripts"

            rich_ingestions.mkdir(parents=True)
            thin_ingestions.mkdir(parents=True)
            rich_transcripts.mkdir(parents=True)
            thin_transcripts.mkdir(parents=True)

            (rich_ingestions / "normalized.md").write_text("---\ntitle: Rich Asset\n---\n", encoding="utf-8")
            (rich_ingestions.parent / "rich-asset-2" / "normalized.md").parent.mkdir(parents=True)
            (rich_ingestions.parent / "rich-asset-2" / "normalized.md").write_text("---\ntitle: Rich Asset 2\n---\n", encoding="utf-8")
            (thin_ingestions / "normalized.md").write_text("---\ntitle: Thin Asset\n---\n", encoding="utf-8")

            (rich_transcripts / "session-a.md").write_text("# Session A\n", encoding="utf-8")
            (rich_transcripts / "session-b.md").write_text("# Session B\n", encoding="utf-8")
            (thin_transcripts / "README.md").write_text("# Readme\n", encoding="utf-8")

            with patch.object(workspace_snapshot_module, "_candidate_roots", return_value=[backend_root, app_root]):
                self.assertEqual(workspace_snapshot_module._ingestions_root().resolve(), (app_root / "knowledge" / "ingestions").resolve())
                self.assertEqual(
                    workspace_snapshot_module._transcripts_root().resolve(),
                    (app_root / "knowledge" / "aiclone" / "transcripts").resolve(),
                )


if __name__ == "__main__":
    unittest.main()
