from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402

brain_route_module = importlib.import_module("app.routes.brain")


class BrainRepoSurfaceRegistryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_repo_surface_registry_route_returns_no_store_payload(self) -> None:
        fake_payload = {
            "schema_version": "repo_surface_registry/v1",
            "summary": {"total_surfaces": 16, "mismatch_count": 3},
            "mismatches": [{"surface_id": "prospect_discovery"}],
            "entries": [{"surface_id": "ops", "status_class": "live_and_production_relevant"}],
        }
        with patch.object(brain_route_module, "build_repo_surface_registry", return_value=fake_payload):
            response = self.client.get("/api/brain/repo-surface-registry")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload.get("schema_version"), "repo_surface_registry/v1")
        self.assertEqual((payload.get("summary") or {}).get("mismatch_count"), 3)
        self.assertEqual(((payload.get("entries") or [{}])[0]).get("surface_id"), "ops")

    def test_fallback_policy_route_returns_no_store_payload(self) -> None:
        fake_payload = {
            "schema_version": "fallback_policy_report/v1",
            "summary": {"total_policies": 7, "temporary_scaffold_count": 4},
            "policies": [{"fallback_id": "content_generation_provider_failover", "policy_class": "allowed_in_production"}],
        }
        with patch.object(brain_route_module, "build_fallback_policy_report", return_value=fake_payload):
            response = self.client.get("/api/brain/fallback-policy")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload.get("schema_version"), "fallback_policy_report/v1")
        self.assertEqual((payload.get("summary") or {}).get("temporary_scaffold_count"), 4)

    def test_truth_lanes_route_returns_no_store_payload(self) -> None:
        fake_payload = {
            "schema_version": "truth_lane_cleanup_report/v1",
            "cleanup_decision": {"mode": "forward_only_with_audit"},
            "summary": {"suspect_line_count": 9},
        }
        with patch.object(brain_route_module, "build_truth_lane_cleanup_report", return_value=fake_payload):
            response = self.client.get("/api/brain/truth-lanes")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload.get("schema_version"), "truth_lane_cleanup_report/v1")
        self.assertEqual(((payload.get("cleanup_decision") or {}).get("mode")), "forward_only_with_audit")

    def test_lifecycle_route_returns_no_store_payload(self) -> None:
        fake_payload = {
            "schema_version": "work_lifecycle_report/v1",
            "summary": {"open_count": 12, "written_back_count": 2, "closed_count": 3},
        }
        with patch.object(brain_route_module, "build_work_lifecycle_report", return_value=fake_payload):
            response = self.client.get("/api/brain/lifecycle")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload.get("schema_version"), "work_lifecycle_report/v1")
        self.assertEqual((payload.get("summary") or {}).get("written_back_count"), 2)

    def test_donor_boundary_route_returns_no_store_payload(self) -> None:
        fake_payload = {
            "schema_version": "donor_repo_boundary_report/v1",
            "summary": {"target_count": 8, "pending_extraction_count": 3},
            "donor_repo": {"repo_id": "downloads_aiclone", "status_class": "reference_only"},
        }
        with patch.object(brain_route_module, "build_donor_repo_boundary_report", return_value=fake_payload):
            response = self.client.get("/api/brain/donor-boundary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload.get("schema_version"), "donor_repo_boundary_report/v1")
        self.assertEqual((payload.get("summary") or {}).get("pending_extraction_count"), 3)


if __name__ == "__main__":
    unittest.main()
