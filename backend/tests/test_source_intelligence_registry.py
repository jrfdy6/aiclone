from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


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
            source_root = repo_root / "knowledge" / "source-intelligence"
            transcript_root.mkdir(parents=True)
            (ingestion_root / "raw").mkdir(parents=True)
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

            payload = registry.build_source_intelligence_index(repo_root)
            registry.write_source_intelligence_index(payload, repo_root)

            self.assertEqual(payload["schema_version"], "source_intelligence_index/v1")
            self.assertEqual(payload["counts"]["total"], 2)
            self.assertEqual(payload["counts"]["routed"], 2)
            source_ids = {entry["source_id"] for entry in payload["sources"]}
            self.assertIn("agent-operating-note", source_ids)
            self.assertIn("ingestion-2026-04-agent_source", source_ids)
            index_path = source_root / "index.json"
            self.assertTrue(index_path.exists())
            self.assertTrue((source_root / "raw").exists())
            self.assertTrue((source_root / "normalized").exists())
            self.assertTrue((source_root / "digests").exists())
            self.assertTrue((source_root / "promotions").exists())


if __name__ == "__main__":
    unittest.main()
