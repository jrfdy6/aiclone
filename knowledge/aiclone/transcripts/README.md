# Transcript Library

Central place to stash every audio/video transcript that feeds the build. Each entry gets:

1. **Raw file** (or link) – keep the original `.txt/.md/.json` somewhere stable (usually under `downloads/transcripts/`).
2. **Metadata sheet** – one Markdown file per transcript with:
   - Source (e.g., Goat OS Episode 1, Discord DM, voice memo)
   - Date received
   - Where it lives (path/URL)
   - Key themes / directives
   - Open tasks / follow-ups
   - Tags (ops, brain, lab, cron, design, etc.)
3. **Index** – `INDEX.md` stays at the root and references every transcript so we can scan what’s been processed.

## Workflow

1. Drop the raw transcript into `downloads/transcripts/` (or note the external URL).
2. Create a new metadata note inside `knowledge/aiclone/transcripts/` using the template in `TEMPLATE.md`.
3. Append a row to `INDEX.md` with the date, title, tags, and a one-line summary.
4. If the transcript spawns tasks, log them in the appropriate roadmap/backlog file and link back to the transcript entry.

Keep everything chronological so we can build a daily trail. EOF