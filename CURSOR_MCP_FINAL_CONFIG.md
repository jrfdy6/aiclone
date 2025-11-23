# Final Cursor MCP Configuration

## ✅ Perplexity MCP Installed

Perplexity MCP is now installed at: `/usr/local/bin/perplexity-mcp`

## Update Your Cursor MCP Settings

Go to **Cursor Settings → Features → MCP** and use this configuration:

```json
{
  "mcpServers": {
    "perplexity-mcp": {
      "command": "perplexity-mcp",
      "args": [
        "--model",
        "sonar-pro",
        "--reasoning-model",
        "sonar-reasoning-pro"
      ],
      "env": {
        "PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE"
      }
    },
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "YOUR_FIRECRAWL_API_KEY_HERE"
      }
    }
  }
}
```

## Key Changes

1. **Perplexity**: Changed from `npx @modelcontextprotocol/server-perplexity` to `perplexity-mcp` (the binary we just installed)
2. **Firecrawl**: Kept as `npx firecrawl-mcp` (this should work)

## After Updating

1. **Restart Cursor** completely (close and reopen)
2. **Test Perplexity MCP:**
   ```
   Use Perplexity MCP to search for "best SaaS tools for SMBs in 2025"
   ```
3. **Test Firecrawl MCP:**
   ```
   Use Firecrawl MCP to scrape https://example.com
   ```

## Troubleshooting

### If Perplexity Still Doesn't Work:
- Check the binary path: `which perplexity-mcp` (should show `/usr/local/bin/perplexity-mcp`)
- Try using full path in config: `"/usr/local/bin/perplexity-mcp"`

### If Firecrawl Doesn't Work:
- Check if `npx` is available: `which npx`
- The package might be `@mendable/firecrawl-mcp` instead - check Firecrawl docs

---

**Update your Cursor settings with the config above and restart Cursor!**

