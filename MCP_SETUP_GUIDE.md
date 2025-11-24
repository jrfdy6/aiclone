# MCP Setup Guide for Cursor

This guide will help you set up the essential MCPs (Model Context Protocol) mentioned in the Vibe Marketing strategies.

## What are MCPs?

MCPs (Model Context Protocol) are APIs for language models that allow agents to interface with external data sources and tools directly within the conversational window. They enable closed-loop workflows where you can go from insight to action in one interface.

## Essential MCPs for Vibe Marketing

### 1. Firecrawl MCP
**Purpose**: Web scraping and content crawling
**Use Cases**: 
- Scraping competitor content
- Building site maps
- Extracting article content for internal linking
- Research gathering

**Setup Steps**:
1. Go to [Firecrawl](https://firecrawl.dev) and create an account
2. Get your API key from the dashboard
3. Install the MCP server:
   ```bash
   npm install -g @mcp/firecrawl
   ```
4. Add to Cursor settings:
   - Open Cursor Settings → General → MCP
   - Add new MCP server with this configuration:
   ```json
   {
     "mcpServers": {
       "firecrawl": {
         "command": "npx",
         "args": ["-y", "@mcp/firecrawl"],
         "env": {
           "FIRECRAWL_API_KEY": "your-api-key-here"
         }
       }
     }
   }
   ```

### 2. Perplexity Ask MCP
**Purpose**: Real-time search and research
**Use Cases**:
- Finding latest tools and trends
- Research for content creation
- Competitive analysis
- Keyword research validation

**Setup Steps**:
1. Go to [Perplexity API](https://www.perplexity.ai/settings/api) and create an account
2. Generate an API key
3. Install the MCP server:
   ```bash
   npm install -g @modelcontextprotocol/server-perplexity
   ```
4. Add to Cursor settings:
   ```json
   {
     "mcpServers": {
       "perplexity": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-perplexity"],
         "env": {
           "PERPLEXITY_API_KEY": "your-api-key-here"
         }
       }
     }
   }
   ```

### 3. Playwright MCP
**Purpose**: Agentic browser automation
**Use Cases**:
- QA testing and screenshots
- Browser-based testing
- Visual verification
- Automated browser interactions

**Setup Steps**:
1. Install Playwright:
   ```bash
   npm install -g playwright
   npx playwright install
   ```
2. Install the MCP server:
   ```bash
   npm install -g @modelcontextprotocol/server-playwright
   ```
3. Add to Cursor settings:
   ```json
   {
     "mcpServers": {
       "playwright": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-playwright"]
       }
     }
   }
   ```

## Project-Level MCPs (Optional)

### Stripe MCP
For payment and subscription management:
```json
{
  "mcpServers": {
    "stripe": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-stripe"],
      "env": {
        "STRIPE_API_KEY": "your-stripe-key"
      }
    }
  }
}
```

### Supabase MCP
For database operations:
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-supabase"],
      "env": {
        "SUPABASE_URL": "your-supabase-url",
        "SUPABASE_KEY": "your-supabase-key"
      }
    }
  }
}
```

## Where to Find More MCPs

- **Smither**: [smither.ai](https://smither.ai) - MCP marketplace
- **Cursor Directory**: [cursory.directory](https://cursory.directory) - Curated MCP list
- **GitHub**: Search for "MCP server" repositories
- **MCP Marketplace**: Search "MCP marketplace" for directories

## Testing Your MCPs

After setup, test in Cursor:
1. Open a new chat in Cursor
2. Try: "Use Perplexity MCP to search for 'best AI tools 2025'"
3. Try: "Use Firecrawl MCP to scrape content from [your-website]"

## Troubleshooting

- **MCP not working**: Check API keys are set correctly
- **Command not found**: Ensure Node.js and npm are installed
- **Permission errors**: May need to run with appropriate permissions
- **Connection issues**: Verify internet connection and API service status

## Next Steps

Once MCPs are set up, you can:
1. Create custom modes in Cursor (see `CURSOR_CUSTOM_MODES.md`)
2. Start using content research workflows
3. Build internal linking automation
4. Create micro tools




