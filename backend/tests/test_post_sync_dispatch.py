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

    def test_build_report_creates_workspace_followup_from_next_focus_when_idle(self) -> None:
        created_cards: list[dict] = []
        standup_payloads: list[dict] = []

        standups = [
            {
                "id": "fusion-standup-1",
                "workspace_key": "fusion-os",
                "status": "completed",
                "created_at": "2026-04-25T19:47:12Z",
                "commitments": [
                    "Bring the latest workspace briefing into the next standup and decide the next move from it.",
                ],
                "payload": {
                    "standup_kind": "workspace_sync",
                    "artifact_deltas": [
                        "Workspace briefing ready: /Users/neo/.openclaw/workspace/workspaces/fusion-os/briefings/20260418T021249Z_briefing.md",
                        "Audience feedback snapshot: /Users/neo/.openclaw/workspace/workspaces/fusion-os/analytics/instagram_public/instagram_public_feedback_summary.json",
                    ],
                    "standup_sections": {
                        "content_produced": [
                            "Execution log is available at `/Users/neo/.openclaw/workspace/workspaces/fusion-os/memory/execution_log.md` for ship-state review."
                        ],
                        "next_focus": [
                            "Ship a `Leadership POV` post in the next cycle so the weekly mix stays balanced."
                        ],
                        "opportunities_created": [
                            "`Leadership POV` has no recent visible post in the public sample, which leaves that narrative lane underrepresented."
                        ],
                    },
                },
            }
        ]
        cards: list[dict] = []

        def fake_fetch(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "POST":
                created = {
                    "id": "created-fusion",
                    "title": payload["title"],
                    "payload": payload["payload"],
                    "link_id": payload["link_id"],
                    "status": payload["status"],
                }
                created_cards.append(created)
                return created
            if method == "PATCH":
                standup_payloads.append(payload or {})
                return {"ok": True}
            if url.endswith("/api/standups/?limit=80"):
                return standups
            if url.endswith("/api/pm/cards?limit=200"):
                return cards
            raise AssertionError(url)

        with mock.patch.object(self.dispatch, "_fetch_json", side_effect=fake_fetch), mock.patch.object(
            self.dispatch, "_now", return_value=self.dispatch.datetime.fromisoformat("2026-04-25T20:00:00+00:00")
        ):
            report = self.dispatch.build_report("https://example.test", lookback_days=2, limit=80, sync_live=True)

        self.assertEqual(report["created_count"], 1)
        self.assertEqual(created_cards[0]["title"], "Ship a Leadership POV post in the next cycle so the weekly mix stays balanced")
        instructions = created_cards[0]["payload"].get("instructions") or []
        self.assertTrue(any("20260418T021249Z_briefing.md" in item for item in instructions))
        self.assertTrue(any("execution_log.md" in item for item in instructions))
        self.assertTrue(any("instagram_public_feedback_summary.json" in item for item in instructions))
        dispatch_payload = standup_payloads[0]["payload"]["post_sync_dispatch"]
        self.assertEqual(dispatch_payload["status"], "ok")
        self.assertEqual(dispatch_payload["candidate_titles"], ["Ship a Leadership POV post in the next cycle so the weekly mix stays balanced"])

    def test_build_report_skips_workspace_fallback_when_active_card_exists(self) -> None:
        standup_payloads: list[dict] = []
        standups = [
            {
                "id": "agc-standup-1",
                "workspace_key": "agc",
                "status": "completed",
                "created_at": "2026-04-25T19:47:17Z",
                "payload": {
                    "standup_kind": "workspace_sync",
                    "artifact_deltas": [
                        "Workspace briefing ready: /Users/neo/.openclaw/workspace/workspaces/agc/briefings/2026-04-18_first_opportunity_seed.md"
                    ],
                    "standup_sections": {
                        "opportunities_created": [
                            "The latest workspace briefing should be reviewed for the next concrete opportunity."
                        ]
                    },
                },
            }
        ]
        cards = [
            {
                "id": "active-agc-card",
                "title": "Existing AGC task",
                "status": "ready",
                "payload": {"workspace_key": "agc"},
            }
        ]

        def fake_fetch(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "POST":
                raise AssertionError("workspace fallback should not create a card when active PM work exists")
            if method == "PATCH":
                standup_payloads.append(payload or {})
                return {"ok": True}
            if url.endswith("/api/standups/?limit=80"):
                return standups
            if url.endswith("/api/pm/cards?limit=200"):
                return cards
            raise AssertionError(url)

        with mock.patch.object(self.dispatch, "_fetch_json", side_effect=fake_fetch), mock.patch.object(
            self.dispatch, "_now", return_value=self.dispatch.datetime.fromisoformat("2026-04-25T20:00:00+00:00")
        ):
            report = self.dispatch.build_report("https://example.test", lookback_days=2, limit=80, sync_live=True)

        self.assertEqual(report["created_count"], 0)
        dispatch_payload = standup_payloads[0]["payload"]["post_sync_dispatch"]
        self.assertEqual(dispatch_payload["status"], "no_action")
        self.assertEqual(dispatch_payload["candidate_titles"], [])

    def test_workspace_scope_alias_treats_feezie_and_linkedin_as_same_lane(self) -> None:
        self.assertTrue(self.dispatch._workspace_scope_matches("feezie-os", "linkedin-os"))
        self.assertTrue(self.dispatch._workspace_scope_matches("linkedin-os", "feezie-os"))
        self.assertFalse(self.dispatch._workspace_scope_matches("agc", "linkedin-os"))

    def test_build_card_payload_ignores_out_of_scope_execution_log_paths(self) -> None:
        payload = self.dispatch._build_card_payload(
            {
                "id": "easy-standup-1",
                "workspace_key": "easyoutfitapp",
                "payload": {
                    "participants": ["Jean-Claude", "Easy Outfit App Operator Agent"],
                    "source_paths": [
                        "/Users/neo/.openclaw/workspace/workspaces/linkedin-content-os/memory/execution_log.md",
                    ],
                    "artifact_deltas": [
                        "Workspace briefing ready: /Users/neo/.openclaw/workspace/workspaces/easyoutfitapp/briefings/2026-04-17_foundation.md",
                        "Workspace analytics note ready: /Users/neo/.openclaw/workspace/workspaces/easyoutfitapp/analytics/2026-04-17_baseline.md",
                    ],
                    "standup_sections": {
                        "next_focus": [
                            "Define the next concrete opportunity for Easy Outfit App from the latest briefing."
                        ]
                    },
                },
            },
            "Define next concrete opportunity for Easy Outfit App",
        )

        instructions = payload.get("instructions") or []
        artifacts_expected = payload.get("artifacts_expected") or []
        self.assertTrue(any("2026-04-17_foundation.md" in item for item in instructions))
        self.assertTrue(any("2026-04-17_baseline.md" in item for item in instructions))
        self.assertFalse(any("linkedin-content-os/memory/execution_log.md" in item for item in instructions))
        self.assertFalse(any("linkedin-content-os/memory/execution_log.md" in item for item in artifacts_expected))


if __name__ == "__main__":
    unittest.main()
