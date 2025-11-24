# Weekly PACER Content Command - Enhanced Features

## Overview

The enhanced Weekly PACER system builds on the Daily PACER foundation with production-ready improvements:
- Enhanced request parameters (topic overrides, cached research)
- Structured LLM prompt templates for deterministic output
- DM templates for engagement conversion
- Weekly summary and learning endpoints
- Sample drafts ready for persistence

---

## New Endpoints

### 1. Generate Weekly PACER Posts

**Endpoint:** `POST /api/linkedin/content/drafts/generate_weekly_pacer`

**Request:**
```json
{
  "user_id": "string",
  "num_posts": 3,
  "include_stealth_founder": false,
  "topic_overrides": ["optional", "list", "of", "topics"],
  "use_cached_research": true
}
```

**Response:**
```json
{
  "success": true,
  "generated": 3,
  "draft_ids": ["draft_x", "draft_y", "draft_z"],
  "summary": [
    {"draft_id": "draft_x", "pillar": "referral", "topic": "..."},
    {"draft_id": "draft_y", "pillar": "thought_leadership", "topic": "..."}
  ],
  "drafts": [...]
}
```

**Key Features:**
- `topic_overrides`: Prioritize specific topics from your research or preferences
- `use_cached_research`: Use Firestore cache instead of API calls (cost optimization)
- Enhanced summary array for quick review
- Structured LLM prompt for more consistent output

---

### 2. Generate Engagement DM Templates

**Endpoint:** `POST /api/linkedin/content/engagement/generate_dm`

**Request:**
```json
{
  "user_id": "string",
  "prospect_name": "John",
  "engagement_type": "comment|connection|like",
  "topic": "optional topic they engaged with",
  "num_variants": 2
}
```

**Response:**
```json
{
  "success": true,
  "engagement_type": "comment",
  "variants": [
    {
      "variant": 1,
      "message": "Hi John, thanks for the comment — I appreciated..."
    },
    {
      "variant": 2,
      "message": "Thanks, John. Your note made me think..."
    }
  ]
}
```

**DM Template Types:**

**A. Comment → Move to DM**
- Variant 1: Invitation to 15-minute chat with resource sharing
- Variant 2: Quick call offer with one-pager

**B. New Connection**
- Variant 1: Resource sharing focused on referrals
- Variant 2: Intro call for partnership alignment

**C. Like Engagement**
- Variant 1: Question about their challenges
- Variant 2: One-pager offer

---

### 3. Generate Weekly Summary

**Endpoint:** `POST /api/linkedin/content/metrics/generate-weekly-summary`

**Request:**
```json
{
  "user_id": "string",
  "week_start_date": 1680000000  // optional, defaults to last 7 days
}
```

**Response:**
```json
{
  "success": true,
  "week_start": 1680000000,
  "week_end": 1680604800,
  "total_posts": 3,
  "top_pillar": "thought_leadership",
  "top_hashtags": [
    {
      "hashtag": "#EdTech",
      "total_engagement": 150,
      "avg_engagement": 50.0,
      "used_in_posts": 3
    }
  ],
  "suggested_topics": ["topic1", "topic2", ...],
  "avg_engagement_rate": 3.5
}
```

**What It Analyzes:**
- Top-performing pillar (by average engagement)
- Top 10 hashtags (sorted by total engagement)
- Suggested topics for next week (based on top pillar)
- Average engagement rate across all posts

**Recommended Schedule:** Run every Sunday night via cron

---

## Enhanced LLM Prompt Template

The new structured prompt ensures more deterministic, consistent output:

```
SYSTEM: You are an expert LinkedIn copywriter who writes concise, high-engagement posts for education leaders. Tone: expert, direct, inspiring. Max 180 words.

USER:
{
  "pillar": "referral|thought_leadership|stealth_founder",
  "topic": "short topic",
  "audience": "private school administrators...",
  "primary_goal": "drive referrals...",
  "constraints": {
    "length_words_max": 180,
    "include_hashtags": true,
    "hashtags_max": 5,
    "avoid_stealth_keywords": true,
    "cta_type": "question"
  }
}

TASK:
1) Output JSON only with fields:
{
  "content": "<post text>",
  "suggested_hashtags": ["#..."],
  "engagement_hook": "<question or CTA>",
  "estimated_read_time_secs": 10
}

2) Use template structure: Hook -> Insight -> Practical takeaways (1–3 bullets) -> CTA
3) Keep founder mentions subtle when pillar=stealth_founder
```

**Benefits:**
- More consistent output format
- Deterministic JSON responses
- Better token efficiency
- Clearer constraints for LLM

---

## Suggested Scheduling & Cadence

### Weekly Generation (Cron Job)

Run every **Monday 08:00 ET** to generate that week's 3 drafts:

