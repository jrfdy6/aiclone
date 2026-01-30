#!/bin/bash

# Test Frontend Connection to Backend
echo "🧪 Testing Frontend Connection to Backend"
echo "=========================================="
echo ""

# Check if backend is running
echo "1. Checking if backend is running..."
if curl -s http://127.0.0.1:8080/ > /dev/null; then
    echo "   ✅ Backend is running on port 8080"
else
    echo "   ❌ Backend is not running. Start it with:"
    echo "      cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080"
    exit 1
fi

# Check if frontend is running
echo ""
echo "2. Checking if frontend is running..."
if curl -s http://localhost:3000/ > /dev/null; then
    echo "   ✅ Frontend is running on port 3000"
else
    echo "   ❌ Frontend is not running. Start it with:"
    echo "      cd frontend && npm run dev"
    exit 1
fi

# Test API endpoints from frontend's perspective
echo ""
echo "3. Testing API endpoints (simulating frontend requests)..."
echo ""

# Test Playbook Summary
echo "   Testing /api/playbook/summary..."
RESPONSE=$(curl -s -H "Origin: http://localhost:3000" http://127.0.0.1:8080/api/playbook/summary)
if echo "$RESPONSE" | grep -q "movement"; then
    echo "   ✅ Playbook summary endpoint works"
else
    echo "   ❌ Playbook summary failed: $RESPONSE"
fi

# Test Playbook Onboarding
echo "   Testing /api/playbook/onboarding..."
RESPONSE=$(curl -s -H "Origin: http://localhost:3000" http://127.0.0.1:8080/api/playbook/onboarding)
if echo "$RESPONSE" | grep -q "prompt"; then
    echo "   ✅ Onboarding prompt endpoint works"
else
    echo "   ❌ Onboarding prompt failed: $RESPONSE"
fi

# Test Playbook Prompts
echo "   Testing /api/playbook/prompts..."
RESPONSE=$(curl -s -H "Origin: http://localhost:3000" http://127.0.0.1:8080/api/playbook/prompts)
if echo "$RESPONSE" | grep -q "prompts"; then
    echo "   ✅ Starter prompts endpoint works"
else
    echo "   ❌ Starter prompts failed: $RESPONSE"
fi

# Test Chat Retrieval
echo "   Testing /api/chat/..."
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -H "Origin: http://localhost:3000" \
    -d '{"user_id":"dev-user","query":"test"}' http://127.0.0.1:8080/api/chat/)
if echo "$RESPONSE" | grep -q "success"; then
    echo "   ✅ Chat retrieval endpoint works"
else
    echo "   ⚠️  Chat retrieval response: $RESPONSE"
fi

# Test Ingest Drive (dry run - just check if endpoint exists)
echo "   Testing /api/ingest_drive endpoint..."
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -H "Origin: http://localhost:3000" \
    -d '{"user_id":"dev-user","folder_id":"test"}' http://127.0.0.1:8080/api/ingest_drive)
if echo "$RESPONSE" | grep -q "success\|error\|message"; then
    echo "   ✅ Ingest drive endpoint is accessible"
else
    echo "   ❌ Ingest drive failed: $RESPONSE"
fi

echo ""
echo "=========================================="
echo "✅ Frontend connection test complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3000/jumpstart in your browser"
echo "2. You should see the Playbook content load"
echo "3. Try ingesting a Drive folder with:"
echo "   - User ID: dev-user"
echo "   - Folder ID: 1sZQZ9r3kfxgSR5A7HOFtU159B-HhvJRH"
echo "   - Max Files: 5 (optional)"
echo "4. Check browser console (F12) for any errors"



