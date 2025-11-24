# Prospecting Workflow API Documentation

Complete API documentation for the semi-autonomous, near-zero-cost AI sales assistant.

## Overview

This workflow connects research → discovery → scoring → outreach → learning in a closed loop system.

**Workflow Flow:**
```
Research (Manual) → Discovery (Semi-Auto) → Approval → Scoring (Hybrid) → Outreach → Learning Loop
```

---

## Environment Variables

### Required for Prospecting Workflow

**Google Custom Search API** (for prospect discovery):
- `GOOGLE_CUSTOM_SEARCH_API_KEY` - Get from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` - Create at [Programmable Search Engine](https://programmablesearchengine.google.com/)

**Already Configured:**
- `PERPLEXITY_API_KEY` - For research
- `FIRECRAWL_API_KEY` - For scraping
- `FIREBASE_SERVICE_ACCOUNT` - For Firestore

---

## API Endpoints

### Step 1: Research Trigger

#### `POST /api/research/trigger`

Manually trigger research on a topic/industry.

**Request:**
```json
{
  "user_id": "user123",
  "topic": "SaaS companies serving SMBs",
  "industry": "SaaS"
}
```

**Response:**
```json
{
  "success": true,
  "research_id": "research_1234567890",
  "status": "success",
  "summary": {
    "title": "SaaS companies serving SMBs",
    "industry": "SaaS",
    "summary": "Lightweight summary of trends...",
    "keywords": ["growth", "scaling", "saas"],
    "job_titles": ["VP", "Director"],
    "sources": [
      {"url": "https://...", "title": "..."}
    ]
  }
}
```

**Process:**
1. Perplexity searches the topic
2. Firecrawl scrapes top source URLs
3. AI extracts insights (keywords, job titles, trends, pains)
4. Stores lightweight summary in Firestore: `users/{userId}/research_insights/{researchId}`

---

### Step 2: Prospect Discovery

#### `POST /api/prospects/discover`

Discover prospects using Google Custom Search + Firecrawl.

**Request:**
```json
{
  "user_id": "user123",
  "company_name": "Acme Corp",
  "industry": "SaaS",
  "location": "San Francisco, CA",
  "job_titles": ["VP Sales", "Head of Growth"],
  "max_results": 50
}
```

**Response:**
```json
{
  "success": true,
  "discovered_count": 25,
  "prospects": [
    {
      "prospect_id": "prospect_1234567890_0",
      "user_id": "user123",
      "name": "John Doe",
      "email": "john@acme.com",
      "job_title": "VP Sales",
      "company": "Acme",
      "website": "https://acme.com",
      "linkedin": "https://linkedin.com/in/johndoe",
      "discovery_source": "SearchAPI + Firecrawl",
      "approval_status": "pending",
      "created_at": 1234567890.0
    }
  ]
}
```

**Process:**
1. Google Custom Search finds company pages
2. Firecrawl scrapes team/about pages
3. Extracts: name, email, job_title, LinkedIn
4. Stores as `approval_status: "pending"` in Firestore: `users/{userId}/prospects/{prospectId}`

#### `POST /api/prospects/approve`

Approve or reject discovered prospects.

**Request:**
```json
{
  "user_id": "user123",
  "prospect_ids": ["prospect_123", "prospect_456"],
  "approval_status": "approved"
}
```

**Response:**
```json
{
  "success": true,
  "approved_count": 2,
  "rejected_count": 0,
  "errors": []
}
```

---

### Step 3: Prospect Scoring

#### `POST /api/prospects/score`

Score prospects using hybrid approach (cached + query research).

**Request:**
```json
{
  "user_id": "user123",
  "prospect_ids": ["prospect_123", "prospect_456"],
  "audience_profile": {
    "brand_name": "My Company",
    "target_pain_points": ["scaling", "efficiency"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "scored_count": 2,
  "prospects": [
    {
      "prospect_id": "prospect_123",
      "fit_score": 85,
      "referral_capacity": 70,
      "signal_strength": 75,
      "best_outreach_angle": "Address pain points: scaling, efficiency",
      "scoring_reasoning": "High-value job title: VP Sales. Found 2 signal keyword(s) in prospect profile.",
      "cached_insights": {
        "industry_trends": ["trend1"],
        "trending_pains": ["pain1"],
        "signal_keywords": ["keyword1"],
        "last_updated": 1234567890.0
      }
    }
  ]
}
```

**Process:**
1. Retrieves cached insights from prospect document
2. Queries Firestore for research by `linked_research_ids` or industry
3. Merges cached + fresh research insights
4. Calculates multi-dimensional scores:
   - `fit_score` (0-100)
   - `referral_capacity` (0-100)
   - `signal_strength` (0-100)
   - `best_outreach_angle`
5. Caches key insights back to prospect document

---

### Step 4: Outreach Generation

#### `POST /api/outreach/manual/prompts/generate` (Enhanced)

Generate outreach drafts using prospect + scoring + research.

**Request:**
```json
{
  "prospect_id": "prospect_123",
  "user_id": "user123",
  "audience_profile": {...},
  "preferred_tone": "professional",
  "include_social": true
}
```

**Response:** (Same as before, but prompt now includes research insights)

The generated prompt now includes:
- Research insights from linked research
- Cached signal keywords
- Trending pains from research
- Industry trends

---

### Step 5: Metrics Tracking

#### `GET /api/metrics/current`

Get current period metrics.

**Request:**
```
GET /api/metrics/current?user_id=user123&period=weekly
```

**Response:**
```json
{
  "success": true,
  "metrics": {
    "metric_id": "week_1234567890",
    "user_id": "user123",
    "week_start": 1234567890.0,
    "prospects_analyzed": 50,
    "emails_sent": 75,
    "meetings_booked": 10,
    "top_industries": [
      {"value": "SaaS", "count": 15, "meetings": 3}
    ],
    "top_job_titles": [
      {"value": "VP Sales", "count": 10, "meetings": 2}
    ],
    "top_outreach_angles": [
      {"value": "scaling revenue", "count": 8, "meetings": 2}
    ]
  }
}
```

#### `POST /api/metrics/update`

Update metrics based on action.

**Request:**
```json
{
  "user_id": "user123",
  "prospect_id": "prospect_123",
  "action": "meetings_booked",
  "engagement_data": {
    "meeting_booked": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "metric_id": "week_1234567890",
  "updated": {
    "meetings_booked": 11,
    "top_industries": [...],
    "updated_at": 1234567890.0
  }
}
```

**Actions:**
- `prospects_analyzed` - Increment when prospect is scored
- `emails_sent` - Increment when email is sent
- `meetings_booked` - Increment when meeting is booked

---

### Step 6: Learning Loop

#### `POST /api/learning/update-patterns`

Update learning patterns based on engagement.

**Request:**
```json
{
  "user_id": "user123",
  "prospect_id": "prospect_123",
  "engagement_data": {
    "email_sent": true,
    "email_opened": true,
    "email_responded": true,
    "meeting_booked": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "updated_patterns": [
    {
      "pattern_id": "industry_saas",
      "pattern_type": "industry",
      "value": "SaaS",
      "performance_score": 85,
      "engagement_count": 15,
      "updated_at": 1234567890.0
    },
    {
      "pattern_id": "job_title_vp_sales",
      "pattern_type": "job_title",
      "value": "VP Sales",
      "performance_score": 80,
      "engagement_count": 10
    }
  ]
}
```

**Process:**
1. Retrieves prospect data (industry, job_title, keywords, outreach_angle)
2. Updates learning patterns in Firestore:
   - Industry performance
   - Job title performance
   - Keyword performance
   - Outreach angle performance
3. Calculates performance scores based on engagement

#### `GET /api/learning/patterns`

Get top performing patterns.

**Request:**
```
GET /api/learning/patterns?user_id=user123&pattern_type=industry&limit=10
```

**Response:**
```json
{
  "success": true,
  "patterns": [
    {
      "pattern_id": "industry_saas",
      "pattern_type": "industry",
      "value": "SaaS",
      "performance_score": 85,
      "engagement_count": 15,
      "meetings_booked": 5,
      "emails_sent": 20,
      "emails_responded": 5
    }
  ]
}
```

---

## Firestore Schema

### Research Insights
**Path**: `users/{userId}/research_insights/{researchId}`

```json
{
  "research_id": "string",
  "title": "string",
  "industry": "string",
  "summary": "string",
  "keywords": ["string"],
  "job_titles": ["string"],
  "linked_research_ids": ["string"],
  "sources": [{"url": "string", "title": "string"}],
  "created_at": timestamp,
  "updated_at": timestamp
}
```

### Prospects
**Path**: `users/{userId}/prospects/{prospectId}`

```json
{
  "prospect_id": "string",
  "user_id": "string",
  "name": "string",
  "email": "string",
  "job_title": "string",
  "company": "string",
  "website": "string",
  "linkedin": "string",
  "discovery_source": "string",
  "approval_status": "pending|approved|rejected",
  "linked_research_ids": ["string"],
  "cached_insights": {
    "industry_trends": ["string"],
    "trending_pains": ["string"],
    "signal_keywords": ["string"],
    "last_updated": timestamp
  },
  "fit_score": 0-100,
  "referral_capacity": 0-100,
  "signal_strength": 0-100,
  "best_outreach_angle": "string",
  "scoring_reasoning": "string",
  "drafts_generated": 0,
  "emails_sent": 0,
  "meetings_booked": 0,
  "created_at": timestamp,
  "updated_at": timestamp
}
```

### Learning Patterns
**Path**: `users/{userId}/learning_patterns/{patternId}`

```json
{
  "pattern_id": "string",
  "user_id": "string",
  "industry": "string",
  "job_title": "string",
  "keywords": ["string"],
  "outreach_angle": "string",
  "performance_score": 0-100,
  "engagement_count": 0,
  "meetings_booked": 0,
  "emails_sent": 0,
  "emails_responded": 0,
  "updated_at": timestamp
}
```

### Metrics
**Path**: `users/{userId}/metrics/{metricId}`

```json
{
  "metric_id": "string",
  "user_id": "string",
  "week_start": timestamp,
  "month": "string",
  "prospects_analyzed": 0,
  "emails_sent": 0,
  "meetings_booked": 0,
  "top_industries": [{"value": "string", "count": 0, "meetings": 0}],
  "top_job_titles": [{"value": "string", "count": 0, "meetings": 0}],
  "top_outreach_angles": [{"value": "string", "count": 0, "meetings": 0}],
  "updated_at": timestamp
}
```

---

## Complete Workflow Example

### 1. Research First
```bash
curl -X POST http://localhost:8080/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "topic": "SaaS companies serving SMBs",
    "industry": "SaaS"
  }'
```

### 2. Discover Prospects
```bash
curl -X POST http://localhost:8080/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "industry": "SaaS",
    "location": "San Francisco, CA",
    "max_results": 20
  }'
```

### 3. Approve Prospects
```bash
curl -X POST http://localhost:8080/api/prospects/approve \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "prospect_ids": ["prospect_123", "prospect_456"],
    "approval_status": "approved"
  }'
```

### 4. Score Prospects
```bash
curl -X POST http://localhost:8080/api/prospects/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "prospect_ids": ["prospect_123", "prospect_456"]
  }'
