# LinkedIn Search Fine-Tuning & Testing Guide

## Quick Start Testing

### 1. Run the Test Script

```bash
cd /Users/johnniefields/Desktop/Cursor/aiclone
./test_linkedin_search.sh
```

This will test:
- Basic search functionality
- Engagement filtering
- Topic-based search

### 2. Use the Test Endpoint

Quick test via API:

```bash
curl -X POST "http://localhost:8080/api/linkedin/test?query=AI%20tools&max_results=3"
```

Or with JSON:

```bash
curl -X POST http://localhost:8080/api/linkedin/test \
  -H "Content-Type: application/json" \
  -d '{"query": "SaaS marketing", "max_results": 5}'
```

## Testing Different Scenarios

### Test 1: Basic Search Accuracy

**Goal**: Verify posts are being found and scraped correctly

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools for developers",
    "max_results": 5,
    "sort_by": "engagement"
  }' | python3 -m json.tool
```

**What to check:**
- ✅ Posts are returned
- ✅ Post URLs are valid LinkedIn URLs
- ✅ Content is extracted (not empty)
- ✅ Engagement scores are calculated

### Test 2: Engagement Filtering

**Goal**: Verify only high-engaging posts are returned

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SaaS marketing",
    "min_engagement_score": 100.0,
    "max_results": 10
  }' | python3 -m json.tool
```

**What to check:**
- ✅ All returned posts have engagement_score >= 100
- ✅ Posts are sorted by engagement (highest first)

### Test 3: Author Information Extraction

**Goal**: Verify author details are being extracted correctly

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "product management",
    "max_results": 5
  }' | python3 -m json.tool | grep -A 5 "author"
```

**What to check:**
- ✅ Author names are extracted
- ✅ Job titles are captured
- ✅ Company names are identified
- ✅ Profile URLs are found

### Test 4: Hashtag and Mention Extraction

**Goal**: Verify hashtags and mentions are captured

```bash
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI technology",
    "max_results": 5
  }' | python3 -m json.tool | grep -E "(hashtags|mentions)"
```

**What to check:**
- ✅ Hashtags are extracted from content
- ✅ Mentions are identified
- ✅ No duplicates in hashtag/mention lists

## Fine-Tuning Parameters

### 1. Engagement Score Calculation

**Location**: `backend/app/services/linkedin_client.py` → `_calculate_engagement_score()`

**Current weights:**
- Likes: 1.0x
- Comments: 3.0x
- Shares: 5.0x
- Reactions: 1.0x

**To adjust:**
```python
def _calculate_engagement_score(
    self,
    likes: int,
    comments: int,
    shares: int,
    reactions: int = 0
) -> float:
    # Adjust these multipliers to change scoring
    score = (
        likes * 1.0 +      # Increase if likes are important
        comments * 3.0 +  # Increase if comments are more valuable
        shares * 5.0 +      # Increase if shares are most valuable
        reactions * 1.0
    )
    return round(score, 2)
```

**Testing different weights:**
1. Modify the multipliers
2. Run test searches
3. Compare which posts rank higher
4. Adjust until results match your criteria

### 2. Engagement Metrics Extraction

**Location**: `backend/app/services/linkedin_client.py` → `_extract_engagement_metrics()`

**Current patterns:**
- Looks for "123 likes", "45 comments", "12 shares"
- Handles various formats and cases

**To improve:**
1. Test with real LinkedIn posts
2. Check backend logs for extraction patterns
3. Add new regex patterns if metrics are missed
4. Test with posts that have different metric formats

**Example improvement:**
```python
# Add pattern for "1.2K likes" format
likes_match = re.search(r'([\d.]+)\s*[Kk]\s*(?:like|👍)', content, re.IGNORECASE)
if likes_match:
    value = float(likes_match.group(1))
    metrics["likes"] = int(value * 1000)  # Convert K to number
```

### 3. Author Information Extraction

**Location**: `backend/app/services/linkedin_client.py` → `_extract_author_info()`

**Current patterns:**
- "Name | Title at Company"
- Profile URLs from links
- Various separator formats

**To improve:**
1. Test with different LinkedIn post formats
2. Check what patterns are common in your industry
3. Add patterns for specific formats you see

**Example improvement:**
```python
# Add pattern for "Name - Title @ Company"
name_pattern3 = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–]\s*([^@\n]+)\s*@\s*([A-Z][^@\n]+)'
```

### 4. Search Query Optimization

**Location**: `backend/app/services/linkedin_client.py` → `search_posts()`

**Current query format:**
```python
linkedin_query = f'site:linkedin.com/posts "{query}"'
```

**To improve:**
- Add industry-specific terms
- Include date filters
- Combine multiple search strategies

**Example improvements:**
```python
# Add date filter for recent posts
linkedin_query = f'site:linkedin.com/posts "{query}" after:2024-01-01'

# Add multiple search strategies
queries = [
    f'site:linkedin.com/posts "{query}"',
    f'site:linkedin.com/posts {query}',
    f'"{query}" site:linkedin.com/posts',
]
```

### 5. Content Filtering

**Location**: `backend/app/services/linkedin_client.py` → `search_posts()`

**Current filter:**
- Minimum content length: 50 characters
- Engagement score threshold (if set)

**To add more filters:**
```python
# Filter by content length
if len(post.content) < 100:  # Too short
    continue

