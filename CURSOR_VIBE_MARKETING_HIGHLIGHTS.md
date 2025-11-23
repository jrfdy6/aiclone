# Cursor & Vibe Marketing - Complete Highlights

## Introduction & Context

### About the Speakers
- **Amir**: Technical background, design engineer → full stack engineer (8 years) via AI/tragedy
- **Host**: Non-technical, relies on Claude/ChatGPT, found Cursor intimidating initially

### The Convergence
- **Vibe Coding + Vibe Marketing**: Natural convergence happening
- **Cursor as Interface**: Not just a developer IDE, but an interface for everything
- **10x Evolution**: Moving from "10x engineer" or "10x marketer" → "10x vibe coder/vibe marketer" → "10x Viber"
- **Natural Progression**: Tools like Replit, Lovable, Bolt → Cursor (as people get more comfortable)

### Cursor's Role
- Built as a tool for coding, but people are expanding use cases
- With MCPs, opened the door for marketing, product design, etc.
- **Thesis**: Cursor will become "the interface for everything"
- Can build software AND market software in one place
- Can build micro tools for specific workflows/automation

---

## MCPs (Model Context Protocol) - Deep Dive

### What Are MCPs?
- **Definition**: Model Context Protocol
- **Simplified**: Just another term for APIs
- **How it works**: APIs for language models to interface with datasets
- **Purpose**: Pull data, push data, make changes within conversational window
- **Key Benefit**: Agents can access APIs within conversation context without custom tools

### MCP Installation & Setup
- **Where to find**: Smither, cursory.directory, MCP marketplace websites
- **Setup**: Simple instructions available, add through Cursor settings
- **Two Levels**:
  - **Global MCPs**: Accessible across all Cursor projects
  - **Project-level MCPs**: Specific to individual projects/folders

### Primary MCPs Used
1. **Firecrawl**: For scraping content
2. **Perplexity Ask**: For search
3. **Playwright**: Agentic browser (QA, screenshots, testing)

### Project-Level MCP Examples
- **Stripe MCP**: Query, call, update payment methods, payment links, subscription updates
- **Database MCPs** (e.g., Supabase): Query, call, update, change database directly in chat

### MCP Impact
- **Death of Workflows?**: Potential future - workflows may become obsolete
- **Background Agents**: Automate tasks, human just monitors/optimizes
- **Closed Loops**: Insight to action in one interface, no friction
- **Before MCPs**: Would build Make/Zapier workflows (scrape Twitter → Google Sheets → AI node → repurpose content)
- **With MCPs**: Understand tweet replies, get insights, act - all in Claude/Cursor

### Key Insight: Closed Loops
- All within one context
- Synchronous flow (vs. Make/Zapier which requires piecing together)
- Cohesive experience
- No need to switch between tools

---

## Cursor Modes & Configuration

### Built-in Modes
- **Agent**: Automated agent mode
- **Ask**: Question/answer mode
- **Manual**: Manual control mode
- **Background Agents**: New feature for background tasks

### Custom Modes (5 Examples)
1. **PRD Generator**: Generates product requirements documentation
   - Detailed breakdown of product backlog
   - Uses Gemini (good for PRDs)
2. **Deep Researcher**: For research tasks
3. **Marketing Expert**: Claude 3.7 with custom configuration
   - Focused on content marketing tasks
4. **Growth UX Engineer**: For UX/growth tasks
5. **Feature Simulator**: For feature simulation

### Custom Modes Explained
- Preconfigured settings on models and prompts
- Define how agent should behave
- Different from Claude's project-level settings (these are agent-level)

### Model Selection Strategy
- **For Planning/Thinking**: Use large complex thinking models (O3, Gemini 2.5)
  - Work through implementation plans
  - Approach to solving problems
  - Fixing bugs (planning phase)
- **For Execution**: Use task-based agents (3.5, 3.7 Sonnet)
  - Execute on the plan
  - Don't require extended thinking
- **Orchestration**: Human supervises, assigns right agents to right tasks

