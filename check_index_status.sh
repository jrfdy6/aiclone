#!/bin/bash

echo "🔍 Checking Firestore Index Status"
echo "===================================="
echo ""

# Test Content Metrics endpoint
echo "1️⃣ Content Metrics Index:"
CONTENT_RESULT=$(curl -s "https://aiclone-production-32dc.up.railway.app/api/metrics/enhanced/content/draft/test_content_1763991273?user_id=test-prod-1763991259" 2>&1)
if echo "$CONTENT_RESULT" | grep -q "index is currently building"; then
    echo "   ⏳ Status: BUILDING (index created, waiting to complete)"
elif echo "$CONTENT_RESULT" | grep -q "requires an index"; then
    echo "   ❌ Status: NOT CREATED (index needs to be created)"
else
    echo "   ✅ Status: WORKING (index is ready!)"
fi
echo ""

# Test Prospect Metrics endpoint  
echo "2️⃣ Prospect Metrics Index:"
PROSPECT_RESULT=$(curl -s "https://aiclone-production-32dc.up.railway.app/api/metrics/enhanced/prospects/test_prospect_1763991270?user_id=test-prod-1763991259" 2>&1)
if echo "$PROSPECT_RESULT" | grep -q "index is currently building"; then
    echo "   ⏳ Status: BUILDING (index created, waiting to complete - 2-5 minutes)"
elif echo "$PROSPECT_RESULT" | grep -q "requires an index"; then
    echo "   ❌ Status: NOT CREATED (index needs to be created)"
else
    echo "   ✅ Status: WORKING (index is ready!)"
fi
echo ""

echo "💡 Check detailed status:"
echo "   https://console.firebase.google.com/project/aiclone-14ccc/firestore/indexes"
echo ""
