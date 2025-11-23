#!/bin/bash

# API Keys Setup Script for Prospecting Workflow
# This script helps you set up all required API keys

echo "🔑 API Keys Setup for Prospecting Workflow"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env file exists
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env file..."
    touch "$ENV_FILE"
fi

echo "This script will help you set up the following API keys:"
echo "1. Google Custom Search API Key (NEW - for prospect discovery)"
echo "2. Google Custom Search Engine ID (NEW - for prospect discovery)"
echo "3. Perplexity API Key (for research)"
echo "4. Firecrawl API Key (for scraping)"
echo ""
echo "Let's start:"
echo ""

# Google Custom Search API Key
echo -e "${YELLOW}Step 1: Google Custom Search API Key${NC}"
echo "Get your API key from: https://console.cloud.google.com/apis/credentials"
echo "1. Go to Google Cloud Console"
echo "2. Create/select a project"
echo "3. Enable 'Custom Search API'"
echo "4. Create API Key"
echo ""
read -p "Enter your Google Custom Search API Key (or press Enter to skip): " GOOGLE_API_KEY

if [ ! -z "$GOOGLE_API_KEY" ]; then
    # Remove old entry if exists
    sed -i.bak '/^GOOGLE_CUSTOM_SEARCH_API_KEY=/d' "$ENV_FILE"
    echo "GOOGLE_CUSTOM_SEARCH_API_KEY=$GOOGLE_API_KEY" >> "$ENV_FILE"
    echo -e "${GREEN}✅ Google Custom Search API Key saved${NC}"
else
    echo -e "${YELLOW}⚠️  Skipped Google Custom Search API Key${NC}"
fi
echo ""

# Google Custom Search Engine ID
echo -e "${YELLOW}Step 2: Google Custom Search Engine ID${NC}"
echo "Get your Search Engine ID from: https://programmablesearchengine.google.com/"
echo "1. Go to Programmable Search Engine"
echo "2. Create a new search engine (set sites to search: *)"
echo "3. Copy the Search Engine ID"
echo ""
read -p "Enter your Google Custom Search Engine ID (or press Enter to skip): " GOOGLE_ENGINE_ID

if [ ! -z "$GOOGLE_ENGINE_ID" ]; then
    # Remove old entry if exists
    sed -i.bak '/^GOOGLE_CUSTOM_SEARCH_ENGINE_ID=/d' "$ENV_FILE"
    echo "GOOGLE_CUSTOM_SEARCH_ENGINE_ID=$GOOGLE_ENGINE_ID" >> "$ENV_FILE"
    echo -e "${GREEN}✅ Google Custom Search Engine ID saved${NC}"
else
    echo -e "${YELLOW}⚠️  Skipped Google Custom Search Engine ID${NC}"
fi
echo ""

# Perplexity API Key
echo -e "${YELLOW}Step 3: Perplexity API Key${NC}"
echo "Get your API key from: https://www.perplexity.ai/settings/api"
echo ""
read -p "Enter your Perplexity API Key (or press Enter to skip): " PERPLEXITY_KEY

if [ ! -z "$PERPLEXITY_KEY" ]; then
    # Remove old entry if exists
    sed -i.bak '/^PERPLEXITY_API_KEY=/d' "$ENV_FILE"
    echo "PERPLEXITY_API_KEY=$PERPLEXITY_KEY" >> "$ENV_FILE"
    echo -e "${GREEN}✅ Perplexity API Key saved${NC}"
else
    echo -e "${YELLOW}⚠️  Skipped Perplexity API Key${NC}"
fi
echo ""

# Firecrawl API Key
echo -e "${YELLOW}Step 4: Firecrawl API Key${NC}"
echo "Get your API key from: https://firecrawl.dev"
echo ""
read -p "Enter your Firecrawl API Key (or press Enter to skip): " FIRECRAWL_KEY

if [ ! -z "$FIRECRAWL_KEY" ]; then
    # Remove old entry if exists
    sed -i.bak '/^FIRECRAWL_API_KEY=/d' "$ENV_FILE"
    echo "FIRECRAWL_API_KEY=$FIRECRAWL_KEY" >> "$ENV_FILE"
    echo -e "${GREEN}✅ Firecrawl API Key saved${NC}"
else
    echo -e "${YELLOW}⚠️  Skipped Firecrawl API Key${NC}"
fi
echo ""

# Clean up backup file
rm -f "$ENV_FILE.bak"

echo ""
echo -e "${GREEN}=========================================="
echo "✅ Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Your API keys have been saved to: $ENV_FILE"
echo ""
echo "Next steps:"
echo "1. Load the environment variables:"
echo "   source .env"
echo ""
echo "2. Or export them in your shell:"
echo "   export \$(cat .env | xargs)"
echo ""
echo "3. Start your backend server:"
echo "   uvicorn app.main:app --reload"
echo ""
echo "4. Test the setup:"
echo "   See PROSPECTING_WORKFLOW_API_DOCS.md for test commands"
echo ""



