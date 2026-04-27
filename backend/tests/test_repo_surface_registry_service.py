from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.repo_surface_registry_service import build_repo_surface_registry  # noqa: E402


class RepoSurfaceRegistryServiceTests(unittest.TestCase):
    def test_build_repo_surface_registry_classifies_primary_and_legacy_surfaces(self) -> None:
        payload = build_repo_surface_registry()

        self.assertEqual(payload.get("schema_version"), "repo_surface_registry/v1")
        entries = {entry["surface_id"]: entry for entry in payload.get("entries") or []}
        self.assertEqual(payload.get("unclassified_runtime_shell_hrefs"), [])
        self.assertEqual(payload.get("unclassified_legacy_nav_hrefs"), [])

        ops = entries["ops"]
        self.assertEqual(ops["status_class"], "live_and_production_relevant")
        self.assertTrue(ops["runtime_shell_visible"])
        self.assertEqual(ops["nav_visibility"], "runtime_shell")
        self.assertFalse(ops["frontend_unmounted_api_calls"])

        inbox = entries["inbox"]
        self.assertEqual(inbox["status_class"], "live_and_production_relevant")
        self.assertTrue(inbox["backend_contract_mounted"])

        archive = entries["downloads_aiclone"]
        self.assertEqual(archive["status_class"], "reference_only")
        self.assertTrue(archive["subtree_exists"])

    def test_build_repo_surface_registry_reports_known_legacy_mismatches(self) -> None:
        payload = build_repo_surface_registry()
        entries = {entry["surface_id"]: entry for entry in payload.get("entries") or []}

        prospect_discovery = entries["prospect_discovery"]
        self.assertEqual(prospect_discovery["status_class"], "present_but_dormant_legacy")
        self.assertEqual(prospect_discovery["mismatch_flags"], ["legacy_surface_calls_unmounted_api"])
        self.assertTrue(
            any(call.startswith("/api/prospect-discovery") for call in prospect_discovery["frontend_unmounted_api_calls"])
        )

        dashboard = entries["dashboard"]
        self.assertEqual(dashboard["mismatch_flags"], ["legacy_surface_calls_unmounted_api"])
        self.assertIn("/api/dashboard", dashboard["frontend_unmounted_api_calls"])

        outreach = entries["outreach"]
        self.assertEqual(outreach["mismatch_flags"], [])

        summary = payload.get("summary") or {}
        self.assertEqual(int(summary.get("mismatch_count") or 0), 2)


if __name__ == "__main__":
    unittest.main()
