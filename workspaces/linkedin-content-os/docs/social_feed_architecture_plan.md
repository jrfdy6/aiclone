# Social Feed Architecture Plan

This document defines the next-stage LinkedIn workspace build for a lower-capability agent that needs exact execution guidance.

Build both tracks:
- Option 1: production-safe hybrid feed
- Option 2: lab-only local browser capture feed

Option 1 becomes the system of record.
Option 2 is an opt-in enrichment lane behind an explicit lab flag.

## Objective

Create a LinkedIn-first workspace experience with:
- a staged unified feed at the top of the Workspace tab
- high-signal posts from relevant people and relevant topics
- comment and repost draft actions
- owner-review controls that appear in the same lane once a real draft artifact exists
- a secondary original-post lane driven by weekly recommendations
- quote selection that creates an approved persona delta instead of only storing a loose note

## Current Live Status

As of the current production implementation:
- the Workspace social feed supports manual URL/text preview generation through `POST /api/workspace/ingest-signal`
- the Workspace UI now renders one unified lane that combines source decisions and owner-review drafts
- the feed uses `source_lifecycle` plus the owner-review queue to keep stage timing intact instead of flattening the workflow into one undifferentiated action set
- source-stage actions remain upstream, while only owner-review `approve` and `revise` queue Jean-Claude follow-up
- the Workspace is LinkedIn-first, but not LinkedIn-only; Reddit, Substack/RSS, web links, and manually pasted text should ultimately flow through the same interpretation path
- LinkedIn URL previews should prefer structured metadata extraction in this order:
  - JSON-LD `SocialMediaPosting` / `articleBody`
  - Open Graph / Twitter metadata
  - filtered body-text fallback
- the frontend feed UI in `frontend/app/ops/OpsClient.tsx` exposes separate lanes for:
  - `admissions`
  - `entrepreneurship`
  - `current-role`
  - `program-leadership`
  - `enrollment-management`
  - `ai`
  - `ops-pm`
  - `therapy`
  - `referral`
  - `personal-story`
- future work should tighten voice inside these lanes, not collapse them back into broader combined buckets
- future work should also split extraction, interpretation, belief contrast, technique selection, rendering, and evaluation into separate layers instead of growing a single preview service

## Shared Signal Architecture

Manual preview capture and harvested feed capture are different ingest paths, but they should converge into one shared internal contract before interpretation.

Target pattern:

```text
manual url/text capture ----\
                             -> NormalizedSignal -> lane interpretation -> copy generation
harvested feed sources -----/
```

The deeper implementation map for that system now lives in:
- `docs/social_intelligence_architecture.md`

Use that document when the work is about:
- cross-channel source handling
- belief modeling
- technique selection
- evaluation
- tuning dashboard design

## Constraint Summary

These constraints informed the two-track design:
- LinkedIn supports posting and some member analytics, but not a supported personal home-feed read API for this use case.
- LinkedIn is the highest-priority content source for this workspace.
- Reddit and RSS-based sources such as Substack are much easier to ingest safely.
- Because of the LinkedIn constraint, the production-safe track should not depend on unsupported feed scraping.
- If we still want visible-post capture from LinkedIn, that should be a local lab-only capture lane with explicit owner approval and clear risk labeling.

## Existing System Anchors

Read these files before implementing anything in this plan:
- `workspaces/linkedin-content-os/docs/linkedin_curation_workflow.md`
- `workspaces/linkedin-content-os/docs/research_intake.md`
- `workspaces/linkedin-content-os/docs/market_intelligence.md`
- `workspaces/linkedin-content-os/research/watchlists.yaml`
- `workspaces/linkedin-content-os/plans/weekly_plan.json`
- `workspaces/linkedin-content-os/plans/reaction_queue.json`
- `frontend/app/ops/OpsClient.tsx`
- `scripts/personal-brand/refresh_linkedin_strategy.py`
- `scripts/personal-brand/curate_linkedin_signal.py`
- `scripts/personal-brand/generate_linkedin_weekly_plan.py`
- `scripts/personal-brand/generate_linkedin_reaction_queue.py`
- `backend/app/routes/persona.py`
- `backend/app/models/persona.py`

## Shared UX Target

Both options should feed the same UI.

### Top of Workspace
- staged unified feed is first
- LinkedIn cards rank above every other platform
- each card shows:
  - platform
  - author
  - recency
  - engagement snapshot when available
  - standout line or excerpt
  - why this matters
  - original source link

