#!/bin/bash

# Detailed Phase 4 API Testing
API_URL="https://aiclone-production-32dc.up.railway.app"
USER_ID="dev-user"

echo "🧪 Phase 4 API Detailed Testing"
echo "================================="
echo ""

# Test 1: Create Research Task
echo "📝 Test 1: Create Research Task"
echo "--------------------------------"
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

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

TASK_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ ! -z "$TASK_ID" ]; then
  echo "✅ Created task ID: $TASK_ID"
else
  echo "❌ Failed to extract task ID"
fi
echo ""

# Test 2: List Research Tasks
echo "📋 Test 2: List Research Tasks"
echo "-------------------------------"
RESPONSE=$(curl -s -X GET "${API_URL}/api/research-tasks?user_id=${USER_ID}&limit=10")
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Test 3: Get Research Task Details
if [ ! -z "$TASK_ID" ]; then
  echo "🔍 Test 3: Get Research Task Details"
  echo "-------------------------------------"
  RESPONSE=$(curl -s -X GET "${API_URL}/api/research-tasks/${TASK_ID}")
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
fi

# Test 4: Create Activity Log
echo "📝 Test 4: Create Activity Log"
echo "-------------------------------"
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

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

ACTIVITY_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ ! -z "$ACTIVITY_ID" ]; then
  echo "✅ Created activity ID: $ACTIVITY_ID"
else
  echo "❌ Failed to extract activity ID"
fi
echo ""

# Test 5: List Activities
echo "📋 Test 5: List Activities"
echo "--------------------------"
RESPONSE=$(curl -s -X GET "${API_URL}/api/activity?user_id=${USER_ID}&limit=10")
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Test 6: List Activities with Filter
echo "📋 Test 6: List Activities (Filtered by type=research)"
echo "------------------------------------------------------"
RESPONSE=$(curl -s -X GET "${API_URL}/api/activity?user_id=${USER_ID}&type=research&limit=10")
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Test 7: Get Activity Details
if [ ! -z "$ACTIVITY_ID" ]; then
  echo "🔍 Test 7: Get Activity Details"
  echo "-------------------------------"
  RESPONSE=$(curl -s -X GET "${API_URL}/api/activity/${ACTIVITY_ID}")
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
fi

# Test 8: Run Research Task (if task exists)
if [ ! -z "$TASK_ID" ]; then
  echo "▶️  Test 8: Run Research Task"
  echo "-----------------------------"
  RESPONSE=$(curl -s -X POST "${API_URL}/api/research-tasks/${TASK_ID}/run")
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
  
  echo "⏳ Waiting 3 seconds for task to start processing..."
  sleep 3
  
  # Check task status
  echo "🔍 Test 9: Check Task Status After Run"
  echo "---------------------------------------"
  RESPONSE=$(curl -s -X GET "${API_URL}/api/research-tasks/${TASK_ID}")
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
fi

echo "✅ All tests completed!"