```

### 5. Generate Outreach
```bash
curl -X POST http://localhost:8080/api/outreach/manual/prompts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prospect_id": "prospect_123",
    "user_id": "user123",
    "include_social": true
  }'
```

### 6. Track Engagement
```bash
curl -X POST http://localhost:8080/api/metrics/update \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "prospect_id": "prospect_123",
    "action": "emails_sent"
  }'
```

### 7. Update Learning Patterns
```bash
curl -X POST http://localhost:8080/api/learning/update-patterns \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "prospect_id": "prospect_123",
    "engagement_data": {
      "email_sent": true,
      "email_responded": true,
      "meeting_booked": true
    }
  }'
```

---

## Cost Optimization

- **Research**: Manual trigger only → near-zero cost
- **Discovery**: Google Custom Search (100 free queries/day) + Firecrawl minimal
- **Scoring**: Uses stored research → $0 recurring cost
- **Outreach**: Can use ChatGPT Free → $0
- **Learning**: Firestore reads/writes only → minimal cost

**Total Estimated Cost**: $5-15/month (mainly search API after free tier)

---

## Next Steps

1. Set environment variables (Google Custom Search API keys)
2. Test research trigger endpoint
3. Test prospect discovery
4. Test scoring with research integration
5. Test learning loop
6. Monitor metrics dashboard

---

**Ready to use!** All endpoints are implemented and registered in `main.py`.