### Card Actions
- source-stage cards:
  - `Open original`
  - `Draft comment`
  - `Draft repost`
  - `Approve line to persona`
  - feedback logging for like / dislike / reject / copy / quote approval
- owner-review cards:
  - `Approve`
  - `Revise`
  - `Park`
  - notes entry
- keep stage-specific side effects intact even though the cards share one feed surface

### Weekly Recommendations
- stay downstream of the live unified feed
- remains the original-post lane
- continues using the existing weekly plan logic
- keeps lens and post-mode controls so the user can force an angle such as entrepreneurship, current job, program leadership, enrollment, AI, ops/project management, therapy, referral, or personal story

## Shared Quote-To-Persona Rule

When the user clicks a strong line:
- do not write directly into canonical persona files
- create a persona delta through `/api/persona/deltas`
- immediately update that delta through `PATCH /api/persona/deltas/{id}` so the status becomes `approved`
- store the source metadata in `metadata`
- let the normal persona promotion flow handle canonical file updates later

Recommended create payload shape:

```json
{
  "persona_target": "feeze.core",
  "trait": "Approved social language - short human-readable label",
  "notes": "Exact selected line plus one sentence on why it matters.",
  "metadata": {
    "target_file": "identity/VOICE_PATTERNS.md",
    "review_source": "linkedin_workspace.feed_quote",
    "approval_state": "pending_workspace_approval_write",
    "platform": "linkedin",
    "author": "Author Name",
    "source_url": "https://...",
    "source_path": "workspaces/linkedin-content-os/research/market_signals/...",
    "selected_line": "Exact line clicked by the user",
    "selected_context": "Optional surrounding sentence",
    "workspace": "linkedin-content-os",
    "tags": ["voice", "social-feed", "approved-quote"]
  }
}
```

Recommended follow-up patch payload:

```json
{
  "status": "approved",
  "metadata": {
    "approval_state": "approved_from_workspace",
    "last_reviewed_at": "2026-03-22T17:00:00Z",
    "review_source": "linkedin_workspace.feed_quote"
  }
}
```

If the line is more belief-oriented than voice-oriented, change `target_file` to one of:
- `identity/philosophy.md`
- `identity/audience_communication.md`
- `prompts/channel_playbooks.md`
- `history/story_bank.md`

## Shared Feed Artifact Contract

Create these new workspace artifacts:
- `workspaces/linkedin-content-os/plans/social_feed.json`
- `workspaces/linkedin-content-os/plans/social_feed.md`

Recommended JSON contract:

```json
{
  "generated_at": "2026-03-22T17:00:00Z",
  "workspace": "linkedin-content-os",
  "strategy_mode": "production",
  "items": [
    {
      "id": "linkedin__author__slug",
      "platform": "linkedin",
      "source_lane": "priority_network_manual",
      "capture_method": "manual_url",
      "title": "Short title",
      "author": "Author Name",
      "source_url": "https://...",
      "source_path": "workspaces/linkedin-content-os/research/market_signals/...",
      "published_at": "2026-03-22T13:15:00Z",
      "captured_at": "2026-03-22T14:03:00Z",
      "summary": "One-paragraph summary",
      "standout_lines": [
        "Line one",
        "Line two"
      ],
      "engagement": {
        "likes": 0,
        "comments": 0,
        "shares": 0
      },
      "ranking": {
        "priority_network": 0,
        "topic_match": 0,
        "recency": 0,
        "engagement": 0,
        "persona_fit": 0,
        "total": 0
      },
      "lenses": [
        "current-role",
        "ai",
        "ops-pm"
      ],
      "comment_draft": "Suggested comment",
      "repost_draft": "Suggested repost take",
      "lens_variants": {
        "current-role": {
          "label": "Current Job",
          "comment": "Lane-specific comment draft",
          "short_comment": "Lane-specific short reply",
          "repost": "Lane-specific repost draft"
        },
        "program-leadership": {
          "label": "Program Leadership",
          "comment": "Lane-specific comment draft",
          "short_comment": "Lane-specific short reply",
          "repost": "Lane-specific repost draft"
        }
      },
      "why_it_matters": "Why this belongs in Feeze's feed",
      "notes": "Any extra explanation"
    }
  ]
}
```

## Option 1

### Name
Production-safe hybrid feed

### Purpose
Build the real daily workspace feed without depending on unsupported LinkedIn feed scraping.

