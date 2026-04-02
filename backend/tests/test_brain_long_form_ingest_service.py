from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.brain_long_form_ingest_service import brain_long_form_ingest_service


class BrainLongFormIngestServiceTests(unittest.TestCase):
    def test_register_source_writes_structured_digest_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            ingestions_root = repo_root / "knowledge" / "ingestions"
            ingestions_root.mkdir(parents=True, exist_ok=True)

            transcript = """
WEBVTT

00:00:00.000 --> 00:00:03.000
<00:00:00.320><c>Workflow</c><00:00:00.560><c> clarity</c><00:00:00.800><c> matters</c> more than tool abundance because operator judgment earns trust.
When my team called the customer, they were relieved a human answered the phone.
Use your tokens on meaningful work instead of noisy busywork.
"""

            with patch("app.services.brain_long_form_ingest_service.workspace_snapshot_module._ingestions_root", return_value=ingestions_root), patch(
                "app.services.brain_long_form_ingest_service.workspace_snapshot_module.ROOT",
                repo_root,
            ), patch(
                "app.services.brain_long_form_ingest_service.workspace_snapshot_module.workspace_snapshot_service.refresh_persisted_linkedin_os_state",
                return_value={},
            ):
                result = brain_long_form_ingest_service.register_source(
                    url="https://www.youtube.com/watch?v=test123",
                    title="Operator Judgment",
                    transcript_text=transcript,
                    summary="",
                    notes="What should route to persona?",
                    run_refresh=False,
                )

            normalized_path = repo_root / result["source_path"]
            raw = normalized_path.read_text(encoding="utf-8")
            self.assertIn("## Lessons Learned", raw)
            self.assertIn("## Key Anecdotes", raw)
            self.assertIn("## Reusable Quotes", raw)
            self.assertIn("## Open Questions", raw)
            self.assertNotIn("<00:00:00.320>", raw)
            self.assertIn("Workflow clarity matters more than tool abundance because operator judgment earns trust.", raw)

            frontmatter = raw.split("---", 2)[1]
            meta = yaml.safe_load(frontmatter)
            self.assertEqual(meta.get("summary_origin"), "derived_transcript")
            self.assertTrue(meta.get("structured_summary"))
            self.assertTrue(meta.get("lessons_learned"))
            self.assertTrue(meta.get("key_anecdotes"))
            self.assertTrue(meta.get("reusable_quotes"))