# Filter by language
if not self._is_english(post.content):
    continue

# Filter by spam indicators
if self._is_spam(post.content):
    continue
```

## Monitoring & Debugging

### 1. Enable Detailed Logging

The LinkedIn client now includes detailed logging. Check backend logs for:

```
[LinkedIn] Searching with query: site:linkedin.com/posts "your query"
[LinkedIn] Found X search results
[LinkedIn] Filtered to X LinkedIn post URLs
[LinkedIn] Scraping 1/X: https://...
[LinkedIn] ✅ Successfully scraped post (engagement: 123.45)
[LinkedIn] Scraping complete: X successful, Y failed
```

### 2. Test Extraction Quality

Use the test endpoint to see extraction quality:

```bash
curl -X POST "http://localhost:8080/api/linkedin/test?query=AI&max_results=5" | python3 -m json.tool
```

Check the `test_metadata.extraction_quality` field:
- `posts_with_author`: How many posts have author info
- `posts_with_engagement`: How many have engagement metrics
- `posts_with_hashtags`: How many have hashtags extracted

### 3. Compare Results

Test the same query multiple times and compare:
- Are results consistent?
- Are engagement scores accurate?
- Is author information complete?

## Common Issues & Solutions

### Issue 1: No Posts Found

**Possible causes:**
- Google Custom Search not configured for LinkedIn
- Query too specific
- LinkedIn blocking automated access

**Solutions:**
1. Verify Google Custom Search Engine includes LinkedIn
2. Try broader queries
3. Check if LinkedIn URLs are in search results
4. Review backend logs for errors

### Issue 2: Low Engagement Scores

**Possible causes:**
- Engagement metrics not visible in scraped content
- LinkedIn requires login to see metrics
- Metrics in different format than expected

**Solutions:**
1. Check scraped content in logs
2. Improve regex patterns in `_extract_engagement_metrics()`
3. Test with posts you know have high engagement
4. Consider using LinkedIn API if available

### Issue 3: Missing Author Information

**Possible causes:**
- Author info not in scraped content
- Different LinkedIn post format
- Profile is private

**Solutions:**
1. Check what content is actually scraped
2. Add more extraction patterns
3. Test with different post types
4. Accept that some posts won't have author info

### Issue 4: Scraping Failures

**Possible causes:**
- Firecrawl rate limits
- LinkedIn blocking Firecrawl
- Invalid URLs
- Timeout issues

**Solutions:**
1. Check Firecrawl API status
2. Add delays between requests
3. Verify URLs are valid
4. Increase timeout values
5. Implement retry logic

## Performance Optimization

### 1. Reduce API Calls

**Current**: Searches for `max_results * 3` URLs, scrapes `max_results * 2`

**Optimization**: Cache search results, reuse scraped content

```python
# Add caching for search results
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search(self, query: str):
    return self.search_client.search(query)
```

### 2. Parallel Scraping

**Current**: Sequential scraping (one at a time)

**Optimization**: Use async/threading for parallel scraping

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Scrape multiple URLs in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(self._scrape_post, url) for url in urls]
    posts = [f.result() for f in futures if f.result()]
```

### 3. Early Filtering

**Current**: Scrapes then filters

**Optimization**: Filter search results before scraping

```python
# Filter search results by snippet/content preview
filtered_urls = [
    url for url in linkedin_urls
    if self._looks_promising(url, search_result.snippet)
]
```

## Validation Checklist

After fine-tuning, verify:

- [ ] Posts are being found (not empty results)
- [ ] Engagement scores are reasonable (not all 0)
- [ ] Author information is extracted (at least 50% of posts)
- [ ] Content is meaningful (not just navigation/ads)
- [ ] Hashtags are captured when present
- [ ] Filtering works (min_engagement_score filters correctly)
- [ ] Sorting works (engagement/recent/relevance)
- [ ] No duplicate posts in results
- [ ] Performance is acceptable (< 30 seconds for 10 posts)

## Next Steps

1. **Run initial tests** with the test script
2. **Identify issues** from test results
3. **Fine-tune parameters** based on your needs
4. **Test with real queries** you'll use in production
5. **Monitor performance** and adjust as needed
6. **Document your settings** for your use case

## Example Fine-Tuning Session

```bash
# 1. Initial test
./test_linkedin_search.sh

# 2. Test specific query
curl -X POST http://localhost:8080/api/linkedin/test?query=your%20topic&max_results=5

# 3. Check extraction quality
# Look at test_metadata.extraction_quality in response

# 4. If author extraction is low, improve _extract_author_info()
# 5. If engagement scores are low, improve _extract_engagement_metrics()
# 6. Re-test and compare results

# 7. Test with production queries
curl -X POST http://localhost:8080/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your actual query", "max_results": 20}'
```

---

**Remember**: Fine-tuning is iterative. Test, adjust, test again until results meet your needs!