### What It Should Do
- rank saved LinkedIn signals first
- mix in Reddit, Substack, blogs, and other safe sources
- allow priority-network curation for followed people and connected people
- keep the feed fresh once per day
- preserve the existing manual-first safety model for LinkedIn capture

### Production Position
- this is the default
- this is the system of record
- all dashboards and analytics should treat this lane as authoritative

### Data Sources
- existing `research/market_signals/`
- existing `workspaces/linkedin-content-os/research/watchlists.yaml`
- manually curated LinkedIn URLs from watched people
- Reddit API inputs
- Substack RSS feeds
- blog/news RSS feeds
- optional approved LinkedIn connection exports if ever available

### New Or Updated Files

#### Workspace config
- update `workspaces/linkedin-content-os/research/watchlists.yaml`
  - add `priority_people`
  - add `priority_companies`
  - add `priority_publications`
  - add `priority_urls`
  - add lens tags per person when useful

#### Workspace artifacts
- add `workspaces/linkedin-content-os/plans/social_feed.json`
- add `workspaces/linkedin-content-os/plans/social_feed.md`
- optionally add `workspaces/linkedin-content-os/analytics/feed_source_notes.md`

#### Scripts to add
- `scripts/personal-brand/build_social_feed.py`
- `scripts/personal-brand/refresh_social_feed.py`
- `scripts/personal-brand/fetch_reddit_signals.py`
- `scripts/personal-brand/fetch_rss_signals.py`

#### Frontend files to change
- `frontend/app/ops/OpsClient.tsx`
- optional extraction target: `frontend/components/workspace/LinkedInSocialFeed.tsx`
- optional extraction target: `frontend/components/workspace/QuoteApprovalAction.tsx`

#### Backend or API changes
- use `POST /api/workspace/ingest-signal` for manual URL/text preview generation
- that route should return a `preview_item` that already contains lane-specific `lens_variants`
- LinkedIn ingestion should prefer structured metadata over naive first-paragraph scraping
- reuse `POST /api/persona/deltas`
- follow it with `PATCH /api/persona/deltas/{id}` to mark the new delta as `approved`
- if needed, add a thin typed helper in `frontend/lib/api-client.ts`

### Option 1 Implementation Order

#### Phase 0: Confirm the current baseline

Run:

```bash
cd /Users/neo/.openclaw/workspace
git status -sb
sed -n '1,220p' workspaces/linkedin-content-os/research/watchlists.yaml
sed -n '1,220p' workspaces/linkedin-content-os/docs/linkedin_curation_workflow.md
sed -n '1,260p' frontend/app/ops/OpsClient.tsx
```

Goal:
- confirm the current watchlist model
- confirm the existing workspace feed code
- confirm there is no existing `social_feed.json`

#### Phase 1: Extend the watchlist model

Edit:
- `workspaces/linkedin-content-os/research/watchlists.yaml`

Add these top-level sections:
- `priority_people`
- `priority_companies`
- `priority_publications`
- `priority_urls`
- `rss_sources`
- `reddit_sources`

Each `priority_people` entry should support:
- `name`
- `platform`
- `relationship`
- `reason`
- `lenses`
- `profile_url`
- `priority_weight`

Each `priority_urls` entry should support:
- `url`
- `author`
- `platform`
- `reason`
- `expires_at`

#### Phase 2: Build the feed compiler

Create:
- `scripts/personal-brand/build_social_feed.py`

Responsibilities:
- read `watchlists.yaml`
- read `plans/weekly_plan.json`
- read `plans/reaction_queue.json`
- read every file in `research/market_signals/`
- normalize them into the shared feed contract
- compute ranking scores
- output `plans/social_feed.json`
- output `plans/social_feed.md`

Scoring order:
- LinkedIn platform boost
- priority network weight
- topic/lens match
- recency
- engagement
- persona fit

Hard rule:
- LinkedIn items from watched people must outrank non-LinkedIn items when their scores are close

#### Phase 3: Add safe source fetchers

Create:
- `scripts/personal-brand/fetch_reddit_signals.py`
- `scripts/personal-brand/fetch_rss_signals.py`

Responsibilities:
- fetch configured Reddit sources
- fetch configured RSS sources such as Substack/blog/news
- convert strong items into normalized signal markdown files under `research/market_signals/`
- preserve `source_url`, `author`, `published_at`, and engagement data if available

Do not:
- scrape LinkedIn
- auto-comment on behalf of the user
- auto-post on behalf of the user