### Key Insight: Model Specialization
- Don't use one model for everything
- Split tasks: research → consolidation → content generation
- Results "go through the roof" when using specialized models
- Ties to Anthropic's article on building effective agents

---

## Use Case 1: Content Research & Article Creation

### The Process
1. **Write topic in document**: Simple markdown file
2. **Create new file**: `article_research.mmd`
3. **Tag agent**: Use custom mode (e.g., "Marketing Expert")
4. **Specify MCPs**: Explicitly request Perplexity MCP and Firecrawl MCP
5. **Output**: Comprehensive research document

### Why Specify MCPs Explicitly?
- Confirms agent will actually run the MCP
- Ensures proper tool usage

### Research Output
- Comprehensive article (598 lines in example)
- Summary
- Top tool recommendations
- Comparison table
- Overview of each tool
- How tools compare

### Key Advantages
- **Data from MCPs**: Not using contextual/trained data (reduces hallucination)
- **Relevant Results**: Much better than ChatGPT for marketing research
- **Self-Improving**: Agent revises, adds comparison tables, enhances output
- **Extended Thinking**: Self-improvement based on prompting

### Next Steps After Research
- Copy to CMS (Webflow, Framer, custom site)
- **Webflow MCP**: Can directly publish articles
- **Programmatic SEO**: Create 25-50 pages at once
  - Create template
  - Generate 50 articles in Cursor
  - Use Webflow MCP to publish all at once

---

## Content Templates & Strategy

### Content Templates
- **Product Comparison Templates**: For comparing products
- **Problem Solution Template**: Problem-focused content
- **Best Competitor Alternative Template**: Alternative-focused content
- **Industry Trend Insights**: Trend-focused content

### Content Strategy Framework
- **Intent-Based**: Work backwards from user intent
  - **Informational**: Looking for information
  - **Commercial**: Comparing options
  - **Transactional**: Ready to buy
- **Template Application**: Prompt LLM to revise article to specific template format
- **Programmatic Scaling**: Apply to 25+ tools at once

### Adding Product Context
- **LLM.ext file**: Complete overview of your product
  - What app is and does
  - Features
  - Pricing
  - Value proposition
  - USP
- **Usage**: "Based on article research and LLM.ext, tell me how [product] compares and add to article"

### SEO Optimization
- **Keyword Research**: Export from Semrush/Ahrefs
  - Keyword difficulty
  - Volume
  - Search intent
- **Integration**: "Based on LLM.ext and keyword data, update article research"
- **Result**: Article optimized for keywords with product context

### Key Insight: Context Windows
- **Larger Context Windows**: Gemini models have huge context windows
- **No RAG Needed**: Can inject everything into system prompt
- **Supervisor Agents**: One Gemini calls 5 different Geminis, each with context
- **Future**: Getting rid of RAG completely

---

## LLM Discovery & SEO

### LLM Discovery = SEO
- **No Difference**: Optimizing for LLM discovery is same as SEO
- **LLMs Scrape**: Still trained on web pages
- **Optimize for Bing**: Partnership with OpenAI/Microsoft
- **Pre-trained Context**: As long as you optimize on Reddit, Bing, have more content → show up in search
- **Traffic Data**: Seeing leads from ChatGPT

### Multi-Format Strategy
- **Repurpose Content**: Article → other media formats
- **UGC Priority**: LLMs/Google prioritize user-generated content
- **YouTube Videos**: Another format to prioritize
- **Multiple Channels**: Tap into all opportunities

### Key Insight: Content Repurposing
- One research session → multiple content pieces
- Article is just one output
- Can repurpose for multiple channels
- Tap into different algorithm preferences

---

## Human-in-the-Loop Process

### Review Process
- **Subject Matter Expert**: Should be able to quickly call out topics/points
- **Critical Checks**:
  - Price points accuracy
  - Feature accuracy
  - Does it make sense?
  - Right keywords?
  - Right messaging for intent (commercial/informational)?
  - No hallucination
- **Lower Risk**: Because pulling from Perplexity/Firecrawl (relevant context)

