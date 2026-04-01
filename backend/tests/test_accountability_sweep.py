from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = WORKSPACE_ROOT / "scripts" / "accountability_sweep.py"
SPEC = importlib.util.spec_from_file_location("accountability_sweep_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AccountabilitySweepTests(unittest.TestCase):
    def test_live_sweep_reroutes_stale_cards_and_creates_followup(self) -> None:
        queue = [
            {
                "card_id": "review-1",
                "title": "Stale review lane",
                "workspace_key": "fusion-os",
                "execution_state": "review",
                "target_agent": "Fusion Systems Operator",
                "last_transition_at": "2026-03-30T00:00:00Z",
            },
            {
                "card_id": "running-1",
                "title": "Stale running lane",
                "workspace_key": "shared_ops",
                "execution_state": "running",
                "target_agent": "Jean-Claude",
                "last_transition_at": "2026-03-30T00:00:00Z",
            },
        ]
        cards = [
            {
                "id": "review-1",
                "title": "Stale review lane",
                "status": "review",
                "source": "standup:test",
                "payload": {
                    "workspace_key": "fusion-os",
                    "execution": {
                        "state": "review",
                        "target_agent": "Fusion Systems Operator",
                        "execution_mode": "delegated",
                        "assigned_runner": "fusion-systems-operator",
                        "workspace_agent": "Fusion Systems Operator",
                    }
                },
            },
            {
                "id": "running-1",
                "title": "Stale running lane",
                "status": "in_progress",
                "source": "standup:test",
                "payload": {
                    "workspace_key": "shared_ops",
                    "execution": {
                        "state": "running",
                        "target_agent": "Jean-Claude",
                        "execution_mode": "direct",
                        "assigned_runner": "jean-claude",
                    }
                },
            },
        ]

        patched: list[tuple[str, dict]] = []
        posted: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return queue
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "PATCH" and "/api/pm/cards/" in url:
                assert payload is not None
                patched.append((url, payload))
                card_id = url.rsplit("/", 1)[-1]
                return {"id": card_id, "status": payload.get("status", "review")}
            if method == "POST" and url.endswith("/api/pm/cards"):
                assert payload is not None
                posted.append((url, payload))
                return {"id": "followup-1", "status": payload.get("status", "todo")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["stale_review_count"], 1)
        self.assertEqual(report["stale_running_count"], 1)
        self.assertEqual(report["rerouted_count"], 2)
        self.assertEqual(len(patched), 2)
        self.assertEqual(len(posted), 1)
        self.assertEqual(report["executive_followup_card"]["action"], "created")
        first_patch_payload = patched[0][1]["payload"]["execution"]
        self.assertEqual(first_patch_payload["target_agent"], "Jean-Claude")
        self.assertEqual(first_patch_payload["assigned_runner"], "jean-claude")
        self.assertEqual(first_patch_payload["execution_mode"], "direct")
        self.assertEqual(first_patch_payload["state"], "queued")

    def test_live_sweep_closes_followup_when_no_stale_cards_remain(self) -> None:
        cards = [
            {
                "id": "followup-1",
                "title": MODULE.FOLLOWUP_TITLE,
                "status": "todo",
                "source": MODULE.FOLLOWUP_SOURCE,
                "payload": {
                    "execution": {
                        "state": "ready",
                        "target_agent": "Jean-Claude",
                    }
                },
            }
        ]
        patched: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "PATCH" and url.endswith("/api/pm/cards/followup-1"):
                assert payload is not None
                patched.append((url, payload))
                return {"id": "followup-1", "status": payload.get("status", "done")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["stale_review_count"], 0)
        self.assertEqual(report["stale_running_count"], 0)
        self.assertEqual(len(patched), 1)
        self.assertEqual(report["executive_followup_card"]["action"], "closed")
        self.assertEqual(report["executive_followup_card"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
