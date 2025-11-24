# Enhanced Research & Knowledge Management Pipeline

## 🎯 Overview

Complete multi-source research pipeline that feeds content generation, outreach, and learning systems **without LinkedIn scraping**.

Implements all 6 workflow steps (A-F) from your specification:
- ✅ Step A: Topic Trigger
- ✅ Step B: Multi-source Research (Perplexity, Firecrawl, Google Search)
- ✅ Step C: Normalization & Deduplication
- ✅ Step D: Prospect Target Extraction
- ✅ Step E: Firestore Storage
- ✅ Step F: Integration with content generation & outreach

---

## 📋 Insight Object Structure (Firestore-Ready)

Each insight is stored as:

```json
{
  "user_id": "user123",
  "insight_id": "insight_1234567890",
  "topic": "AI in K-12 Education",
  "pillar": "thought_leadership",
  "sources": [
    {
      "type": "perplexity",
      "source_name": "Perplexity AI",
      "summary": "AI-powered adaptive learning improves student engagement...",
      "key_points": [
        "Adaptive learning platforms increase personalized instruction.",
        "Early adopters report 15% higher student engagement.",
        "Data privacy remains a top concern."
      ],
      "source_url": "https://perplexity.ai/...",
      "date_collected": "2025-11-24T12:00:00Z"
    }
  ],
  "prospect_targets": [
    {
      "name": "John Doe",
      "role": "Director of EdTech Innovation",
      "organization": "Private School X",
      "contact_url": "https://schoolx.org/staff/john-doe",
      "pillar_relevance": ["referral"],
      "relevance_score": 0.92
    }
  ],
  "tags": ["AI", "EdTech", "Adaptive Learning"],
  "engagement_signals": {
    "relevance_score": 0.92,
    "trend_score": 0.88,
    "urgency_score": 0.75
  },
  "date_collected": "2025-11-24T12:15:00Z",
  "status": "ready_for_content_generation",
  "linked_research_ids": ["research_abc123"],
  "normalized_key_points": [...],
  "normalized_tags": [...],
  "deduplication_hash": "..."
}
```

**Storage Location:** `users/{userId}/research_insights/{insightId}`

---

## 🚀 API Endpoints

### Complete Workflow (Recommended)

**Endpoint:** `POST /api/research/enhanced/complete-workflow`

**Request:**
```json
{
  "user_id": "user123",
  "topic": "AI in K-12 Education",
  "industry": "EdTech",
  "use_cached": true
}
```

**Response:**
```json
{
  "success": true,
  "insight_id": "insight_1234567890",
  "topic": "AI in K-12 Education",
  "pillar": "thought_leadership",
  "sources_collected": 8,
  "prospects_extracted": 3,
  "normalized_key_points": 15,
  "status": "ready_for_content_generation",
  "workflow_steps_completed": [
    "topic_trigger",
    "multi_source_research",
    "normalization",
    "prospect_extraction"
  ]
}
```

This **single endpoint** orchestrates all 6 steps automatically.

---

### Step-by-Step Endpoints

#### Step A: Topic Trigger

**Endpoint:** `POST /api/research/enhanced/trigger`

```json
{
  "user_id": "user123",
  "topic": "AI in K-12 Education",
  "industry": "EdTech",
  "pillar": null,  // Auto-assigned if null
  "use_cached": true,
  "include_prospect_extraction": true
}
```

#### Step B: Multi-source Research

**Endpoint:** `POST /api/research/enhanced/collect`

```json
{
  "user_id": "user123",
  "insight_id": "insight_1234567890",
  "topic": "AI in K-12 Education",
  "use_perplexity": true,
  "use_firecrawl": true,
  "use_google_search": true,
  "max_sources_per_type": 5,
  "batch_mode": true  // Free-tier optimization
}
```

#### Step C: Normalization

**Endpoint:** `POST /api/research/enhanced/normalize`

```json
{
  "user_id": "user123",
  "insight_id": "insight_1234567890"
}
```

#### Step D: Prospect Extraction

**Endpoint:** `POST /api/research/enhanced/extract-prospects`

```json
{
  "user_id": "user123",
  "insight_id": "insight_1234567890",
  "min_relevance_score": 0.7
}
```

---

## 💡 Usage Examples

### Example 1: Complete Workflow

```bash
curl -X POST "https://your-backend.up.railway.app/api/research/enhanced/complete-workflow?user_id=user123&topic=AI%20in%20K-12%20Education&industry=EdTech" \
  -H "Content-Type: application/json"
```

**What happens:**
1. ✅ Topic trigger creates insight object
2. ✅ Collects from Perplexity, Firecrawl, Google Search
3. ✅ Normalizes and deduplicates
4. ✅ Extracts prospect targets
5. ✅ Stores in Firestore with status `ready_for_content_generation`

---

### Example 2: Use in Content Generation

