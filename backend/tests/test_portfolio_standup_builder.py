from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PortfolioStandupBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.builder = _load_module("build_portfolio_standups", SCRIPTS_ROOT / "ops" / "build_portfolio_standups.py")

    def _write_prep(self, root: Path, *, workspace_key: str = "feezie-os", standup_kind: str = "workspace_sync") -> Path:
        path = root / "prep.json"
        path.write_text(
            json.dumps(
                {
                    "prep_id": "prep-1",
                    "workspace_key": workspace_key,
                    "standup_kind": standup_kind,
                    "owner_agent": "jean-claude",
                    "summary": "Standup prep should become a completed decision record.",
                    "agenda": ["Route the current signal into the right next state."],
                    "blockers": [],
                    "commitments": [],
                    "needs": [],
                    "artifact_deltas": ["Brain context: test signal."],
                    "audience_response": [],
                    "standup_sections": {},
                    "source_paths": ["/tmp/source.md"],
                    "memory_promotions": [],
                    "pm_snapshot": {},
                    "strategy_context": {},
                    "strategy_context_lines": [],
                    "chronicle_entries": [{"workspace_key": workspace_key, "summary": "Recent test signal."}],
                    "standup_payload": {
                        "owner": "jean-claude",
                        "status": "prepared",
                        "blockers": [],
                        "commitments": [],
                        "needs": [],
                        "source": "codex-chronicle-standup-prep",
                        "conversation_path": "/tmp/prep.md",
                        "workspace_key": workspace_key,
                        "payload": {"standup_kind": standup_kind, "summary": "Prepared packet."},
                    },
                    "pm_updates": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_run_builder_promotes_prep_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prep_path = self._write_prep(Path(temp_dir))
            captured_posts: list[tuple[str, dict]] = []

            def fake_post(url: str, payload: dict):
                captured_posts.append((url, payload))
                return {"standup": {"id": "completed-1"}, "created_cards": [{"id": "card-1"}], "existing_cards": []}

            with (
                mock.patch.object(
                    self.builder.subprocess,
                    "run",
                    return_value=SimpleNamespace(
                        returncode=0,
                        stdout=f"summary\nJSON: {prep_path}\nMarkdown: {prep_path.with_suffix('.md')}\n",
                        stderr="",
                    ),
                ),
                mock.patch.object(self.builder, "_post_json", side_effect=fake_post),
            ):
                result = self.builder._run_builder(
                    self.builder.StandupTarget("feezie-os", "workspace_sync", 36),
                    api_url="https://example.test",
                    chronicle_limit=8,
                    create_entry=True,
                    promote_entry=True,
                )

        self.assertEqual(result["status"], "promoted")
        self.assertEqual(result["created_standup_id"], "completed-1")
        self.assertEqual(result["created_card_count"], 1)
        self.assertEqual(captured_posts[0][0], "https://example.test/api/standups/promote")
        self.assertEqual(captured_posts[0][1]["workspace_key"], "feezie-os")
        self.assertEqual(captured_posts[0][1]["standup_kind"], "workspace_sync")
        self.assertTrue(captured_posts[0][1]["discussion_rounds"])

    def test_run_builder_keeps_legacy_prepared_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prep_path = self._write_prep(Path(temp_dir))
            captured_posts: list[tuple[str, dict]] = []

            def fake_post(url: str, payload: dict):
                captured_posts.append((url, payload))
                return {"id": "prepared-1"}

            with (
                mock.patch.object(
                    self.builder.subprocess,
                    "run",
                    return_value=SimpleNamespace(
                        returncode=0,
                        stdout=f"summary\nJSON: {prep_path}\nMarkdown: {prep_path.with_suffix('.md')}\n",
                        stderr="",
                    ),
                ),
                mock.patch.object(self.builder, "_post_json", side_effect=fake_post),
            ):
                result = self.builder._run_builder(
                    self.builder.StandupTarget("feezie-os", "workspace_sync", 36),
                    api_url="https://example.test",
                    chronicle_limit=8,
                    create_entry=True,
                    promote_entry=False,
                )

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["created_standup_id"], "prepared-1")
        self.assertEqual(captured_posts[0][0], "https://example.test/api/standups/")
        self.assertEqual(captured_posts[0][1]["status"], "prepared")

    def test_build_portfolio_promotes_existing_prepared_standup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prep_path = self._write_prep(Path(temp_dir))
            existing = {
                "id": "prepared-1",
                "workspace_key": "feezie-os",
                "status": "prepared",
                "created_at": "2026-04-21T01:00:00Z",
                "payload": {"standup_kind": "workspace_sync", "prep_json_path": str(prep_path)},
            }

            with (
                mock.patch.object(self.builder, "_load_recent_standups", return_value=[existing]),
                mock.patch.object(
                    self.builder,
                    "_promote_prep_path",
                    return_value={
                        "created_standup_id": "completed-1",
                        "created_card_count": 0,
                        "existing_card_count": 0,
                        "created_card_ids": [],
                        "existing_card_ids": [],
                    },
                ),
            ):
                report = self.builder.build_portfolio_standups(
                    api_url="https://example.test",
                    limit=20,
                    chronicle_limit=8,
                    force=False,
                    create_entry=True,
                    promote_entry=True,
                    targets=(self.builder.StandupTarget("feezie-os", "workspace_sync", 36),),
                )

        self.assertEqual(report["counts"]["promoted"], 1)
        self.assertEqual(report["counts"]["skipped"], 0)
        self.assertEqual(report["results"][0]["status"], "promoted")
        self.assertEqual(report["results"][0]["reason"], "prepared_needs_promotion")
        self.assertEqual(report["results"][0]["promoted_from_standup_id"], "prepared-1")

    def test_build_portfolio_skips_fresh_completed_standup(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        existing = {
            "id": "completed-1",
            "workspace_key": "feezie-os",
            "status": "completed",
            "created_at": now,
            "payload": {"standup_kind": "workspace_sync"},
        }

        with (
            mock.patch.object(self.builder, "_load_recent_standups", return_value=[existing]),
            mock.patch.object(self.builder, "_run_builder") as run_builder,
        ):
            report = self.builder.build_portfolio_standups(
                api_url="https://example.test",
                limit=20,
                chronicle_limit=8,
                force=False,
                create_entry=True,
                promote_entry=True,
                targets=(self.builder.StandupTarget("feezie-os", "workspace_sync", 36),),
            )

        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertEqual(report["results"][0]["reason"], "fresh")
        run_builder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
