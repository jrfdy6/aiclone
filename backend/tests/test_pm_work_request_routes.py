from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import PMCard
from app.routes import pm_board as pm_board_routes
from app.routes import workspace as workspace_routes


def _client_for(router) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class PMWorkRequestRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _client_for(pm_board_routes.router)

    @staticmethod
    def _payload() -> dict[str, object]:
        return {
            "request_id": str(uuid4()),
            "workspace_key": "shared_ops",
            "outcome": "Deliver a bounded result and return verification evidence.",
            "approved_for_queue": True,
        }

    def test_rejects_client_supplied_path_agent_and_lane_overrides(self) -> None:
        payload = self._payload()
        payload.update(
            {
                "repository_path": "/tmp/untrusted-repository",
                "target_agent": "Untrusted Agent",
                "lane": "arbitrary-runner",
            }
        )

        with patch.object(pm_board_routes, "enqueue_work_request") as enqueue:
            response = self.client.post("/api/pm/request-work", json=payload)

        self.assertEqual(response.status_code, 422)
        rejected_fields = {
            str(error["loc"][-1])
            for error in response.json().get("detail", [])
            if error.get("type") == "extra_forbidden"
        }
        self.assertEqual(rejected_fields, {"repository_path", "target_agent", "lane"})
        enqueue.assert_not_called()

    def test_maps_invalid_request_to_bad_request(self) -> None:
        with patch.object(
            pm_board_routes,
            "enqueue_work_request",
            side_effect=ValueError("Unknown project workspace: made-up-project"),
        ):
            response = self.client.post("/api/pm/request-work", json=self._payload())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Unknown project workspace: made-up-project")

    def test_maps_missing_signing_configuration_to_service_unavailable(self) -> None:
        with patch.object(
            pm_board_routes,
            "enqueue_work_request",
            side_effect=RuntimeError("The signed Codex work queue is not configured."),
        ):
            response = self.client.post("/api/pm/request-work", json=self._payload())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "The signed Codex work queue is not configured.")

    def test_execution_source_returns_raw_signed_payload_without_client_decoration(self) -> None:
        card_id = uuid4()
        now = datetime.now(timezone.utc)
        signed_payload = {
            "workspace_key": "shared_ops",
            "execution": {"state": "queued", "lane": "codex"},
            "_control_plane_authorization": {
                "version": 1,
                "algorithm": "hmac-sha256",
                "signature": "signed-value",
            },
        }
        card = PMCard(
            id=str(card_id),
            title="Signed execution source",
            status="todo",
            payload=signed_payload,
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(pm_board_routes.pm_card_service, "get_card", return_value=card) as get_card,
            patch.object(pm_board_routes.pm_card_service, "decorate_card_for_client") as decorate,
        ):
            response = self.client.get(f"/api/pm/cards/{card_id}/execution-source")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"], signed_payload)
        self.assertNotIn("pm_review_policy", response.json()["payload"])
        get_card.assert_called_once_with(str(card_id))
        decorate.assert_not_called()

    def test_execution_source_returns_not_found_for_missing_card(self) -> None:
        card_id = uuid4()
        with patch.object(pm_board_routes.pm_card_service, "get_card", return_value=None):
            response = self.client.get(f"/api/pm/cards/{card_id}/execution-source")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "PM card not found")


class WorkspaceRegistryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _client_for(workspace_routes.router)

    def test_registry_returns_canonical_shape_and_no_store_header(self) -> None:
        fake_payload = {
            "generated_at": "2026-07-19T12:00:00+00:00",
            "workspaces": [
                {
                    "key": "work-life-tools",
                    "kind": "workspace",
                    "display_name": "Work Life Tools",
                    "manager_agent": "Jean-Claude",
                    "target_agent": "Work Life Tools Operator Agent",
                    "workspace_agent": "Work Life Tools Operator Agent",
                    "execution_mode": "delegated",
                }
            ],
        }

        with patch.object(
            workspace_routes,
            "workspace_registry_payload",
            return_value=fake_payload,
        ) as build_registry:
            response = self.client.get("/api/workspace/registry?include_executive=false")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")
        self.assertEqual(response.json(), fake_payload)
        build_registry.assert_called_once_with(include_executive=False)


if __name__ == "__main__":
    unittest.main()
