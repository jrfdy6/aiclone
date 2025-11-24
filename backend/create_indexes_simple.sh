#!/bin/bash

# Simple script to create Firestore indexes via Firebase CLI
# Alternative to Python script if Firebase CLI is installed

echo "🔧 Creating Firestore Indexes via Firebase CLI"
echo "=============================================="
echo ""

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "❌ Firebase CLI not found"
    echo ""
    echo "Install it with:"
    echo "  npm install -g firebase-tools"
    echo ""
    echo "Or use the manual links:"
    echo ""
    echo "1. Content Metrics:"
    echo "   https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClVwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9jb250ZW50X21ldHJpY3MvaW5kZXhlcy9fEAEaDgoKY29udGVudF9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC"
    echo ""
    echo "2. Prospect Metrics:"
    echo "   https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClZwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9wcm9zcGVjdF9tZXRyaWNzL2luZGV4ZXMvXxABGg8KC3Byb3NwZWN0X2lkEAEaDgoKY3JlYXRlZF9hdBACGgwKCF9fbmFtZV9fEAI"
    exit 1
fi

# Create firestore.indexes.json if it doesn't exist
cat > firestore.indexes.json << 'EOF'
{
  "indexes": [
    {
      "collectionGroup": "content_metrics",
      "queryScope": "COLLECTION",
      "fields": [
        {
          "fieldPath": "content_id",
          "order": "ASCENDING"
        },
        {
          "fieldPath": "created_at",
          "order": "DESCENDING"
        }
      ]
    },
    {
      "collectionGroup": "prospect_metrics",
      "queryScope": "COLLECTION",
      "fields": [
        {
          "fieldPath": "prospect_id",
          "order": "ASCENDING"
        },
        {
          "fieldPath": "created_at",
          "order": "DESCENDING"
        }
      ]
    }
  ],
  "fieldOverrides": []
}
EOF

echo "✅ Created firestore.indexes.json"
echo ""
echo "📋 Deploying indexes..."
firebase deploy --only firestore:indexes

echo ""
echo "✅ Done! Indexes will be ready in 2-5 minutes."
echo "   Check status: https://console.firebase.google.com/project/aiclone-14ccc/firestore/indexes"

