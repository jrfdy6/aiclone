from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_source_asset_service import build_source_asset_inventory


class SocialSourceAssetServiceTests(unittest.TestCase):
    def test_placeholder_bullets_do_not_count_as_real_extractions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            ingestions_root = repo_root / "knowledge" / "ingestions" / "2026" / "04" / "placeholder_asset"
            transcripts_root = repo_root / "knowledge" / "aiclone" / "transcripts"
            ingestions_root.mkdir(parents=True, exist_ok=True)
            transcripts_root.mkdir(parents=True, exist_ok=True)

            (ingestions_root / "normalized.md").write_text(
                """---
id: placeholder_asset
title: Placeholder Asset
source_type: youtube_transcript
source_url: https://youtube.com/watch?v=abc123
topics: [transcript, youtube]
tags: [brain_ingest]
summary: This source needs review.
structured_summary: This source needs review.
lessons_learned: []
key_anecdotes: []
reusable_quotes: []
open_questions: []
---

# Structured Extraction

## Summary
This source needs review.

## Lessons Learned
- No clear lessons extracted yet.

## Key Anecdotes
- No strong anecdote extracted yet.

## Reusable Quotes
- No strong quote extracted yet.

## Open Questions
- What build implications matter, what persona implications matter, and what should be emphasized?

# Clean Transcript / Document
Workflow clarity matters more than tool abundance because operator judgment earns trust.
""",
                encoding="utf-8",
            )

            payload = build_source_asset_inventory(
                transcripts_root=transcripts_root,
                ingestions_root=repo_root / "knowledge" / "ingestions",
                repo_root=repo_root,
            )

            self.assertEqual(payload["counts"]["total"], 1)
            self.assertEqual(payload["counts"]["lessons_ready"], 0)
            self.assertEqual(payload["counts"]["anecdotes_ready"], 0)
            self.assertEqual(payload["counts"]["quotes_ready"], 0)

            asset = payload["items"][0]
            self.assertEqual(asset["lessons_learned"], [])
            self.assertEqual(asset["key_anecdotes"], [])
            self.assertEqual(asset["reusable_quotes"], [])

    def test_transcript_notes_get_voice_and_persona_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            ingestions_root = repo_root / "knowledge" / "ingestions"
            transcripts_root = repo_root / "knowledge" / "aiclone" / "transcripts"
            ingestions_root.mkdir(parents=True, exist_ok=True)
            transcripts_root.mkdir(parents=True, exist_ok=True)

            (transcripts_root / "persona_interview.md").write_text(
                """---
title: Persona Interview – Experience Relevance and Deep Voice Match
source: user interview
---

## Summary
- Johnnie explains how lived operator experience shapes trust.
""",
                encoding="utf-8",
            )
            (transcripts_root / "voice_proof.md").write_text(
                """---
title: 2026-03-30 user-provided-voice-proof-draft
source: voice memo
---

Guided voice/proof notes with phrase boundaries and cadence examples.
""",
                encoding="utf-8",
            )

            payload = build_source_asset_inventory(
                transcripts_root=transcripts_root,
                ingestions_root=ingestions_root,
                repo_root=repo_root,
            )

            by_title = {item["title"]: item for item in payload["items"]}
            interview = by_title["Persona Interview – Experience Relevance and Deep Voice Match"]
            voice_proof = by_title["2026-03-30 user-provided-voice-proof-draft"]

            self.assertEqual(interview["transcript_note_kind"], "persona_interview")
            self.assertEqual(interview["persona_use_mode"], "voice_and_experience")
            self.assertEqual(interview["voice_signal_priority"], "high")

            self.assertEqual(voice_proof["transcript_note_kind"], "voice_proof")
            self.assertEqual(voice_proof["persona_use_mode"], "voice_guidance_only")
            self.assertEqual(voice_proof["voice_signal_priority"], "high")


if __name__ == "__main__":
    unittest.main()
