# Key Rotation Checklist

## ✅ Keys Rotated - Next Steps

Since you've rotated your API keys, here's what needs to be updated:

---

## 🔄 Update Environment Variables

### Local Development (`backend/.env`)

Update these in your local `.env` file:
```bash
# Perplexity (new key)
PERPLEXITY_API_KEY=your-new-perplexity-key

# Firecrawl (new key)
FIRECRAWL_API_KEY=your-new-firecrawl-key

# Google Custom Search (new key)
GOOGLE_CUSTOM_SEARCH_API_KEY=your-new-google-key

# Search Engine ID (can be same or new)
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your-search-engine-id
```

### Railway Production

Update in Railway Dashboard → Your Service → Variables:
1. `PERPLEXITY_API_KEY` = [new key]
2. `FIRECRAWL_API_KEY` = [new key]
3. `GOOGLE_CUSTOM_SEARCH_API_KEY` = [new key]
4. `GOOGLE_CUSTOM_SEARCH_ENGINE_ID` = [same or new]

Railway will automatically redeploy after updating variables.

### Cursor MCP Config

Update `cursor_mcp_config.json`:
```json
{
  "mcpServers": {
    "perplexity-mcp": {
      "env": {
        "PERPLEXITY_API_KEY": "your-new-perplexity-key"
      }
    },
    "firecrawl-mcp": {
      "env": {
        "FIRECRAWL_API_KEY": "your-new-firecrawl-key"
      }
    }
  }
}
```

Then update Cursor Settings → Features → MCP with the new config.

---

## ✅ Verification Steps

### 1. Test Local Backend
```bash
cd backend
source ../.venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
uvicorn app.main:app --reload --port 3001
```

Check startup logs for:
- ✅ `PERPLEXITY_API_KEY set: True`
- ✅ `FIRECRAWL_API_KEY set: True`
- ✅ `GOOGLE_CUSTOM_SEARCH_API_KEY set: True`

### 2. Test Research Endpoint
```bash
curl -X POST http://localhost:3001/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","topic":"SaaS companies","industry":"SaaS"}'
```

Should return success (not API key errors).

### 3. Test Prospect Discovery
```bash
curl -X POST http://localhost:3001/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","industry":"SaaS","max_results":3}'
```

Should return prospects (not API key errors).

### 4. Test Railway Deployment
After updating Railway variables:
```bash
curl https://your-railway-url.railway.app/health
```

Check Railway logs for successful startup.

### 5. Test Cursor MCP
In Cursor chat:
```
Use Perplexity MCP to search for "best SaaS tools 2025"
```

Should work without API key errors.

---

## 🔒 Security Status

- ✅ Old keys revoked
- ✅ New keys generated
- ⚠️ Old keys still in git history (optional to clean)
- ✅ Current files are clean

---

## 📋 Complete Checklist

- [x] Rotate Firecrawl API key ✅
- [x] Rotate Google Custom Search API key ✅
- [x] Rotate Perplexity API key ✅
- [ ] Update local `.env` file
- [ ] Update Railway environment variables
- [ ] Update Cursor MCP config
- [ ] Test local backend
- [ ] Test Railway deployment
- [ ] Test Cursor MCP
- [ ] Verify all endpoints working

---

## 🧹 Optional: Clean Git History

If you want to remove secrets from git history entirely:

### Quick Method (BFG Repo-Cleaner)
```bash
# Install BFG
brew install bfg

# Create replacement file
echo "YOUR_OLD_KEY==>YOUR_PLACEHOLDER" > replacements.txt

# Clean history
bfg --replace-text replacements.txt

# Force push (WARNING: Rewrites history)
git push --force
```

**Note**: This is optional. Since keys are rotated, old keys in history are harmless.

---

## 🎯 Priority Actions

1. **Update local `.env`** - So local development works
2. **Update Railway variables** - So production works
3. **Update Cursor MCP config** - So MCP works
4. **Test everything** - Verify all keys work
5. **Clean history** (optional) - Remove old keys from history

---

**You're almost done!** Just update the environment variables and test everything.


