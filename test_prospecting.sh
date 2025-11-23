#!/bin/bash
# Quick test script for AI Clone prospecting/retrieval

echo "🧪 Testing AI Clone Prospecting/Retrieval"
echo "=========================================="
echo ""

BACKEND_URL="http://127.0.0.1:8080"
USER_ID="dev-user"

echo "1. Testing Chat Retrieval..."
RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/chat/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"query\":\"What is the onboarding prompt?\",\"top_k\":3}")

if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "   ✅ Chat retrieval working"
    RESULT_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('results', [])))" 2>/dev/null || echo "0")
    echo "   📊 Found $RESULT_COUNT result(s)"
else
    echo "   ❌ Chat retrieval failed"
    echo "   Response: $RESPONSE"
fi

echo ""
echo "2. Testing Knowledge Search..."
RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/knowledge/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"search_query\":\"starter prompts\",\"top_k\":5}")

if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "   ✅ Knowledge search working"
    RESULT_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('results', [])))" 2>/dev/null || echo "0")
    echo "   📊 Found $RESULT_COUNT result(s)"
else
    echo "   ❌ Knowledge search failed"
    echo "   Response: $RESPONSE"
fi

echo ""
echo "3. Testing Playbook Endpoints..."
PLAYBOOK_SUMMARY=$(curl -s "$BACKEND_URL/api/playbook/summary")
if echo "$PLAYBOOK_SUMMARY" | grep -q "movement"; then
    echo "   ✅ Playbook summary working"
else
    echo "   ❌ Playbook summary failed"
fi

echo ""
echo "=========================================="
echo "✅ Testing complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3002 in your browser"
echo "2. Try queries in the chat interface"
echo "3. Visit http://localhost:3002/knowledge for advanced search"
echo "4. Visit http://localhost:3002/jumpstart for playbook content"
