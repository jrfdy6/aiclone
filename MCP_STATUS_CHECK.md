# MCP Setup Status Check

## Current Configuration

Your `cursor_mcp_config.json` is configured with:

### ✅ Perplexity MCP
```json
{
  "command": "perplexity-mcp",
  "args": ["--model", "sonar", "--reasoning-model", "sonar-reasoning"],
  "env": {
    "PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE"
  }
}
```

**Status:** ✅ Configured
- Model: `sonar` (cost-optimized)
- Reasoning: `sonar-reasoning` (cost-optimized)
- API Key: Set

### ✅ Firecrawl MCP
```json
{
  "command": "npx",
  "args": ["-y", "firecrawl-mcp"],
  "env": {
    "FIRECRAWL_API_KEY": "fc-ce10579f6df4449c84b31c0dbc69a949"
  }
}
```

**Status:** ✅ Configured
- Command: `npx -y firecrawl-mcp`
- API Key: Set

## How to Verify MCPs Are Working

### Step 1: Check Cursor Settings

1. Open Cursor
2. Go to **Settings** (Cmd/Ctrl + ,)
3. Navigate to **Features** → **MCP**
4. Verify both servers are listed:
   - `perplexity-mcp`
   - `firecrawl-mcp`

### Step 2: Test Perplexity MCP

**In Cursor chat, type:**
```
Use Perplexity MCP to search for "best SaaS tools for SMBs in 2025" and provide a summary.
```

**✅ Working Signs:**
- Cursor mentions "using Perplexity MCP" or shows MCP tool usage
- You get actual research results
- No error messages

**❌ Not Working Signs:**
- Error: "MCP server not found"
- Error: "Command not found: perplexity-mcp"
- Error: "Invalid API key"
- Cursor doesn't use MCP (just uses regular chat)

### Step 3: Test Firecrawl MCP

**In Cursor chat, type:**
```
Use Firecrawl MCP to scrape https://example.com and summarize the main content.
```

**✅ Working Signs:**
- Cursor mentions "using Firecrawl MCP"
- You get scraped content
- No error messages

**❌ Not Working Signs:**
- Error: "MCP server not found"
- Error: "npx command not found"
- Error: "Invalid API key"
- Timeout errors

### Step 4: Test Combined Workflow

**In Cursor chat, type:**
```
Use Perplexity MCP to find 3 articles about "SaaS companies serving SMBs",
then use Firecrawl MCP to scrape those URLs and extract key insights.
```

**✅ Working Signs:**
- Both MCPs are used in sequence
- You get research + scraped content
- No errors

## Troubleshooting

### Issue: "Command not found: perplexity-mcp"

**Solution:**
- The `perplexity-mcp` command needs to be installed globally
- Try: `npm install -g @modelcontextprotocol/server-perplexity`
- Or change config to use `npx`:
  ```json
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-perplexity"]
  ```

### Issue: "npx command not found"

**Solution:**
- Install Node.js: `brew install node` (Mac) or download from nodejs.org
- Verify: `node --version` should show v14+
- Verify: `npx --version` should work

### Issue: "Invalid API key"

**Solution:**
- Check API keys in `cursor_mcp_config.json`
- Verify keys are valid:
  - Perplexity: https://www.perplexity.ai/settings/api
  - Firecrawl: https://firecrawl.dev/dashboard
- Restart Cursor after updating keys

### Issue: MCPs not showing in Cursor Settings

**Solution:**
1. Copy config from `cursor_mcp_config.json`
2. Paste into Cursor Settings → Features → MCP
3. Save settings
4. **Restart Cursor completely** (Cmd+Q, then reopen)

### Issue: MCPs configured but not working

**Solution:**
1. Check Cursor logs:
   - Help → Toggle Developer Tools
   - Look for MCP errors in console
2. Verify Node.js is installed: `node --version`
3. Try reinstalling MCP packages:
   ```bash
   npm install -g @modelcontextprotocol/server-perplexity
   npm install -g firecrawl-mcp
   ```

## Expected Behavior

### When MCPs Are Working:

1. **Perplexity MCP:**
   - Cursor will use Perplexity API directly
   - Returns real-time web search results
   - No timeout issues (runs in Cursor, not Railway)
   - Can take 30-90 seconds for complex queries

2. **Firecrawl MCP:**
   - Cursor will scrape URLs directly
   - Returns structured content
   - No timeout issues
   - Can take 10-30 seconds per URL

### When MCPs Are NOT Working:

- Cursor falls back to regular chat (no MCP usage)
- You'll get generic responses, not real research
- No web search or scraping happens

## Quick Test Commands

Copy-paste these into Cursor chat:

**Test 1:**
```
Use Perplexity MCP to search for "AI coding tools 2025" and give me the top 3 tools with their key features.
```

**Test 2:**
```
Use Firecrawl MCP to scrape https://www.perplexity.ai and tell me what the homepage says about their product.
```

**Test 3:**
```
Use Perplexity MCP to find recent articles about "SaaS trends 2025", then use Firecrawl MCP to scrape the first article URL and summarize it.
```

## Next Steps

Once MCPs are working:

1. ✅ Use MCPs for research in Cursor
2. ✅ Store results via `/api/research/store` endpoint
3. ✅ Use stored research for prospect scoring
4. ✅ Generate outreach using research insights

See `MCP_WORKFLOW_GUIDE.md` for the complete workflow.

---

**Need help?** Try the test commands above and check what happens. If MCPs aren't working, follow the troubleshooting steps.

