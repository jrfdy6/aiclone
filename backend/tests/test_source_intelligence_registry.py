from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import source_intelligence_register_existing as registry  # noqa: E402


class SourceIntelligenceRegistryTests(unittest.TestCase):
    def test_registers_transcripts_and_ingestions_without_copying_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            transcript_root = repo_root / "knowledge" / "aiclone" / "transcripts"
            ingestion_root = repo_root / "knowledge" / "ingestions" / "2026" / "04" / "agent_source"
            linkedin_root = repo_root / "workspaces" / "linkedin-content-os"
            signal_root = linkedin_root / "research" / "market_signals"
            archive_root = linkedin_root / "research" / "market_signal_archive"
            source_root = repo_root / "knowledge" / "source-intelligence"
            transcript_root.mkdir(parents=True)
            (ingestion_root / "raw").mkdir(parents=True)
            signal_root.mkdir(parents=True)
            archive_root.mkdir(parents=True)
            source_root.mkdir(parents=True)

            transcript_path = transcript_root / "2026-04-19_agent-operating-note.md"
            transcript_path.write_text("# Agent Operating Note\n\nA transcript note about AI operating systems.\n", encoding="utf-8")
            transcript_path.with_suffix(".shared_source_packet.json").write_text(
                json.dumps(
                    {
                        "source_identity": {
                            "id": "agent-operating-note",
                            "source_url": "https://example.com/video",
                            "source_channel": "youtube",
                            "source_type": "transcript_note",
                            "source_class": "long_form_media",
                            "captured_at": "2026-04-19",
                        },
                        "source_understanding": {
                            "title": "Agent Operating Note",
                            "summary": "A structured digest about agent operations.",
                        },
                        "route_affordances": {"brain_review": True, "post_seed": True},
                    }
                ),
                encoding="utf-8",
            )

            (ingestion_root / "normalized.md").write_text("# Normalized Agent Source\n\nStructured extraction body.\n", encoding="utf-8")
            (ingestion_root / "raw" / "source.url").write_text("https://youtu.be/example\n", encoding="utf-8")
            (ingestion_root / "routing_status.json").write_text(json.dumps({"status": "routed"}), encoding="utf-8")

            signal_path = signal_root / "2026-04-20__rss__fixture.md"
            signal_path.write_text("# Fixture Market Signal\n\nA market signal worth reviewing.\n", encoding="utf-8")
            (archive_root / "2026-04.jsonl").write_text(
                json.dumps(
                    {
                        "id": "2026-04-20__rss__fixture",
                        "title": "Fixture Market Signal",
                        "summary": "A market signal worth reviewing.",
                        "source_path": "research/market_signals/2026-04-20__rss__fixture.md",
                        "source_platform": "rss",
                        "source_type": "article",
                        "source_url": "https://example.com/article",
                        "priority_lane": "ai",
                        "watchlist_matches": ["rss", "Fixture Feed"],
                        "created_at": "2026-04-20T12:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = registry.build_source_intelligence_index(repo_root)
            registry.write_source_intelligence_index(payload, repo_root)

            self.assertEqual(payload["schema_version"], "source_intelligence_index/v1")
            self.assertEqual(payload["counts"]["total"], 3)
            self.assertEqual(payload["counts"]["routed"], 3)
            source_ids = {entry["source_id"] for entry in payload["sources"]}
            self.assertIn("agent-operating-note", source_ids)
            self.assertIn("ingestion-2026-04-agent_source", source_ids)
            self.assertIn("market-signal-2026-04-20__rss__fixture", source_ids)
            market_entry = next(
                entry for entry in payload["sources"] if entry["source_id"] == "market-signal-2026-04-20__rss__fixture"
            )
            self.assertEqual(market_entry["source_kind"], "feezie_market_signal")
            self.assertEqual(market_entry["route_decision"]["workspace_key"], "feezie-os")
            self.assertTrue(market_entry["route_decision"]["route_affordances"]["brain_review"])
            transcript_entry = next(entry for entry in payload["sources"] if entry["source_id"] == "agent-operating-note")
            self.assertEqual(
                transcript_entry["sharing"],
                {
                    "classification": "shared",
                    "content_shareable": True,
                    "basis": "shared_source_packet",
                },
            )
            index_path = source_root / "index.json"
            self.assertTrue(index_path.exists())
            self.assertTrue((source_root / "raw").exists())
            self.assertTrue((source_root / "normalized").exists())
            self.assertTrue((source_root / "digests").exists())
            self.assertTrue((source_root / "promotions").exists())

    def test_index_write_is_lock_protected_and_atomically_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            index_path = repo_root / "knowledge" / "source-intelligence" / "index.json"
            index_path.parent.mkdir(parents=True)
            index_path.write_text(
                json.dumps(
                    {
                        "schema_version": "source_intelligence_index/v1",
                        "sources": [{"source_id": "existing", "status": "raw"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            old_bytes = index_path.read_bytes()
            real_replace = registry.os.replace
            observed: dict[str, object] = {}

            def inspect_then_replace(source: str | Path, destination: str | Path) -> None:
                observed["destination_before_replace"] = Path(destination).read_bytes()
                observed["temp_payload"] = json.loads(Path(source).read_text(encoding="utf-8"))
                real_replace(source, destination)

            with mock.patch.object(registry.os, "replace", side_effect=inspect_then_replace):
                written = registry.write_source_intelligence_index(
                    {
                        "schema_version": "source_intelligence_index/v1",
                        "sources": [{"source_id": "new", "status": "reviewed"}],
                    },
                    repo_root,
                )

            self.assertEqual(written, index_path)
            self.assertEqual(observed["destination_before_replace"], old_bytes)
            self.assertEqual(
                {
                    item["source_id"]
                    for item in (observed["temp_payload"] or {}).get("sources", [])
                },
                {"existing", "new"},
            )
            self.assertTrue(
                registry.sibling_lock_path(
                    index_path,
                    operation="source-index-write",
                ).exists()
            )
            self.assertFalse(list(index_path.parent.glob(".index.json.*.tmp")))


if __name__ == "__main__":
    unittest.main()
