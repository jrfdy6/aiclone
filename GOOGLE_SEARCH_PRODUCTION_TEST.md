# Testing Google Custom Search in Production

This guide shows you how to test Google Custom Search functionality from the frontend in production.

## Overview

Google Custom Search is used in your app through:
1. **LinkedIn Search** (`/api/linkedin/search`) - Uses Google Custom Search to find LinkedIn posts
2. **Research Tasks** (`/api/research-tasks`) - Can use Google Search engine (partially implemented)

## Method 1: Test via LinkedIn Search (Recommended)

The LinkedIn search endpoint uses Google Custom Search under the hood to find LinkedIn posts. This is the easiest way to test Google Custom Search in production.

### Step 1: Access Your Production Frontend

1. Navigate to your production frontend URL (e.g., `https://aiclone-frontend-production.up.railway.app`)
2. Make sure you're logged in or using the app

### Step 2: Test via Browser Console

Open your browser's developer console (F12) and run:

```javascript
// Test Google Custom Search via LinkedIn endpoint
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://aiclone-production-32dc.up.railway.app';

async function testGoogleSearch() {
  try {
    console.log('🔍 Testing Google Custom Search via LinkedIn endpoint...');
    
    const response = await fetch(`${API_URL}/api/linkedin/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: 'AI tools for education',
        max_results: 5,
        industry: 'EdTech',
        sort_by: 'engagement'
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`HTTP ${response.status}: ${error.detail || response.statusText}`);
    }

    const data = await response.json();
    console.log('✅ Google Custom Search test successful!');
    console.log('📊 Results:', {
      total_results: data.total_results,
      posts_found: data.posts?.length || 0,
      first_post: data.posts?.[0] ? {
        url: data.posts[0].post_url,
        author: data.posts[0].author_name,
        engagement: data.posts[0].engagement_score
      } : null
    });
    console.log('📝 Full response:', data);
    
    return data;
  } catch (error) {
    console.error('❌ Test failed:', error);
    throw error;
  }
}

// Run the test
testGoogleSearch();
```

### Step 3: Test via LinkedIn Test Endpoint

The backend has a dedicated test endpoint that provides detailed metrics:

```javascript
async function testGoogleSearchDetailed() {
  try {
    console.log('🧪 Testing Google Custom Search with detailed metrics...');
    
    const response = await fetch(`${API_URL}/api/linkedin/test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: 'AI tools',
        max_results: 3
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`HTTP ${response.status}: ${error.detail || response.statusText}`);
    }

    const data = await response.json();
    console.log('✅ Detailed test successful!');
    console.log('📊 Extraction Quality:', data.test_metadata?.extraction_quality);
    console.log('📈 Engagement Stats:', data.test_metadata?.engagement_stats);
    console.log('📝 Posts:', data.posts);
    
    return data;
  } catch (error) {
    console.error('❌ Test failed:', error);
    throw error;
  }
}

testGoogleSearchDetailed();
```

## Method 2: Test via Research Tasks Page

You can also test Google Custom Search through the Research Tasks interface:

1. Navigate to `/research-tasks` in your production frontend
2. Click **"+ New Research Task"**
3. Fill in:
   - **Task Title:** "Test Google Search"
   - **Input Source:** "AI tools for education"
   - **Research Engine:** Select **"Google Search"**
4. Click **"Create Task"**
5. Click **"Run Now"** on the created task
6. Wait for the task to complete
7. Click **"View Insights"** to see results

**Note:** The Google Search engine in research tasks is currently a placeholder. For a full test, use Method 1.

## Method 3: Direct API Test (Using curl or Postman)

If you want to test the backend directly:

```bash
# Test LinkedIn search (uses Google Custom Search)
curl -X POST https://aiclone-production-32dc.up.railway.app/api/linkedin/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools for education",
    "max_results": 5,
    "industry": "EdTech"
  }'

# Test with detailed metrics
curl -X POST https://aiclone-production-32dc.up.railway.app/api/linkedin/test \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools",
    "max_results": 3
  }'
```

## What to Check

When testing, verify:

1. **✅ API Connection:** Request completes without errors
2. **✅ Results Returned:** You get search results back
3. **✅ Google Search Working:** Results contain LinkedIn post URLs found via Google Custom Search
4. **✅ Content Extraction:** Post content, author info, and engagement metrics are extracted
5. **✅ Error Handling:** If quota is exceeded, you get a clear error message

## Expected Results

### Success Response:
```json
{
  "success": true,
  "query": "AI tools for education",
  "total_results": 5,
  "posts": [
    {
      "post_id": "...",
      "post_url": "https://linkedin.com/posts/...",
      "author_name": "...",
      "content": "...",
      "engagement_score": 150,
      ...
    }
  ]
}
```

### Error Responses:

**Quota Exceeded:**
```json
{
  "detail": "Daily quota exceeded (100 free queries/day). Enable billing or wait 24h."
}
```

**Missing API Key:**
```json
{
  "detail": "GOOGLE_CUSTOM_SEARCH_API_KEY environment variable not set..."
}
```

## Troubleshooting

### Issue: "Configuration error"
- **Solution:** Check that `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` are set in Railway backend environment variables

### Issue: "Quota exceeded"
- **Solution:** Google Custom Search free tier allows 100 queries/day. Either:
  - Wait 24 hours for quota reset
  - Enable billing in Google Cloud Console for higher limits

### Issue: "No results found"
- **Solution:** Try a different search query. Some queries may not return LinkedIn posts.

### Issue: CORS errors
- **Solution:** Make sure your frontend URL is added to `CORS_ADDITIONAL_ORIGINS` in backend environment variables

## Quick Test Script

Save this as a bookmarklet or run in browser console:

```javascript
javascript:(async function(){
  const API_URL = 'https://aiclone-production-32dc.up.railway.app';
  const test = await fetch(`${API_URL}/api/linkedin/test`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: 'AI tools', max_results: 3})
  });
  const data = await test.json();
  console.log('Google Search Test:', data);
  alert(`Test ${data.success ? 'PASSED' : 'FAILED'}: ${data.total_posts_found || 0} posts found`);
})();
```

## Production URLs

Update these URLs with your actual Railway deployment URLs:

- **Backend API:** `https://aiclone-production-32dc.up.railway.app`
- **Frontend:** `https://aiclone-frontend-production.up.railway.app`

Replace with your actual URLs from Railway dashboard.

