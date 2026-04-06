from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"

for candidate in (BACKEND_ROOT, SCRIPTS_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import openclaw_workspace_alignment_audit as audit


class OpenClawWorkspaceAlignmentAuditTests(unittest.TestCase):
    def test_spec_uses_canonical_workspace_portfolio(self) -> None:
        spec = audit.build_alignment_spec()
        self.assertEqual(spec["portfolio"]["feezie-os"]["filesystem_root"], "workspaces/linkedin-content-os")
        self.assertEqual(spec["portfolio"]["fusion-os"]["status"], "standing_up")
        self.assertEqual(spec["portfolio"]["shared_ops"]["kind"], "executive")

    def test_lane_contract_evaluation_passes_exact_expected_shape(self) -> None:
        spec = audit.build_alignment_spec()
        case = next(item for item in audit.build_audit_cases(spec) if item.case_id == "lane_contract")
        payload = {
            "minimum_lane_directories": list(audit.MINIMUM_LANE_DIRECTORIES),
            "startup_anchors": dict(audit.STARTUP_ANCHORS),
            "shared_ops_is_exempt": True,
        }
        result = audit.evaluate_case(case, payload)
        self.assertTrue(result["passed"])
        self.assertEqual(result["mismatches"], [])

    def test_lane_contract_evaluation_fails_when_directory_is_missing(self) -> None:
        spec = audit.build_alignment_spec()
        case = next(item for item in audit.build_audit_cases(spec) if item.case_id == "lane_contract")
        payload = {
            "minimum_lane_directories": ["dispatch/", "briefings/", "docs/", "memory/"],
            "startup_anchors": dict(audit.STARTUP_ANCHORS),
            "shared_ops_is_exempt": True,
        }
        result = audit.evaluate_case(case, payload)
        self.assertFalse(result["passed"])
        self.assertTrue(any("minimum_lane_directories mismatch" in item for item in result["mismatches"]))

    def test_feezie_alias_case_requires_legacy_aliases(self) -> None:
        spec = audit.build_alignment_spec()
        case = next(item for item in audit.build_audit_cases(spec) if item.case_id == "feezie_alias")
        payload = {
            "canonical_workspace_key": "feezie-os",
            "filesystem_root": "workspaces/linkedin-content-os",
            "legacy_aliases": ["linkedin-content-os"],
        }
        result = audit.evaluate_case(case, payload)
        self.assertFalse(result["passed"])
        self.assertTrue(any("linkedin-os" in item for item in result["mismatches"]))


if __name__ == "__main__":
    unittest.main()
