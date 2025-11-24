# LinkedIn PACER Strategy Integration

This document explains how to use the LinkedIn integration built into AI Clone to execute your PACER content strategy.

## Overview

The LinkedIn integration provides end-to-end support for:
1. **Content Research** - Find high-performing posts in your niches
2. **Content Drafting** - Generate post drafts aligned with PACER pillars
3. **Audience Targeting** - Discover and score prospects
4. **Outreach Generation** - Create personalized DMs and connection requests
5. **Content Scheduling** - Manage posting cadence
6. **Metrics Tracking** - Track engagement and learn what works

## API Endpoints

### 1. Content Research & Inspiration

#### Search LinkedIn Posts
```bash
POST /api/linkedin/search
```

Find high-performing LinkedIn posts to use as inspiration:

```json
{
  "query": "EdTech AI education technology",
  "industry": "Education",
  "max_results": 20,
  "sort_by": "engagement",
  "min_engagement_score": 10.0
}
```

**Response:** List of LinkedIn posts with engagement metrics, hashtags, and content.

#### Research Topics
```bash
POST /api/research/trigger
```

Research trending topics and insights:

```json
{
  "user_id": "your-user-id",
  "topic": "EdTech AI trends 2025",
  "industry": "Education"
}
```

**Response:** Research insights stored in Firestore at `users/{userId}/research_insights/`

### 2. Content Drafting

#### Generate Content Drafts
```bash
POST /api/linkedin/content/drafts/generate
```

Generate LinkedIn post drafts based on PACER pillars:

```json
{
  "user_id": "your-user-id",
  "pillar": "referral",  // or "thought_leadership", "stealth_founder", "mixed"
  "topic": "Supporting students with mental health challenges",
  "include_stealth_founder": false,
  "linked_research_ids": ["research_123"],
  "num_drafts": 3,
  "tone": "authentic and insightful"
}
```

**Response:** Multiple draft variants with:
- Post content
- Suggested hashtags
- Engagement hooks/questions
- Linked research insights

**Alternative: Generate Prompt for Manual Creation**
```bash
POST /api/linkedin/content/drafts/generate-prompt
```

Returns a prompt you can paste into ChatGPT/Claude for content generation, then use:
```bash
POST /api/linkedin/content/drafts/store
```

#### List Drafts
```bash
GET /api/linkedin/content/drafts?user_id=your-user-id&pillar=referral&status=draft
```

### 3. Audience Targeting

#### Discover Prospects
```bash
POST /api/prospects/discover
```

Find prospects in your target networks:

```json
{
  "user_id": "your-user-id",
  "industry": "Education",
  "location": "United States",
  "job_titles": ["School Administrator", "Mental Health Director"],
  "max_results": 50
}
```

**Response:** List of discovered prospects stored with `approval_status: "pending"`

#### Approve Prospects
```bash
POST /api/prospects/approve
```

```json
{
  "user_id": "your-user-id",
  "prospect_ids": ["prospect_123", "prospect_456"],
  "approval_status": "approved"
}
```

#### Score Prospects
```bash
POST /api/prospects/score
```

Score prospects based on fit, referral capacity, and signal strength:

```json
{
  "user_id": "your-user-id",
  "prospect_ids": ["prospect_123"],
  "audience_profile": {
    "target_pain_points": ["student mental health", "educational support"],
    "industry_focus": "Education"
  }
}
```

**Response:** Scored prospects with:
- `fit_score` (0-100)
- `referral_capacity` (0-100)
- `signal_strength` (0-100)
- `best_outreach_angle`

### 4. Outreach Generation

#### Generate Outreach Messages
```bash
POST /api/prospects/outreach
```

Generate personalized outreach for approved prospects:

```json
{
  "user_id": "your-user-id",
  "prospect_id": "prospect_123",
  "outreach_type": "dm",  // or "connection_request", "follow_up"
  "use_research_insights": true,
  "tone": "professional and authentic"
}
```

**Response:** Multiple outreach variants ready for review and sending.

### 5. Content Calendar & Scheduling

#### Schedule Content
```bash
POST /api/linkedin/content/calendar/schedule
```

Schedule a draft for publishing:

```json
{
  "user_id": "your-user-id",
  "draft_id": "draft_123",
  "scheduled_date": 1703980800,  // Unix timestamp
  "notes": "Post for Tuesday morning"
}
```

#### View Calendar
```bash
GET /api/linkedin/content/calendar?user_id=your-user-id&start_date=1703980800&end_date=1704566400
```

