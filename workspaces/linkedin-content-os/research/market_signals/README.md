# Market Signals Runtime Lane

`research/market_signals/` is the live runtime lane for harvested and manual signal markdown.

- Cron jobs and manual ingest write raw signal files here by path.
- These files remain available on disk for local retrieval and feed generation.
- Git does not track the raw `.md` files in this directory anymore.

Durable restore copies live in the tracked archive lane:

- `research/market_signal_archive/<YYYY-MM>.md`
- `research/market_signal_archive/<YYYY-MM>.jsonl`

If the runtime lane and archive lane drift, run:

```bash
python3 scripts/personal-brand/sync_market_signal_archive.py
```
