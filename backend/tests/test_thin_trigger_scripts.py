from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThinTriggerScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.content_script = _load_module("enqueue_content_generation_job", SCRIPTS_ROOT / "enqueue_content_generation_job.py")
        cls.pm_script = _load_module("enqueue_pm_execution_card", SCRIPTS_ROOT / "enqueue_pm_execution_card.py")

    def test_content_request_payload_matches_thin_contract(self) -> None:
        args = types.SimpleNamespace(
            user_id="johnnie_fields",
            topic="workflow clarity",
            context="Use the operator angle.",
            content_type="linkedin_post",
            category="value",
            tone="expert_direct",
            audience="tech_ai",
            source_mode="persona_only",
            workspace_slug="linkedin-content-os",
        )

        payload = self.content_script.build_request_payload(args)

        self.assertEqual(payload["topic"], "workflow clarity")
        self.assertEqual(payload["workspace_slug"], "linkedin-content-os")
        self.assertEqual(payload["content_type"], "linkedin_post")
        self.assertTrue(payload["idempotency_key"])

    def test_content_request_payload_uses_stable_idempotency_key(self) -> None:
        args = types.SimpleNamespace(
            user_id="johnnie_fields",
            topic="workflow clarity",
            context="Use the operator angle.",
            content_type="linkedin_post",
            category="value",
            tone="expert_direct",
            audience="tech_ai",
            source_mode="persona_only",
            workspace_slug="linkedin-content-os",
        )

        first = self.content_script.build_request_payload(args)
        second = self.content_script.build_request_payload(args)

        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_pm_card_request_uses_workspace_defaults_for_delegated_workspace(self) -> None:
        args = types.SimpleNamespace(
            title="Turn the trigger flow into a reusable coding lane",
            workspace_key="fusion-os",
            owner=None,
            status="todo",
            source="openclaw:thin-trigger",
            source_agent="Neo",
            requested_by="Neo",
            manager_agent=None,
            target_agent=None,
            workspace_agent=None,
            execution_mode=None,
            execution_state="queued",
            lane="codex",
            assigned_runner="codex",
            reason="Ship the delegated coding trigger.",
            instruction=["Use the PM card as the source of truth."],
            acceptance_criterion=["Card appears in delegated queue."],
            artifact=["dispatch note"],
            repo_path="/Users/neo/.openclaw/workspace",
            branch="main",
            sop_path="",
            briefing_path="",
        )

        payload = self.pm_script.build_card_request(args, now_iso="2026-04-05T12:00:00+00:00")

        self.assertEqual(payload["owner"], "Neo")
        self.assertEqual(payload["payload"]["workspace_key"], "fusion-os")
        self.assertEqual(payload["payload"]["front_door_agent"], "Neo")
        self.assertEqual(payload["payload"]["execution"]["manager_agent"], "Jean-Claude")
        self.assertEqual(payload["payload"]["execution"]["target_agent"], "Fusion Systems Operator")
        self.assertEqual(payload["payload"]["execution"]["workspace_agent"], "Fusion Systems Operator")
        self.assertEqual(payload["payload"]["execution"]["execution_mode"], "delegated")
        self.assertEqual(payload["payload"]["execution"]["state"], "queued")
        self.assertEqual(payload["payload"]["execution"]["queued_at"], "2026-04-05T12:00:00+00:00")
        self.assertEqual(payload["payload"]["downstream_route"]["manager_agent"], "Jean-Claude")
        self.assertEqual(payload["payload"]["downstream_route"]["target_agent"], "Fusion Systems Operator")
        self.assertEqual(payload["payload"]["downstream_route"]["workspace_agent"], "Fusion Systems Operator")
        self.assertEqual(payload["payload"]["downstream_route"]["execution_mode"], "delegated")
        self.assertTrue(str(payload["payload"]["trigger_key"]).startswith("openclaw:"))

    def test_pm_card_request_allows_direct_workspace_overrides(self) -> None:
        args = types.SimpleNamespace(
            title="Review the next executive coding task",
            workspace_key="shared_ops",
            owner="Neo",
            status="todo",
            source="openclaw:thin-trigger",
            source_agent="Neo",
            requested_by="Neo",
            manager_agent="Jean-Claude",
            target_agent="Jean-Claude",
            workspace_agent=None,
            execution_mode="direct",
            execution_state="ready",
            lane="codex",
            assigned_runner="codex",
            reason="Open a direct coding lane for Neo.",
            instruction=[],
            acceptance_criterion=[],
            artifact=[],
            repo_path="/Users/neo/.openclaw/workspace",
            branch="feature/thin-trigger",
            sop_path="/tmp/sop.md",
            briefing_path="/tmp/briefing.md",
        )

        payload = self.pm_script.build_card_request(args, now_iso="2026-04-05T12:30:00+00:00")

        self.assertEqual(payload["owner"], "Neo")
        self.assertEqual(payload["payload"]["scope"], "shared_ops")
        self.assertEqual(payload["payload"]["execution"]["manager_agent"], "Jean-Claude")
        self.assertEqual(payload["payload"]["execution"]["target_agent"], "Jean-Claude")
        self.assertEqual(payload["payload"]["execution"]["execution_mode"], "direct")
        self.assertNotIn("front_door_agent", payload["payload"])
        self.assertNotIn("queued_at", payload["payload"]["execution"])
        self.assertEqual(payload["payload"]["execution"]["sop_path"], "/tmp/sop.md")
        self.assertEqual(payload["payload"]["execution"]["briefing_path"], "/tmp/briefing.md")
        self.assertTrue(str(payload["payload"]["trigger_key"]).startswith("openclaw:"))


if __name__ == "__main__":
    unittest.main()
