# Perplexity API Setup Guide

## Step 1: Sign Up / Log In

1. Go to: https://www.perplexity.ai/
2. Click **"Sign Up"** or **"Log In"** (top right)
3. You can sign up with:
   - Email
   - Google account
   - Apple account

## Step 2: Get Your API Key

1. Once logged in, go to: https://www.perplexity.ai/settings/api
   - Or navigate: Settings → API (in your account menu)
2. You'll see the API section
3. Click **"Generate API Key"** or **"Create API Key"**
4. Copy the API key immediately (you might not see it again)

## Step 3: Check Your Plan

Perplexity offers:
- **Free tier**: Limited requests (good for testing)
- **Paid plans**: Based on usage
- Check your plan limits in the dashboard

## Step 4: Add to .env File

Once you have your API key, add it to `backend/.env`:

```bash
PERPLEXITY_API_KEY=your-perplexity-api-key-here
```

## What Perplexity is Used For

In your prospecting workflow, Perplexity is used for:
- **Research trigger** (`POST /api/research/trigger`)
- Finding industry trends, pains, keywords
- Getting real-time search results for research topics

## Testing

After adding the key, test it:

```bash
curl -X POST http://localhost:8080/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "topic": "SaaS companies", "industry": "SaaS"}'
```

---

**Next**: After Perplexity, you'll need Firecrawl API key for web scraping.