### Publishing Options
- Copy as markdown → paste into Webflow/Framer
- Use CMS MCP to directly publish
- Mass publishing capability

### Results
- Getting customers and traffic
- Tracking keywords
- Tracking where users come from
- Tactic working well

---

## Use Case 2: Internal Linking for SEO

### The Problem
- Tools exist (site map builders, internal linking tools)
- They cost money
- Want to do it in "true vibe coding/vibe marketing fashion" (save money)
- Tools are great but want closed loop in Cursor

### The Process
1. **Prompt Agent**: Use Firecrawl to build site map
2. **Crawl Articles**: Specify number (e.g., 10 articles)
3. **Scrape Content**: Get all content from articles
4. **Find Opportunities**: Agent finds internal linking opportunities
5. **Output**: Specific recommendations
   - Which article links to which
   - Content snippets to use
   - Anchor text suggestions

### Output Format
- Full breakdown of articles
- Specific linking recommendations
- Exact snippets to use
- Target pages to link to

### Implementation
- Go to CMS
- Open specific article
- Add recommended links
- **Future**: With Webflow MCP, can do this automatically

### Advanced Use: Content Maintenance
- **Google's Recommendation**: Update older content, keep it fresh
- **Process**:
  1. Check position ranking in Ahrefs/Semrush
  2. See what's gone up/down
  3. Identify outdated content (2023, 2024)
  4. Scrape all links and content
  5. Make recommendations based on research workflow
  6. Update articles
- **Scale**: Do this for many pages at once
- **Cost Savings**: Instead of paying SEO agency

---

## Use Case 3: Micro Tools for Top-of-Funnel

### Why Micro Tools?
- **Big Advocate**: Highly effective for top-of-funnel traffic
- **Example**: UTM link generator
- **Results**: When ranking on first page → hundreds of thousands of clicks/impressions
- **Competitive Space**: But worth competing in

### Micro Tools Strategy
- **Value Add**: Build awareness for your product/service
- **Extension of Product**: If you have analytics tool → free UTM generator
- **Upsell Opportunity**: Free tool → upsell to full product
- **Example Company**: V.io (video editor)
  - Built suite of 20-30 micro tools
  - Specific tasks: remove image background, add transcriptions
  - Free tools → upsell to full product suite

### Why Micro Tools Work
- **Time to Value**: Shortcut vs. ebooks/guides/downloads
- **Actionable Immediately**: No need to turn info into action
- **Faster Conversion**: Moves users along conversion path quicker
- **More Value**: Add more value in shorter time

### Finding Opportunities
- **SEO Tools**: Use Semrush/Ahrefs
- **Search For**: "Free [X] tool", "Free YouTube thumbnail generator", "Free AB test calculator", "Free UTM link generator"
- **Huge Impact**: These searches have significant volume

### The Process
1. **Prompt Agent**: Study LLM.ext, research website via Firecrawl MCP
2. **Request**: Top 5 micro tool recommendations
3. **Provide Context**: Keyword data
4. **Output**: List of 5 tools
5. **Choose One**: Based on keyword volume, difficulty, CPC

### Keyword Research Integration
- Look at keyword data
- Check volume for long-tail keywords
- Assess keyword difficulty
- Check CPC
- Complement with SEO research

---

## Building Micro Tools: The Complete Workflow

### Step 1: PRD Generation
- **Use PRD Generator Mode**: Custom mode with Gemini 2.5
- **Prompt**: "Build out PRD of [tool name]"
- **Output**: Extensive product requirements documentation

### PRD Generator Features
- **Scope**: MVP scope defined
- **Out of Scope**: Items to build later
- **User Stories**: Thinking through user journey
- **Personas**: Small business owner, junior marketer, freelance content creator
- **Flows**: User flows documented
- **Features Breakdown**: Front-end and back-end features
- **Subtasks**: Broken down into manageable pieces