```python
# 1. Run research workflow
research_response = await complete_research_workflow(
    user_id="user123",
    topic="AI in K-12 Education"
)

insight_id = research_response["insight_id"]

# 2. Generate content using the insight
content_response = await generate_comprehensive_content({
    "user_id": "user123",
    "content_type": "linkedin_post",
    "format": "both",
    "num_variations": 5,
    "topic": "AI in K-12 Education",
    # Link to research insight
    "linked_research_ids": [insight_id]
})
```

---

### Example 3: Use in Outreach

```python
# 1. Get insight with prospect targets
insight = await get_insight(user_id="user123", insight_id="insight_123")

# 2. Use prospect targets for outreach
for prospect in insight["prospect_targets"]:
    outreach_response = await generate_outreach({
        "user_id": "user123",
        "prospect_name": prospect["name"],
        "engagement_type": "connection",
        "topic": insight["topic"]
    })
```

---

## 🔧 Free-Tier Optimizations

### Batch Mode

The pipeline includes built-in optimizations:

1. **Caching** - Check for existing insights before collecting
2. **Rate Throttling** - Stagger requests (1-2s delays between sources)
3. **Batch Queries** - Limit sources per type (default: 5)
4. **Fallback Logic** - Continue if one source fails

**Enable batch mode:**
```json
{
  "batch_mode": true,  // Adds delays between requests
  "max_sources_per_type": 5  // Limits API calls
}
```

### Estimated Costs

- **Perplexity:** ~$0.01 per research query
- **Firecrawl:** Free tier = 50 scrapes/day
- **Google Search:** Free tier = 100 queries/day

**Total per complete workflow:** ~$0.01 (well within free tiers)

---

## 🔗 Integration Points

### Integration F: Content Generation

Insights automatically feed into content generation:

```python
# Insight status changes to: ready_for_content_generation
# Use in:
POST /api/content/generate
{
  "user_id": "...",
  "content_type": "linkedin_post",
  "linked_research_ids": ["insight_123"]
}
```

### Integration F: Outreach

Prospect targets feed into outreach:

```python
# Get prospects from insight
GET /api/research/enhanced/insight/{insight_id}

# Use prospects in:
POST /api/linkedin/content/engagement/generate_dm
{
  "prospect_name": "...",
  "engagement_type": "connection"
}
```

### Integration F: Learning

Track which insights drive engagement:

```python
# After posting content from insight
POST /api/linkedin/content/metrics/update-learning-patterns
{
  "user_id": "...",
  "draft_id": "...",
  "linked_research_ids": ["insight_123"]
}
```

---

## 📊 Workflow Diagram

```
┌─────────────────┐
│  Topic Trigger  │ (Step A)
└────────┬────────┘
         │
    ┌────▼────┐
    │ Create  │
    │ Insight │
    └────┬────┘
         │
┌────────▼────────────────────────┐
│  Multi-Source Research (Step B) │
├─────────────────────────────────┤
│  • Perplexity                   │
│  • Firecrawl                    │
│  • Google Custom Search         │
└────────┬────────────────────────┘
         │
┌────────▼───────────────┐
│ Normalization (Step C) │
├────────────────────────┤
│  • Deduplicate         │
│  • Normalize tags      │
│  • Merge sources       │
└────────┬───────────────┘
         │
┌────────▼──────────────────────┐
│ Prospect Extraction (Step D)  │
├───────────────────────────────┤
│  • Identify organizations     │
│  • Extract contacts           │
│  • Score relevance            │
└────────┬──────────────────────┘
         │
┌────────▼──────────────┐
│ Storage (Step E)      │
├───────────────────────┤
│  • Save to Firestore  │
│  • Update status      │
└────────┬──────────────┘
         │
┌────────▼──────────────────────┐
│ Integration (Step F)          │
├───────────────────────────────┤
│  • Content Generation         │
│  • Outreach                   │
│  • Learning Patterns          │
└───────────────────────────────┘
```

---

## 🎯 Status Flow

1. `collecting` → Initial topic trigger
2. `processing` → Multi-source research in progress
3. `ready_for_content_generation` → Ready to use in content creation
4. `ready_for_outreach` → Prospects extracted, ready for outreach
5. `archived` → Research completed/archived

---

## 📁 Files Created

1. **`backend/app/models/enhanced_research.py`** - All models for enhanced research
2. **`backend/app/services/enhanced_research_service.py`** - Core research logic
3. **`backend/app/routes/enhanced_research.py`** - API endpoints
4. **`backend/app/main.py`** - Router registration (updated)

---

## ✅ Summary

**Complete pipeline ready:**

✅ **Step A-F** - All workflow steps implemented
✅ **Multi-source** - Perplexity + Firecrawl + Google Search
✅ **Prospect extraction** - Automatic target identification
✅ **Normalization** - Deduplication and tag normalization
✅ **Firestore storage** - Ready-to-use insight objects
✅ **Integration** - Feeds content generation & outreach
✅ **Free-tier optimized** - Batch mode, caching, rate limiting

**Ready to use!** Start with `/complete-workflow` endpoint for the full pipeline.

