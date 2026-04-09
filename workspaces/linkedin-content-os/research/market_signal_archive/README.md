# Market Signal Archive

This tracked archive preserves durable LinkedIn research signals without requiring every live runtime file to stay in git.

Each month has two artifacts:

- `<YYYY-MM>.jsonl`: structured manifest for application fallback
- `<YYYY-MM>.md`: markdown archive for human review and semantic retrieval

The live runtime lane remains:

- `research/market_signals/`

Archive files are refreshed automatically whenever a signal is written and can be repaired with:

```bash
python3 scripts/personal-brand/sync_market_signal_archive.py
```