### Why PRD First?
- **Foundation**: Good foundation for agents to build
- **Level of Detail**: Comprehensive breakdown
- **Progress Tracking**: Use as requirements document
- **Context for Agent**: Agent keeps all context while building
- **Continuous Updates**: Agent can update document as progress is made

### Step 2: Building the Tool
- **Take PRD**: Reference it in prompt
- **Request**: "Using this PRD, create simple HTML/JS/CSS micro tool"
- **Agent Builds**: With all context from PRD
- **Output**: Fully deployable tool

### Debugging & Iteration
- **Vibe Marketing Context**: Not much debugging needed
  - More time on reprompting
  - Different approach to prompting
  - Getting output right
- **Vibe Coding Context**: More debugging
  - Planning, approaching build, debugging = core components
  - Getting it to build isn't easy part
  - Solving problems and thinking through approach is core

### Step 3: Deployment
- **Embed**: Add to Framer site, Webflow site, custom site
- **Code Embed**: Just embed the code
- **Create Page**: Add tool to page
- **Ready to Use**: Immediately functional

### Example: UTM Link Generator
- **Input**: Link, campaign parameters
- **Output**: Generated UTM link
- **Use Case**: Marketers running CPC campaigns
- **Value**: Attribute traffic in analytics software
- **Relevance**: Directly relevant to analytics products

---

## Strategy & Philosophy

### The Right Foundation
- **Doesn't Replace Strategy**: Tool doesn't replace having right strategy/logic/approach
- **10x Leverage**: If you have those things, this 10xs you
- **Speed, Efficiency, Cost**: What tools provide
- **Augmentation**: LLMs are extension of your work
- **You're the Architect**: Still need to articulate what you want
- **Outcome Focus**: Help approach the outcome you're going towards

### Common Mistakes
- **Vibe Coding**: Novice people building quickly, skipping steps
  - Not helping LM think through implementation plan
  - Not thinking through approach
- **Same Applies to Marketing**: Understanding what you're trying to do
  - Who is end user?
  - What do you want to get out of this?
- **You're the Architect**: Piecing everything together

### Time & Cost Savings
- **30 Minutes**: What took 30 minutes in demo
- **Traditional**: Would take a week with SEO agency or content marketer
- **Cost**: Thousands of dollars and month+ of work traditionally
- **Output**: Moving faster, higher output, saving money

### Buyer Journey Focus
- **Always Think About End User**: From research to internal linking to buyer journey
- **ICP Understanding**: Who you're building for
- **Buyer Journey**: Commercial, informational, transactional
- **User Flows**: Build cohesive flows
- **Drip Campaigns**: Serve exact needs

### Content Strategy Insight
- **Programmatic SEO Problem**: Most people generating informational blog posts
  - Throwing on site
  - Not adding value
  - Get penalized by Google
  - Say "AI in SEO doesn't work"
- **Right Approach**: 
  - Solve real problems
  - Provide highly relevant information
  - Format based on customer journey stage
  - Discovery layer: "What are AB testing tools?"
  - Comparison layer: "Compare AB testing tools"
  - Product comparison: "Your product vs. Optimizely"
  - Provide value at each stage

### Lead Magnets & Conversion
- **Match Intent**: Tools/calculators/lead magnets match visitor intent
- **Discovery Phase**: Email guide or course (e.g., "How to approach your first AB test")
- **Add Value**: Capture person on content with lead magnet
- **Drive Conversion**: Drip sequence in email automation tool
- **Cohesive Flow**: Build from content gathered

---

## About Humbolytics

### The Product
- **Built for Self**: Tool built to address own pain point
- **Problem**: Too caught up in Google Analytics
  - "Too much data is no data at all"
  - Not good data
- **Solution**: Simple analytics tool
  - Run experiments with AB testing
  - Increase conversions
  - Funnel visualization (the way you want)
  - Simple traffic and website data
  - Understand what data is telling you
  - What you can do with it

### Users
- **Agencies**: Empower agencies
- **Creators**: Help creators
- **Goal**: Enable marketers and performance marketers
- **All-in-One**: Conversion optimization tools
  - Test experiments
  - See funnels
  - See if marketing efforts are working

