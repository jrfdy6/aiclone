# Environment Variables Guide

This guide covers all environment variables needed for the vibe marketing features.

## Required for Prospecting Workflow

### Google Custom Search API Key (NEW)
**Variable**: `GOOGLE_CUSTOM_SEARCH_API_KEY`  
**Purpose**: Powers prospect discovery via search  
**How to get it**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable "Custom Search API" (APIs & Services → Library)
4. Go to APIs & Services → Credentials
5. Click "Create Credentials" → "API Key"
6. Copy the key

**Set locally**:
```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-api-key-here"
```

**Set in Railway**:
1. Go to Railway Dashboard → Your Service → Variables
2. Click "New Variable"
3. Name: `GOOGLE_CUSTOM_SEARCH_API_KEY`
4. Value: Your API key
5. Click "Add"

### Google Custom Search Engine ID (NEW)
**Variable**: `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`  
**Purpose**: Identifies your custom search engine  
**How to get it**:
1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click "Add" to create a new search engine
3. **Sites to search**: Enter `*` (asterisk) to search entire web
4. Click "Create"
5. Copy the Search Engine ID (looks like: `017576662512468239146:omuauf_lfve`)

**Set locally**:
```bash
export GOOGLE_CUSTOM_SEARCH_ENGINE_ID="your-search-engine-id"
```

**Set in Railway**:
1. Go to Railway Dashboard → Your Service → Variables
2. Click "New Variable"
3. Name: `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`
4. Value: Your Search Engine ID
5. Click "Add"

**Pricing**: 100 free queries/day, then $5 per 1,000 queries

## Required for Content Marketing Features

### Perplexity API Key
**Variable**: `PERPLEXITY_API_KEY`  
**Purpose**: Powers content research and search functionality  
**How to get it**:
1. Go to [Perplexity Settings](https://www.perplexity.ai/settings/api)
2. Sign up or log in
3. Generate an API key
4. Copy the key

**Set locally**:
```bash
export PERPLEXITY_API_KEY="your-api-key-here"
```

**Set in Railway**:
1. Go to Railway Dashboard → Your Service → Variables
2. Click "New Variable"
3. Name: `PERPLEXITY_API_KEY`
4. Value: Your API key
5. Click "Add"

### Firecrawl API Key
**Variable**: `FIRECRAWL_API_KEY`  
**Purpose**: Powers web scraping and crawling for internal linking analysis  
**How to get it**:
1. Go to [Firecrawl](https://firecrawl.dev)
2. Sign up for an account
3. Navigate to API Keys section
4. Generate a new API key
5. Copy the key

**Set locally**:
```bash
export FIRECRAWL_API_KEY="your-api-key-here"
```

**Set in Railway**:
1. Go to Railway Dashboard → Your Service → Variables
2. Click "New Variable"
3. Name: `FIRECRAWL_API_KEY`
4. Value: Your API key
5. Click "Add"

## Existing Environment Variables

These are already configured in your project:

### Firebase Service Account
**Variable**: `FIREBASE_SERVICE_ACCOUNT`  
**Purpose**: Firestore database access  
**Status**: ✅ Already configured

### Google Drive Service Account
**Variable**: `GOOGLE_DRIVE_SERVICE_ACCOUNT`  
**Purpose**: Google Drive ingestion  
**Status**: ✅ Already configured

## Local Development Setup

Create a `.env` file in the `backend/` directory (or export in your shell):

```bash
# Backend .env file
PERPLEXITY_API_KEY=your-perplexity-key
FIRECRAWL_API_KEY=your-firecrawl-key

# Existing variables (if not using service account files)
FIREBASE_SERVICE_ACCOUNT="$(cat ../keys/firebase-service-account.json | jq -c .)"
GOOGLE_DRIVE_SERVICE_ACCOUNT="$(cat ../keys/aiclone-drive-ingest-e717f9932b1b.json | jq -c .)"
```

Or export in your shell:
```bash
export PERPLEXITY_API_KEY="your-key"
export FIRECRAWL_API_KEY="your-key"
```

## Railway Production Setup

1. Go to Railway Dashboard
2. Select your backend service
3. Go to "Variables" tab
4. Add these variables:
   - `PERPLEXITY_API_KEY` = [your key]
   - `FIRECRAWL_API_KEY` = [your key]
5. Railway will automatically redeploy

## Testing Your Setup

### Test Perplexity
```bash
curl -X POST http://localhost:8080/api/content/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "best AI tools 2025", "num_results": 5}'
```

If you get an error about `PERPLEXITY_API_KEY`, the key is not set correctly.

### Test Firecrawl
```bash
curl -X POST http://localhost:8080/api/content/internal-linking \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://example.com", "num_articles": 5}'
```

If you get an error about `FIRECRAWL_API_KEY`, the key is not set correctly.

## Troubleshooting

### "API configuration error: PERPLEXITY_API_KEY not set"
- Check that the environment variable is exported in your shell
- If using Railway, verify it's set in the Variables tab
- Restart your backend server after setting the variable

### "API configuration error: FIRECRAWL_API_KEY not set"
- Same as above - verify the variable is set
- Make sure there are no extra spaces or quotes around the key

### API Rate Limits
- Perplexity: Check your plan limits at [Perplexity Dashboard](https://www.perplexity.ai/settings)
- Firecrawl: Check your plan limits at [Firecrawl Dashboard](https://firecrawl.dev)

### Invalid API Key
- Verify the key is correct (no extra characters)
- Check if the key has expired
- Regenerate the key if needed

## Security Notes

- **Never commit API keys to git**
- Use environment variables, not hardcoded values
- Rotate keys periodically
- Use different keys for development and production if possible

## Cost Considerations

### Perplexity
- Free tier: Limited requests
- Paid plans: Based on usage
- Check [Perplexity Pricing](https://www.perplexity.ai/pricing) for details

### Firecrawl
- Free tier: Limited pages/month
- Paid plans: Based on pages crawled
- Check [Firecrawl Pricing](https://firecrawl.dev/pricing) for details

## Next Steps

Once environment variables are set:
1. Restart your backend server
2. Test the endpoints using the test commands above
3. Use the frontend at `/content-marketing` to test workflows
4. Check server logs for any API errors

