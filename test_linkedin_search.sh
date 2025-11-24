#!/bin/bash
# Test script for LinkedIn Post Search

echo "🔍 Testing LinkedIn Post Search"
echo "=================================="
echo ""

BACKEND_URL="http://127.0.0.1:8080"

# Check if backend is running
echo "1. Checking backend connection..."
if curl -s "$BACKEND_URL/health" > /dev/null; then
    echo "   ✅ Backend is running"
else
    echo "   ❌ Backend is not running. Start it first!"
    exit 1
fi

echo ""
echo "2. Testing LinkedIn Search Endpoint..."
echo "   Query: 'AI tools for developers'"
echo "   Max Results: 5"
echo ""

RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/linkedin/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools for developers",
    "max_results": 5,
    "sort_by": "engagement"
  }')

# Check if response is valid JSON and has success field
if echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    echo "   ✅ Search endpoint responded successfully"
    
    # Extract and display results
    TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_results', 0))" 2>/dev/null || echo "0")
    echo "   📊 Total results: $TOTAL"
    
    if [ "$TOTAL" -gt 0 ]; then
        echo ""
        echo "   Top posts found:"
        echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])[:3]
for i, post in enumerate(posts, 1):
    author = post.get('author_name', 'Unknown')
    score = post.get('engagement_score', 0)
    content_preview = post.get('content', '')[:100].replace('\n', ' ')
    print(f'   {i}. {author} (Score: {score})')
    print(f'      {content_preview}...')
    print()
" 2>/dev/null || echo "   (Could not parse post details)"
    else
        echo "   ⚠️  No posts found. This could mean:"
        echo "      - No LinkedIn posts match the query"
        echo "      - Google Custom Search needs configuration"
        echo "      - Firecrawl scraping failed"
    fi
else
    echo "   ❌ Search failed or returned error"
    echo "   Response: $RESPONSE" | head -20
fi

echo ""
echo "3. Testing with engagement filter..."
echo "   Query: 'SaaS marketing'"
echo "   Min Engagement Score: 50"
echo ""

RESPONSE2=$(curl -s -X POST "$BACKEND_URL/api/linkedin/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SaaS marketing",
    "max_results": 3,
    "min_engagement_score": 50.0,
    "sort_by": "engagement"
  }')

if echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    TOTAL2=$(echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_results', 0))" 2>/dev/null || echo "0")
    echo "   ✅ Filtered search completed"
    echo "   📊 Results with engagement >= 50: $TOTAL2"
else
    echo "   ❌ Filtered search failed"
fi

echo ""
echo "4. Testing extraction quality (test endpoint)..."
echo "   Query: 'AI tools'"
echo ""

RESPONSE_TEST=$(curl -s -X POST "$BACKEND_URL/api/linkedin/test" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI tools",
    "max_results": 3
  }')

if echo "$RESPONSE_TEST" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    echo "   ✅ Test endpoint working"
    QUALITY=$(echo "$RESPONSE_TEST" | python3 -c "
import sys, json
data = json.load(sys.stdin)
quality = data.get('test_metadata', {}).get('extraction_quality', {})
print(f\"Author extraction: {quality.get('author_extraction_rate', 0)}%\")
print(f\"Engagement extraction: {quality.get('engagement_extraction_rate', 0)}%\")
print(f\"Hashtag extraction: {quality.get('hashtag_extraction_rate', 0)}%\")
" 2>/dev/null || echo "Could not parse quality metrics")
    echo "$QUALITY"
else
    echo "   ❌ Test endpoint failed"
fi

echo ""
echo "5. Testing topic-based search..."
echo "   Topics: ['AI', 'developer tools']"
echo ""

RESPONSE3=$(curl -s -X POST "$BACKEND_URL/api/linkedin/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "technology",
    "topics": ["AI", "developer tools"],
    "max_results": 3
  }')

if echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    TOTAL2=$(echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_results', 0))" 2>/dev/null || echo "0")
    echo "   ✅ Filtered search completed"
    echo "   📊 Results with engagement >= 50: $TOTAL2"
else
    echo "   ❌ Filtered search failed"
fi

echo ""
echo "4. Testing topic-based search..."
echo "   Topics: ['AI', 'developer tools']"
echo ""

RESPONSE3=$(curl -s -X POST "$BACKEND_URL/api/linkedin/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "technology",
    "topics": ["AI", "developer tools"],
    "max_results": 3
  }')

if echo "$RESPONSE3" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    TOTAL3=$(echo "$RESPONSE3" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_results', 0))" 2>/dev/null || echo "0")
    echo "   ✅ Topic search completed"
    echo "   📊 Results: $TOTAL3"
else
    echo "   ❌ Topic search failed"
fi

echo ""
echo "6. Testing industry targeting..."
echo "   Industry: SaaS"
echo "   Query: 'product launch'"
echo ""

RESPONSE_INDUSTRY=$(curl -s -X POST "$BACKEND_URL/api/linkedin/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "product launch",
    "industry": "SaaS",
    "max_results": 3
  }')

if echo "$RESPONSE_INDUSTRY" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    TOTAL_INDUSTRY=$(echo "$RESPONSE_INDUSTRY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_results', 0))" 2>/dev/null || echo "0")
    echo "   ✅ Industry search completed"
    echo "   📊 Results for SaaS industry: $TOTAL_INDUSTRY"
else
    echo "   ❌ Industry search failed"
fi

echo ""
echo "7. Testing industry insights..."
echo "   Industry: SaaS"
echo ""

RESPONSE_INSIGHTS=$(curl -s "$BACKEND_URL/api/linkedin/industry/SaaS/insights?max_results=10")

if echo "$RESPONSE_INSIGHTS" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    echo "   ✅ Industry insights retrieved"
    INSIGHTS=$(echo "$RESPONSE_INSIGHTS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Posts analyzed: {data.get('total_posts_analyzed', 0)}\")
print(f\"Avg engagement: {data.get('average_engagement_score', 0)}\")
hashtags = data.get('top_hashtags', [])[:3]
if hashtags:
    print('Top hashtags:', ', '.join([h['tag'] for h in hashtags]))
" 2>/dev/null || echo "Could not parse insights")
    echo "$INSIGHTS"
else
    echo "   ❌ Industry insights failed"
fi

echo ""
echo "8. Listing available industries..."
echo ""

INDUSTRIES=$(curl -s "$BACKEND_URL/api/linkedin/industries")

if echo "$INDUSTRIES" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('success') else 1)" 2>/dev/null; then
    echo "   ✅ Industries endpoint working"
    INDUSTRY_LIST=$(echo "$INDUSTRIES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
industries = data.get('industries', [])
print('Available industries:', ', '.join(industries[:10]))
" 2>/dev/null || echo "Could not parse industries")
    echo "   $INDUSTRY_LIST"
else
    echo "   ❌ Industries endpoint failed"
fi

echo ""
echo "=================================="
echo "✅ Testing complete!"
echo ""
echo "Next steps:"
echo "1. Review the results above"
echo "2. Try different industries: curl $BACKEND_URL/api/linkedin/industries"
echo "3. Get insights for your industry: curl $BACKEND_URL/api/linkedin/industry/YOUR_INDUSTRY/insights"
echo "4. Search with industry targeting (see examples below)"
echo ""
echo "Industry targeting examples:"
echo "curl -X POST $BACKEND_URL/api/linkedin/search \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"your query\", \"industry\": \"SaaS\", \"max_results\": 10}'"
echo ""
echo "Get industry insights:"
echo "curl $BACKEND_URL/api/linkedin/industry/SaaS/insights"