#### Phase 4: Create the refresh orchestrator

Create:
- `scripts/personal-brand/refresh_social_feed.py`

Responsibilities:
- optionally run the safe fetchers
- rebuild the feed artifacts
- run `refresh_linkedin_strategy.py` after new signals are stored

Recommended behavior:
- `--sources safe` runs Reddit/RSS only
- `--sources all` includes every non-lab source
- `--skip-fetch` rebuilds from existing local signals only

Recommended first command:

```bash
cd /Users/neo/.openclaw/workspace
python3 scripts/personal-brand/refresh_social_feed.py --skip-fetch
```

#### Phase 5: Connect the Workspace UI

Update:
- `frontend/app/ops/OpsClient.tsx`

UI order inside Workspace:
1. `Social feed`
2. `Comment and repost draft area`
3. `Weekly recommendations`
4. `Raw source files`

Requirements:
- read `social_feed.json`
- group by platform and source lane
- show a visible LinkedIn badge
- show engagement data when present
- show standout lines as clickable chips or blocks
- `Approve line to persona` should call `POST /api/persona/deltas`
- after create succeeds, it should call `PATCH /api/persona/deltas/{id}` with `status: approved`
- `Draft comment` uses the selected lens plus the source record
- `Draft repost` uses the selected lens plus the source record
- keep the weekly recommendation composer below the feed
- keep `current-role` distinct from `program-leadership`
- keep `ai` distinct from `ops-pm`
- keep `therapy` distinct from `referral`

#### Phase 6: Daily refresh automation

After the scripts are stable, wire a daily cron or automation that runs:

```bash
cd /Users/neo/.openclaw/workspace
python3 scripts/personal-brand/refresh_social_feed.py --sources safe
```

Keep the cron quiet unless:
- refresh fails
- source fetchers error out
- feed artifact generation fails

#### Phase 7: Validate and ship

Run:

```bash
cd /Users/neo/.openclaw/workspace
python3 scripts/personal-brand/refresh_social_feed.py --skip-fetch
python3 scripts/personal-brand/refresh_linkedin_strategy.py
npm --prefix frontend run build
git status -sb
```

Deploy:

```bash
cd /Users/neo/.openclaw/workspace
git add workspaces/linkedin-content-os frontend scripts
git commit -m "Add production-safe LinkedIn social feed pipeline"
git push origin main
./scripts/deploy_railway_service.sh frontend
```

### Option 1 Acceptance Criteria
- Workspace shows a social feed before weekly recommendations
- LinkedIn is visually first
- watched people and watched topics are visible in the feed
- comment and repost drafts are generated from feed cards
- quote approval creates an approved persona delta
- weekly recommendations still work
- a daily safe refresh can rebuild the feed without manual UI edits

### Option 1 Failure Conditions
- no visible distinction between LinkedIn and non-LinkedIn items
- the feed feels generated but cannot show original sources
- quote approval writes directly to canonical persona files
- the feed depends on unsupported LinkedIn scraping

## Option 2

### Name
Local authenticated browser-capture lane

### Purpose
Capture the real visible LinkedIn experience from the owner's authenticated local session when higher fidelity is worth the risk.

### Lab Position
- lab only
- explicit owner opt-in
- default off
- never the only feed lane

### What It Should Do
- capture visible LinkedIn posts from:
  - Home
  - Notifications
  - priority people pages
  - targeted search pages
- extract:
  - author
  - source URL
  - visible body text
  - standout lines
  - visible engagement counts
  - recency
- store them as normalized market signals
- merge them into the same Workspace feed with a visible `lab-browser` provenance badge

### Risk Rules
- no automatic likes
- no automatic comments
- no automatic reposts
- no hidden background browser capture
- no production cron without explicit owner approval
- any broken browser capture must fail without damaging Option 1

### Feature Flags

Add and default to off:
- `LINKEDIN_BROWSER_CAPTURE_ENABLED=0`
- `LINKEDIN_BROWSER_CAPTURE_MAX_POSTS=40`
- `LINKEDIN_BROWSER_CAPTURE_OWNER_SESSION_ONLY=1`
- `LINKEDIN_BROWSER_CAPTURE_ALLOW_HOME=1`
- `LINKEDIN_BROWSER_CAPTURE_ALLOW_NOTIFICATIONS=1`
- `LINKEDIN_BROWSER_CAPTURE_ALLOW_SEARCH=1`

### New Or Updated Files

