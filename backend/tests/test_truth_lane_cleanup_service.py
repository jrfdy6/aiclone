from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.truth_lane_cleanup_service import (  # noqa: E402
    CLEANUP_MODE_FORWARD_ONLY,
    build_truth_lane_cleanup_report,
)


class TruthLaneCleanupServiceTests(unittest.TestCase):
    def test_build_truth_lane_cleanup_report_returns_decision_and_summary(self) -> None:
        payload = build_truth_lane_cleanup_report(include_findings=False)

        self.assertEqual(payload.get("schema_version"), "truth_lane_cleanup_report/v1")
        cleanup_decision = payload.get("cleanup_decision") or {}
        self.assertEqual(cleanup_decision.get("mode"), CLEANUP_MODE_FORWARD_ONLY)
        summary = payload.get("summary") or {}
        self.assertGreaterEqual(int(summary.get("files_scanned") or 0), 2)
        self.assertIn("suspect_line_count", summary)
        self.assertNotIn("files", payload)


if __name__ == "__main__":
    unittest.main()
