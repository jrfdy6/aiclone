# AI Clone Archive — Sensitive / High-Risk Items

> Reference list of files or directories that likely contain secrets, credentials, or binary cruft. Do **not** commit these into our active workspace or share externally without scrubbing.

## Environment & Credential Files
- `backend/.env`, `.env.bak`, `.env.backup`, `.env.example` — Firebase, Drive, Perplexity, LinkedIn, Railway tokens.
- `frontend/.env.local`, `.env.production`, `.env.*` — Next.js client/server env vars, API keys.
- `keys/` — placeholder today (`.gitkeep`) but intended home for service-account JSONs.
- `cursor_mcp_config.json` & `cursor_mcp_config.json.example` — MCP integrations often embed API keys.
- `LOCAL_DEVELOPMENT_API_KEY.md` / `ADD_API_KEY.md` — may reference secrets or instructions on storing them.
- `LLM.ext` — extension manifests frequently include auth tokens.

## Logs & Test Artifacts
- `backend/server.log`, `frontend/server.log`, `test_results*.json/txt`, `query_test_results.json`, `test_report_*.json` — can expose PII, LinkedIn queries, or API responses.
- `comprehensive_test*.txt` and `mom_groups_test*.txt` — contain scraped data (likely sensitive prospect info).

## Build/Binary Directories
- `.venv/` (Python virtualenv with site-packages).
- `frontend/node_modules/`, `frontend/.next/`, `frontend/.vercel/`, `.git/cursor/`, `.git/objects/`.
- Notebook exports (`notebooklm_ready/*.md`) are fine to read but should stay internal.

## Git History
- `.git/` is incomplete but still contains historical objects; treat every commit as potentially leaking tokens/passwords. Avoid pushing this raw history until it’s audited.

## Action Items
1. Keep these paths out of any commits to `workspace/` repos unless scrubbed.
2. When we extract specific secrets (e.g., Firebase service accounts), relocate them into our managed `secrets/` directory with documentation.
3. Before publishing any documentation derived from logs/test data, strip prospect names/emails.
