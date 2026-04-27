from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
for root in (WORKSPACE_ROOT, BACKEND_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from app.services.repo_surface_registry_service import build_repo_surface_registry  # noqa: E402
from scripts.verify_repo_surface_truth import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    build_verification_report,
    load_baseline,
)


class VerifyRepoSurfaceTruthTests(unittest.TestCase):
    def test_current_registry_passes_frozen_baseline_guard(self) -> None:
        baseline_payload = load_baseline(DEFAULT_BASELINE_PATH)
        registry_payload = build_repo_surface_registry(include_entries=True)

        report = build_verification_report(registry_payload, baseline_payload)

        self.assertTrue(report["ok"])
        self.assertEqual(report["mode"], "baseline_guard")
        self.assertEqual(len(report["active_surface_mismatches"]), 0)
        self.assertEqual(len(report["new_surface_mismatches"]), 0)
        self.assertEqual(len(report["changed_surface_mismatches"]), 0)
        self.assertEqual(len(report["reduced_surface_mismatches"]), 2)
        self.assertEqual(report["resolved_baseline_surfaces"], ["outreach"])

    def test_strict_mode_fails_on_preserved_legacy_debt(self) -> None:
        baseline_payload = load_baseline(DEFAULT_BASELINE_PATH)
        registry_payload = build_repo_surface_registry(include_entries=True)

        report = build_verification_report(registry_payload, baseline_payload, strict=True)

        self.assertFalse(report["ok"])
        self.assertEqual(report["mode"], "strict")


if __name__ == "__main__":
    unittest.main()