### Website
- humbolytics.com

---

## Key Takeaways & Future Predictions

### Cursor Evolution
- **Interface for Everything**: Becoming the interface for all work
- **Not Just Coding**: Marketing, product design, workflows
- **MCPs Unlock**: Opened door for all backgrounds

### Workflow Evolution
- **Death of Workflows?**: MCPs + background agents may replace traditional workflows
- **Background Agents**: Automate tasks, human monitors
- **Human-in-the-Loop**: Evolve to monitoring and optimizing

### Model Evolution
- **Larger Context Windows**: Gemini models
- **No RAG Needed**: Inject everything into context
- **Supervisor Agents**: One model calls multiple specialized models
- **Getting Rid of RAG**: Natural evolution

### The 10x Evolution
- **10x Engineer** → **10x Marketer** → **10x Vibe Coder/Vibe Marketer** → **10x Viber**
- **Hiring**: Will hire "Vibe employees"
  - Vibe marketing
  - Vibe coding
  - Vibe building

### Natural Progression
- **Start**: Replit, Lovable (build MVPs, market there)
- **Next Step**: Cursor (take to next level)
- **Evolution**: As people get more familiar with tools
- **Expansion**: More complex tools expand workflows

### Closed Loop Systems
- **Everything in One**: Get everything all at once
- **Easier Setup**: Once setup is done, much easier
- **No Friction**: No switching between tools
- **Synchronous Flow**: Cohesive experience

---

## Technical Details & Tips

### Prompting Best Practices
- **Explicit MCP Requests**: Say "run Perplexity MCP and Firecrawl MCP"
- **Confirms Usage**: Ensures agent actually runs the MCP
- **Custom Modes**: Use for specific behaviors
- **Model Selection**: Right model for right task

### File Management
- **Markdown Files**: Use .mmd or .md for documents
- **LLM.ext**: Use for product context
- **Organization**: Keep research, PRDs, outputs organized

### MCP Configuration
- **Global vs. Project**: Understand difference
- **API Keys**: Need developer accounts for some (e.g., Perplexity)
- **Documentation**: Step-by-step on Smither, directories
- **Simple Setup**: Just API key + configuration

### Model Behavior
- **Tool Calls**: Models always refining how they call MCPs
- **May Not Work First Try**: Sometimes need to change model or retry
- **Part of Vibing**: Natural process, iterate

### Content Formats
- **HTML Preview**: Can create HTML versions of articles
- **Markdown**: Primary format for content
- **Tables**: Supported in markdown
- **Sources**: Can list sources

### Integration Points
- **CMS Integration**: Webflow, Framer via MCPs
- **Direct Publishing**: Can publish directly from Cursor
- **Mass Publishing**: Programmatic SEO capability
- **Code Embeds**: Micro tools as code embeds

---

## Contact & Resources

### Amir's Contact
- **Twitter/X**: @amirmxc
- **Find**: "amir mirxc" anywhere

### Resources Mentioned
- **MCP Directories**: Smither, cursory.directory
- **MCP Marketplaces**: Search "MCP marketplace"
- **Documentation**: GitHub docs for MCP setup
- **Tools**: Perplexity, Firecrawl, Playwright

---

## Final Thoughts

### The Convergence
- **Vibe Coding + Vibe Marketing**: Natural convergence
- **Cursor as Hub**: Where both can happen
- **Co-vibing**: Working together

### The Future
- **Interface of Life**: Cursor becoming interface for everything
- **Lower Barriers**: AI tools lowering barriers to entry
- **10x Everything**: 10x employees doing everything
- **Evolution**: Natural progression as tools improve

### The Message
- **Strategy First**: Tools augment, don't replace strategy
- **You're the Architect**: Still need to think and plan
- **Speed & Efficiency**: Tools provide these
- **Closed Loops**: Everything in one place
- **Value Focus**: Always think about end user

---

*This document captures every point, insight, tip, and detail from the 60-minute conversation about Cursor, MCPs, and Vibe Marketing.*



