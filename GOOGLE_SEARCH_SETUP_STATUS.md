# Google Custom Search API Setup Status

## ✅ Local Testing - CONFIGURED

**Status**: ✅ **Working**

**Configuration**:
- ✅ API Key: Set in `backend/.env` file
- ✅ Search Engine ID: Set in `backend/.env` file
- ✅ Code implementation: Complete in `backend/app/services/search_client.py`
- ✅ Tested: Working (prospect discovery endpoint tested successfully)

**Location**: `backend/.env`
```
GOOGLE_CUSTOM_SEARCH_API_KEY=YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=YOUR_SEARCH_ENGINE_ID_HERE
```

**Test Command**:
```bash
curl -X POST http://localhost:3001/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","industry":"SaaS","max_results":5}'
```

---

## ⚠️ Railway Deployment - NEEDS VERIFICATION

**Status**: ⚠️ **Documented but needs verification**

**Important**: Since your local API key is IP-restricted, you've created a **separate API key for Railway**. This is a security best practice! ✅

**What's Needed**:
1. Go to Railway Dashboard
2. Select your backend service
3. Go to "Variables" tab
4. Add these environment variables:
   - `GOOGLE_CUSTOM_SEARCH_API_KEY` = **[Your Railway-specific API key]** (different from local)
   - `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` = `YOUR_SEARCH_ENGINE_ID_HERE` (can be same or different)

**Railway Setup Steps**:
1. **Open Railway Dashboard**
   - Go to https://railway.app
   - Select your project
   - Select your backend service

2. **Add Environment Variables**
   - Click on "Variables" tab
   - Click "New Variable"
   - Add `GOOGLE_CUSTOM_SEARCH_API_KEY` with your API key value
   - Click "Add"
   - Repeat for `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`

3. **Verify Setup**
   - Railway will automatically redeploy after adding variables
   - Check deployment logs for any errors
   - Test the endpoint on Railway URL

**Railway Test Command** (after setup):
```bash
curl -X POST https://your-app.railway.app/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","industry":"SaaS","max_results":5}'
```

---

## Implementation Details

### Code Location
- **Client**: `backend/app/services/search_client.py`
- **Routes**: `backend/app/routes/prospects.py` (discover endpoint)
- **Main**: `backend/app/main.py` (router registration)

### Environment Variable Usage
The code reads from environment variables:
```python
self.api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
self.search_engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
```

### Error Handling
- ✅ Validates API key is set
- ✅ Validates Search Engine ID is set
- ✅ Raises clear error messages if missing
- ✅ Handles API errors gracefully

---

## Current Status Summary

| Environment | API Key | Search Engine ID | Status |
|------------|---------|------------------|--------|
| **Local** | ✅ Set (IP-restricted) | ✅ Set | ✅ **Working** |
| **Railway** | ✅ Created (separate key) | ✅ Can use same ID | ⚠️ **Needs Setup in Railway** |

---

## Next Steps

### To Complete Railway Setup:

1. **Log into Railway Dashboard**
   ```
   https://railway.app
   ```

2. **Navigate to Your Service**
   - Select your project
   - Select backend service

3. **Add Environment Variables**
   - Variables tab → New Variable
   - Add both variables with values from `.env` file

4. **Verify Deployment**
   - Check deployment logs
   - Test endpoint on Railway URL

5. **Optional: Restrict API Key** (Security)
   - In Google Cloud Console
   - Restrict API key to Railway IP addresses
   - Or restrict to specific HTTP referrers

---

## Security Recommendations

### ✅ Best Practice: Separate API Keys (You're Doing This!)

**Local Key** (IP-restricted):
- Restricted to your local IP address
- Used for: Local development and testing
- Stored in: `backend/.env` file

**Railway Key** (Production):
- Can be restricted to Railway IPs or HTTP referrers
- Used for: Production deployment
- Stored in: Railway environment variables

**Benefits**:
- ✅ Better security isolation
- ✅ Can revoke one without affecting the other
- ✅ Different restrictions for different environments
- ✅ Easier to monitor usage per environment

### For Railway Production:

1. **API Key Restrictions** (Recommended)
   - Go to Google Cloud Console → APIs & Services → Credentials
   - Edit your **Railway API key** (separate from local)
   - Under "Application restrictions":
     - Option A: Select "IP addresses" → Add Railway's IP ranges
     - Option B: Select "HTTP referrers" → Add your Railway domain
     - Option C: No restrictions (if Railway IPs are dynamic)

2. **Search Engine Restrictions**
   - In Programmable Search Engine settings
   - Consider restricting to specific domains if needed
   - Note: Search Engine ID can be shared or separate

3. **Monitor Usage**
   - Check Google Cloud Console for API usage per key
   - Set up billing alerts
   - Monitor quota usage (100 free/day per key)
   - Track which key is used for which environment

---

## Troubleshooting

### Local Issues
- ✅ Keys are set in `.env` file
- ✅ Code is implemented
- ✅ Tested and working

### Railway Issues
If Railway deployment fails:
1. Check Railway logs for environment variable errors
2. Verify variables are set correctly (no extra spaces)
3. Ensure Railway has access to environment variables
4. Check if service account permissions are correct

---

## Summary

- ✅ **Local**: Fully configured and working
- ⚠️ **Railway**: Needs manual setup in Railway dashboard (documented but not verified)

**Action Required**: Add environment variables to Railway dashboard to complete setup.

