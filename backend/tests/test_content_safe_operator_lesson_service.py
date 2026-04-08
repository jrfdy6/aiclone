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
from app.services.content_safe_operator_lesson_service import (
    build_content_safe_operator_lessons_payload,
    render_content_safe_operator_lessons_markdown,
)


class ContentSafeOperatorLessonServiceTests(unittest.TestCase):
    def test_build_payload_generalizes_internal_details(self) -> None:
        operator_story_payload = {
            "generated_at": "2026-04-07T02:19:28Z",
            "signals": [
                {
                    "id": "sig-1",
                    "title": "Fusion lane proof",
                    "claim": "Start treating Turn Fusion OS delegated proof into a recurring workspace execution lane as a documented playbook instead of a one-off experiment.",
                    "proof": "SOP written to /Users/neo/.openclaw/workspace/workspaces/fusion-os/dispatch/proof.json and briefing written by Jean-Claude.",
                    "lesson": "Capturing the full dispatch to write-back loop in one doc stops redundant packets.",
                    "topic_tags": ["execution", "fusion-os", "openclaw", "workspace"],
                    "workspace_keys": ["fusion-os"],
                    "route": "content_reservoir",
                    "source_kind": "chronicle",
                    "created_at": "2026-04-07T02:19:28Z",
                },
                {
                    "id": "sig-2",
                    "title": "FEEZIE backlog lesson",
                    "claim": "Execution result recorded for Seed FEEZIE backlog from canonical persona and lived work.",
                    "proof": "Created /Users/neo/.openclaw/workspace/workspaces/linkedin-content-os/drafts/queue_01.md with the first eight FEEZIE queue items.",
                    "lesson": "FEEZIE backlog quality improves when queue items cite proof anchors and approval state.",
                    "topic_tags": ["content", "persona", "workspace"],
                    "workspace_keys": ["linkedin-content-os"],
                    "route": "persona_candidate",
                    "source_kind": "chronicle",
                    "created_at": "2026-04-07T02:18:28Z",
                },
                {
                    "id": "sig-3",
                    "title": "Ops only",
                    "claim": "Jean-Claude will tackle promotion boundary to ensure smooth workflow.",
                    "proof": "No current blockers identified.",
                    "lesson": "Keep watching the queue.",
                    "topic_tags": ["pm"],
                    "workspace_keys": ["shared_ops"],
                    "route": "keep_in_ops",
                    "source_kind": "daily_brief",
                    "created_at": "2026-04-07T02:17:28Z",
                },
            ],
        }

        payload = build_content_safe_operator_lessons_payload(
            workspace_key="linkedin-content-os",
            operator_story_payload=operator_story_payload,
        )

        lessons = payload.get("lessons") or []
        self.assertEqual(payload.get("workspace"), "linkedin-content-os")
        self.assertEqual((payload.get("counts") or {}).get("total"), 2)
        self.assertEqual(len(lessons), 2)
        serialized = json.dumps(lessons)
        self.assertNotIn("/Users/neo/", serialized)
        self.assertNotIn("fusion-os", serialized.lower())
        self.assertNotIn("Jean-Claude", serialized)
        self.assertIn("public_safe", serialized)
        self.assertNotIn("executive leadership", serialized.lower())
        self.assertNotIn("approval state", serialized.lower())
        self.assertNotIn("semantic gating", serialized.lower())
        first = lessons[0]
        self.assertTrue(first.get("macro_thesis"))
        self.assertTrue(first.get("public_proof"))
        self.assertIn(first.get("workspace_scope"), {"single_workspace_pattern", "shared_pattern", "cross_workspace_pattern"})
        markdown = render_content_safe_operator_lessons_markdown(payload)
        self.assertIn("# Content-Safe Operator Lessons", markdown)

    def test_workspace_snapshot_runtime_reads_content_safe_report(self) -> None:
        payload = {
            "generated_at": "2026-04-07T02:25:00Z",
            "workspace": "linkedin-content-os",
            "lessons": [
                {
                    "id": "lesson-1",
                    "macro_thesis": "If a process matters more than once, it probably needs a playbook.",
                    "public_takeaway": "Repeated work gets better when it is documented.",
                    "public_proof": "Recent system work turned repeated work into documented process.",
                    "safe_angle": "documentation",
                    "visibility": "public_safe",
                    "workspace_scope": "shared_pattern",
                    "source_kind": "chronicle",
                }
            ],
            "counts": {"total": 1, "by_angle": {"documentation": 1}},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "content_safe_operator_lessons_latest.json"
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(workspace_snapshot_module, "CONTENT_SAFE_OPERATOR_LESSONS_PATH", report_path):
                loaded = workspace_snapshot_module._runtime_snapshot_payload(
                    workspace_snapshot_module.SNAPSHOT_CONTENT_SAFE_OPERATOR_LESSONS
                )

        self.assertEqual((loaded or {}).get("counts", {}).get("total"), 1)


class ContentSafeOperatorLessonRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(brain.router)
        self.client = TestClient(app)

    def test_sync_route_persists_snapshot(self) -> None:
        payload = {
            "generated_at": "2026-04-07T02:25:00Z",
            "source": "content_safe_operator_lesson_distiller",
            "workspace_key": "linkedin-content-os",
            "lesson_count": 1,
            "source_snapshot_type": "operator_story_signals",
            "source_generated_at": "2026-04-07T02:19:28Z",
            "counts": {"total": 1, "by_angle": {"documentation": 1}},
            "lessons": [
                {
                    "id": "lesson-1",
                    "macro_thesis": "If a process matters more than once, it probably needs a playbook.",
                    "public_takeaway": "Repeated work gets better when it is documented.",
                    "public_proof": "Recent system work turned repeated work into documented process.",
                    "safe_angle": "documentation",
                    "visibility": "public_safe",
                    "workspace_scope": "shared_pattern",
                    "source_kind": "chronicle",
                }
            ],
        }
        with patch("app.routes.brain.upsert_snapshot", return_value={"id": "snapshot-2"}) as upsert_mock:
            response = self.client.post("/api/brain/content-safe-operator-lessons/sync", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Content-safe operator lessons stored.")
        args, kwargs = upsert_mock.call_args
        self.assertEqual(args[0], "linkedin-content-os")
        self.assertEqual(args[1], "content_safe_operator_lessons")
        self.assertEqual(kwargs["metadata"]["lesson_count"], 1)


if __name__ == "__main__":
    unittest.main()
