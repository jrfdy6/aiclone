#!/bin/bash
# Capture recent Railway logs to a file for analysis

echo "📊 Capturing recent Railway backend logs..."
echo "This may take a moment..."

# Capture logs to file with a time limit
railway logs --service aiclone-backend > /tmp/railway_logs.txt 2>&1 &
PID=$!

# Wait 10 seconds to capture logs
sleep 10

# Kill the background process
kill $PID 2>/dev/null

# Show prospect-related logs
echo ""
echo "=== PROSPECT DISCOVERY LOGS ==="
grep -i -E "prospect|category|extraction|save summary|\[CATEGORY:|\[EXTRACTION|\[SAVE" /tmp/railway_logs.txt | tail -100

echo ""
echo "=== ERROR/WARNING LOGS ==="
grep -i -E "error|warn|failed|exception" /tmp/railway_logs.txt | tail -50

echo ""
echo "Full logs saved to: /tmp/railway_logs.txt"
echo "View with: cat /tmp/railway_logs.txt | grep -i prospect"

