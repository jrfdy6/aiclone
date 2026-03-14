 # Phase 6 Roadmap

 ## Current context
1. Memory and context management for OpenClaw/Jarvis requires a full audit: compaction is distorting critical facts, search (QMD) is not triggered reliably, and raw memory/offline files need to be surfaced via learnings.md.
2. Heartbeat automation is firing every 30 minutes with a hefty system prompt (agents.md + tools + memory) and calling the expensive model (Kimmy or Sonnet) which has cost/tokens implications.
3. Frontend dashboard on Railway still attempts to load stale Next.js chunk hashes and is hitting mixed-content issues because the deployed build references `http://` API URLs.

## Phase 6 priorities
### Memory + context
- Implement and verify memory flush instructions so important facts persist to `memory/*.md` before compactions occur.
- Improve memory search (QMD) adoption by ensuring agent instructions check `learnings.md` and the memory files on each task.
- Audit `openclaw.json`, `agents.md`, `soul.md`, `tools.md` for redundant/ bloated prompt content; use Claude Code (or similar tooling) to trim them.

### Heartbeat
- Configure heartbeat window and `light_context` settings in `openclaw.json` so it only loads `heartbeat.md` and a cheaper model (Gemini 3.1 Flash Light or local Qwen) outside active hours.
- Ensure heartbeat environment variables and shared secrets remain clean; double-check any heartbeat cron scripts.

### Frontend deployment
- Redeploy the frontend with the latest commit so `_next/static/chunks/app/page-*.js` hashes match the bundle, and confirm CDN cache clears.
- Guarantee `NEXT_PUBLIC_API_URL` on Railway is `https://aiclone-production-32dc.up.railway.app` to eliminate Mixed Content errors.
- Consider adding a `cache-buster` label / comment to the deployment or `app/page.tsx` when triggering builds so clients always fetch the newest manifest.

## Next steps for the team
1. Verify Railway frontend build log matches the latest commit; re-trigger deploy if necessary and confirm chunk files exist by curling the `/_next/static/chunks/app` paths.
2. Re-run `npm run build` locally to produce the new hashes and share (or commit) the cache-buster change; push to GitHub so Railway sees a new SHA.
3. Follow up with the heartbeat and memory instructions above, and document outcomes in `HEARTBEAT_GUIDANCE.md`, `memory/*`, and `LEARNINGS.md` for traceability.

## Success criteria
- No more `ChunkLoadError` warnings in Chrome when visiting `/ops`, `/dashboard`, `/prospects`, etc.
- Heartbeat runs on the cheaper model only during active hours and logs show `light_context: true` without repeated compaction errors.
- Important facts persist to disk during memory flush turns, and `learnings.md` contains rules that prevent repeated mistakes.
