from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes import brain
from app.services import workspace_snapshot_service as workspace_snapshot_module
from app.services.operator_story_signal_service import (
    build_operator_story_signals_payload,
    render_operator_story_signals_markdown,
)


class OperatorStorySignalServiceTests(unittest.TestCase):
    def test_build_payload_distills_bounded_story_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_root = Path(tmpdir) / "memory"
            reports_dir = memory_root / "reports"
            reports_dir.mkdir(parents=True)

            chronicle_entries = [
                {
                    "schema_version": "codex_chronicle/v1",
                    "entry_id": "chronicle-proof-1",
                    "created_at": "2026-04-06T23:09:43Z",
                    "source": "jean-claude-dispatch",
                    "workspace_key": "fusion-os",
                    "summary": "Jean-Claude opened a bounded Fusion execution lane and wrote the result back.",
                    "project_updates": [
                        "Execution memo written to /Users/neo/.openclaw/workspace/workspaces/fusion-os/docs/execution_lane.md"
                    ],
                    "learning_updates": ["Execution proof should travel with the PM card and the workspace artifact."],
                    "artifacts": ["/Users/neo/.openclaw/workspace/workspaces/fusion-os/docs/execution_lane.md"],
                    "tags": ["fusion-os", "workflow"],
                },
                {
                    "schema_version": "codex_chronicle/v1",
                    "entry_id": "chronicle-identity-1",
                    "created_at": "2026-04-06T23:41:35Z",
                    "source": "owner-review",
                    "workspace_key": "linkedin-content-os",
                    "summary": "Synced 2 new Codex history entries across 1 sessions.",
                    "identity_signals": ["Johnnie should sound like an operator, not a consultant."],
                    "mindset_signals": ["Favor direct language when the workflow proof is strong."],
                    "tags": ["linkedin-content-os", "persona"],
                },
                {
                    "schema_version": "codex_chronicle/v1",
                    "entry_id": "chronicle-chat-identity-1",
                    "created_at": "2026-04-06T23:49:35Z",
                    "source": "codex-history",
                    "workspace_key": "linkedin-content-os",
                    "summary": "Synced 1 new Codex history entry across 1 sessions.",
                    "identity_signals": ["I want the posts to sound more direct and less polished."],
                    "mindset_signals": ["That means the voice should be cleaner, not softer."],
                    "tags": ["linkedin-content-os", "persona"],
                },
                {
                    "schema_version": "codex_chronicle/v1",
                    "entry_id": "chronicle-noise-1",
                    "created_at": "2026-04-06T23:56:35Z",
                    "source": "codex-history",
                    "workspace_key": "shared_ops",
                    "summary": "Synced 1 new Codex history entries across 1 sessions.",
                    "tags": ["codex", "chronicle"],
                },
            ]
            (memory_root / "codex_session_handoff.jsonl").write_text(
                "\n".join(json.dumps(item) for item in chronicle_entries) + "\n",
                encoding="utf-8",
            )
            (memory_root / "persistent_state.md").write_text(
                """# Snapshot for April 6, 2026

### Snapshot
- The system is stable after the local execution rewrite.

### Automation Health
- Chronicle sync and PM execution both completed successfully.

### Findings
- Execution artifacts now close the loop faster than ad hoc summaries.

### Actions
- Keep the bounded packet pattern in place.
""",
                encoding="utf-8",
            )
            (memory_root / "daily-briefs.md").write_text(
                """# Daily Brief - April 6, 2026

## Summary
1. Local execution lanes are now writing real artifacts.
2. The PM board and Chronicle are staying aligned.

## Blockers/Alerts
- No current blockers. Continue watching write-back health.

## Follow-ups
- Review whether the new execution lane should become the standard.
""",
                encoding="utf-8",
            )
            (memory_root / "dream_cycle_log.md").write_text(
                """# Dream Cycle Log — April 6, 2026

## Overview
We focused on making the Codex and OpenClaw workflow read from the same real artifacts.

### Latest Codex Handoff Highlights
1. Workflow rewiring now reads the Codex handoff before stale context.
   - Decisions: use the Chronicle lane as the bridge.

### Learning and Action Items
- Keep the build story tied to the artifacts that prove it.

### Follow-Up Actions
- Use the new lane to inform future content framing.
""",
                encoding="utf-8",
            )
            (memory_root / "cron-prune.md").write_text(
                """Progress Pulse — 2026-04-06T21:43:00Z
Status: green
Highlights:
- Rewired OpenClaw brain jobs to read Codex handoff before stale control-session context.
- Fusion execution proof now lands in workspace docs.
Blockers:
- No significant blockers identified.
Follow-up: yes (Jean-Claude)
""",
                encoding="utf-8",
            )

            payload = build_operator_story_signals_payload(workspace_key="linkedin-content-os", memory_root=memory_root)

        counts = payload.get("counts") or {}
        signals = payload.get("signals") or []
        routes = {item.get("route") for item in signals if isinstance(item, dict)}
        source_kinds = {item.get("source_kind") for item in signals if isinstance(item, dict)}

        self.assertEqual(payload.get("workspace"), "linkedin-content-os")
        self.assertEqual(set(payload.get("source_paths") or {}), {
            "codex_session_handoff.jsonl",
            "persistent_state.md",
            "daily-briefs.md",
            "dream_cycle_log.md",
            "cron-prune.md",
        })
        self.assertGreaterEqual(counts.get("total", 0), 5)
        self.assertIn("content_reservoir", routes)
        self.assertIn("persona_candidate", routes)
        self.assertIn("keep_in_ops", routes)
        self.assertIn("chronicle", source_kinds)
        self.assertEqual(len([item for item in signals if isinstance(item, dict) and item.get("source_kind") == "chronicle"]), 3)
        proof_signal = next(item for item in signals if item.get("source_kind") == "chronicle" and item.get("route") == "content_reservoir")
        self.assertTrue(proof_signal.get("artifact_paths"))
        chat_signal = next(item for item in signals if item.get("claim") == "I want the posts to sound more direct and less polished.")
        self.assertEqual(chat_signal.get("route"), "keep_in_ops")
        markdown = render_operator_story_signals_markdown(payload)
        self.assertIn("# Operator Story Signals", markdown)
        self.assertIn("content_reservoir", markdown)

    def test_workspace_snapshot_runtime_reads_operator_story_report(self) -> None:
        payload = {
            "generated_at": "2026-04-07T01:00:00Z",
            "workspace": "linkedin-content-os",
            "signals": [
                {
                    "id": "sig-1",
                    "title": "Signal",
                    "claim": "Execution proof now lands in workspace docs.",
                    "proof": "Artifact written to the workspace docs lane.",
                    "lesson": "Keep the build story tied to proof.",
                    "route": "content_reservoir",
                    "source_kind": "chronicle",
                }
            ],
            "counts": {"total": 1, "by_route": {"content_reservoir": 1}},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "operator_story_signals_latest.json"
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(workspace_snapshot_module, "OPERATOR_STORY_SIGNALS_PATH", report_path):
                loaded = workspace_snapshot_module._runtime_snapshot_payload(
                    workspace_snapshot_module.SNAPSHOT_OPERATOR_STORY_SIGNALS
                )

        self.assertEqual((loaded or {}).get("counts", {}).get("total"), 1)


class OperatorStorySignalRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(brain.router)
        self.client = TestClient(app)

    def test_sync_route_persists_snapshot(self) -> None:
        payload = {
            "generated_at": "2026-04-07T01:00:00Z",
            "source": "operator_story_signal_distiller",
            "workspace_key": "linkedin-content-os",
            "signal_count": 1,
            "source_paths": {"codex_session_handoff.jsonl": "/tmp/codex.jsonl"},
            "counts": {"total": 1, "by_route": {"content_reservoir": 1}},
            "signals": [
                {
                    "id": "sig-1",
                    "title": "Signal",
                    "claim": "Execution proof now lands in workspace docs.",
                    "proof": "Artifact written to the workspace docs lane.",
                    "lesson": "Keep the build story tied to proof.",
                    "route": "content_reservoir",
                    "source_kind": "chronicle",
                }
            ],
        }
        with patch("app.routes.brain.upsert_snapshot", return_value={"id": "snapshot-1"}) as upsert_mock:
            response = self.client.post("/api/brain/operator-story-signals/sync", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Operator story signals stored.")
        upsert_mock.assert_called_once()
        args, kwargs = upsert_mock.call_args
        self.assertEqual(args[0], "linkedin-content-os")
        self.assertEqual(args[1], "operator_story_signals")
        self.assertEqual(kwargs["metadata"]["signal_count"], 1)


if __name__ == "__main__":
    unittest.main()
