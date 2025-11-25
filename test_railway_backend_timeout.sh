#!/bin/bash

# Comprehensive Railway Backend API Test Script
# Tests for timeout issues and structured JSON responses

RAILWAY_URL="https://aiclone-production-32dc.up.railway.app"
TIMEOUT=30  # 30 second timeout per request
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Railway Backend API Timeout Test"
echo "=========================================="
echo "Testing: $RAILWAY_URL"
echo "Timeout: ${TIMEOUT}s per request"
echo ""

# Test function
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "[$TOTAL_TESTS] Testing $description... "
    
    local start_time=$(date +%s)
    local response
    local status_code
    local elapsed_time
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -L -w "\n%{http_code}" --max-time $TIMEOUT \
            -H "Content-Type: application/json" \
            "$RAILWAY_URL$endpoint" 2>&1)
    else
        response=$(curl -s -L -w "\n%{http_code}" --max-time $TIMEOUT \
            -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$RAILWAY_URL$endpoint" 2>&1)
    fi
    
    local end_time=$(date +%s)
    elapsed_time=$((end_time - start_time))
    
    # Extract status code (last line)
    status_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | sed '$d')
    
    # Check for timeout
    if echo "$response" | grep -q "Operation timed out\|timeout\|Connection timed out"; then
        echo -e "${RED}FAILED - TIMEOUT after ${elapsed_time}s${NC}"
        echo "  Error: Request timed out"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
    
    # Check for connection errors
    if echo "$response" | grep -q "Failed to connect\|Connection refused\|Could not resolve"; then
        echo -e "${RED}FAILED - CONNECTION ERROR${NC}"
        echo "  Error: Could not connect to server"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
    
    # Check status code
    if [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
        # Check if response is valid JSON
        if echo "$response_body" | jq . >/dev/null 2>&1; then
            # Check if response is structured (not chatty/verbose)
            local word_count=$(echo "$response_body" | wc -w)
            if [ "$word_count" -lt 1000 ]; then  # Reasonable limit for structured JSON
                echo -e "${GREEN}PASS${NC} (${elapsed_time}s, ${status_code})"
                PASSED_TESTS=$((PASSED_TESTS + 1))
                return 0
            else
                echo -e "${YELLOW}WARNING - Response too verbose (${word_count} words)${NC}"
                echo "  Response preview: $(echo "$response_body" | head -c 200)..."
                PASSED_TESTS=$((PASSED_TESTS + 1))
                return 0
            fi
        else
            echo -e "${RED}FAILED - Invalid JSON${NC}"
            echo "  Response: $(echo "$response_body" | head -c 200)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            return 1
        fi
    elif [ "$status_code" -ge 400 ] && [ "$status_code" -lt 500 ]; then
        # 4xx errors are acceptable if they return structured JSON
        if echo "$response_body" | jq . >/dev/null 2>&1; then
            echo -e "${YELLOW}WARNING - Client Error (${status_code})${NC}"
            echo "  Response: $(echo "$response_body" | jq -c . | head -c 200)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            return 0
        else
            echo -e "${RED}FAILED - Client Error (${status_code}) without JSON${NC}"
            echo "  Response: $(echo "$response_body" | head -c 200)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            return 1
        fi
    else
        echo -e "${RED}FAILED - Server Error (${status_code})${NC}"
        echo "  Response: $(echo "$response_body" | head -c 200)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Test 1: Health endpoint
test_endpoint "GET" "/health" "" "Health Check"

# Test 2: Root endpoint
test_endpoint "GET" "/" "" "Root Endpoint"

# Test 3: Test endpoint
test_endpoint "GET" "/test" "" "Test Endpoint"

# Test 4: Chat/Query endpoint (retrieval)
echo ""
echo "--- Testing Query/Retrieval Endpoints ---"
test_endpoint "POST" "/api/chat/" \
    '{"user_id":"test_user","query":"What is AI?","top_k":3}' \
    "Chat Query (Retrieval)"

# Test 5: Knowledge search endpoint
test_endpoint "POST" "/api/knowledge/" \
    '{"user_id":"test_user","search_query":"machine learning","top_k":5}' \
    "Knowledge Search"

# Test 6: Prospects listing (prospect scoring)
echo ""
echo "--- Testing Prospect Endpoints ---"
test_endpoint "GET" "/api/prospects/?user_id=test_user&limit=10" "" "List Prospects"

# Test 7: Content generation endpoints
echo ""
echo "--- Testing Content Generation Endpoints ---"
test_endpoint "POST" "/api/content/generate/blog" \
    '{"topic":"AI in business","length":"short","tone":"professional"}' \
    "Generate Blog Post"

test_endpoint "POST" "/api/content/generate/email" \
    '{"subject":"Introduction","recipient_type":"prospect","purpose":"introduction","tone":"professional"}' \
    "Generate Email"

# Test 8: Research tasks (Firestore access)
echo ""
echo "--- Testing Research/Data Endpoints ---"
test_endpoint "GET" "/api/research-tasks?user_id=test_user&limit=5" "" "Research Tasks"

# Test 9: Analytics endpoint
test_endpoint "GET" "/api/analytics/summary?user_id=test_user" "" "Analytics Summary"

# Test 10: Templates endpoint
test_endpoint "GET" "/api/templates?user_id=test_user" "" "Templates"

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed! No timeout issues detected.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check the output above for details.${NC}"
    exit 1
fi

