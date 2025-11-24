#!/bin/bash

# Comprehensive Test Suite for All Phase 4 APIs
API_URL="${API_URL:-https://aiclone-production-32dc.up.railway.app}"
USER_ID="dev-user"

echo "🧪 Comprehensive Phase 4 API Test Suite"
echo "========================================"
echo "API URL: $API_URL"
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
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    
    echo -e "${BLUE}Testing: $name${NC}"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "${API_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "${API_URL}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $http_code)"
        echo "$body" | python3 -m json.tool 2>/dev/null | head -10 || echo "$body" | head -5
        ((PASSED++))
        echo ""
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $http_code)"
        echo "$body" | head -5
        ((FAILED++))
        echo ""
        return 1
    fi
}

# ==========================================
# 1. Research Tasks API
# ==========================================
echo -e "${YELLOW}=== 1. Research Tasks API ===${NC}"

test_endpoint "Create Research Task" "POST" "/api/research-tasks" "{
    \"user_id\": \"$USER_ID\",
    \"title\": \"Test Research\",
    \"input_source\": \"AI in education\",
    \"source_type\": \"keywords\",
    \"research_engine\": \"perplexity\",
    \"priority\": \"high\"
}"

RESEARCH_TASK_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$RESEARCH_TASK_ID" ]; then
    test_endpoint "List Research Tasks" "GET" "/api/research-tasks?user_id=$USER_ID&limit=5"
    test_endpoint "Get Research Task" "GET" "/api/research-tasks/$RESEARCH_TASK_ID"
fi

# ==========================================
# 2. Activity API
# ==========================================
echo -e "${YELLOW}=== 2. Activity Logging API ===${NC}"

test_endpoint "Create Activity" "POST" "/api/activity" "{
    \"user_id\": \"$USER_ID\",
    \"type\": \"research\",
    \"title\": \"Test Activity\",
    \"message\": \"Testing activity logging\"
}"

ACTIVITY_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$ACTIVITY_ID" ]; then
    test_endpoint "Get Activity" "GET" "/api/activity/$ACTIVITY_ID"
fi

test_endpoint "List Activities" "GET" "/api/activity?user_id=$USER_ID&limit=5"

# ==========================================
# 3. Templates API
# ==========================================
echo -e "${YELLOW}=== 3. Templates API ===${NC}"

test_endpoint "Create Template" "POST" "/api/templates" "{
    \"user_id\": \"$USER_ID\",
    \"name\": \"Test Template\",
    \"category\": \"linkedin_post\",
    \"content\": \"Hello {name}, welcome!\",
    \"description\": \"Test template\"
}"

TEMPLATE_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$TEMPLATE_ID" ]; then
    test_endpoint "Get Template" "GET" "/api/templates/$TEMPLATE_ID"
    test_endpoint "Toggle Favorite" "POST" "/api/templates/$TEMPLATE_ID/favorite"
    test_endpoint "Use Template" "POST" "/api/templates/$TEMPLATE_ID/use" "{
        \"user_id\": \"$USER_ID\",
        \"variables\": {\"name\": \"John\"}
    }"
fi

test_endpoint "List Templates" "GET" "/api/templates?user_id=$USER_ID&limit=5"

# ==========================================
# 4. Vault API
# ==========================================
echo -e "${YELLOW}=== 4. Knowledge Vault API ===${NC}"

test_endpoint "Create Vault Item" "POST" "/api/vault" "{
    \"user_id\": \"$USER_ID\",
    \"title\": \"Test Insight\",
    \"summary\": \"Test insight summary\",
    \"category\": \"industry_insights\",
    \"tags\": [\"test\", \"insight\"]
}"

VAULT_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$VAULT_ID" ]; then
    test_endpoint "Get Vault Item" "GET" "/api/vault/$VAULT_ID"
fi

test_endpoint "List Vault Items" "GET" "/api/vault?user_id=$USER_ID&limit=5"
test_endpoint "Get Topic Clusters" "GET" "/api/vault/topics/clusters?user_id=$USER_ID"

# ==========================================
# 5. Personas API
# ==========================================
echo -e "${YELLOW}=== 5. Personas API ===${NC}"

test_endpoint "Create Persona" "POST" "/api/personas" "{
    \"user_id\": \"$USER_ID\",
    \"name\": \"Test Persona\",
    \"outreach_tone\": \"professional\",
    \"industry_focus\": [\"education\"]
}"

PERSONA_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$PERSONA_ID" ]; then
    test_endpoint "Get Persona" "GET" "/api/personas/$PERSONA_ID"
    test_endpoint "Set Default Persona" "POST" "/api/personas/$PERSONA_ID/set-default?user_id=$USER_ID"
fi

test_endpoint "List Personas" "GET" "/api/personas?user_id=$USER_ID"

# ==========================================
# 6. System Logs API
# ==========================================
echo -e "${YELLOW}=== 6. System Logs API ===${NC}"

test_endpoint "Create Log" "POST" "/api/system/logs" "{
    \"user_id\": \"$USER_ID\",
    \"level\": \"info\",
    \"category\": \"system\",
    \"message\": \"Test log entry\"
}"

LOG_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$LOG_ID" ]; then
    test_endpoint "Get Log" "GET" "/api/system/logs/$LOG_ID"
fi

test_endpoint "List Logs" "GET" "/api/system/logs?user_id=$USER_ID&limit=5"
test_endpoint "Get Log Stats" "GET" "/api/system/logs/stats/summary?user_id=$USER_ID"

# ==========================================
# 7. Automations API
# ==========================================
echo -e "${YELLOW}=== 7. Automations Engine API ===${NC}"

test_endpoint "Create Automation" "POST" "/api/automations" "{
    \"user_id\": \"$USER_ID\",
    \"name\": \"Test Automation\",
    \"trigger\": \"new_prospect_added\",
    \"actions\": [\"generate_outreach\", \"send_notification\"]
}"

AUTOMATION_ID=$(echo "$body" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4 || echo "")

if [ ! -z "$AUTOMATION_ID" ]; then
    test_endpoint "Get Automation" "GET" "/api/automations/$AUTOMATION_ID"
    test_endpoint "Activate Automation" "POST" "/api/automations/$AUTOMATION_ID/activate"
    test_endpoint "Get Executions" "GET" "/api/automations/$AUTOMATION_ID/executions"
fi

test_endpoint "List Automations" "GET" "/api/automations?user_id=$USER_ID&limit=5"

# ==========================================
# 8. Playbooks API (Enhanced)
# ==========================================
echo -e "${YELLOW}=== 8. Playbooks API (Enhanced) ===${NC}"

test_endpoint "List Playbooks" "GET" "/api/playbooks?user_id=$USER_ID"
test_endpoint "Get Playbook" "GET" "/api/playbooks/ai_advantage_jumpstart?user_id=$USER_ID"
test_endpoint "Toggle Favorite" "POST" "/api/playbooks/ai_advantage_jumpstart/favorite?user_id=$USER_ID"
test_endpoint "Get Favorites" "GET" "/api/playbooks/favorites/list?user_id=$USER_ID"

# ==========================================
# Summary
# ==========================================
echo ""
echo -e "${YELLOW}=== Test Summary ===${NC}"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

