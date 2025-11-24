#!/bin/bash

# Create Firestore indexes by opening Firebase Console links
# This will open the links in your default browser where you can click "Create" to create the indexes

echo "🔧 Opening Firebase Console to create indexes..."
echo "================================================"
echo ""
echo "This will open 2 browser tabs with the index creation pages."
echo "Just click 'Create' on each page!"
echo ""

# Open Content Metrics index
echo "1️⃣ Opening Content Metrics index creation page..."
open "https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClVwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9jb250ZW50X21ldHJpY3MvaW5kZXhlcy9fEAEaDgoKY29udGVudF9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC" 2>/dev/null || \
xdg-open "https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClVwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9jb250ZW50X21ldHJpY3MvaW5kZXhlcy9fEAEaDgoKY29udGVudF9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC" 2>/dev/null || \
echo "Please open this link manually:"
echo "https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClVwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9jb250ZW50X21ldHJpY3MvaW5kZXhlcy9fEAEaDgoKY29udGVudF9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC"

sleep 2

# Open Prospect Metrics index
echo ""
echo "2️⃣ Opening Prospect Metrics index creation page..."
open "https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClZwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9wcm9zcGVjdF9tZXRyaWNzL2luZGV4ZXMvXxABGg8KC3Byb3NwZWN0X2lkEAEaDgoKY3JlYXRlZF9hdBACGgwKCF9fbmFtZV9fEAI" 2>/dev/null || \
xdg-open "https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClZwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9wcm9zcGVjdF9tZXRyaWNzL2luZGV4ZXMvXxABGg8KC3Byb3NwZWN0X2lkEAEaDgoKY3JlYXRlZF9hdBACGgwKCF9fbmFtZV9fEAI" 2>/dev/null || \
echo "Please open this link manually:"
echo "https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClZwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9wcm9zcGVjdF9tZXRyaWNzL2luZGV4ZXMvXxABGg8KC3Byb3NwZWN0X2lkEAEaDgoKY3JlYXRlZF9hdBACGgwKCF9fbmFtZV9fEAI"

echo ""
echo "================================================"
echo "✅ Browser tabs opened!"
echo ""
echo "📋 Instructions:"
echo "   1. Sign in to Firebase Console if prompted"
echo "   2. Click 'Create Index' button on each page"
echo "   3. Wait 2-5 minutes for indexes to build"
echo ""
echo "🔍 Check index status:"
echo "   https://console.firebase.google.com/project/aiclone-14ccc/firestore/indexes"
echo ""

