# Cursor Workflow Templates

Copy and paste these prompts directly into Cursor to execute vibe marketing workflows.

## Template 1: Content Research & Article Creation

### Step 1: Research
```
Mode: Marketing Expert

Task: Research [TOPIC] for 2025

Instructions:
1. Use Perplexity MCP to search for "[TOPIC] 2025"
2. Use Firecrawl MCP to scrape content from top 10 relevant URLs
3. Create comprehensive research document
4. Include:
   - Summary
   - Top tools/products/services
   - Comparison table
   - Overview of each option
   - How they compare

Output: Save to article_research.mmd
```

### Step 2: Add Product Context
```
Mode: Marketing Expert

Task: Enhance article with product context

Instructions:
1. Read LLM.ext for product information
2. Read article_research.mmd
3. Add [YOUR PRODUCT] as a comparison
4. Highlight unique selling points
5. Optimize for keywords: [KEYWORD1, KEYWORD2, KEYWORD3]

Output: Update article_research.mmd
```

### Step 3: SEO Optimization
```
Mode: Marketing Expert

Task: Optimize article for SEO

Instructions:
1. Read article_research.mmd
2. Read keyword_data.txt (if available)
3. Optimize keyword density naturally
4. Add internal linking suggestions
5. Improve structure and readability
6. Ensure content matches [INFORMATIONAL/COMMERCIAL/TRANSACTIONAL] intent

Output: Update article_research.mmd with optimized version
```

---

## Template 2: Internal Linking Analysis

```
Mode: Marketing Expert

Task: Find internal linking opportunities

Instructions:
1. Use Firecrawl MCP to build site map of [YOUR_WEBSITE_URL]/[SECTION]
2. Crawl [NUMBER] articles from that section
3. Scrape content from each article
4. Analyze content for linking opportunities
5. For each opportunity, provide:
   - Source article URL
   - Target article URL
   - Anchor text suggestion
   - Content snippet where link should go
   - Context for why this link makes sense

Output: Save to internal_linking_opportunities.mmd
```

---

## Template 3: Micro Tool Generation

### Step 1: Generate PRD
```
Mode: PRD Generator

Task: Create PRD for [TOOL_NAME]

Instructions:
Create comprehensive PRD including:
1. Executive Summary
2. Problem Statement
3. User Personas: [PERSONA1, PERSONA2, PERSONA3]
4. User Stories for each persona
5. MVP Scope (what to build first)
6. Out of Scope (what to build later)
7. Feature Breakdown:
   - Front-end features
   - Back-end features
   - Subtasks for each feature
8. User Flows
9. Technical Requirements
10. Success Metrics

Focus on:
- Time to value for users
- Conversion goals
- Lead generation potential
- User experience

Output: Save to [tool_name]_prd.mmd
```

### Step 2: Build the Tool
```
Mode: Growth UX Engineer

Task: Build [TOOL_NAME] based on PRD

Instructions:
1. Read [tool_name]_prd.mmd
2. Create HTML/JS/CSS micro tool
3. Focus on:
   - Clean, modern UI
   - Fast time to value
   - Mobile responsive
   - Conversion-focused design
4. Include:
   - Input fields as specified in PRD
   - Clear call-to-action
   - Result display area
   - Copy-to-clipboard functionality (if applicable)

Output: Save to [tool_name].html
```

---

## Template 4: Programmatic SEO

```
Mode: Marketing Expert

Task: Create programmatic SEO content

Instructions:
1. Use Perplexity MCP to research "[BASE_TOPIC] tools"
2. Get list of [NUMBER] tools in this space
3. For each tool, create comparison article:
   - Use content template: [COMPARISON/PROBLEM-SOLUTION/ALTERNATIVES]
   - Include [YOUR PRODUCT] in comparison
   - Optimize for keyword: "[YOUR PRODUCT] vs [COMPETITOR]"
   - Match intent: [INFORMATIONAL/COMMERCIAL/TRANSACTIONAL]
4. Use LLM.ext for product context
5. Ensure each article provides unique value

Output: Create [NUMBER] markdown files, one per tool comparison
```

---

## Template 5: Content Maintenance & Updates

```
Mode: Marketing Expert

Task: Update outdated content

Instructions:
1. Use Firecrawl MCP to scrape [LIST_OF_ARTICLE_URLS]
2. Analyze each article for:
   - Outdated information
   - Missing recent data
   - Broken internal links
   - Low keyword optimization
3. Use Perplexity MCP to get latest information on topics
4. Update each article with:
   - Current data and statistics
   - Recent examples
   - Updated best practices
   - Improved internal linking
   - Better keyword optimization
5. Maintain original structure and value

Output: Updated versions of articles
```

---

## Template 6: Keyword Research Integration

```
Mode: Deep Researcher

Task: Research keywords and create content strategy

Instructions:
1. Use Perplexity MCP to research "[TOPIC] keywords"
2. Find long-tail keywords with:
   - Good search volume
   - Low-medium competition
   - Commercial/intent potential
3. For each keyword, determine:
   - Search intent (informational/commercial/transactional)
   - Content type needed
   - Buyer journey stage
4. Create content plan:
   - Informational: guides, how-tos
   - Commercial: comparisons, alternatives
   - Transactional: product pages, pricing
5. Prioritize by opportunity

Output: Save to keyword_content_strategy.mmd
```

---

## Template 7: Multi-Format Content Repurposing

```
Mode: Marketing Expert

Task: Repurpose article into multiple formats

Instructions:
1. Read article_research.mmd
2. Create versions for:
   - Blog post (current format)
   - Social media posts (5-10 posts)
   - Email newsletter (1-2 versions)
   - Video script outline
   - Twitter/X thread
   - LinkedIn article
3. Adapt tone and format for each platform
4. Maintain core message and value
5. Add platform-specific CTAs

Output: Create separate files for each format
```

---

## Template 8: Competitive Analysis

```
Mode: Deep Researcher

Task: Competitive analysis

Instructions:
1. Use Perplexity MCP to find competitors in "[YOUR_SPACE]"
2. Use Firecrawl MCP to scrape competitor websites
3. Analyze:
   - Features and pricing
   - Content strategy
   - SEO approach
   - Positioning
   - Gaps and opportunities
4. Compare with [YOUR PRODUCT] (from LLM.ext)
5. Identify:
   - Where you're better
   - Where they're better
   - Unique positioning opportunities
   - Content gaps to fill

Output: Save to competitive_analysis.mmd
```

---

## Usage Tips

1. **Replace Placeholders**: Replace [BRACKETED] text with your actual values
2. **Be Specific**: The more specific your prompt, the better the output
3. **Iterate**: Don't expect perfect output first try - refine and iterate
4. **Use Context Files**: Reference LLM.ext and other context files in prompts
5. **Explicit MCP Requests**: Always specify which MCPs to use
6. **Mode Selection**: Use the right mode for the right task
7. **Human Review**: Always review and refine agent output

## Customization

These templates are starting points. Customize them for:
- Your specific industry
- Your content style
- Your target audience
- Your business goals
- Your technical capabilities

---

**Remember**: These are templates - adapt them to your needs. The key is having a clear process and using the right tools (MCPs, modes, context) for each step.



