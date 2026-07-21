from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import worktree_doctor


class WorktreeDoctorTests(unittest.TestCase):
    def test_build_report_captures_branch_divergence_and_categories(self) -> None:
        lines = [
            " M backend/app/services/automation_mismatch_service.py",
            " M automations/youtube_watchlist_auto_ingest.py",
            "?? workspaces/agc/docs/current_questions.md",
        ]

        with patch.object(worktree_doctor, "read_repo_root", return_value=Path("/repo")):
            report = worktree_doctor.build_report(
                lines,
                [],
                branch_line="## main...origin/main [ahead 1, behind 11]",
            )

        self.assertEqual(report["branch"]["branch"], "main")
        self.assertEqual(report["branch"]["upstream"], "origin/main")
        self.assertEqual(report["branch"]["ahead"], 1)
        self.assertEqual(report["branch"]["behind"], 11)
        self.assertEqual(report["counts"]["total"], 3)
        self.assertEqual(report["counts"]["modified"], 2)
        self.assertEqual(report["counts"]["untracked"], 1)
        self.assertEqual(report["counts"]["by_category"]["backend"], 1)
        self.assertEqual(report["counts"]["by_category"]["automation"], 1)
        self.assertEqual(report["counts"]["by_category"]["workspace"], 1)
        self.assertEqual(report["push_recommendation"], "blocked_reconcile_remote_first")


if __name__ == "__main__":
    unittest.main()
