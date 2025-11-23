# Fix MCP Setup - Correct Configuration

## The Problem

The error shows that `@modelcontextprotocol/server-perplexity` doesn't exist as an npm package. Perplexity MCP is actually a **Go binary**, not an npm package.

## Solution: Install Perplexity MCP Correctly

### Option 1: Install via Homebrew (Easiest)

```bash
brew tap alcova-ai/tap
brew install perplexity-mcp
```

### Option 2: Download Binary

1. Go to: https://github.com/Alcova-AI/perplexity-mcp/releases
2. Download the binary for macOS
3. Make it executable: `chmod +x perplexity-mcp`
4. Move it to your PATH or use full path in config

## Updated Cursor MCP Configuration

Once Perplexity MCP is installed, use this configuration:

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

## Firecrawl MCP

Firecrawl MCP should work with `npx` since it's an npm package. If it doesn't work, you might need to check the exact package name.

## Steps to Fix

1. **Install Perplexity MCP:**
   ```bash
   brew tap alcova-ai/tap
   brew install perplexity-mcp
   ```

2. **Verify Installation:**
   ```bash
   which perplexity-mcp
   # Should show: /opt/homebrew/bin/perplexity-mcp (or similar)
   ```

3. **Update Cursor MCP Config:**
   - Go to Cursor Settings → Features → MCP
   - Replace the Perplexity config with the one above (using `perplexity-mcp` command, not `npx`)

4. **Restart Cursor**

5. **Test:**
   ```
   Use Perplexity MCP to search for "best SaaS tools 2025"
   ```

## Alternative: Use Backend APIs Instead

If MCP setup is too complex, you can always use the backend APIs we built:
- They're already working ✅
- No additional installation needed
- Production-ready

The backend APIs work great for automated workflows, while MCP is nice-to-have for interactive Cursor chat.

---

**Let me know if you want to install Perplexity MCP via Homebrew, or if you prefer to stick with backend APIs!**

