# Core Memory Snapshot Lane

This directory is the tracked restore lane for live core memory files under `memory/`.

Rules:

- Live runtime files stay at their original paths under `memory/`.
- Selected noisy runtime files are no longer tracked directly in git.
- Exact tracked copies live under dated snapshot folders here.
- `LATEST.json` points at the current snapshot readers should use as a fallback when a live runtime file is missing.

Create or refresh a snapshot:

```bash
python3 scripts/build_core_memory_snapshot.py --snapshot-id 2026-04-09
```

Restore live files from the tracked snapshot:

```bash
python3 scripts/restore_core_memory_snapshot.py --snapshot-id 2026-04-09
```

Current policy:

- `memory/persistent_state.md` and `memory/codex_session_handoff.jsonl` remain tracked for now because they are still the most central live control-plane files.
- Other high-churn markdown memory files can fall back to this snapshot lane when absent.
