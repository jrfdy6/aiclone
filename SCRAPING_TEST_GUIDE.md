# LinkedIn Scraping Success Testing Guide

This guide helps you test and improve LinkedIn scraping success rates.

## Quick Start

### 1. Using the Test Script

The `test_scraping_success.py` script provides detailed metrics on scraping performance:

```bash
# Basic test
python test_scraping_success.py --query "AI tools" --max-results 5

# Multiple iterations to get average success rates
python test_scraping_success.py --query "machine learning" --max-results 10 --iterations 3

# Test against production API
python test_scraping_success.py \
  --query "SaaS tools" \
  --max-results 5 \
  --api-url "https://your-api-url.up.railway.app" \
  --output results.json
```

### 2. Using the Test Endpoint

The `/api/linkedin/test` endpoint provides detailed metrics:

```bash
curl -X POST https://your-api-url.up.railway.app/api/linkedin/test \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools",
    "max_results": 5
  }'
```

### 3. Using the Frontend Test Page

Navigate to `/api-test` in your frontend application and use the UI to test different queries.

## Understanding the Metrics

### Scraping Performance Metrics

The system tracks 4 different scraping approaches:

1. **Approach 1 (v2 + auto proxy)**: Fastest, most cost-effective
   - Uses Firecrawl v2 API
   - Auto proxy (tries basic, then stealth if needed)
   - 5 second wait time
   - **Cost**: 1 credit (basic) or 5 credits (if stealth needed)

2. **Approach 2 (scroll actions)**: For lazy-loaded content
   - Scrolls page to trigger lazy loading
   - 8 second wait time
   - Auto proxy
   - **Cost**: 1-5 credits

3. **Approach 3 (extended wait + stealth)**: For difficult posts
   - 10 second wait time
   - Forces stealth proxy
   - **Cost**: 5 credits

4. **Approach 4 (v1 fallback)**: Last resort
   - Uses Firecrawl v1 API
   - Sometimes works when v2 is blocked
   - **Cost**: 1 credit

### Success Rate Calculation

```
Success Rate = (Successful Scrapes / Total Attempts) × 100%
```

A good success rate is typically:
- **> 60%**: Excellent
- **40-60%**: Good
- **20-40%**: Acceptable (LinkedIn blocking is common)
- **< 20%**: May indicate API issues

### Extraction Quality Metrics

- **Author Extraction Rate**: Percentage of posts with author names
- **Engagement Extraction Rate**: Percentage of posts with engagement scores
- **Company Extraction Rate**: Percentage of posts with company info
- **Content Length**: Average characters per post

## Improving Success Rates

### 1. Monitor Which Approaches Work Best

Run multiple test iterations and check which approach has the highest success rate:

```bash
python test_scraping_success.py --query "your query" --iterations 5 --output results.json
```

Look at the "Overall Scraping Success Rates" in the output.

### 2. Adjust Scraping Strategy

If Approach 1 is working well (>50% success), you can optimize costs by:
- Reducing wait times
- Using fewer retry attempts
- Prioritizing Approach 1

If Approach 3 (stealth) is needed frequently:
- LinkedIn may be blocking aggressively
- Consider reducing scraping frequency
- Use longer delays between requests

### 3. Test Different Queries

Some queries may have better success rates than others:

```bash
# Test multiple queries
for query in "AI tools" "machine learning" "SaaS" "startups"; do
  python test_scraping_success.py --query "$query" --max-results 5
done
```

### 4. Monitor Over Time

Track success rates over time to identify patterns:

```bash
# Run daily tests and save results
python test_scraping_success.py \
  --query "AI tools" \
  --iterations 3 \
  --output "results_$(date +%Y%m%d).json"
```

## Common Issues and Solutions

### Low Success Rate (< 20%)

**Possible causes:**
- Firecrawl API key issues
- LinkedIn blocking all requests
- Network/timeout issues

**Solutions:**
1. Check Firecrawl API key is valid
2. Check Firecrawl account credits
3. Try different queries (some may be less blocked)
4. Increase delays between requests

### High "Content Too Short" Count

**Possible causes:**
- LinkedIn showing login prompts
- Content not loading properly
- JavaScript-heavy pages

**Solutions:**
1. Increase `wait_for` time
2. Use Approach 2 (scroll actions) more
3. Check if LinkedIn changed their page structure

### All Approaches Failing

**Possible causes:**
- LinkedIn blocking Firecrawl completely
- API endpoint issues
- Invalid URLs from Google Search

**Solutions:**
1. Verify URLs are valid LinkedIn post URLs
2. Test Firecrawl API directly
3. Check backend logs for specific error messages
4. Try manual scraping of a URL to verify it's accessible

## Best Practices

1. **Start Small**: Test with 3-5 results first
2. **Monitor Costs**: Stealth proxy costs 5x more
3. **Use Delays**: Don't scrape too quickly
4. **Track Metrics**: Save test results for comparison
5. **Iterate**: Run multiple tests to get averages

## Example Output

```
============================================================
Testing LinkedIn Scraping
============================================================
Query: AI tools
Max Results: 5
Iterations: 3
API URL: http://localhost:8080
============================================================

--- Iteration 1/3 ---
  Sending request to http://localhost:8080/api/linkedin/test...
  ✅ Request completed in 45.2s
  Posts found: 5

  Extraction Quality:
    - Author extraction: 80.0%
    - Engagement extraction: 60.0%
    - Company extraction: 40.0%

  Scraping Performance:
    - Total attempts: 5
    - Successful scrapes: 3
    - Success rate: 60.0%
    - Approach 1 success: 2
    - Approach 2 success: 1
    - Approach 3 success: 0
    - Approach 4 success: 0
    - Content too short: 1
    - No LinkedIn indicators: 1

============================================================
Summary Statistics
============================================================

Overall Scraping Success Rates:
  Total attempts: 15
  Approach 1 (v2 + auto): 8 (53.3%)
  Approach 2 (scroll): 3 (20.0%)
  Approach 3 (stealth): 1 (6.7%)
  Approach 4 (v1 fallback): 0 (0.0%)

Average Extraction Quality:
  Author extraction: 75.0%
  Engagement extraction: 55.0%

Performance:
  Average posts per request: 4.7
  Average time per request: 42.3s
```

## Next Steps

1. Run baseline tests to establish current success rates
2. Test different queries to find optimal search terms
3. Monitor success rates over time
4. Adjust scraping strategy based on results
5. Optimize costs by prioritizing successful approaches

