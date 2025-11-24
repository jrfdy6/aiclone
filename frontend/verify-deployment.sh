#!/bin/bash

# Verify Railway Frontend Deployment
# This script checks if the frontend is properly configured and can connect to the backend

set -e

echo "🚀 Verifying Railway Frontend Deployment..."
echo ""

# Check if API URL is set
if [ -z "$NEXT_PUBLIC_API_URL" ]; then
    echo "❌ ERROR: NEXT_PUBLIC_API_URL is not set"
    echo "   Please set it in Railway Dashboard → Settings → Variables"
    exit 1
else
    echo "✅ NEXT_PUBLIC_API_URL is set: $NEXT_PUBLIC_API_URL"
fi

# Test backend connection
echo ""
echo "🔌 Testing backend connection..."
if curl -f -s "$NEXT_PUBLIC_API_URL/" > /dev/null 2>&1; then
    echo "✅ Backend is reachable"
else
    echo "❌ WARNING: Backend is not reachable at $NEXT_PUBLIC_API_URL"
    echo "   Check your backend service is running on Railway"
fi

# Check if build directory exists
echo ""
echo "📦 Checking build artifacts..."
if [ -d ".next" ]; then
    echo "✅ Build directory (.next) exists"
else
    echo "❌ ERROR: Build directory not found. Run 'npm run build' first"
    exit 1
fi

# Check package.json scripts
echo ""
echo "📋 Verifying package.json scripts..."
if grep -q '"start"' package.json; then
    echo "✅ 'start' script found"
else
    echo "❌ ERROR: 'start' script not found in package.json"
    exit 1
fi

echo ""
echo "✅ All checks passed! Frontend is ready for deployment."

