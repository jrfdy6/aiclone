from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.fallback_policy_service import build_fallback_policy_report  # noqa: E402


class FallbackPolicyServiceTests(unittest.TestCase):
    def test_build_fallback_policy_report_returns_summary_and_entries(self) -> None:
        payload = build_fallback_policy_report()

        self.assertEqual(payload.get("schema_version"), "fallback_policy_report/v1")
        policies = payload.get("policies") or []
        self.assertGreaterEqual(len(policies), 6)

        summary = payload.get("summary") or {}
        self.assertEqual(summary.get("total_policies"), len(policies))
        self.assertGreaterEqual(summary.get("allowed_in_production_count"), 1)
        self.assertGreaterEqual(summary.get("temporary_scaffold_count"), 1)
        self.assertEqual(summary.get("treat_as_failure_count"), 0)


if __name__ == "__main__":
    unittest.main()
