from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "personal-brand" / "linkedin_content_bank.py"


def load_module():
    spec = importlib.util.spec_from_file_location("linkedin_content_bank", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def latent_payload(*items: dict) -> dict:
    return {
        "generated_at": "2026-04-23T11:15:10+00:00",
        "workspace": "workspaces/linkedin-content-os",
        "summary": {"total": len(items)},
        "items": list(items),
    }


def drafted_item(**overrides: object) -> dict:
    item = {
        "idea_id": "idea-1",
        "title": "Workflow clarity beats model novelty",
        "score": 116.0,
        "source_kind": "external_signal",
        "content_lane": "ai",
        "content_type": "utility",
        "source_path": "workspaces/linkedin-content-os/research/market_signals/source-1.md",
        "source_url": "https://example.com/source-1",
        "latent_reason": "needs_context_translation",
        "suggested_fix": "The source needs an operator consequence before promotion.",
        "transform_status": "drafted",
        "draft_path": "workspaces/linkedin-content-os/drafts/workflow-clarity.md",
        "transform_plan": {
            "transform_type": "context_translation",
            "proposed_angle": "If the workflow is unclear, AI just scales confusion.",
            "proof_prompt": "AI Clone / Brain System",
            "promotion_rule": "Promote only with one concrete audience consequence.",
        },
    }
    item.update(overrides)
    return item


class LinkedInContentBankTests(unittest.TestCase):
    def test_banks_drafted_latent_transform_and_projects_backlog(self) -> None:
        module = load_module()
        fixed_now = datetime(2026, 4, 23, 11, 15, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace = repo_root / "workspaces" / "linkedin-content-os"
            draft = workspace / "drafts" / "workflow-clarity.md"
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text("# Workflow clarity beats model novelty\n", encoding="utf-8")
            (repo_root / "memory" / "runtime").mkdir(parents=True, exist_ok=True)
            (repo_root / "memory" / "runtime" / "LEARNINGS.md").write_text("# Learnings\n", encoding="utf-8")
            write_json(workspace / "plans" / "latent_ideas.json", latent_payload(drafted_item()))

            report = module.run_autonomous_content_bank(workspace_dir=workspace, repo_root=repo_root, now=fixed_now)

            self.assertEqual(report["summary"]["terminal_state"], "banked")
            self.assertEqual(report["summary"]["banked_count"], 1)
            posts = read_jsonl(workspace / "content_bank" / "posts.jsonl")
            events = read_jsonl(workspace / "content_bank" / "events.jsonl")
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]["status"], "banked")
            self.assertEqual(posts[0]["draft_path"], "workspaces/linkedin-content-os/drafts/workflow-clarity.md")
            self.assertIn("memory/runtime/LEARNINGS.md", posts[0]["canon_refs"])
            self.assertEqual(events[0]["terminal_state"], "banked")
            backlog = (workspace / "backlog.md").read_text(encoding="utf-8")
            self.assertIn("## Autonomous Content Bank", backlog)
            self.assertIn(posts[0]["id"], backlog)

    def test_duplicate_candidate_writes_terminal_event_without_rebanking(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace = repo_root / "workspaces" / "linkedin-content-os"
            draft = workspace / "drafts" / "workflow-clarity.md"
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text("# Workflow clarity beats model novelty\n", encoding="utf-8")
            write_json(workspace / "plans" / "latent_ideas.json", latent_payload(drafted_item()))

            module.run_autonomous_content_bank(
                workspace_dir=workspace,
                repo_root=repo_root,
                now=datetime(2026, 4, 23, 11, 15, tzinfo=timezone.utc),
            )
            second = module.run_autonomous_content_bank(
                workspace_dir=workspace,
                repo_root=repo_root,
                now=datetime(2026, 4, 23, 13, 15, tzinfo=timezone.utc),
            )

            posts = read_jsonl(workspace / "content_bank" / "posts.jsonl")
            events = read_jsonl(workspace / "content_bank" / "events.jsonl")
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(events), 2)
            self.assertEqual(second["summary"]["terminal_state"], "duplicate")
            self.assertEqual(second["summary"]["duplicate_count"], 1)
            self.assertEqual(second["summary"]["no_op_reason"], "All drafted latent-transform candidates were already banked.")

    def test_no_drafted_candidates_writes_no_op_status(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace = repo_root / "workspaces" / "linkedin-content-os"
            write_json(workspace / "plans" / "latent_ideas.json", latent_payload())

            report = module.run_autonomous_content_bank(
                workspace_dir=workspace,
                repo_root=repo_root,
                now=datetime(2026, 4, 23, 11, 15, tzinfo=timezone.utc),
            )

            events = read_jsonl(workspace / "content_bank" / "events.jsonl")
            self.assertEqual(report["summary"]["terminal_state"], "no_qualified_signal")
            self.assertEqual(report["summary"]["banked_count"], 0)
            self.assertEqual(events[0]["terminal_state"], "no_qualified_signal")
            status = json.loads((workspace / "reports" / "autonomous_loop_status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["summary"]["no_op_reason"], "No drafted latent-transform candidates were available to bank.")


if __name__ == "__main__":
    unittest.main()
