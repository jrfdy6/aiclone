#!/bin/bash

# Test Phase 4 APIs - Research Tasks and Activity Logging
# Backend URL (update if different)
API_URL="${API_URL:-https://aiclone-production-32dc.up.railway.app}"
USER_ID="dev-user"

echo "🧪 Testing Phase 4 APIs"
echo "========================"
echo "API URL: $API_URL"
echo "User ID: $USER_ID"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Create Research Task
echo -e "${YELLOW}Test 1: Create Research Task${NC}"
RESPONSE=$(curl -s -X POST "${API_URL}/api/research-tasks" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"${USER_ID}\",
    \"title\": \"Test Research: AI in Education\",
    \"input_source\": \"AI tools for personalized learning in K-12 education\",
    \"source_type\": \"keywords\",
    \"research_engine\": \"perplexity\",
    \"priority\": \"high\"
  }")

echo "Response: $RESPONSE"
TASK_ID=$(echo $RESPONSE | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
echo -e "${GREEN}✓ Created task ID: ${TASK_ID}${NC}"
echo ""

# Test 2: List Research Tasks
echo -e "${YELLOW}Test 2: List Research Tasks${NC}"
RESPONSE=$(curl -s -X GET "${API_URL}/api/research-tasks?user_id=${USER_ID}&limit=10")
echo "Response: $RESPONSE" | head -c 500
echo ""
echo -e "${GREEN}✓ Listed tasks${NC}"
echo ""

# Test 3: Get Research Task Details
if [ ! -z "$TASK_ID" ]; then
  echo -e "${YELLOW}Test 3: Get Research Task Details${NC}"
  RESPONSE=$(curl -s -X GET "${API_URL}/api/research-tasks/${TASK_ID}")
  echo "Response: $RESPONSE" | head -c 500
  echo ""
  echo -e "${GREEN}✓ Retrieved task details${NC}"
  echo ""
fi

# Test 4: Create Activity Log
echo -e "${YELLOW}Test 4: Create Activity Log${NC}"
RESPONSE=$(curl -s -X POST "${API_URL}/api/activity" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"${USER_ID}\",
    \"type\": \"research\",
    \"title\": \"Research Task Created\",
    \"message\": \"New research task created: Test Research\",
    \"metadata\": {
      \"task_id\": \"${TASK_ID}\"
    },
    \"link\": \"/research-tasks?id=${TASK_ID}\"
  }")

echo "Response: $RESPONSE"
ACTIVITY_ID=$(echo $RESPONSE | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
echo -e "${GREEN}✓ Created activity ID: ${ACTIVITY_ID}${NC}"
echo ""

# Test 5: List Activities
echo -e "${YELLOW}Test 5: List Activities${NC}"
RESPONSE=$(curl -s -X GET "${API_URL}/api/activity?user_id=${USER_ID}&limit=10")
echo "Response: $RESPONSE" | head -c 500
echo ""
echo -e "${GREEN}✓ Listed activities${NC}"
echo ""

# Test 6: Get Activity Details
if [ ! -z "$ACTIVITY_ID" ]; then
  echo -e "${YELLOW}Test 6: Get Activity Details${NC}"
  RESPONSE=$(curl -s -X GET "${API_URL}/api/activity/${ACTIVITY_ID}")
  echo "Response: $RESPONSE" | head -c 500
  echo ""
  echo -e "${GREEN}✓ Retrieved activity details${NC}"
  echo ""
fi

# Test 7: Run Research Task (if task exists)
if [ ! -z "$TASK_ID" ]; then
  echo -e "${YELLOW}Test 7: Run Research Task${NC}"
  RESPONSE=$(curl -s -X POST "${API_URL}/api/research-tasks/${TASK_ID}/run")
  echo "Response: $RESPONSE" | head -c 500
  echo ""
  echo -e "${GREEN}✓ Task execution started${NC}"
  echo ""
  
  echo -e "${YELLOW}Waiting 5 seconds for task to process...${NC}"
  sleep 5
  
  # Check task status
  echo -e "${YELLOW}Test 8: Check Task Status After Run${NC}"
  RESPONSE=$(curl -s -X GET "${API_URL}/api/research-tasks/${TASK_ID}")
  echo "Response: $RESPONSE" | head -c 500
  echo ""
fi

echo ""
echo -e "${GREEN}✅ All tests completed!${NC}"

