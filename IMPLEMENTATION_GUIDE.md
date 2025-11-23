# Vibe Marketing Implementation Guide

This guide will help you implement the strategies from the Cursor & Vibe Marketing conversation.

## Quick Start

### 1. Set Up MCPs in Cursor

Follow the detailed guide in `MCP_SETUP_GUIDE.md` to install:
- **Firecrawl MCP**: For web scraping
- **Perplexity MCP**: For research
- **Playwright MCP**: For browser automation

### 2. Configure Custom Modes

Follow `CURSOR_CUSTOM_MODES.md` to set up:
- PRD Generator Mode
- Marketing Expert Mode
- Deep Researcher Mode
- Growth UX Engineer Mode
- Feature Simulator Mode

### 3. Create Your LLM.ext File

1. Copy `LLM.ext` template
2. Fill in your product information
3. Keep it updated as your product evolves

### 4. Use the API Endpoints

The backend now includes routes at `/api/content/*`:
- `/api/content/research` - Content research
- `/api/content/internal-linking` - Internal linking analysis
- `/api/content/micro-tool` - Micro tool generation
- `/api/content/prd` - PRD generation
- `/api/content/seo-optimize` - SEO optimization

### 5. Access the Frontend

Navigate to `/content-marketing` in your frontend to use the UI.

## Implementation Roadmap

### Phase 1: Foundation (Current)
✅ MCP setup guides
✅ Custom modes configuration
✅ LLM.ext template
✅ Backend API structure
✅ Frontend UI components

### Phase 2: MCP Integration (✅ Complete)
- [x] Integrate Perplexity API for research
- [x] Integrate Firecrawl API for scraping
- [ ] Add OpenAI/Anthropic for content synthesis (Optional - can enhance results)
- [x] Test MCP workflows end-to-end

### Phase 3: Enhanced Features
- [ ] Keyword research integration (Semrush/Ahrefs)
- [ ] CMS integration (Webflow MCP)
- [ ] Programmatic SEO workflows
- [ ] Content template system
- [ ] Automated publishing

### Phase 4: Advanced Workflows
- [ ] Background agents for automation
- [ ] Multi-agent orchestration
- [ ] Content repurposing workflows
- [ ] Analytics integration
- [ ] A/B testing workflows

## Workflow Examples

### Example 1: Content Research Workflow

1. **In Cursor**:
   - Switch to "Marketing Expert" mode
   - Create new file: `article_research.mmd`
   - Prompt: "Use Perplexity MCP and Firecrawl MCP to research 'best AB testing tools 2025'. Put output in article_research.mmd"

2. **Or via API**:
   ```bash
   curl -X POST http://localhost:8080/api/content/research \
     -H "Content-Type: application/json" \
     -d '{
       "topic": "best AB testing tools 2025",
       "num_results": 10,
       "include_comparison": true
     }'
   ```

3. **Review and Refine**:
   - Check for accuracy
   - Add your product context (LLM.ext)
   - Optimize for keywords

### Example 2: Internal Linking Workflow

1. **In Cursor**:
   - Use "Marketing Expert" mode
   - Prompt: "Use Firecrawl MCP to build a site map of https://example.com/guides. Crawl 10 articles and find internal linking opportunities."

2. **Or via API**:
   ```bash
   curl -X POST http://localhost:8080/api/content/internal-linking \
     -H "Content-Type: application/json" \
     -d '{
       "website_url": "https://example.com",
       "section_path": "/guides",
       "num_articles": 10
     }'
   ```

3. **Implement**:
   - Review recommendations
   - Add links to your CMS
   - Track impact on SEO

### Example 3: Micro Tool Generation

1. **Generate PRD First**:
   ```bash
   curl -X POST http://localhost:8080/api/content/prd \
     -H "Content-Type: application/json" \
     -d '{
       "product_name": "UTM Link Generator",
       "product_description": "A tool to generate UTM parameters for tracking campaigns",
       "target_users": ["small business owner", "junior marketer"]
     }'
   ```

2. **Generate Tool**:
   ```bash
   curl -X POST http://localhost:8080/api/content/micro-tool \
     -H "Content-Type: application/json" \
     -d '{
       "tool_name": "UTM Link Generator",
       "tool_description": "Generate UTM tracking links for your campaigns",
       "target_audience": ["small business owner", "junior marketer"]
     }'
   ```

3. **Deploy**:
   - Copy HTML code
   - Embed in your website
   - Start collecting leads

## Best Practices

### Content Strategy
1. **Always start with research** - Use MCPs to gather real data
2. **Think about intent** - Informational, commercial, or transactional?
3. **Provide value** - Don't just keyword stuff, solve real problems
4. **Match buyer journey** - Content should match where users are

### Technical
1. **Use PRD first** - Always generate PRD before building
2. **Explicit MCP requests** - Always specify which MCPs to use
3. **Human-in-the-loop** - Review and refine agent output
4. **Iterate** - Don't expect perfect output first try

### Workflow
1. **Plan with large models** - Use Gemini 2.5/GPT-4o for planning
2. **Execute with task models** - Use Claude 3.7/GPT-3.5 for execution
3. **Use context files** - LLM.ext for product context
4. **Markdown output** - Request markdown for better structure

## Troubleshooting

### MCPs Not Working
- Check API keys are set correctly
- Verify Node.js/npm are installed
- Check internet connection
- Review MCP server logs

### API Errors
- Check backend is running
- Verify CORS settings
- Check environment variables
- Review server logs

### Content Quality
- Provide more context in prompts
- Use explicit MCP requests
- Review and refine output
- Adjust model temperature if needed

## Next Steps

1. **Complete MCP Setup**: Follow `MCP_SETUP_GUIDE.md`
2. **Configure Custom Modes**: Follow `CURSOR_CUSTOM_MODES.md`
3. **Fill in LLM.ext**: Add your product information
4. **Test Workflows**: Try each workflow end-to-end
5. **Integrate Real APIs**: Replace placeholders with actual MCP/API calls
6. **Scale**: Build programmatic workflows for multiple pieces of content

## Resources

- **MCP Setup**: `MCP_SETUP_GUIDE.md`
- **Custom Modes**: `CURSOR_CUSTOM_MODES.md`
- **Highlights**: `CURSOR_VIBE_MARKETING_HIGHLIGHTS.md`
- **LLM.ext Template**: `LLM.ext`

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the detailed guides
3. Test with simple examples first
4. Iterate and refine

---

**Remember**: Tools augment your strategy, they don't replace it. You're still the architect. These tools provide speed, efficiency, and cost savings - but you need the right strategy and logic first.

