# Google Custom Search API Setup Guide

## Overview

Google Custom Search API provides 100 free queries per day, perfect for prospect discovery.

## Step 1: Create Custom Search Engine

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click "Add" to create a new search engine
3. **Sites to search**: Enter `*` (asterisk) to search the entire web
4. Click "Create"
5. Note your **Search Engine ID** (looks like: `017576662512468239146:omuauf_lfve`)

## Step 2: Get API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Custom Search API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Custom Search API"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy your **API Key**

## Step 3: Set Environment Variables

### Local Development

```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-api-key-here"
export GOOGLE_CUSTOM_SEARCH_ENGINE_ID="your-search-engine-id"
```

Or add to `.env` file:
```bash
GOOGLE_CUSTOM_SEARCH_API_KEY=your-api-key-here
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your-search-engine-id
```

### Railway Production

**Important**: Since your local key is IP-restricted, create a **separate API key for Railway**. This is a security best practice! ✅

1. **Create Railway API Key** (if not done):
   - Go to Google Cloud Console → APIs & Services → Credentials
   - Create new API key (name it: `google-custom-search-railway`)
   - Configure restrictions (HTTP referrers for Railway domain, or Railway IPs)
   - Restrict to Custom Search API only

2. **Add to Railway**:
   - Go to Railway Dashboard → Your Service → Variables
   - Add:
     - `GOOGLE_CUSTOM_SEARCH_API_KEY` = [your Railway-specific API key]
     - `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` = [your search engine ID - can be same as local]
   - Railway will automatically redeploy

**Note**: You can use the same Search Engine ID for both local and Railway, but use separate API keys for security.

## Step 4: Test

```bash
curl -X POST http://localhost:8080/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "industry": "SaaS",
    "location": "San Francisco",
    "max_results": 10
  }'
```

## Pricing

- **Free Tier**: 100 queries per day
- **Paid**: $5 per 1,000 queries after free tier
- **Perfect for**: Prospect discovery (typically 10-50 queries per discovery session)

## Troubleshooting

### "API key not valid"
- Check API key is correct
- Ensure Custom Search API is enabled
- Verify API key restrictions (if any)

### "Search engine ID not found"
- Check Search Engine ID is correct
- Ensure search engine is set to search entire web (`*`)

### "Quota exceeded"
- You've used your 100 free queries for the day
- Wait until next day or upgrade to paid tier

## Security Notes

- **Never commit API keys to git**
- Use environment variables only
- Consider restricting API key to specific IPs in production (Railway IP)

---

**Ready!** Your Google Custom Search API is configured for prospect discovery.


