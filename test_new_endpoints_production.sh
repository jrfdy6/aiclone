#!/bin/bash

# Test New Endpoints in Production
# Tests Outreach Engine and Enhanced Metrics endpoints

RAILWAY_URL="https://aiclone-production-32dc.up.railway.app"
USER_ID="test-prod-$(date +%s)"

echo "🚀 Testing New Endpoints in Production"
echo "======================================"
echo "URL: $RAILWAY_URL"
echo "User ID: $USER_ID"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local method=$2
    local url=$3
    local data=$4
    
    echo -e "${BLUE}Testing: $name${NC}"
    
    if [ "$method" == "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)
    
    if [ "$http_code" == "200" ] || [ "$http_code" == "201" ]; then
        echo -e "${GREEN}✅ PASSED (HTTP $http_code)${NC}"
        echo "$body" | head -c 200
        echo "..."
        ((PASSED++))
        echo ""
        return 0
    else
        echo -e "${RED}❌ FAILED (HTTP $http_code)${NC}"
        echo "Response: $body"
        ((FAILED++))
        echo ""
        return 1
    fi
}

# ====================
# Health Check
# ====================
echo "🔍 STEP 1: Health Check"
echo "-----------------------"
test_endpoint "Health Check" "GET" "$RAILWAY_URL/health"
echo ""

# ====================
# OUTREACH ENGINE TESTS
# ====================
echo "📧 OUTREACH ENGINE TESTS"
echo "========================"
echo ""

# First, we need some prospects to segment
echo "🔍 STEP 2: Discover Prospects (Prerequisite)"
echo "----------------------------------------------"
PROSPECT_DATA=$(curl -s -X POST "$RAILWAY_URL/api/prospects/discover" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"industry\": \"EdTech\",
    \"max_results\": 5
  }")

PROSPECT_IDS=$(echo "$PROSPECT_DATA" | grep -o '"prospect_id":"[^"]*"' | cut -d'"' -f4 | head -3)
PROSPECT_ID=$(echo "$PROSPECT_IDS" | head -1)

if [ -z "$PROSPECT_ID" ]; then
    echo -e "${YELLOW}⚠️  No prospects found, using mock prospect ID${NC}"
    PROSPECT_ID="test_prospect_$(date +%s)"
fi

echo "Using Prospect ID: $PROSPECT_ID"
echo ""

# Approve and score the prospect
if [ ! -z "$PROSPECT_ID" ] && [ "$PROSPECT_ID" != "test_prospect_"* ]; then
    echo "Approving prospect..."
    curl -s -X POST "$RAILWAY_URL/api/prospects/approve" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$USER_ID\",
        \"prospect_ids\": [\"$PROSPECT_ID\"],
        \"approval_status\": \"approved\"
      }" > /dev/null
    
    echo "Scoring prospect..."
    curl -s -X POST "$RAILWAY_URL/api/prospects/score" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$USER_ID\",
        \"prospect_ids\": [\"$PROSPECT_ID\"]
      }" > /dev/null
fi
echo ""

# Test 3: Segment Prospects
echo "🔍 STEP 3: Segment Prospects"
echo "-----------------------------"
test_endpoint "Segment Prospects" "POST" "$RAILWAY_URL/api/outreach/segment" \
  "{
    \"user_id\": \"$USER_ID\"
  }"
echo ""

# Test 4: Prioritize Prospects
echo "🔍 STEP 4: Prioritize Prospects"
echo "--------------------------------"
test_endpoint "Prioritize Prospects" "POST" "$RAILWAY_URL/api/outreach/prioritize" \
  "{
    \"user_id\": \"$USER_ID\",
    \"min_fit_score\": 50,
    \"min_referral_capacity\": 40,
    \"min_signal_strength\": 30,
    \"limit\": 10
  }"
echo ""

# Test 5: Generate Outreach Sequence
echo "🔍 STEP 5: Generate Outreach Sequence"
echo "--------------------------------------"
test_endpoint "Generate Outreach Sequence" "POST" "$RAILWAY_URL/api/outreach/sequence/generate" \
  "{
    \"user_id\": \"$USER_ID\",
    \"prospect_id\": \"$PROSPECT_ID\",
    \"sequence_type\": \"3-step\",
    \"num_variants\": 2
  }"
echo ""

# Test 6: Generate Weekly Cadence
echo "🔍 STEP 6: Generate Weekly Cadence"
echo "-----------------------------------"
test_endpoint "Generate Weekly Cadence" "POST" "$RAILWAY_URL/api/outreach/cadence/weekly" \
  "{
    \"user_id\": \"$USER_ID\",
    \"target_connection_requests\": 10,
    \"target_followups\": 5
  }"
echo ""

# Test 7: Track Engagement
echo "🔍 STEP 7: Track Engagement"
echo "----------------------------"
test_endpoint "Track Engagement" "POST" "$RAILWAY_URL/api/outreach/track-engagement" \
  "{
    \"user_id\": \"$USER_ID\",
    \"prospect_id\": \"$PROSPECT_ID\",
    \"outreach_type\": \"initial_dm\",
    \"engagement_status\": \"replied\",
    \"engagement_data\": {
      \"reply_text\": \"Thanks, I'm interested!\"
    }
  }"
