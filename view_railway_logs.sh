#!/bin/bash
# Railway CLI Log Viewer for Backend
# This script helps you view backend logs with filtering options

echo "🚂 Railway Backend Log Viewer"
echo "================================"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Install it first:"
    echo "   npm i -g @railway/cli"
    echo "   railway login"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged in to Railway. Run: railway login"
    exit 1
fi

echo "Select log view:"
echo "1. All backend logs (streaming)"
echo "2. Filter by category tags [CATEGORY: ...]"
echo "3. Filter by extraction [EXTRACTION START]"
echo "4. Filter by save summary [SAVE SUMMARY]"
echo "5. Filter by errors/warnings"
echo "6. Recent logs (last 100 lines)"
echo ""

read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo "📊 Streaming all backend logs..."
        railway logs --service aiclone-backend --follow
        ;;
    2)
        echo "📊 Filtering by category tags..."
        railway logs --service aiclone-backend --follow | grep --color=always -E "\[CATEGORY:|Category|category"
        ;;
    3)
        echo "📊 Filtering by extraction..."
        railway logs --service aiclone-backend --follow | grep --color=always -E "\[EXTRACTION START\]|Extracted.*prospects|Extracted organization"
        ;;
    4)
        echo "📊 Filtering by save summary..."
        railway logs --service aiclone-backend --follow | grep --color=always -E "\[SAVE SUMMARY\]|\[SAVE\]|CATEGORY BREAKDOWN|Total prospects|Successfully saved"
        ;;
    5)
        echo "📊 Filtering errors and warnings..."
        railway logs --service aiclone-backend --follow | grep --color=always -E "ERROR|WARN|Error|Warning|Failed|failed"
        ;;
    6)
        echo "📊 Last 100 lines of logs..."
        railway logs --service aiclone-backend --tail 100
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

