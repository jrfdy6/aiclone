# Cursor MCP Setup for Perplexity & Firecrawl

This guide shows you how to set up MCP (Model Context Protocol) in Cursor so you can use Perplexity and Firecrawl directly in Cursor chat.

## Benefits

- **Interactive Research**: Ask Cursor to research topics using Perplexity
- **Direct Scraping**: Have Cursor scrape websites using Firecrawl
- **Faster Iteration**: Test ideas quickly without leaving Cursor
- **Combined Workflows**: Use MCP for exploration, backend APIs for production

## Setup Steps

### 1. Open Cursor Settings

1. Open Cursor
2. Go to **Settings** (Cmd/Ctrl + ,)
3. Navigate to **Features** → **MCP** (or search for "MCP")

### 2. Add Firecrawl MCP

Add this configuration:

```json
{
  "mcpServers": {
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

### 3. Add Perplexity MCP

Add this configuration (add to the same `mcpServers` object):

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
    "perplexity": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-perplexity"],
      "env": {
        "PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE"
      }
    }
  }
}
```

### 4. Complete MCP Configuration

Your full MCP configuration in Cursor should look like:

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
    "perplexity": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-perplexity"],
      "env": {
        "PERPLEXITY_API_KEY": "YOUR_PERPLEXITY_API_KEY_HERE"
      }
    }
  }
}
```

### 5. Restart Cursor

After adding the configuration, restart Cursor to load the MCP servers.

## Testing MCP Setup

### Test Perplexity MCP

In Cursor chat, try:
```
Use Perplexity MCP to research "best SaaS tools for SMBs in 2025"
```

### Test Firecrawl MCP

In Cursor chat, try:
```
Use Firecrawl MCP to scrape https://example.com and summarize the content
```

## Usage Examples

### Research Workflow
```
Use Perplexity MCP to research "trending pain points for SaaS companies serving SMBs". 
Then use Firecrawl MCP to scrape the top 3 source URLs and extract key insights.
```

### Prospect Discovery
```
Use Perplexity MCP to find "SaaS companies in San Francisco with VP Sales roles".
Then use Firecrawl MCP to scrape their team pages and extract contact information.
```

### Content Research
```
Use Perplexity MCP to research "best AB testing tools 2025". 
Create a markdown document with the findings, including comparison tables.
```

## MCP vs Backend APIs

### Use MCP When:
- ✅ Quick research/testing in Cursor
- ✅ Interactive exploration
- ✅ One-off tasks
- ✅ Prototyping workflows

### Use Backend APIs When:
- ✅ Production workflows
- ✅ Scheduled/automated tasks
- ✅ Frontend integration
- ✅ Batch processing
- ✅ Storing results in Firestore

## Troubleshooting

### MCP Not Working
- Check API keys are correct in Cursor settings
- Restart Cursor after configuration
- Check Cursor console for errors
- Verify Node.js is installed (`node --version`)

### "Command not found"
- Ensure Node.js and npm are installed
- MCP uses `npx` which comes with npm

### API Key Errors
- Verify keys match your `.env` file
- Check keys haven't expired
- Ensure keys have proper permissions

## Security Note

⚠️ **Important**: The MCP configuration stores API keys in Cursor settings. This is fine for local development, but:
- Don't commit Cursor settings to git
- Use different keys for production if possible
- Rotate keys periodically

---

**Ready!** Once configured, you can use Perplexity and Firecrawl directly in Cursor chat alongside your backend APIs.


