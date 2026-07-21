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
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return []
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
        created_payload = posted[0][1]["payload"]
        self.assertEqual((created_payload.get("execution") or {}).get("state"), "queued")
        self.assertTrue((created_payload.get("execution") or {}).get("queued_at"))
        self.assertEqual((created_payload.get("completion_contract") or {}).get("source"), "accountability_sweep")
        self.assertTrue(created_payload.get("acceptance_criteria"))

    def test_live_sweep_closes_followup_when_no_stale_cards_remain(self) -> None:
        cards = [
            {
                "id": "followup-1",
                "title": MODULE.FOLLOWUP_TITLE,
                "status": "todo",
                "source": MODULE.FOLLOWUP_SOURCE,
                "payload": {
                    "rerouted_card_ids": ["rerouted-1"],
                    "execution": {
                        "state": "ready",
                        "target_agent": "Jean-Claude",
                    }
                },
            },
            {
                "id": "rerouted-1",
                "title": "Recovered lane",
                "status": "review",
                "source": "standup:test",
                "payload": {
                    "execution": {
                        "state": "review",
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
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return []
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

    def test_live_sweep_keeps_followup_open_until_tracked_cards_reach_review_or_done(self) -> None:
        cards = [
            {
                "id": "followup-1",
                "title": MODULE.FOLLOWUP_TITLE,
                "status": "todo",
                "source": MODULE.FOLLOWUP_SOURCE,
                "payload": {
                    "rerouted_card_ids": ["rerouted-1"],
                    "execution": {
                        "state": "ready",
                        "target_agent": "Jean-Claude",
                    }
                },
            },
            {
                "id": "rerouted-1",
                "title": "Still in flight",
                "status": "todo",
                "source": "standup:test",
                "payload": {
                    "execution": {
                        "state": "queued",
                        "target_agent": "Jean-Claude",
                    }
                },
            },
        ]
        patched: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return []
            if method == "PATCH":
                patched.append((url, payload or {}))
                raise AssertionError("follow-up should stay open until tracked cards are healthy")
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
        self.assertEqual(patched, [])
        self.assertEqual(report["executive_followup_card"]["action"], "tracked")
        self.assertEqual(report["executive_followup_card"]["pending_card_ids"], ["rerouted-1"])

    def test_live_sweep_updates_existing_followup_without_resetting_active_execution_state(self) -> None:
        queue = [
            {
                "card_id": "review-1",
                "title": "Stale review lane",
                "workspace_key": "fusion-os",
                "execution_state": "review",
                "target_agent": "Fusion Systems Operator",
                "last_transition_at": "2026-03-30T00:00:00Z",
            }
        ]
        cards = [
            {
                "id": "followup-1",
                "title": MODULE.FOLLOWUP_TITLE,
                "status": "in_progress",
                "source": MODULE.FOLLOWUP_SOURCE,
                "payload": {
                    "execution": {
                        "state": "running",
                        "queued_at": "2026-04-10T00:00:00Z",
                        "last_transition_at": "2026-04-10T00:30:00Z",
                        "assigned_runner": "codex",
                        "executor_status": "running",
                        "executor_worker_id": "worker-123",
                    }
                },
            },
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
        ]
        patched: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return queue
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return []
            if method == "PATCH" and url.endswith("/api/pm/cards/review-1"):
                assert payload is not None
                patched.append((url, payload))
                return {"id": "review-1", "status": payload.get("status", "review")}
            if method == "PATCH" and url.endswith("/api/pm/cards/followup-1"):
                assert payload is not None
                patched.append((url, payload))
                return {"id": "followup-1", "status": payload.get("status", "in_progress")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["executive_followup_card"]["action"], "updated")
        self.assertEqual(len(patched), 2)
        followup_patch = next(payload for url, payload in patched if url.endswith("/api/pm/cards/followup-1"))
        execution = followup_patch["payload"]["execution"]
        self.assertEqual(execution["state"], "running")
        self.assertEqual(execution["queued_at"], "2026-04-10T00:00:00Z")
        self.assertEqual(execution["executor_worker_id"], "worker-123")
        self.assertEqual((followup_patch["payload"].get("completion_contract") or {}).get("source"), "accountability_sweep")

    def test_report_carries_brain_context_sources(self) -> None:
        brain_context = {
            "brain_signals": [
                {
                    "id": "signal-1",
                    "source_workspace_key": "shared_ops",
                    "summary": "Accountability sweep should cite Brain context.",
                    "review_status": "reviewed",
                }
            ],
            "portfolio_snapshot": {"workspaces": []},
            "source_intelligence": {
                "available": True,
                "counts": {"total": 1, "digested": 1, "reviewed": 0, "routed": 0},
            },
            "source_paths": ["/tmp/brain_signals.jsonl"],
        }

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return []
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return []
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=False,
            fetch_json=fake_fetch_json,
            brain_context=brain_context,
        )

        self.assertIn("/tmp/brain_signals.jsonl", report["source_paths"])
        self.assertTrue(any("Brain Signal" in item for item in report["brain_context_lines"]))
        self.assertIn("## Brain Context", MODULE._markdown_report(report))

    def test_live_sweep_creates_starvation_followup_for_completed_standup_without_output(self) -> None:
        standups = [
            {
                "id": "standup-1",
                "workspace_key": "feezie-os",
                "status": "completed",
                "created_at": "2026-04-27T00:00:00Z",
                "payload": {
                    "standup_kind": "workspace_sync",
                    "summary": "Feezie standup completed without downstream execution.",
                    "pm_recommendation_count": 1,
                },
            }
        ]
        posted: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return []
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return standups
            if method == "POST" and url.endswith("/api/pm/cards"):
                assert payload is not None
                posted.append((url, payload))
                return {"id": "starvation-followup-1", "status": payload.get("status", "todo")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["starved_standup_count"], 1)
        self.assertEqual(report["starved_standups"][0]["standup_id"], "standup-1")
        self.assertEqual(report["starved_standups"][0]["output_category"], "no_output")
        self.assertEqual(len(posted), 2)
        posted_titles = {payload["title"] for _, payload in posted}
        self.assertIn(MODULE.STANDUP_STARVATION_FOLLOWUP_TITLE, posted_titles)
        self.assertIn("Run the current FEEZIE owner-review packet and record decisions", posted_titles)
        remediation_payload = next(payload for _, payload in posted if payload["title"] != MODULE.STANDUP_STARVATION_FOLLOWUP_TITLE)
        self.assertEqual(remediation_payload["source"], "accountability_sweep:workspace_starvation:standup-1")
        self.assertEqual((remediation_payload["payload"].get("execution") or {}).get("state"), "queued")
        self.assertEqual(report["workspace_starvation_remediation_count"], 1)
        self.assertEqual(report["workspace_starvation_remediation_cards"][0]["action"], "created")
        self.assertEqual(report["standup_starvation_followup_card"]["action"], "created")

    def test_live_sweep_creates_direct_remediation_lane_for_starved_executive_standup(self) -> None:
        standups = [
            {
                "id": "standup-1",
                "workspace_key": "shared_ops",
                "status": "completed",
                "created_at": "2026-04-27T00:00:00Z",
                "payload": {
                    "standup_kind": "executive_ops",
                    "summary": "Executive standup ended without a qualifying downstream lane.",
                },
            }
        ]
        posted: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return []
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return standups
            if method == "POST" and url.endswith("/api/pm/cards"):
                assert payload is not None
                posted.append((url, payload))
                return {"id": payload.get("title", "posted-card"), "status": payload.get("status", "todo")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["starved_standup_count"], 1)
        self.assertEqual(report["workspace_starvation_remediation_count"], 1)
        self.assertEqual(len(posted), 2)
        posted_titles = {payload["title"] for _, payload in posted}
        self.assertIn(MODULE.STANDUP_STARVATION_FOLLOWUP_TITLE, posted_titles)
        self.assertIn("Resolve the carried Executive lane from the latest standup context", posted_titles)
        remediation_payload = next(payload for _, payload in posted if payload["title"] != MODULE.STANDUP_STARVATION_FOLLOWUP_TITLE)
        self.assertEqual(remediation_payload["source"], "accountability_sweep:workspace_starvation:standup-1")
        self.assertEqual(remediation_payload.get("link_type"), "standup")
        self.assertEqual(remediation_payload.get("link_id"), "standup-1")
        self.assertEqual((remediation_payload["payload"].get("execution") or {}).get("target_agent"), "Jean-Claude")
        self.assertEqual(report["workspace_starvation_remediation_cards"][0]["workspace_key"], "shared_ops")

    def test_starvation_guard_treats_low_value_placeholder_lane_as_starved(self) -> None:
        standups = [
            {
                "id": "standup-1",
                "workspace_key": "fusion-os",
                "status": "completed",
                "created_at": "2026-04-27T00:00:00Z",
                "payload": {
                    "standup_kind": "workspace_sync",
                    "summary": "Fusion standup only produced placeholder planning work.",
                },
            }
        ]
        cards = [
            {
                "id": "card-1",
                "title": "Define next concrete opportunity for Fusion",
                "status": "todo",
                "link_type": "standup",
                "link_id": "standup-1",
                "source": "standup:test",
                "payload": {
                    "created_from_standup_id": "standup-1",
                    "execution": {
                        "state": "queued",
                        "target_agent": "Fusion Systems Operator",
                    }
                },
            }
        ]

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return standups
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=False,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["starved_standup_count"], 1)
        self.assertEqual(report["starved_standups"][0]["output_category"], "low_value")
        self.assertEqual(report["starved_standups"][0]["low_value_titles"], ["Define next concrete opportunity for Fusion"])

    def test_live_sweep_closes_starvation_followup_when_standup_gets_qualifying_lane(self) -> None:
        standups = [
            {
                "id": "standup-1",
                "workspace_key": "feezie-os",
                "status": "completed",
                "created_at": "2026-04-27T00:00:00Z",
                "payload": {
                    "standup_kind": "workspace_sync",
                    "summary": "Feezie standup now has a real downstream lane.",
                },
            }
        ]
        cards = [
            {
                "id": "starvation-followup-1",
                "title": MODULE.STANDUP_STARVATION_FOLLOWUP_TITLE,
                "status": "todo",
                "source": MODULE.STANDUP_STARVATION_FOLLOWUP_SOURCE,
                "payload": {
                    "starved_standup_ids": ["standup-1"],
                    "execution": {
                        "state": "ready",
                        "target_agent": "Jean-Claude",
                    },
                },
            },
            {
                "id": "card-1",
                "title": "Draft the next Feezie SOP from the latest workspace briefing",
                "status": "todo",
                "link_type": "standup",
                "link_id": "standup-1",
                "source": "standup:test",
                "payload": {
                    "created_from_standup_id": "standup-1",
                    "execution": {
                        "state": "queued",
                        "target_agent": "Jean-Claude",
                    },
                },
            },
        ]
        patched: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return standups
            if method == "PATCH" and url.endswith("/api/pm/cards/starvation-followup-1"):
                assert payload is not None
                patched.append((url, payload))
                return {"id": "starvation-followup-1", "status": payload.get("status", "done")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["starved_standup_count"], 0)
        self.assertEqual(len(patched), 1)
        self.assertEqual(report["standup_starvation_followup_card"]["action"], "closed")
        self.assertEqual(report["standup_starvation_followup_card"]["status"], "done")

    def test_starvation_guard_ignores_fresh_and_strategy_only_standups(self) -> None:
        fresh_created_at = MODULE._iso(MODULE._now() - MODULE.timedelta(minutes=30))
        strategy_created_at = MODULE._iso(MODULE._now() - MODULE.timedelta(days=1))
        standups = [
            {
                "id": "standup-fresh",
                "workspace_key": "fusion-os",
                "status": "completed",
                "created_at": fresh_created_at,
                "payload": {
                    "standup_kind": "workspace_sync",
                },
            },
            {
                "id": "standup-strategy",
                "workspace_key": "shared_ops",
                "status": "completed",
                "created_at": strategy_created_at,
                "payload": {
                    "standup_kind": "saturday_vision",
                },
            },
        ]

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return []
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return standups
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=False,
            standup_age_minutes=120,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["starved_standup_count"], 0)

    def test_live_sweep_refreshes_low_value_workspace_placeholder_into_real_remediation_lane(self) -> None:
        standups = [
            {
                "id": "standup-1",
                "workspace_key": "fusion-os",
                "status": "completed",
                "created_at": "2026-04-27T00:00:00Z",
                "payload": {
                    "standup_kind": "workspace_sync",
                    "summary": "Fusion standup is still pointing at the same leadership POV move.",
                    "standup_sections": {
                        "next_focus": ["Ship a `Leadership POV` post in the next cycle so the weekly mix stays balanced."],
                    },
                },
            }
        ]
        cards = [
            {
                "id": "placeholder-1",
                "title": "Define next concrete opportunity for Fusion",
                "status": "todo",
                "link_type": "standup",
                "link_id": "standup-1",
                "source": "standup:test",
                "payload": {
                    "created_from_standup_id": "standup-1",
                    "execution": {
                        "state": "queued",
                        "target_agent": "Fusion Systems Operator",
                    },
                },
                "created_at": "2026-04-27T00:00:00Z",
                "updated_at": "2026-04-27T00:10:00Z",
            }
        ]
        patched: list[tuple[str, dict]] = []
        posted: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return standups
            if method == "PATCH" and url.endswith("/api/pm/cards/placeholder-1"):
                assert payload is not None
                patched.append((url, payload))
                return {"id": "placeholder-1", "status": payload.get("status", "todo"), "title": payload.get("title"), "payload": payload.get("payload", {})}
            if method == "POST" and url.endswith("/api/pm/cards"):
                assert payload is not None
                posted.append((url, payload))
                return {"id": payload.get("title", "card"), "status": payload.get("status", "todo")}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["workspace_starvation_remediation_count"], 1)
        self.assertEqual(report["workspace_starvation_remediation_cards"][0]["action"], "refreshed")
        self.assertEqual(len(patched), 1)
        refresh_payload = patched[0][1]
        self.assertEqual(refresh_payload["title"], "Schedule the next Fusion leadership POV move and capture proof")
        self.assertEqual(refresh_payload["source"], "accountability_sweep:workspace_starvation:standup-1")
        self.assertEqual((refresh_payload["payload"].get("execution") or {}).get("state"), "queued")
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0][1]["title"], MODULE.STANDUP_STARVATION_FOLLOWUP_TITLE)

    def test_live_sweep_closes_duplicate_workspace_starvation_lanes(self) -> None:
        cards = [
            {
                "id": "agc-new",
                "title": "Advance the next AGC opportunity lane from the latest workspace briefing",
                "status": "in_progress",
                "source": "accountability_sweep:workspace_starvation:standup-new",
                "payload": {
                    "workspace_key": "agc",
                    "accountability_starved_standup_id": "standup-new",
                    "execution": {
                        "state": "running",
                        "target_agent": "AGC Operator Agent",
                        "last_transition_at": "2026-04-29T20:49:21Z",
                    },
                },
                "created_at": "2026-04-29T20:49:21Z",
                "updated_at": "2026-04-29T20:49:29Z",
            },
            {
                "id": "agc-old",
                "title": "Advance the next AGC opportunity lane from the latest workspace briefing",
                "status": "in_progress",
                "source": "accountability_sweep:workspace_starvation:standup-old",
                "payload": {
                    "workspace_key": "agc",
                    "accountability_starved_standup_id": "standup-old",
                    "execution": {
                        "state": "running",
                        "target_agent": "AGC Operator Agent",
                        "last_transition_at": "2026-04-29T20:39:02Z",
                    },
                },
                "created_at": "2026-04-29T20:39:02Z",
                "updated_at": "2026-04-29T20:39:11Z",
            },
        ]
        patched: list[tuple[str, dict]] = []

        def fake_fetch_json(url: str, *, method: str = "GET", payload: dict | None = None):
            if method == "GET" and url.endswith("/api/pm/execution-queue?limit=200"):
                return []
            if method == "GET" and url.endswith("/api/pm/cards?limit=400"):
                return cards
            if method == "GET" and url.endswith("/api/standups/?limit=200"):
                return []
            if method == "PATCH" and "/api/pm/cards/" in url:
                assert payload is not None
                patched.append((url, payload))
                return {"id": url.rsplit("/", 1)[-1], "status": payload.get("status", "todo"), "title": "patched", "payload": payload.get("payload", {})}
            raise AssertionError(f"Unexpected call: {method} {url}")

        report = MODULE.build_report(
            "https://example.test",
            ready_age_minutes=90,
            review_age_hours=24,
            sync_live=True,
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(report["starved_standup_count"], 0)
        self.assertEqual(report["workspace_starvation_remediation_count"], 0)
        self.assertEqual(report["workspace_starvation_duplicate_cleanup_count"], 1)
        self.assertEqual(report["workspace_starvation_duplicate_cleanup_cards"][0]["card_id"], "agc-old")
        self.assertEqual(len(patched), 1)
        self.assertEqual(patched[0][0], "https://example.test/api/pm/cards/agc-old")
        self.assertEqual(patched[0][1]["status"], "done")
        self.assertEqual(patched[0][1]["payload"]["superseded_by_pm_card_id"], "agc-new")


if __name__ == "__main__":
    unittest.main()
