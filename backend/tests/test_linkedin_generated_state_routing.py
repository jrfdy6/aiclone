from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
PERSONAL_BRAND_ROOT = REPO_ROOT / "scripts" / "personal-brand"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT), str(PERSONAL_BRAND_ROOT), str(SCRIPTS_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.services import (  # noqa: E402
    brain_control_plane_service,
    brain_signal_intake_service,
    social_signal_archive_service,
    workspace_snapshot_service,
)
import source_intelligence_register_existing as source_registry  # noqa: E402


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class LinkedInGeneratedStateRoutingTests(unittest.TestCase):
    def test_market_archive_seeds_legacy_month_and_mutates_only_private_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspaces" / "linkedin-content-os"
            state_root = root / "private-state"
            signals = workspace / "research" / "market_signals"
            legacy_archive = workspace / "research" / "market_signal_archive"
            signals.mkdir(parents=True)
            legacy_archive.mkdir(parents=True)
            legacy_record = {
                "id": "2026-07-01__rss__legacy",
                "title": "Legacy fixture",
                "source_path": "research/market_signals/legacy.md",
                "published_at": "2026-07-01T12:00:00Z",
            }
            legacy_manifest = legacy_archive / "2026-07.jsonl"
            legacy_markdown = legacy_archive / "2026-07.md"
            legacy_manifest.write_text(json.dumps(legacy_record) + "\n", encoding="utf-8")
            legacy_markdown.write_text("# Legacy archive\n", encoding="utf-8")
            manifest_before = legacy_manifest.read_bytes()
            markdown_before = legacy_markdown.read_bytes()
            state_archive = state_root / "workspaces" / "feezie-os" / "research" / "market_signal_archive"
            state_archive.mkdir(parents=True)
            (state_archive / "2026-07.jsonl").write_text(
                json.dumps(
                    {
                        "id": "2026-07-01__rss__state-only",
                        "title": "State-only fixture",
                        "source_path": "research/market_signals/state-only.md",
                        "published_at": "2026-07-01T13:00:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            signal_path = signals / "2026-07-02__rss__new.md"
            signal_path.write_text(
                """---
title: New fixture
source_platform: rss
source_type: article
published_at: '2026-07-02T12:00:00Z'
summary: A safe test summary
---

# New fixture
""",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"AI_CLONE_STATE_ROOT": str(state_root)}):
                record = social_signal_archive_service.sync_market_signal_archive_entry(signal_path, workspace)
                records = social_signal_archive_service.load_market_signal_archive_records(workspace)

            self.assertTrue((state_archive / "2026-07.jsonl").exists())
            self.assertTrue((state_archive / "2026-07.md").exists())
            self.assertEqual(legacy_manifest.read_bytes(), manifest_before)
            self.assertEqual(legacy_markdown.read_bytes(), markdown_before)
            self.assertEqual(len(records), 3)
            self.assertEqual(record["archive_manifest_path"], "research/market_signal_archive/2026-07.jsonl")
            self.assertNotIn(str(state_root), json.dumps(record))

    def test_plans_drafts_and_backlog_use_state_with_legacy_fallback(self) -> None:
        qualification = _load_module(
            PERSONAL_BRAND_ROOT / "linkedin_idea_qualification.py",
            "linkedin_idea_qualification_state_test",
        )
        materialize = _load_module(
            PERSONAL_BRAND_ROOT / "materialize_latent_transform_drafts.py",
            "materialize_latent_transform_drafts_state_test",
        )
        content_bank = _load_module(
            PERSONAL_BRAND_ROOT / "linkedin_content_bank.py",
            "linkedin_content_bank_state_test",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspaces" / "linkedin-content-os"
            state_root = root / "private-state"
            legacy_backlog = workspace / "backlog.md"
            legacy_backlog.parent.mkdir(parents=True)
            legacy_backlog.write_text("# Canonical backlog seed\n", encoding="utf-8")
            _write_json(
                workspace / "plans" / "social_feed.json",
                {"generated_at": "2026-07-25T10:00:00Z", "items": []},
            )

            with patch.dict(os.environ, {"AI_CLONE_STATE_ROOT": str(state_root)}):
                qualification.load_or_build_idea_qualification_payload(workspace)
                draft_path = materialize._draft_path_for_title(workspace, "Private state fixture")
                state_workspace = state_root.resolve() / "workspaces" / "feezie-os"
                self.assertEqual(draft_path.parent.resolve(), (state_workspace / "drafts").resolve())

                draft_path.parent.mkdir(parents=True, exist_ok=True)
                draft_path.write_text("# Private state fixture\n", encoding="utf-8")
                _write_json(
                    state_workspace / "plans" / "latent_ideas.json",
                    {
                        "items": [
                            {
                                "idea_id": "fixture-1",
                                "title": "Private state fixture",
                                "content_lane": "ai",
                                "content_type": "utility",
                                "source_path": "workspaces/linkedin-content-os/research/market_signals/fixture.md",
                                "transform_status": "drafted",
                                "draft_path": (
                                    "workspaces/linkedin-content-os/drafts/"
                                    f"{draft_path.name}"
                                ),
                                "transform_plan": {
                                    "proposed_angle": "A bounded fixture",
                                    "promotion_rule": "Owner review required",
                                },
                            }
                        ]
                    },
                )
                content_bank.run_autonomous_content_bank(
                    workspace_dir=workspace,
                    repo_root=root,
                    now=datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc),
                )

            self.assertTrue((state_workspace / "plans" / "idea_qualification.json").exists())
            self.assertTrue((state_workspace / "plans" / "idea_qualification.md").exists())
            self.assertFalse((workspace / "plans" / "idea_qualification.json").exists())
            self.assertEqual(legacy_backlog.read_text(encoding="utf-8"), "# Canonical backlog seed\n")
            state_backlog = (state_workspace / "backlog.md").read_text(encoding="utf-8")
            self.assertIn("# Canonical backlog seed", state_backlog)
            self.assertIn("## Autonomous Content Bank", state_backlog)

    def test_source_registry_reads_state_archive_but_emits_logical_repo_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspaces" / "linkedin-content-os"
            state_root = root / "private-state"
            signal = workspace / "research" / "market_signals" / "fixture.md"
            signal.parent.mkdir(parents=True)
            signal.write_text("# Fixture\n", encoding="utf-8")
            legacy_archive = workspace / "research" / "market_signal_archive"
            legacy_archive.mkdir(parents=True)
            (legacy_archive / "2026-07.jsonl").write_text(
                json.dumps(
                    {
                        "id": "legacy-fixture",
                        "title": "Legacy fixture",
                        "summary": "Legacy safe fixture summary",
                        "source_path": "research/market_signals/fixture.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state_archive = state_root / "workspaces" / "feezie-os" / "research" / "market_signal_archive"
            state_archive.mkdir(parents=True)
            (state_archive / "2026-07.jsonl").write_text(
                json.dumps(
                    {
                        "id": "fixture",
                        "title": "Fixture",
                        "summary": "Safe fixture summary",
                        "source_path": "research/market_signals/fixture.md",
                        "archive_markdown_path": "research/market_signal_archive/2026-07.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (state_archive / "2026-07.md").write_text("# Fixture archive\n", encoding="utf-8")

            with patch.dict(os.environ, {"AI_CLONE_STATE_ROOT": str(state_root)}):
                payload = source_registry.build_source_intelligence_index(root)

            market_entry = next(
                item for item in payload["sources"] if item.get("source_kind") == "feezie_market_signal"
            )
            market_entries = [
                item for item in payload["sources"] if item.get("source_kind") == "feezie_market_signal"
            ]
            self.assertEqual(len(market_entries), 2)
            self.assertEqual(
                market_entry["metadata_path"],
                "workspaces/linkedin-content-os/research/market_signal_archive/2026-07.jsonl",
            )
            self.assertEqual(
                market_entry["digest_path"],
                "workspaces/linkedin-content-os/research/market_signal_archive/2026-07.md",
            )
            self.assertNotIn(str(state_root), json.dumps(market_entry))

    def test_source_index_writes_state_and_backend_readers_prefer_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_root = root / "private-state"
            canonical_index = root / "knowledge" / "source-intelligence" / "index.json"
            canonical_index.parent.mkdir(parents=True)
            canonical_index.write_text(
                json.dumps(
                    {
                        "schema_version": "source_intelligence_index/v1",
                        "counts": {"total": 1},
                        "sources": [{"source_id": "canonical-fixture"}],
                    }
                ),
                encoding="utf-8",
            )
            canonical_before = canonical_index.read_bytes()
            payload = {
                "schema_version": "source_intelligence_index/v1",
                "counts": {"total": 2},
                "sources": [
                    {"source_id": "state-fixture-1"},
                    {"source_id": "state-fixture-2"},
                ],
            }

            with patch.dict(os.environ, {"AI_CLONE_STATE_ROOT": str(state_root)}):
                written_path = source_registry.write_source_intelligence_index(payload, root)
                intake_payload = brain_signal_intake_service.load_source_intelligence_index()
                control_payload = brain_control_plane_service._load_source_intelligence_index()

            expected = state_root.resolve() / "memory" / "source-intelligence" / "index.json"
            self.assertEqual(written_path.resolve(), expected)
            self.assertEqual(canonical_index.read_bytes(), canonical_before)
            self.assertEqual((intake_payload.get("counts") or {}).get("total"), 3)
            self.assertEqual(
                intake_payload.get("source_ref"),
                "knowledge/source-intelligence/index.json",
            )
            self.assertEqual((control_payload or {}).get("counts", {}).get("total"), 3)
            self.assertNotIn(str(state_root), json.dumps(payload))

    def test_automation_context_and_deploy_staging_prefer_only_explicit_state_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_root = Path(temp_dir) / "private-state"
            state_index = state_root / "memory" / "source-intelligence" / "index.json"
            state_index.parent.mkdir(parents=True)
            state_index.write_text("{}\n", encoding="utf-8")
            with patch.dict(os.environ, {"AI_CLONE_STATE_ROOT": str(state_root)}):
                context_module = _load_module(
                    SCRIPTS_ROOT / "brain_automation_context.py",
                    "brain_automation_context_state_test",
                )
            self.assertEqual(context_module.SOURCE_INDEX_PATH.resolve(), state_index.resolve())
            context_payload = context_module._read_source_index()
            self.assertEqual(
                context_payload.get("source_ref"),
                "knowledge/source-intelligence/index.json",
            )

        deploy_script = (SCRIPTS_ROOT / "deploy_railway_service.sh").read_text(encoding="utf-8")
        self.assertIn('memory/source-intelligence/index.json', deploy_script)
        self.assertIn("source_intelligence_cloud_projection.py", deploy_script)
        self.assertIn('--input "$index_source"', deploy_script)
        self.assertIn('--output "$destination_root/index.json"', deploy_script)
        self.assertIn(
            '"$destination_root/index.json" "$destination_root/index.json.txt"',
            deploy_script,
        )
        self.assertNotIn(
            'rsync_if_exists "$DATA_ROOT/knowledge/source-intelligence/"',
            deploy_script,
        )
        self.assertNotIn(
            'rsync_if_exists "$DATA_ROOT/knowledge/source-intelligence/README.md"',
            deploy_script,
        )
        self.assertNotIn(
            'rsync -a "$index_source" "$target_root/knowledge/source-intelligence/index.json"',
            deploy_script,
        )

    def test_deploy_stages_only_explicitly_shared_aiclone_transcript_packets(self) -> None:
        deploy_script = (SCRIPTS_ROOT / "deploy_railway_service.sh").read_text(encoding="utf-8")

        self.assertIn("stage_shared_aiclone_transcripts", deploy_script)
        self.assertIn("--include='*.shared_source_packet.json'", deploy_script)
        self.assertIn("--exclude='*'", deploy_script)
        self.assertIn("--exclude='transcripts/'", deploy_script)
        self.assertNotIn(
            'rsync_if_exists "$DATA_ROOT/knowledge/aiclone/transcripts/"',
            deploy_script,
        )

    def test_workspace_file_snapshot_prefers_state_file_for_same_logical_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_workspace = root / "state-workspace"
            legacy_workspace = root / "legacy-workspace"
            state_workspace.mkdir()
            legacy_workspace.mkdir()
            (state_workspace / "backlog.md").write_text("state projection\n", encoding="utf-8")
            (legacy_workspace / "backlog.md").write_text("legacy seed\n", encoding="utf-8")
            roots = [
                (state_workspace, "linkedin-content-os", "workspaces/linkedin-content-os"),
                (legacy_workspace, "linkedin-content-os", "workspaces/linkedin-content-os"),
            ]

            with patch.object(workspace_snapshot_service, "_workspace_file_roots", return_value=roots):
                files = workspace_snapshot_service._load_workspace_files()

            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]["path"], "workspaces/linkedin-content-os/backlog.md")
            self.assertEqual(files[0]["content"], "state projection\n")


if __name__ == "__main__":
    unittest.main()
