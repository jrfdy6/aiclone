# LinkedIn Industry Targeting Guide

## Overview

The LinkedIn search now supports **industry-specific targeting** to help you find and analyze what works in your target industries.

## Supported Industries

Get the full list:
```bash
curl http://localhost:8080/api/linkedin/industries
```

**Available industries:**
- **SaaS** - Software as a Service
- **FinTech** - Financial Technology
- **Healthcare** - Healthcare & Health Tech
- **E-commerce** - Online Retail & Digital Commerce
- **AI/ML** - Artificial Intelligence & Machine Learning
- **Marketing** - Marketing & Digital Marketing
- **Real Estate** - Real Estate & PropTech
- **Education** - Education & EdTech
- **Cybersecurity** - Information Security
- **Biotech** - Biotechnology & Life Sciences
- **Gaming** - Video Games & Gaming Industry
- **Energy** - Energy & Renewable Energy

## Usage Examples

### 1. Search Posts in a Specific Industry

**Basic industry search:**
```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "product launch",
    "industry": "SaaS",
    "max_results": 20
  }'
```

**With engagement filter:**
```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "customer success",
    "industry": "SaaS",
    "min_engagement_score": 100.0,
    "max_results": 15
  }'
```

### 2. Filter by Company (Industry-Specific Companies Only)

**Only show posts from companies in the target industry:**
```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools",
    "industry": "AI/ML",
    "filter_by_company": true,
    "max_results": 20
  }'
```

This filters results to only include posts from authors whose company/title matches the industry keywords.

### 3. Get Industry Insights

**Analyze what works in your target industry:**
```bash
curl http://localhost:8080/api/linkedin/industry/SaaS/insights
```

Or with a specific query:
```bash
curl "http://localhost:8080/api/linkedin/industry/FinTech/insights?query=payments&max_results=30"
```

**Response includes:**
- Top hashtags used in the industry
- Top companies posting
- Common job titles
- Average engagement scores
- Content length patterns
- Sample high-performing posts

### 4. Combine Industry + Topics

**Target specific topics within an industry:**
```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "growth strategies",
    "industry": "SaaS",
    "topics": ["B2B", "enterprise", "startups"],
    "max_results": 20
  }'
```

## Industry Insights Endpoint

### Get Insights for Your Industry

```bash
# SaaS industry insights
curl http://localhost:8080/api/linkedin/industry/SaaS/insights

# FinTech with specific query
curl "http://localhost:8080/api/linkedin/industry/FinTech/insights?query=blockchain&max_results=40"
```

**What you'll learn:**
1. **Top Hashtags** - What hashtags perform well in your industry
2. **Top Companies** - Which companies are posting successfully
3. **Job Titles** - What roles are creating engaging content
4. **Engagement Patterns** - Average engagement scores and ranges
5. **Content Length** - Optimal content length for your industry
6. **Sample Posts** - Examples of high-performing posts

**Example Response:**
```json
{
  "success": true,
  "industry": "SaaS",
  "total_posts_analyzed": 25,
  "average_engagement_score": 245.5,
  "average_content_length": 850,
  "top_hashtags": [
    {"tag": "SaaS", "count": 18},
    {"tag": "B2B", "count": 12},
    {"tag": "Startup", "count": 8}
  ],
  "top_companies": [
    {"company": "Salesforce", "count": 5},
    {"company": "HubSpot", "count": 4}
  ],
  "top_job_titles": [
    {"title": "VP of Marketing", "count": 6},
    {"title": "CEO", "count": 5}
  ],
  "engagement_range": {
    "min": 50.0,
    "max": 850.0
  },
  "sample_posts": [...]
}
```

## Use Cases

### Use Case 1: Content Research for Your Industry

**Goal**: Find high-engaging posts in your industry to model your content after

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "product updates",
    "industry": "SaaS",
    "min_engagement_score": 150.0,
    "sort_by": "engagement",
    "max_results": 20
  }'
```

### Use Case 2: Competitive Analysis

**Goal**: See what your competitors are posting

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "company news",
    "industry": "FinTech",
    "filter_by_company": true,
    "max_results": 30
  }'
```

### Use Case 3: Industry Best Practices

**Goal**: Understand what works in your industry

```bash
# Get comprehensive insights
curl http://localhost:8080/api/linkedin/industry/Healthcare/insights?max_results=50
```

### Use Case 4: Find Industry Thought Leaders

**Goal**: Discover who's creating engaging content in your industry

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "industry trends",
    "industry": "AI/ML",
    "min_engagement_score": 200.0,
    "max_results": 25
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
authors = {}
for post in posts:
    author = post.get('author_name', 'Unknown')
    score = post.get('engagement_score', 0)
    if author not in authors or authors[author] < score:
        authors[author] = score
for author, score in sorted(authors.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f'{author}: {score}')
"
```

## Industry-Specific Query Tips

### SaaS Industry
- Focus on: B2B, enterprise, customer success, product updates
- Good queries: "customer onboarding", "product roadmap", "B2B growth"

### FinTech Industry
- Focus on: Payments, banking, cryptocurrency, financial services
- Good queries: "digital payments", "banking innovation", "crypto adoption"

### Healthcare Industry
- Focus on: Digital health, medical technology, patient care
- Good queries: "telemedicine", "healthcare innovation", "patient experience"

### AI/ML Industry
- Focus on: Machine learning, AI applications, data science
- Good queries: "AI tools", "machine learning applications", "data science"

## Filtering Options

### 1. Content-Based Filtering (Default)
- Searches for posts with industry keywords in content
- Broader results
- Use when you want to see what topics are discussed in the industry

### 2. Company-Based Filtering (`filter_by_company: true`)
- Only includes posts from companies/people in the industry
- More focused results
- Use when you want to see what industry companies are posting

**Example:**
```json
{
  "query": "product launch",
  "industry": "SaaS",
  "filter_by_company": true  // Only SaaS companies
}
```

## Best Practices

1. **Start Broad, Then Narrow**
   - First: Get industry insights to understand patterns
   - Then: Search specific topics within the industry

2. **Use Engagement Filters**
   - Set `min_engagement_score` to focus on high-performing posts
   - Start with 50-100, adjust based on results

3. **Combine with Topics**
   - Use `topics` array to narrow within industry
   - Example: `"industry": "SaaS", "topics": ["B2B", "enterprise"]`

4. **Analyze Patterns**
   - Use insights endpoint to identify what works
   - Look at top hashtags, companies, and job titles
   - Model your content after successful patterns

5. **Test Different Industries**
   - Compare insights across industries
   - Find cross-industry opportunities

## Example Workflow

### Step 1: Get Industry Insights
```bash
curl http://localhost:8080/api/linkedin/industry/SaaS/insights
```

### Step 2: Identify Top Hashtags
Look at the `top_hashtags` in the response

### Step 3: Search for High-Engaging Posts
```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "customer success",
    "industry": "SaaS",
    "topics": ["B2B", "enterprise"],
    "min_engagement_score": 150.0,
    "max_results": 20
  }'
```

### Step 4: Analyze Results
- Review top-performing posts
- Note common themes
- Identify content structures that work
- Model your content after successful posts

## API Reference

### Search with Industry
```
POST /api/linkedin/search
{
  "query": "your query",
  "industry": "SaaS",  // Optional
  "filter_by_company": false,  // Optional
  "max_results": 20
}
```

### Get Industry Insights
```
GET /api/linkedin/industry/{industry}/insights?query=optional&max_results=30
```

### List Industries
```
GET /api/linkedin/industries
```

---

**Ready to target your industry!** Start by getting insights for your target industry, then search for high-engaging posts to model your content after.


