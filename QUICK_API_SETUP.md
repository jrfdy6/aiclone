# Quick API Keys Setup Guide

## Option 1: Use the Setup Script (Easiest)

```bash
cd backend
./setup_api_keys.sh
```

The script will guide you through entering all API keys interactively.

## Option 2: Manual Setup

### Step 1: Get Google Custom Search API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable "Custom Search API":
   - Go to "APIs & Services" → "Library"
   - Search for "Custom Search API"
   - Click "Enable"
4. Create API Key:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the key

### Step 2: Get Google Custom Search Engine ID

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click "Add" to create new search engine
3. **Sites to search**: Enter `*` (to search entire web)
4. Click "Create"
5. Copy the Search Engine ID

### Step 3: Get Perplexity API Key

1. Go to [Perplexity Settings](https://www.perplexity.ai/settings/api)
2. Sign up or log in
3. Generate an API key
4. Copy the key

### Step 4: Get Firecrawl API Key

1. Go to [Firecrawl](https://firecrawl.dev)
2. Sign up for an account
3. Navigate to API Keys section
4. Generate a new API key
5. Copy the key

### Step 5: Set Environment Variables

**Local Development:**

Create `backend/.env` file:
```bash
GOOGLE_CUSTOM_SEARCH_API_KEY=your-google-api-key
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your-search-engine-id
PERPLEXITY_API_KEY=your-perplexity-key
FIRECRAWL_API_KEY=your-firecrawl-key
```

Or export in your shell:
```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-google-api-key"
export GOOGLE_CUSTOM_SEARCH_ENGINE_ID="your-search-engine-id"
export PERPLEXITY_API_KEY="your-perplexity-key"
export FIRECRAWL_API_KEY="your-firecrawl-key"
```

**Railway Production:**

1. Go to Railway Dashboard → Your Service → Variables
2. Add each variable:
   - `GOOGLE_CUSTOM_SEARCH_API_KEY`
   - `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`
   - `PERPLEXITY_API_KEY`
   - `FIRECRAWL_API_KEY`
3. Railway will automatically redeploy

## Step 6: Test Your Setup

```bash
# Test research (uses Perplexity + Firecrawl)
curl -X POST http://localhost:8080/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "topic": "SaaS companies", "industry": "SaaS"}'

# Test discovery (uses Google Custom Search + Firecrawl)
curl -X POST http://localhost:8080/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "industry": "SaaS", "max_results": 5}'
```

## Troubleshooting

### "GOOGLE_CUSTOM_SEARCH_API_KEY not set"
- Check the key is exported: `echo $GOOGLE_CUSTOM_SEARCH_API_KEY`
- Restart your backend server after setting

### "GOOGLE_CUSTOM_SEARCH_ENGINE_ID not set"
- Check the ID is exported: `echo $GOOGLE_CUSTOM_SEARCH_ENGINE_ID`
- Verify the Search Engine is set to search entire web (`*`)

### "Quota exceeded" (Google Custom Search)
- You've used your 100 free queries for the day
- Wait until next day or upgrade to paid tier

### API Key Invalid
- Verify keys are correct (no extra spaces)
- Check keys haven't expired
- Regenerate if needed

## Cost Summary

- **Google Custom Search**: 100 free queries/day → $0-5/month
- **Perplexity**: Free tier available → $0-10/month
- **Firecrawl**: Free tier available → $0-10/month
- **Total**: ~$5-25/month depending on usage

---

**Ready!** Once keys are set, restart your backend and start using the workflow.