### 6. Engagement Metrics & Learning

#### Update Metrics
```bash
POST /api/linkedin/content/metrics/update
```

Record engagement metrics after posting:

```json
{
  "user_id": "your-user-id",
  "draft_id": "draft_123",
  "post_url": "https://linkedin.com/posts/...",
  "likes": 45,
  "comments": 12,
  "shares": 8,
  "reactions": {"like": 40, "love": 5},
  "profile_views": 23,
  "impressions": 500
}
```

#### Update Learning Patterns
```bash
POST /api/linkedin/content/metrics/update-learning-patterns?user_id=your-user-id&draft_id=draft_123
```

Tracks which pillars, hashtags, and topics perform best.

#### Get Draft Metrics
```bash
GET /api/linkedin/content/metrics/draft/{draft_id}?user_id=your-user-id
```

## Workflow Examples

### Month 1 Content Playbook

1. **Research Phase**
   ```bash
   # Research EdTech + AI niches
   POST /api/research/trigger
   # Search high-performing posts
   POST /api/linkedin/search
   ```

2. **Content Drafting**
   ```bash
   # Generate 3 drafts per pillar
   POST /api/linkedin/content/drafts/generate
   # Pillar: referral (40% of content)
   # Pillar: thought_leadership (50% of content)
   # Pillar: stealth_founder (10% of content)
   ```

3. **Review & Approve**
   - Review drafts in Firestore or via `GET /api/linkedin/content/drafts`
   - Edit as needed
   - Approve for scheduling

4. **Schedule Posts**
   ```bash
   # Schedule 2-3 posts per week
   POST /api/linkedin/content/calendar/schedule
   ```

5. **Track Engagement**
   ```bash
   # After posting, update metrics
   POST /api/linkedin/content/metrics/update
   # Learn from performance
   POST /api/linkedin/content/metrics/update-learning-patterns
   ```

### Prospecting Workflow

1. **Discover**
   ```bash
   POST /api/prospects/discover
   ```

2. **Review & Approve**
   ```bash
   POST /api/prospects/approve
   ```

3. **Score**
   ```bash
   POST /api/prospects/score
   ```

4. **Generate Outreach**
   ```bash
   POST /api/prospects/outreach
   ```

5. **Track Results**
   ```bash
   POST /api/learning/update-patterns
   ```

## PACER Pillar Distribution

- **Referral Network (40%)**: Private school admins, mental health professionals
- **Thought Leadership (50%)**: EdTech business leaders, AI-savvy executives
- **Stealth Founder (10%)**: Early adopters, investors, founders

## Content Guidelines

### Referral Pillar
- Target: Private school administrators, mental health professionals, treatment centers
- Goal: Build referral network
- Tone: Supportive, educational, resource-focused

### Thought Leadership Pillar
- Target: EdTech business leaders, AI-savvy executives
- Goal: Establish expertise
- Tone: Insightful, forward-thinking, data-driven

### Stealth Founder Pillar
- Target: Early adopters, investors, stealth founders
- Goal: Connect with like-minded entrepreneurs
- Tone: Authentic, story-driven, subtle (not salesy)
- Frequency: Use sparingly (5-10% of posts)

## Data Storage Structure

All data is stored in Firestore under `users/{userId}/`:

- `research_insights/` - Research summaries and insights
- `content_drafts/` - Generated post drafts
- `content_calendar/` - Scheduled posts
- `linkedin_metrics/` - Engagement metrics
- `prospects/` - Discovered and scored prospects
- `learning_patterns/` - Performance patterns (pillars, hashtags, topics)

## Next Steps

1. **Set up your user_id** - Use a consistent identifier across all API calls
2. **Run initial research** - Use `/api/research/trigger` to build your insight base
3. **Generate Month 1 content** - Create drafts for each pillar
4. **Discover your network** - Use `/api/prospects/discover` to find referral sources
5. **Schedule and post** - Use the calendar to manage your cadence
6. **Track and learn** - Update metrics and refine based on performance

## Integration with Existing Systems

- **Research**: Integrates with Perplexity + Firecrawl for content insights
- **LinkedIn Search**: Uses Google Custom Search + Firecrawl to find posts
- **Prospecting**: Uses Search API + Firecrawl to discover prospects
- **Learning**: Tracks patterns in content performance and outreach success

## Future Enhancements

- Direct LinkedIn API integration for automated posting (once compliant)
- Advanced LLM integration for automated content generation
- Real-time engagement tracking via LinkedIn API
- Automated follow-up workflows based on engagement