#### Scripts to add
- `scripts/personal-brand/browser_capture/collect_linkedin_visible_posts.py`
- `scripts/personal-brand/browser_capture/normalize_linkedin_visible_posts.py`

#### Workspace artifacts
- reuse `research/market_signals/`
- optionally add `research/browser_capture/README.md` for raw capture debugging

#### Frontend
- no second feed UI
- same feed reads these items when `source_lane` is `browser_capture`
- render a `Lab` or `Browser Capture` badge

### Option 2 Implementation Order

#### Phase 0: Keep Option 1 working first

Do not start browser capture until Option 1 is already generating `social_feed.json`.

#### Phase 1: Build a local read-only capture

Create:
- `scripts/personal-brand/browser_capture/collect_linkedin_visible_posts.py`

Responsibilities:
- run only on the local machine
- use an already authenticated browser session
- collect visible posts only
- write raw captures to a temp or debug folder

Do not:
- post
- click engagement buttons
- navigate unpredictably

#### Phase 2: Normalize into market signals

Create:
- `scripts/personal-brand/browser_capture/normalize_linkedin_visible_posts.py`

Responsibilities:
- convert raw captured posts into the same signal format used by `research/market_signals/`
- include:
  - `source_lane: browser_capture`
  - `capture_method: browser_visible`
  - `source_platform: linkedin`

#### Phase 3: Merge into the shared feed

Update:
- `scripts/personal-brand/build_social_feed.py`
- `scripts/personal-brand/refresh_social_feed.py`

Behavior:
- when browser capture is enabled, include these items in `social_feed.json`
- keep them clearly labeled as lab-derived
- rank them highly because they are the closest approximation of the actual LinkedIn experience

#### Phase 4: Run manually

Example command sequence after these scripts exist:

```bash
cd /Users/neo/.openclaw/workspace
export LINKEDIN_BROWSER_CAPTURE_ENABLED=1
python3 scripts/personal-brand/browser_capture/collect_linkedin_visible_posts.py --limit 30
python3 scripts/personal-brand/browser_capture/normalize_linkedin_visible_posts.py
python3 scripts/personal-brand/refresh_social_feed.py --skip-fetch
npm --prefix frontend run build
```

#### Phase 5: Keep it opt-in

Do not attach this to a cron until:
- the owner explicitly asks for it
- the capture is stable
- the owner accepts the platform risk

### Option 2 Acceptance Criteria
- captured LinkedIn posts appear in the same feed UI
- items show a `lab-browser` or similar badge
- original post links are preserved
- comment/repost generation works from those cards
- disabling the feature flag removes the lane without breaking Option 1

### Option 2 Failure Conditions
- capture runs without explicit owner activation
- the lane becomes the only source of feed freshness
- UI cannot distinguish lab-derived vs production-safe items
- the system attempts direct LinkedIn interaction beyond read-only capture

## Recommended Rollout

Build in this order:
1. finish Option 1 feed artifact contract
2. finish Option 1 UI and quote approval
3. stabilize daily refresh
4. only then add Option 2 browser capture as a lab lane

## Lowest-Model Execution Checklist

If a smaller model has to execute this plan, tell it to do exactly this:

1. Read:
   - `workspaces/linkedin-content-os/docs/social_feed_architecture_plan.md`
   - `workspaces/linkedin-content-os/docs/linkedin_curation_workflow.md`
   - `frontend/app/ops/OpsClient.tsx`
   - `backend/app/routes/persona.py`
2. Implement Option 1 first.
3. Do not invent a new persona queue format. Reuse `POST /api/persona/deltas`.
4. Immediately patch the created delta to `approved`, because the create model does not accept `status`.
5. Do not add unsupported LinkedIn scraping to the production path.
6. Do not move weekly recommendations above the social feed.
7. After each code pass, run:

```bash
cd /Users/neo/.openclaw/workspace
python3 scripts/personal-brand/refresh_linkedin_strategy.py
npm --prefix frontend run build
git status -sb
```

8. Before deploy, verify:
- unified feed is first in Workspace
- feed cards expose original links
- quote approval calls persona delta API
- weekly recommendations are still visible below the feed

## Parking Lot

Not required in the first implementation pass:
- social post analytics dashboard
- DM analytics
- per-post likes/comments performance review
- automated recommendations on what Feeze should post more or less often
- direct canonical persona rewrites from the workspace UI

Those should come later after the feed and quote-approval loop are stable.
