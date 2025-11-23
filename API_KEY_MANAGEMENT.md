# API Key Management Guide

## ✅ Best Practice: Separate Keys for Local vs Production

You're using **separate API keys** for local development and Railway production. This is a security best practice! 🎯

---

## Current Setup

### Local Development
- **API Key**: IP-restricted to your local IP
- **Location**: `backend/.env` file
- **Restrictions**: IP address whitelist
- **Purpose**: Development and testing

### Railway Production
- **API Key**: Separate key (created for Railway)
- **Location**: Railway environment variables
- **Restrictions**: Can be Railway IPs or HTTP referrers
- **Purpose**: Production deployment

---

## Why Separate Keys?

### ✅ Security Benefits
1. **Isolation**: Compromise of one key doesn't affect the other
2. **Different Restrictions**: Local can be IP-restricted, Railway can be domain-restricted
3. **Easy Revocation**: Can revoke one without affecting the other
4. **Usage Tracking**: Monitor usage per environment separately

### ✅ Operational Benefits
1. **Flexibility**: Change restrictions independently
2. **Testing**: Test production key restrictions before deploying
3. **Debugging**: Easier to identify which environment has issues
4. **Compliance**: Better audit trail

---

## Managing Your Keys

### Google Cloud Console

**View All Keys**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. APIs & Services → Credentials
3. See all API keys listed

**Key Naming Convention** (Recommended):
- `google-custom-search-local` - For local development
- `google-custom-search-railway` - For Railway production

**Edit Key Restrictions**:
1. Click on the key name
2. Under "Application restrictions":
   - **Local key**: IP addresses (your local IP)
   - **Railway key**: HTTP referrers (Railway domain) or IP addresses (Railway IPs)

---

## Environment Variables

### Local (.env file)
```bash
# Local development - IP-restricted key
GOOGLE_CUSTOM_SEARCH_API_KEY=YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=YOUR_SEARCH_ENGINE_ID_HERE
```

### Railway (Environment Variables)
```
# Railway production - Separate key
GOOGLE_CUSTOM_SEARCH_API_KEY=[Your Railway-specific key]
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=YOUR_SEARCH_ENGINE_ID_HERE  # Can be same or different
```

---

## Setting Up Railway Key

### Step 1: Create Railway API Key
1. Go to Google Cloud Console
2. APIs & Services → Credentials
3. Click "Create Credentials" → "API Key"
4. Name it: `google-custom-search-railway`
5. Copy the key

### Step 2: Configure Restrictions (Recommended)
1. Click on the new key
2. Under "Application restrictions":
   - **Option A**: HTTP referrers → Add your Railway domain
   - **Option B**: IP addresses → Add Railway IP ranges (if known)
   - **Option C**: None (if Railway IPs are dynamic)

3. Under "API restrictions":
   - Select "Restrict key"
   - Choose "Custom Search API"
   - Save

### Step 3: Add to Railway
1. Go to Railway Dashboard
2. Your Service → Variables
3. Add: `GOOGLE_CUSTOM_SEARCH_API_KEY` = [Your Railway key]
4. Add: `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` = [Same or different ID]
5. Railway will redeploy automatically

---

## Search Engine ID

**Question**: Can I use the same Search Engine ID for both?

**Answer**: Yes! The Search Engine ID is not restricted by IP. You can:
- ✅ Use the same ID for both local and Railway
- ✅ Or create separate engines if you want different search configurations

**Recommendation**: Use the same ID unless you need different search settings.

---

## Monitoring Usage

### Per-Key Usage
1. Go to Google Cloud Console
2. APIs & Services → Dashboard
3. Select "Custom Search API"
4. View usage metrics
5. Filter by API key (if needed)

### Quota Limits
- **Free Tier**: 100 queries per day per key
- **Paid**: $5 per 1,000 queries after free tier
- **Note**: Each key has its own quota

---

## Security Checklist

### Local Key
- ✅ IP-restricted to your local IP
- ✅ Stored in `.env` (not committed to git)
- ✅ Only used for development

### Railway Key
- ✅ Separate from local key
- ✅ Stored in Railway environment variables
- ✅ Restricted to Railway domain/IPs (recommended)
- ✅ API restrictions enabled (Custom Search API only)

### General
- ✅ Never commit keys to git
- ✅ Rotate keys periodically
- ✅ Monitor usage regularly
- ✅ Set up billing alerts

---

## Troubleshooting

### "API key not valid" on Railway
- Check Railway environment variable is set correctly
- Verify key restrictions allow Railway domain/IP
- Ensure Custom Search API is enabled for the key

### "Quota exceeded"
- Check which key is being used
- Verify quota per key (100 free/day)
- Consider if you need separate quotas or can share

### "Search engine ID not found"
- Verify Search Engine ID is correct
- Check if engine is set to search entire web (`*`)
- Ensure engine is active

---

## Summary

✅ **You're doing it right!** Separate keys for local and production is the best practice.

**Current Status**:
- ✅ Local key: Created and IP-restricted
- ✅ Railway key: Created (separate)
- ⚠️ Railway setup: Needs to be added to Railway environment variables

**Next Step**: Add the Railway API key to Railway dashboard environment variables.

