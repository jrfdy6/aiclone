# LinkedIn Post Search Feature

## Overview

Your backend now includes a LinkedIn post search feature that allows you to find high-engaging posts from both your connections and non-connections. This helps you model your content after successful posts.

## How It Works

1. **Google Custom Search**: Searches for LinkedIn post URLs matching your query
2. **Firecrawl Scraping**: Scrapes the LinkedIn post content to extract:
   - Post content/text
   - Author information (name, title, company)
   - Engagement metrics (likes, comments, shares, reactions)
   - Hashtags and mentions
   - Media URLs
3. **Engagement Scoring**: Calculates an engagement score based on:
   - Likes (1x weight)
   - Comments (3x weight)
   - Shares (5x weight)
   - Reactions (1x weight)

## API Endpoints

### Search LinkedIn Posts

**Endpoint:** `POST /api/linkedin/search`

**Request Body:**
```json
{
  "query": "AI tools for developers",
  "include_connections": true,
  "include_non_connections": true,
  "min_engagement_score": 50.0,
  "max_results": 20,
  "sort_by": "engagement",
  "topics": ["AI", "developer tools", "SaaS"]
}
```

**Response:**
```json
{
  "success": true,
  "query": "AI tools for developers",
  "total_results": 15,
  "posts": [
    {
      "post_id": "1234567890",
      "post_url": "https://www.linkedin.com/posts/...",
      "author_name": "John Doe",
      "author_title": "Senior Developer",
      "author_company": "Tech Corp",
      "content": "Here's my take on the best AI tools...",
      "engagement_metrics": {
        "likes": 150,
        "comments": 25,
        "shares": 10,
        "reactions": 150
      },
      "engagement_score": 255.0,
      "hashtags": ["AI", "DeveloperTools", "Tech"],
      "scraped_at": "2025-01-23T12:00:00Z"
    }
  ],
  "search_metadata": {
    "search_time": "now",
    "filters_applied": {...},
    "sort_by": "engagement"
  }
}
```

### Analyze Posts

**Endpoint:** `POST /api/linkedin/analyze`

**Request Body:**
```json
[
  {
    "post_id": "...",
    "post_url": "...",
    "content": "...",
    "engagement_score": 255.0,
    ...
  }
]
```

**Response:**
```json
{
  "success": true,
  "analysis": {
    "total_posts": 15,
    "average_engagement_score": 180.5,
    "top_hashtags": [
      {"tag": "AI", "count": 8},
      {"tag": "Tech", "count": 5}
    ],
    "top_companies": [...],
    "top_posts": [...]
  }
}
```

## Request Parameters

### LinkedInSearchRequest

- **query** (required): Search query string (e.g., "AI tools for developers")
- **include_connections** (default: true): Include posts from people you're connected with
- **include_non_connections** (default: true): Include posts from people you're not connected with
- **min_engagement_score** (optional): Minimum engagement score to filter posts
- **max_results** (default: 20, max: 100): Maximum number of posts to return
- **sort_by** (default: "engagement"): Sort order - "engagement", "recent", or "relevance"
- **topics** (optional): List of topics/keywords to filter by

## Usage Examples

### Example 1: Find High-Engaging Posts About AI

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools for developers",
    "min_engagement_score": 100.0,
    "max_results": 10,
    "sort_by": "engagement"
  }'
```

### Example 2: Search by Topics

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SaaS marketing strategies",
    "topics": ["SaaS", "marketing", "growth"],
    "max_results": 15
  }'
```

### Example 3: Find Posts from Connections Only

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "product management",
    "include_connections": true,
    "include_non_connections": false,
    "max_results": 20
  }'
```

## Integration with Frontend

You can integrate this into your frontend by calling the API endpoint:

```typescript
// Example React/Next.js integration
async function searchLinkedInPosts(query: string) {
  const response = await fetch('/api/linkedin/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      max_results: 20,
      sort_by: 'engagement',
      min_engagement_score: 50.0,
    }),
  });
  
  const data = await response.json();
  return data.posts;
}
```

## How to Use for Content Modeling

1. **Search for High-Engaging Posts**: Use queries related to your industry/topic
2. **Filter by Engagement**: Set `min_engagement_score` to find top-performing posts
3. **Analyze Patterns**: Use the `/analyze` endpoint to identify:
   - Common themes
   - Popular hashtags
   - Effective content structures
   - Top-performing authors/companies
4. **Model Your Content**: Use insights from high-engaging posts to create similar content

## Important Notes

### LinkedIn Terms of Service

⚠️ **Important**: This feature uses web scraping to access LinkedIn content. Be aware of:
- LinkedIn's Terms of Service regarding automated access
- Rate limiting and potential blocks
- Ethical use of scraped data
- Consider using LinkedIn's official API if available for your use case

### Limitations

- **Post Detection**: The system identifies posts by URL patterns, which may not capture all posts
- **Engagement Metrics**: Engagement metrics are extracted from scraped content and may not be 100% accurate
- **Connection Status**: The system cannot automatically determine if someone is a connection (you may need to manually tag this)
- **Rate Limits**: Google Custom Search and Firecrawl have rate limits

### Future Enhancements

Potential improvements:
- Store posts in Firestore for faster retrieval
- Add connection status detection
- Implement caching to reduce API calls
- Add sentiment analysis
- Track post performance over time
- Integrate with LinkedIn official API (if available)

## Environment Variables Required

Make sure these are set in your environment:

- `GOOGLE_CUSTOM_SEARCH_API_KEY` - For searching LinkedIn post URLs
- `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` - Your Custom Search Engine ID
- `FIRECRAWL_API_KEY` - For scraping LinkedIn post content

## Testing

Test the endpoint:

```bash
# Test search
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{"query": "AI tools", "max_results": 5}'

# Check health
curl http://localhost:8080/health
```

## Troubleshooting

### No Posts Found

- Check that your Google Custom Search is configured to search LinkedIn
- Verify your search query is specific enough
- Try different query terms

### Scraping Failures

- LinkedIn may block automated scraping
- Check Firecrawl API key and limits
- Some posts may require authentication to view

### Low Engagement Scores

- Engagement metrics are extracted from visible content
- Some posts may not display engagement metrics publicly
- Try searching for more popular topics

---

**Ready to use!** Your backend now has LinkedIn post search capabilities. Start by searching for topics relevant to your content strategy and analyze the high-engaging posts to model your own content.