echo ""

# Test 8: Get Outreach Metrics
echo "🔍 STEP 8: Get Outreach Metrics"
echo "--------------------------------"
test_endpoint "Get Outreach Metrics" "POST" "$RAILWAY_URL/api/outreach/metrics" \
  "{
    \"user_id\": \"$USER_ID\",
    \"date_range_days\": 30
  }"
echo ""

# ====================
# ENHANCED METRICS TESTS
# ====================
echo "📊 ENHANCED METRICS TESTS"
echo "========================="
echo ""

# Test 9: Update Content Metrics
echo "🔍 STEP 9: Update Content Metrics"
echo "----------------------------------"
CONTENT_ID="test_content_$(date +%s)"
test_endpoint "Update Content Metrics" "POST" "$RAILWAY_URL/api/metrics/enhanced/content/update" \
  "{
    \"user_id\": \"$USER_ID\",
    \"content_id\": \"$CONTENT_ID\",
    \"pillar\": \"thought_leadership\",
    \"platform\": \"LinkedIn\",
    \"post_type\": \"post\",
    \"post_url\": \"https://linkedin.com/posts/test\",
    \"publish_date\": \"2024-12-24T09:00:00Z\",
    \"metrics\": {
      \"likes\": 45,
      \"comments\": 12,
      \"shares\": 8,
      \"reactions\": {
        \"like\": 30,
        \"love\": 10,
        \"celebrate\": 5,
        \"insightful\": 0,
        \"curious\": 0
      },
      \"impressions\": 500,
      \"profile_views\": 25,
      \"clicks\": 10
    },
    \"top_hashtags\": [\"#AI\", \"#EdTech\"],
    \"top_mentions\": [],
    \"audience_segment\": [\"edtech_executives\"]
  }"
echo ""

# Test 10: Get Content Metrics
echo "🔍 STEP 10: Get Content Metrics for Draft"
echo "------------------------------------------"
test_endpoint "Get Content Metrics" "GET" "$RAILWAY_URL/api/metrics/enhanced/content/draft/$CONTENT_ID?user_id=$USER_ID"
echo ""

# Test 11: Update Prospect Metrics
echo "🔍 STEP 11: Update Prospect Metrics"
echo "------------------------------------"
test_endpoint "Update Prospect Metrics" "POST" "$RAILWAY_URL/api/metrics/enhanced/prospects/update" \
  "{
    \"user_id\": \"$USER_ID\",
    \"prospect_id\": \"$PROSPECT_ID\",
    \"sequence_id\": \"test_sequence_123\",
    \"connection_request_sent\": \"2024-12-20T09:00:00Z\",
    \"connection_accepted\": \"2024-12-21T14:00:00Z\",
    \"dm_sent\": [
      {
        \"message_id\": \"dm_001\",
        \"sent_at\": \"2024-12-22T10:00:00Z\",
        \"response_received_at\": \"2024-12-22T15:30:00Z\",
        \"response_text\": \"Thanks, I'm interested!\",
        \"response_type\": \"positive\"
      }
    ],
    \"meetings_booked\": [
      {
        \"meeting_id\": \"meeting_001\",
        \"scheduled_at\": \"2024-12-28T14:00:00Z\",
        \"attended\": false,
        \"notes\": \"Scheduled for next week\"
      }
    ]
  }"
echo ""

# Test 12: Get Prospect Metrics
echo "🔍 STEP 12: Get Prospect Metrics"
echo "---------------------------------"
test_endpoint "Get Prospect Metrics" "GET" "$RAILWAY_URL/api/metrics/enhanced/prospects/$PROSPECT_ID?user_id=$USER_ID"
echo ""

# Test 13: Update Learning Patterns
echo "🔍 STEP 13: Update Learning Patterns"
echo "-------------------------------------"
test_endpoint "Update Learning Patterns" "POST" "$RAILWAY_URL/api/metrics/enhanced/learning/update-patterns" \
  "{
    \"user_id\": \"$USER_ID\",
    \"pattern_type\": null,
    \"date_range_days\": 30
  }"
echo ""

# Test 14: Get Learning Patterns
echo "🔍 STEP 14: Get Learning Patterns"
echo "----------------------------------"
test_endpoint "Get Learning Patterns" "GET" "$RAILWAY_URL/api/metrics/enhanced/learning/patterns?user_id=$USER_ID&limit=10"
echo ""

# Test 15: Generate Weekly Report
echo "🔍 STEP 15: Generate Weekly Report"
echo "-----------------------------------"
test_endpoint "Generate Weekly Report" "POST" "$RAILWAY_URL/api/metrics/enhanced/weekly-report" \
  "{
    \"user_id\": \"$USER_ID\"
  }"
echo ""

# ====================
# SUMMARY
# ====================
echo "======================================"
echo "📊 TEST SUMMARY"
echo "======================================"
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"
echo ""
echo "Total Tests: $((PASSED + FAILED))"
echo ""
echo "User ID used: $USER_ID"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Check output above.${NC}"
    exit 1
fi

