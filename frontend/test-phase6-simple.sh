#!/bin/bash

# Simple Phase 6 API Test Script
# Tests key endpoints to confirm Phase 6 is working

API_URL="${NEXT_PUBLIC_API_URL:-https://aiclone-production-32dc.up.railway.app}"
TEST_USER_ID="dev-user-test"

echo "🧪 Phase 6 API Test Suite"
echo "Testing against: $API_URL"
echo "=========================================="

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local body=$4
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "${API_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$body" \
            "${API_URL}${endpoint}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 400 ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $http_code)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $http_code)"
        echo "   Response: $body" | head -c 200
        echo ""
        ((FAILED++))
        return 1
    fi
}

echo ""
echo "📊 Testing Predictive Analytics..."
test_endpoint "Optimal Posting Time" "GET" "/api/predictive/optimal-posting-time?user_id=${TEST_USER_ID}"

echo ""
echo "🎯 Testing Recommendations..."
test_endpoint "Prospect Recommendations" "GET" "/api/recommendations/prospects?user_id=${TEST_USER_ID}&limit=5"
test_endpoint "Content Topic Recommendations" "GET" "/api/recommendations/content-topics?user_id=${TEST_USER_ID}&limit=5"
test_endpoint "Hashtag Recommendations" "GET" "/api/recommendations/hashtags?user_id=${TEST_USER_ID}&limit=5"

echo ""
echo "🧠 Testing NLP Services..."
test_endpoint "Detect Intent" "POST" "/api/nlp/detect-intent" '"I am interested in your product"'
test_endpoint "Extract Entities" "POST" "/api/nlp/extract-entities" '"John Smith works at Acme Corp"'
test_endpoint "Summarize Text" "POST" "/api/nlp/summarize?max_sentences=2" '"This is a long text that needs summarization. It has multiple sentences."'

echo ""
echo "✨ Testing Content Optimization..."
test_endpoint "Score Content" "POST" "/api/content-optimization/score" '{"content":"Sample post #AI","metadata":{"hashtags":["AI"]}}'

echo ""
echo "📈 Testing Business Intelligence..."
test_endpoint "Executive Dashboard" "GET" "/api/bi/executive-dashboard?user_id=${TEST_USER_ID}&days=30"

echo ""
echo "📝 Testing Content Generation..."
test_endpoint "Generate Blog Post" "POST" "/api/content/generate/blog" '{"topic":"AI in Education","length":"short","tone":"professional"}'
test_endpoint "Generate Email" "POST" "/api/content/generate/email" '{"subject":"Introduction","recipient_type":"prospect","purpose":"introduction"}'

echo ""
echo "📚 Testing Content Library..."
test_endpoint "List Content Library" "GET" "/api/content-library?user_id=${TEST_USER_ID}&limit=10"

echo ""
echo "🌐 Testing Cross-Platform Analytics..."
test_endpoint "Unified Performance" "GET" "/api/analytics/cross-platform/unified?user_id=${TEST_USER_ID}&days=30"

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Check output above.${NC}"
    exit 1
fi

