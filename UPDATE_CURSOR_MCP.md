# Update Cursor MCP Config - Step by Step

## Current Config File

The file `cursor_mcp_config.json` currently has placeholders. You need to replace them with your new rotated API keys.

---

## Step 1: Update the Config File

Open `cursor_mcp_config.json` and replace the placeholders:

### Replace This:
```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "YOUR_FIRECRAWL_API_KEY_HERE"
      }
    },
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
    }
  }
}
```

### With Your New Keys:
```json
{
  "mcpServers": {
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "your-new-firecrawl-key-here"
      }
    },
    "perplexity-mcp": {
      "command": "perplexity-mcp",
      "args": [
        "--model",
        "sonar",
        "--reasoning-model",
        "sonar-reasoning-pro"
      ],
      "env": {
        "PERPLEXITY_API_KEY": "your-new-perplexity-key-here"
      }
    }
  }
}
```

**Note**: I also updated the model from `sonar-pro` to `sonar` (cost-optimized, as we discussed earlier).

---

## Step 2: Copy Config to Cursor Settings

### Option A: Direct File Path (Recommended)

1. **Find Cursor MCP Config Location**:
   - **macOS**: `~/.cursor/mcp.json` or `~/Library/Application Support/Cursor/User/globalStorage/mcp.json`
   - **Windows**: `%APPDATA%\Cursor\User\globalStorage\mcp.json`
   - **Linux**: `~/.config/Cursor/User/globalStorage/mcp.json`

2. **Copy Your Config**:
   ```bash
   # On macOS, you can run:
   cp cursor_mcp_config.json ~/.cursor/mcp.json
   
   # Or manually copy the contents
   ```

3. **Or Use Cursor Settings UI** (see Option B)

### Option B: Via Cursor Settings UI

1. **Open Cursor Settings**:
   - Press `Cmd+,` (macOS) or `Ctrl+,` (Windows/Linux)
   - Or: Cursor → Settings → Settings

2. **Navigate to MCP**:
   - Search for "MCP" in settings
   - Or go to: Features → MCP

3. **Edit MCP Configuration**:
   - Click "Edit in settings.json" or similar
   - Paste your entire config from `cursor_mcp_config.json`
   - Save the file

---

## Step 3: Restart Cursor

**Important**: Cursor needs to be restarted for MCP changes to take effect.

1. **Quit Cursor completely**:
   - `Cmd+Q` (macOS) or close all windows
   - Don't just close the window - fully quit

2. **Reopen Cursor**

3. **Verify MCP is Loaded**:
   - Check Cursor Settings → Features → MCP
   - You should see both servers listed

---

## Step 4: Test MCP

### Test Perplexity MCP

In Cursor chat, try:
```
Use Perplexity MCP to search for "best SaaS tools for SMBs in 2025" and give me a summary.
```

**What to look for**:
- ✅ Cursor mentions "using Perplexity MCP"
- ✅ You get research results
- ✅ No API key errors

### Test Firecrawl MCP

In Cursor chat, try:
```
Use Firecrawl MCP to scrape https://example.com and summarize the main content.
```

**What to look for**:
- ✅ Cursor uses Firecrawl MCP
- ✅ You get scraped content
- ✅ No API key errors

---

## Troubleshooting

### "MCP server not found"
- Check the config file path is correct
- Verify JSON syntax is valid (no trailing commas)
- Restart Cursor

### "API key invalid"
- Double-check the key is correct (no extra spaces)
- Verify key is active in Perplexity/Firecrawl dashboard
- Check key hasn't expired

### "Command not found: perplexity-mcp"
- Make sure Perplexity MCP is installed: `brew install perplexity-mcp`
- Verify it's in your PATH: `which perplexity-mcp`

### MCP not showing in Cursor
- Check Cursor Settings → Features → MCP is enabled
- Verify config file location is correct
- Try restarting Cursor again

---

## Quick Reference

**Config File Location**:
- Local: `cursor_mcp_config.json` (in project root)
- Cursor: `~/.cursor/mcp.json` (macOS) or similar

**Keys to Update**:
- `FIRECRAWL_API_KEY` = Your new Firecrawl key
- `PERPLEXITY_API_KEY` = Your new Perplexity key

**After Updating**:
1. Save the file
2. Copy to Cursor config location
3. Restart Cursor
4. Test in chat

---

**Ready to update?** Replace the placeholders in `cursor_mcp_config.json` with your new keys, then follow the steps above!



