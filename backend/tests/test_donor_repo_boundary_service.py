from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.donor_repo_boundary_service import build_donor_repo_boundary_report  # noqa: E402


class DonorRepoBoundaryServiceTests(unittest.TestCase):
    def test_build_donor_repo_boundary_report_returns_summary_and_targets(self) -> None:
        payload = build_donor_repo_boundary_report()

        self.assertEqual(payload.get("schema_version"), "donor_repo_boundary_report/v1")
        donor_repo = payload.get("donor_repo") or {}
        self.assertEqual(donor_repo.get("repo_id"), "downloads_aiclone")
        self.assertEqual(donor_repo.get("status_class"), "reference_only")

        targets = payload.get("targets") or []
        self.assertGreaterEqual(len(targets), 6)

        summary = payload.get("summary") or {}
        self.assertEqual(summary.get("target_count"), len(targets))
        self.assertGreaterEqual(summary.get("worth_porting_count"), 1)
        self.assertGreaterEqual(summary.get("reference_only_count"), 1)
        self.assertGreaterEqual(summary.get("abandon_count"), 1)
        self.assertGreaterEqual(summary.get("pending_extraction_count"), 1)
        self.assertGreaterEqual(summary.get("do_not_port_count"), 1)


if __name__ == "__main__":
    unittest.main()
