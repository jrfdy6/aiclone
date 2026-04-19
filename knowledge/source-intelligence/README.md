# Source Intelligence

This folder is the intake lane for external learning material that may shape the AI Clone system over time.

Examples:
- video transcripts
- screenshots
- notes from operator-system videos
- strategic references
- examples that may influence `FEEZIE OS` or other workspaces later

Recommended structure:
- `raw/` for original source material
- `normalized/` for normalized source records and cross-source references
- `digests/` for structured summaries
- `promotions/` for approved memory / PM / pack promotion notes
- `index.json` for the canonical registry linking older transcript-library files, machine ingestions, digests, route decisions, and promotions

Rules:
- raw sources are not canonical memory
- digests should classify workspace relevance and actionability
- promotions should happen only after standup or explicit review
- `knowledge/ingestions/**` remains the machine-written staging area; do not copy it into a second ingest lane
- `scripts/source_intelligence_register_existing.py` registers existing sources into `index.json` without moving the source files

Reference:
- [source_intelligence_contract.md](/Users/neo/.openclaw/workspace/docs/source_intelligence_contract.md)
