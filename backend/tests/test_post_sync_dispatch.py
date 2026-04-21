from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PostSyncDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.dispatch = _load_module("post_sync_dispatch", SCRIPTS_ROOT / "post_sync_dispatch.py")

    def test_build_card_payload_autostarts_and_includes_execution_contract(self) -> None:
        payload = self.dispatch._build_card_payload(
            {
                "id": "standup-xyz",
                "workspace_key": "shared_ops",
                "payload": {"participants": ["Jean-Claude", "Neo"]},
            },
            "Advance a post-sync commitment",
        )

        execution = dict(payload.get("execution") or {})
        self.assertEqual(execution.get("state"), "queued")
        self.assertTrue(str(execution.get("queued_at") or "").strip())
        self.assertEqual(payload.get("completion_contract", {}).get("source"), "post_sync_dispatch")
        self.assertTrue(payload.get("completion_contract", {}).get("autostart"))
        self.assertGreaterEqual(len(payload.get("instructions") or []), 1)
        self.assertGreaterEqual(len(payload.get("acceptance_criteria") or []), 1)

    def test_build_report_marks_recommendations_covered_by_existing_cards(self) -> None:
        standup_payloads: list[dict] = []

        standups = [
            {
                "id": "weekly-1",
                "workspace_key": "shared_ops",
                "status": "completed",
                "created_at": "2026-04-21T04:32:38Z",
                "payload": {
                    "standup_kind": "weekly_review",
                    "decisions": [
                        "Create or queue `Promote Codex Chronicle into durable memory` on the PM board.",
                    ],
                },
            }
        ]
        cards = [
            {
                "id": "existing-shared",
                "title": "Promote Codex Chronicle into durable memory",
                "payload": {"workspace_key": "shared_ops"},
            },
            {
                "id": "wrong-workspace",
                "title": "Promote Codex Chronicle into durable memory",
                "payload": {"workspace_key": "fusion-os"},
            },
        ]

        def fake_fetch(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "PATCH":
                standup_payloads.append(payload or {})
                return {"ok": True}
            if url.endswith("/api/standups/?limit=80"):
                return standups
            if url.endswith("/api/pm/cards?limit=200"):
                return cards
            raise AssertionError(url)

        with mock.patch.object(self.dispatch, "_fetch_json", side_effect=fake_fetch), mock.patch.object(
            self.dispatch, "_now", return_value=self.dispatch.datetime.fromisoformat("2026-04-21T05:00:00+00:00")
        ):
            report = self.dispatch.build_report("https://example.test", lookback_days=2, limit=80, sync_live=True)

        self.assertEqual(report["created_count"], 0)
        self.assertEqual(report["standups"][0]["covered_card_ids"], ["existing-shared"])
        dispatch_payload = standup_payloads[0]["payload"]["post_sync_dispatch"]
        self.assertEqual(dispatch_payload["status"], "covered_by_existing_cards")
        self.assertEqual(dispatch_payload["covered_card_ids"], ["existing-shared"])
        self.assertEqual(dispatch_payload["candidate_titles"], ["Promote Codex Chronicle into durable memory"])

    def test_build_report_ignores_wrong_workspace_title_match(self) -> None:
        created_cards: list[dict] = []

        standups = [
            {
                "id": "weekly-1",
                "workspace_key": "shared_ops",
                "status": "completed",
                "created_at": "2026-04-21T04:32:38Z",
                "payload": {
                    "standup_kind": "weekly_review",
                    "decisions": [
                        "Create or queue `Promote Codex Chronicle into durable memory` on the PM board.",
                    ],
                },
            }
        ]
        cards = [
            {
                "id": "wrong-workspace",
                "title": "Promote Codex Chronicle into durable memory",
                "payload": {"workspace_key": "fusion-os"},
            },
        ]

        def fake_fetch(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "POST":
                created = {
                    "id": "created-shared",
                    "title": payload["title"],
                    "payload": payload["payload"],
                    "link_id": payload["link_id"],
                }
                created_cards.append(created)
                return created
            if method == "PATCH":
                return {"ok": True}
            if url.endswith("/api/standups/?limit=80"):
                return standups
            if url.endswith("/api/pm/cards?limit=200"):
                return cards
            raise AssertionError(url)

        with mock.patch.object(self.dispatch, "_fetch_json", side_effect=fake_fetch), mock.patch.object(
            self.dispatch, "_now", return_value=self.dispatch.datetime.fromisoformat("2026-04-21T05:00:00+00:00")
        ):
            report = self.dispatch.build_report("https://example.test", lookback_days=2, limit=80, sync_live=True)

        self.assertEqual(report["created_count"], 1)
        self.assertEqual(created_cards[0]["id"], "created-shared")
        self.assertEqual(report["standups"][0]["linked_card_ids"], ["created-shared"])


if __name__ == "__main__":
    unittest.main()
