# Test MCP Setup in Cursor

## Quick Tests

Try these commands in Cursor chat to verify MCP is working:

### Test 1: Perplexity MCP
```
Use Perplexity MCP to search for "best SaaS tools for SMBs in 2025" and give me a summary.
```

**Expected**: Cursor should use Perplexity MCP and return research results.

### Test 2: Firecrawl MCP
```
Use Firecrawl MCP to scrape https://example.com and summarize the main content.
```

**Expected**: Cursor should use Firecrawl MCP and return scraped content.

### Test 3: Combined Workflow
```
Use Perplexity MCP to find 3 articles about "SaaS companies serving SMBs", 
then use Firecrawl MCP to scrape those URLs and extract key insights.
```

**Expected**: Cursor should use both MCPs in sequence.

## What to Look For

✅ **Working Signs:**
- Cursor mentions "using Perplexity MCP" or "using Firecrawl MCP"
- You get actual research/scraped content
- No errors about "MCP not found" or "API key invalid"

❌ **Not Working Signs:**
- Error messages about MCP servers
- "Command not found" errors
- API key errors
- Cursor doesn't mention using MCP tools

## Troubleshooting

### If MCP Not Working:

1. **Check Cursor Settings:**
   - Go to Settings → Features → MCP
   - Verify the configuration is saved
   - Check API keys are correct

2. **Restart Cursor:**
   - Close Cursor completely
   - Reopen it
   - MCP servers load on startup

3. **Check Node.js:**
   - MCP uses `npx` which requires Node.js
   - Run: `node --version` in terminal
   - Should show v14+ or higher

4. **Check Console:**
   - Cursor may show errors in developer console
   - Help → Toggle Developer Tools

## Alternative: Test Backend APIs

If MCP isn't working, you can test the backend APIs directly:

```bash
# Test research endpoint
curl -X POST http://localhost:8080/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "topic": "SaaS companies", "industry": "SaaS"}'
```

This will verify your API keys work even if MCP has issues.

---

**Try the tests above and let me know what happens!**

