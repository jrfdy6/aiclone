# Quick Test Guide - API Integrations

Test that Perplexity and Firecrawl integrations are working correctly.

## Prerequisites

1. ✅ API keys set (see `ENVIRONMENT_VARIABLES.md`)
2. ✅ Backend server running: `cd backend && uvicorn app.main:app --reload`
3. ✅ Frontend running (optional): `cd frontend && npm run dev`

## Test 1: Perplexity Integration

### Via API
```bash
curl -X POST http://localhost:8080/api/content/research \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "best AI coding tools 2025",
    "num_results": 5,
    "include_comparison": true
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "topic": "best AI coding tools 2025",
  "research_content": "# Research: best AI coding tools 2025\n\n## Summary\n[Perplexity research summary]...",
  "tools_found": [...],
  "comparison_table": "...",
  "sources": ["https://...", "https://..."]
}
```

**If you get an error about `PERPLEXITY_API_KEY`**:
- Check that the environment variable is set
- Restart your backend server
- See `ENVIRONMENT_VARIABLES.md` for setup

### Via Frontend
1. Navigate to `http://localhost:3002/content-marketing`
2. Click "Content Research" tab
3. Enter topic: "best AI coding tools 2025"
4. Click "Start Research"
5. Wait for results (may take 10-30 seconds)

## Test 2: Firecrawl Integration

### Via API
```bash
curl -X POST http://localhost:8080/api/content/internal-linking \
  -H "Content-Type: application/json" \
  -d '{
    "website_url": "https://example.com",
    "section_path": "/blog",
    "num_articles": 5,
    "depth": 1
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "website_url": "https://example.com",
  "articles_analyzed": ["https://example.com/blog/article1", ...],
  "opportunities": [
    {
      "source_article": "https://...",
      "target_article": "https://...",
      "anchor_text": "...",
      "content_snippet": "...",
      "context": "...",
      "relevance_score": 0.75
    }
  ],
  "total_opportunities": 5
}
```

**Note**: This may take 30-60 seconds as it crawls the website.

**If you get an error about `FIRECRAWL_API_KEY`**:
- Check that the environment variable is set
- Restart your backend server
- See `ENVIRONMENT_VARIABLES.md` for setup

### Via Frontend
1. Navigate to `http://localhost:3002/content-marketing`
2. Click "Internal Linking" tab
3. Enter website URL
4. Optionally enter section path (e.g., `/blog`)
5. Click "Analyze Internal Linking"
6. Wait for results (may take 30-60 seconds)

## Test 3: Combined Workflow

Test the full content research workflow:

```bash
# Step 1: Research topic
curl -X POST http://localhost:8080/api/content/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "best marketing automation tools", "num_results": 10}'

# Step 2: Analyze your own website (if you have one)
curl -X POST http://localhost:8080/api/content/internal-linking \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://yourwebsite.com", "num_articles": 10}'
```

## Common Issues

### Issue: "API configuration error: PERPLEXITY_API_KEY not set"
**Solution**:
1. Check environment variable: `echo $PERPLEXITY_API_KEY`
2. If empty, set it: `export PERPLEXITY_API_KEY="your-key"`
3. Restart backend server

### Issue: "API configuration error: FIRECRAWL_API_KEY not set"
**Solution**:
1. Check environment variable: `echo $FIRECRAWL_API_KEY`
2. If empty, set it: `export FIRECRAWL_API_KEY="your-key"`
3. Restart backend server

### Issue: "Perplexity API request failed: 401"
**Solution**:
- Invalid API key
- Check key is correct
- Regenerate key if needed

### Issue: "Firecrawl scrape failed: 401"
**Solution**:
- Invalid API key
- Check key is correct
- Regenerate key if needed

### Issue: Request times out
**Solution**:
- Perplexity: Normal, can take 10-30 seconds
- Firecrawl crawl: Normal, can take 30-60+ seconds for large sites
- Reduce `num_articles` or `depth` if needed

### Issue: Rate limit errors
**Solution**:
- Check your API plan limits
- Wait a few minutes and retry
- Consider upgrading plan for production

## Success Indicators

✅ **Perplexity Working**:
- Returns research summary
- Includes sources
- Content is relevant and current

✅ **Firecrawl Working**:
- Successfully crawls website
- Returns scraped content
- Finds linking opportunities

✅ **Both Working**:
- Content research includes scraped source content
- Internal linking analysis completes successfully
- No API key errors

## Next Steps

Once tests pass:
1. ✅ APIs are integrated and working
2. Use the workflows in production
3. Consider adding LLM synthesis for better content (optional)
4. Monitor API usage and costs
5. Set up caching if needed

---

**Need Help?**
- See `ENVIRONMENT_VARIABLES.md` for API key setup
- See `API_INTEGRATION_SUMMARY.md` for technical details
- Check backend logs for detailed error messages




