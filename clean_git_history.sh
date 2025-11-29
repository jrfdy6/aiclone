#!/bin/bash
# CRITICAL: Clean git history to remove exposed service account keys
# This rewrites git history - make sure you want to do this!

echo "⚠️  WARNING: This will rewrite git history!"
echo "This removes service account keys from ALL commits."
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo "Removing keys from git history..."

# Remove keys from entire git history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch keys/*.json keys/*/*.json' \
  --prune-empty --tag-name-filter cat -- --all

echo ""
echo "✅ Git history cleaned!"
echo ""
echo "⚠️  NEXT STEP: Force push to GitHub:"
echo "   git push origin main --force"
echo ""
echo "⚠️  WARNING: Force push rewrites history on remote!"
echo "   Make sure no one else is working on this branch."
