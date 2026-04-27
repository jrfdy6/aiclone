# DUPLICATE_INVENTORY.md

This file tracks the overlap between the live workspace root and the `downloads/aiclone` archive so we can keep only one editable copy while preserving the reference snapshot.

## How it works
- The root-level markdown/json files are the “active” set you edit daily.
- Their clones under `workspace/downloads/aiclone/` are read-only archives; rely on `notes/aiclone-inventory.md` when you need the historic copy.
- The current extraction/retirement decision for the archive lives in `docs/downloads_aiclone_donor_boundary.md`.
- The scripts in `workspace/scripts/` (e.g., `list_duplicate_docs.py`) can refresh this list whenever the archive changes.

## High-level duplicates
| Filename | Live path | Archive path | Notes |
| --- | --- | --- | --- |
| `JOHNNIE_FIELDS_PERSONA*.md` | `workspace/JOHNNIE_FIELDS_PERSONA*.md` | `workspace/downloads/aiclone/JOHNNIE_FIELDS_PERSONA*.md` | Persona briefs—use the live files for updates and the archive for reference history.
| `PHASE_6_*` series | `workspace/PHASE_6_*.md` | `workspace/downloads/aiclone/PHASE_6_*.md` | Roadmaps/build notes—archive retains earlier drafts.
| `RAILWAY_*` guides | `workspace/RAILWAY_*.md` | `workspace/downloads/aiclone/RAILWAY_*.md` | Deployment docs—review both when prepping releases.
| `README.md` | `workspace/README.md` | `workspace/downloads/aiclone/README.md` and `/downloads/aiclone/automations/README.md` | Treat the root README as canonical and the others as references.
| `cursor_mcp_config.json` | `workspace/cursor_mcp_config.json` | `workspace/downloads/aiclone/cursor_mcp_config.json` | The archived config is useful for rollback.

## Next steps
1. Keep this sheet updated by running `python3 scripts/list_duplicate_docs.py` after any archive refresh.
2. When a live file becomes obsolete, either delete it or move it into `archive/` while leaving the `downloads/aiclone` copy untouched.
3. Do not edit the archive files directly—use the live versions so your agent’s memory search tracks the latest content.