```bash
# Example cron entry
0 8 * * 1 curl -X POST https://your-backend.up.railway.app/api/linkedin/content/drafts/generate_weekly_pacer \
  -H "Content-Type: application/json" \
  -d '{"user_id": "your-user-id", "num_posts": 3, "use_cached_research": true}'
```

### Suggested Posting Schedule (EST)

- **Tuesday 9:00 AM** — Thought Leadership
- **Wednesday 2:00 PM** — Thought Leadership / Operational Insight
- **Friday 9:00 AM** — Referral / Partner-facing Post

### Weekly Summary (Cron Job)

Run every **Sunday 11:00 PM ET**:

```bash
0 23 * * 0 curl -X POST https://your-backend.up.railway.app/api/linkedin/content/metrics/generate-weekly-summary \
  -H "Content-Type: application/json" \
  -d '{"user_id": "your-user-id"}'
```

---

## Rate-Limiting & Cost Strategy

### Optimizations:

1. **One LLM call per draft** (3 calls/week total)
2. **Cached research** — Set `use_cached_research: true` to use Firestore instead of API calls
3. **Weekly learning updates only** — Run summary endpoint once per week
4. **No LinkedIn scraping** — Manual paste reduces compliance risk

### Estimated Costs:

- **Weekly generation (3 posts):** ~$0.01-0.05 (Perplexity free tier)
- **Weekly summary:** Free (Firestore queries only)
- **DM templates:** Free (static templates, no LLM calls)

**Total monthly cost:** ~$0.04-0.20 (well within free tiers)

---

## Sample Drafts

Three ready-to-post drafts are available in `SAMPLE_DRAFTS_JSON_PAYLOADS.json`:

1. **Thought Leadership** - "AI as a co-teacher in K–12"
2. **Thought Leadership** - "Ethical guardrails when using AI in specialized education"
3. **Referral** - "Practical referral step for mental health pros"

**To persist them:**

```bash
curl -X POST 'https://your-backend.up.railway.app/api/linkedin/content/drafts/store' \
  -H 'Content-Type: application/json' \
  -d @SAMPLE_DRAFTS_JSON_PAYLOADS.json
```

Or use the `/store` endpoint with the JSON from that file.

---

## Workflow Example

### Week 1: Initial Setup

1. **Monday 8 AM** - Generate weekly drafts:
   ```bash
   POST /api/linkedin/content/drafts/generate_weekly_pacer
   ```

2. **Review & Schedule** - Review drafts, schedule for Tue/Wed/Fri

3. **Post & Track** - Post manually, then update metrics:
   ```bash
   POST /api/linkedin/content/metrics/update
   ```

4. **Sunday 11 PM** - Generate weekly summary:
   ```bash
   POST /api/linkedin/content/metrics/generate-weekly-summary
   ```

### Week 2: With Learning

1. **Monday 8 AM** - Generate with preferred topics from week 1:
   ```json
   {
     "user_id": "user-123",
     "num_posts": 3,
     "topic_overrides": ["topic from week 1 summary"],
     "use_cached_research": true
   }
   ```

2. **Engagement** - When someone comments:
   ```bash
   POST /api/linkedin/content/engagement/generate_dm
   {
     "prospect_name": "Sarah",
     "engagement_type": "comment",
     "topic": "AI in education"
   }
   ```

3. **Repeat** - Continue weekly cycle

---

## Files Modified/Created

1. **`backend/app/models/linkedin_content.py`** - Added new request/response models
2. **`backend/app/routes/linkedin_content.py`** - Added 3 new endpoints
3. **`SAMPLE_DRAFTS_JSON_PAYLOADS.json`** - Ready-to-use sample drafts
4. **`WEEKLY_PACER_ENHANCEMENTS.md`** - This documentation

---

## Comparison: Daily vs Weekly

| Feature | Daily PACER | Weekly PACER |
|---------|-------------|--------------|
| Endpoint | `/generate_daily_pacer` | `/generate_weekly_pacer` |
| Topic Overrides | ❌ | ✅ |
| Cached Research | ❌ | ✅ |
| Summary Array | ❌ | ✅ |
| DM Templates | ❌ | ✅ |
| Weekly Summary | ❌ | ✅ |
| Structured Prompt | Basic | Enhanced |

**Recommendation:** Use **Weekly PACER** for production. Daily PACER remains available for on-demand generation.

---

## Next Steps

1. ✅ **Test the endpoints** - Try generating weekly drafts
2. ✅ **Persist sample drafts** - Use the JSON payloads file
3. ✅ **Set up cron jobs** - Schedule weekly generation and summary
4. ✅ **Test DM templates** - Generate DM variants for engagement
5. ✅ **Start posting** - Use generated drafts and track metrics

---

## Support

All endpoints are production-ready and integrated with your existing Firestore schema. The system works seamlessly with your current research insights, learning patterns, and content drafts.

For questions or issues, check the logs at:
- `backend/server.log` (local)
- Railway logs (production)

