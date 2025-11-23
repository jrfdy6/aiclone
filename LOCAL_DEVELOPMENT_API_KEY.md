# Local Development API Key Setup

## Understanding API Key Restrictions

When you restricted your Google Custom Search API key to Railway's website, that restriction is mainly for **client-side** (browser) usage. For **server-side** API calls (which is what your backend does), the restriction works differently.

## Options for Local Development

### Option 1: Create a Separate API Key for Local Dev (Recommended)

**Best Practice**: Create a second API key just for local development:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" → "API Key" again
3. Name it: `Custom Search API - Local Development`
4. **Application restrictions**: Select "None" (for local testing)
5. **API restrictions**: Select "Restrict key" → Choose "Custom Search API"
6. Use this key in your local `.env` file
7. Keep the Railway-restricted key for production

**Benefits**:
- ✅ No security risk (separate keys)
- ✅ Easy local testing
- ✅ Production key stays secure

### Option 2: Use IP Address Restriction

If you want to use the same key:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Edit your existing API key
3. Change **Application restrictions** from "Websites" to "IP addresses"
4. Add your public IP address (see below)
5. Also add Railway's IP if you know it

**Note**: Your public IP changes if you switch networks (home → coffee shop, etc.)

### Option 3: Temporarily Remove Restrictions (Quick Testing)

For quick local testing only:

1. Edit your API key
2. Set **Application restrictions** to "None"
3. Keep **API restrictions** to "Custom Search API" (still secure)
4. Test locally
5. Re-add restrictions before deploying

## Finding Your Public IP Address

Your public IP address is: **See command output above**

This is the IP address Google sees when your backend makes API calls.

## Recommended Setup

**For Production (Railway)**:
- Use the Railway-restricted key
- Set in Railway environment variables

**For Local Development**:
- Create a separate unrestricted key (Option 1)
- Use in your local `.env` file

## Environment Variable Setup

**Local `.env` file** (`backend/.env`):
```bash
GOOGLE_CUSTOM_SEARCH_API_KEY=your-local-dev-key-here
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your-search-engine-id
```

**Railway Variables**:
- `GOOGLE_CUSTOM_SEARCH_API_KEY` = your-production-key (Railway-restricted)
- `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` = same search engine ID

## Testing

After setting up your local key:

```bash
# Load environment variables
source backend/.env

# Start backend
cd backend
uvicorn app.main:app --reload

# Test discovery
curl -X POST http://localhost:8080/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "industry": "SaaS", "max_results": 5}'
```

---

**Recommendation**: Use Option 1 (separate keys) for the cleanest setup!


