"""
Content Marketing Routes - Vibe Marketing Workflows

This module provides API endpoints for:
- Content research using MCPs (Perplexity, Firecrawl)
- Internal linking analysis
- Micro tools generation
- PRD generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import json

from app.services.perplexity_client import get_perplexity_client
from app.services.firecrawl_client import get_firecrawl_client

router = APIRouter()


# ============================================================================
# Content Research
# ============================================================================

class ContentResearchRequest(BaseModel):
    topic: str = Field(..., description="Topic to research (e.g., 'best AB testing tools 2025')")
    num_results: int = Field(10, ge=1, le=50, description="Number of results to gather")
    include_comparison: bool = Field(True, description="Include comparison tables")
    output_format: str = Field("markdown", description="Output format (markdown, json)")


class ContentResearchResponse(BaseModel):
    success: bool
    topic: str
    research_content: str
    tools_found: List[Dict[str, Any]]
    comparison_table: Optional[str] = None
    sources: List[str] = []


@router.post("/research", response_model=ContentResearchResponse)
async def content_research(req: ContentResearchRequest):
    """
    Research a topic using Perplexity and Firecrawl APIs to generate comprehensive content.
    
    Process:
    1. Use Perplexity to search and get initial research
    2. Use Firecrawl to scrape content from source URLs
    3. Synthesize into comprehensive article
    """
    try:
        # Step 1: Research with Perplexity
        perplexity = get_perplexity_client()
        research_data = perplexity.research_topic(
            topic=req.topic,
            num_results=req.num_results,
            include_comparison=req.include_comparison,
        )
        
        # Step 2: Scrape additional content from sources using Firecrawl
        firecrawl = get_firecrawl_client()
        scraped_content = []
        sources_to_scrape = research_data.get("sources", [])[:5]  # Limit to 5 URLs
        
        for source in sources_to_scrape:
            url = source.get("url", "")
            if url:
                try:
                    scraped = firecrawl.scrape_url(url)
                    scraped_content.append({
                        "url": url,
                        "title": scraped.title,
                        "content": scraped.content[:2000],  # Limit content length
                    })
                except Exception as e:
                    print(f"Failed to scrape {url}: {e}", flush=True)
                    continue
        
        # Step 3: Build comprehensive research content
        research_content = f"""# Research: {req.topic}

## Summary
{research_data.get('summary', 'Research summary not available')}

## Key Findings

{research_data.get('summary', '')}

## Sources
"""
        
        # Add sources
        all_sources = research_data.get("sources", [])
        for i, source in enumerate(all_sources[:req.num_results], 1):
            url = source.get("url", "")
            title = source.get("title", url)
            research_content += f"{i}. [{title}]({url})\n"
        
        # Add comparison table if requested
        comparison_table = None
        if req.include_comparison:
            comparison_table = f"""
## Comparison

Based on research, here are the key options for {req.topic}:

{research_data.get('summary', 'Comparison details available in summary above.')}
"""
            research_content += comparison_table
        
        # Extract tools/products mentioned (simple extraction)
        tools_found = []
        summary_lower = research_data.get('summary', '').lower()
        # This is a simple extraction - in production, use LLM to extract structured data
        if 'tool' in summary_lower or 'software' in summary_lower:
            tools_found.append({
                "name": "Extracted from research",
                "description": "See summary for details"
            })
        
        return ContentResearchResponse(
            success=True,
            topic=req.topic,
            research_content=research_content,
            tools_found=tools_found,
            comparison_table=comparison_table,
            sources=[s.get("url", "") for s in all_sources]
        )
    except ValueError as e:
        # API key not configured
        raise HTTPException(
            status_code=400,
            detail=f"API configuration error: {str(e)}. Please set PERPLEXITY_API_KEY and/or FIRECRAWL_API_KEY environment variables."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content research failed: {str(e)}")


# ============================================================================
# Internal Linking Analysis
# ============================================================================

class InternalLinkingRequest(BaseModel):
    website_url: str = Field(..., description="Base URL of website to analyze")
    section_path: Optional[str] = Field(None, description="Specific section path (e.g., '/guides')")
    num_articles: int = Field(10, ge=1, le=50, description="Number of articles to analyze")
    depth: int = Field(2, ge=1, le=5, description="Crawl depth")


class InternalLinkingOpportunity(BaseModel):
    source_article: str
    target_article: str
    anchor_text: str
    content_snippet: str
    context: str
    relevance_score: float


class InternalLinkingResponse(BaseModel):
    success: bool
    website_url: str
    articles_analyzed: List[str]
    opportunities: List[InternalLinkingOpportunity]
    total_opportunities: int


@router.post("/internal-linking", response_model=InternalLinkingResponse)
async def analyze_internal_linking(req: InternalLinkingRequest):
    """
    Analyze a website for internal linking opportunities using Firecrawl API.
    
    Process:
    1. Build site map using Firecrawl
    2. Scrape content from articles
    3. Analyze content for linking opportunities
    4. Return specific recommendations
    """
    try:
        firecrawl = get_firecrawl_client()
        
        # Step 1: Build site map
        base_url = req.website_url.rstrip('/')
        if req.section_path:
            crawl_url = f"{base_url}{req.section_path}"
            include_paths = [req.section_path]
        else:
            crawl_url = base_url
            include_paths = None
        
        # Step 2: Crawl and scrape articles
        scraped_articles = firecrawl.crawl_url(
            url=crawl_url,
            max_depth=req.depth,
            max_pages=req.num_articles,
            limit=req.num_articles,
            include_paths=include_paths,
        )
        
        articles_analyzed = [article.url for article in scraped_articles]
        
        # Step 3: Analyze for linking opportunities
        # Simple keyword-based matching (in production, use LLM for semantic analysis)
        opportunities = []
        
        # Extract keywords/topics from each article
        article_topics = {}
        for article in scraped_articles:
            # Simple topic extraction from title and content
            content_lower = (article.title + " " + article.content[:1000]).lower()
            topics = []
            
            # Common marketing/tech keywords to match
            keywords = ['tool', 'guide', 'tutorial', 'comparison', 'best', 'how to', 'strategy']
            for keyword in keywords:
                if keyword in content_lower:
                    topics.append(keyword)
            
            article_topics[article.url] = {
                "title": article.title,
                "topics": topics,
                "content": article.content[:500],  # First 500 chars for context
            }
        
        # Step 4: Find linking opportunities
        for source_url, source_data in article_topics.items():
            for target_url, target_data in article_topics.items():
                if source_url == target_url:
                    continue
                
                # Check if topics overlap or if source mentions something related to target
                source_content = source_data["content"].lower()
                target_title = target_data["title"].lower()
                
                # Simple matching: if source content mentions target title keywords
                target_keywords = target_title.split()[:3]  # First 3 words of target title
                matches = sum(1 for kw in target_keywords if len(kw) > 3 and kw in source_content)
                
                if matches >= 1:  # At least one keyword match
                    # Find snippet where link should go
                    content_snippet = source_data["content"][:200] + "..."
                    
                    opportunities.append(InternalLinkingOpportunity(
                        source_article=source_url,
                        target_article=target_url,
                        anchor_text=target_data["title"],
                        content_snippet=content_snippet,
                        context=f"Source article discusses topics related to '{target_data['title']}'",
                        relevance_score=matches / len(target_keywords) if target_keywords else 0.5
                    ))
        
        # Sort by relevance
        opportunities.sort(key=lambda x: x.relevance_score, reverse=True)
        opportunities = opportunities[:20]  # Limit to top 20
        
        return InternalLinkingResponse(
            success=True,
            website_url=req.website_url,
            articles_analyzed=articles_analyzed,
            opportunities=opportunities,
            total_opportunities=len(opportunities)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"API configuration error: {str(e)}. Please set FIRECRAWL_API_KEY environment variable."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal linking analysis failed: {str(e)}")


# ============================================================================
# Micro Tools Generation
# ============================================================================

class MicroToolRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the micro tool (e.g., 'UTM Link Generator')")
    tool_description: str = Field(..., description="Description of what the tool does")
    target_audience: List[str] = Field(..., description="Target personas (e.g., ['small business owner', 'junior marketer'])")
    features: List[str] = Field(default_factory=list, description="Required features")
    output_format: str = Field("html", description="Output format (html, react, vue)")


class MicroToolResponse(BaseModel):
    success: bool
    tool_name: str
    html_code: str
    css_code: Optional[str] = None
    js_code: Optional[str] = None
    deployment_instructions: str
    prd_summary: Optional[str] = None


@router.post("/micro-tool", response_model=MicroToolResponse)
async def generate_micro_tool(req: MicroToolRequest):
    """
    Generate a micro tool (HTML/JS/CSS) based on requirements.
    
    This can be used to create:
    - UTM link generators
    - AB test calculators
    - SEO tools
    - Other lead magnets
    """
    try:
        # TODO: Integrate with LLM to generate tool code
        # Use PRD generator first, then code generator
        
        # Placeholder HTML template
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{req.tool_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .tool-container {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 24px;
            margin-top: 20px;
        }}
        input, button {{
            padding: 12px;
            margin: 8px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
            box-sizing: border-box;
        }}
        button {{
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
        }}
        button:hover {{
            background: #0056b3;
        }}
        .result {{
            margin-top: 20px;
            padding: 16px;
            background: white;
            border-radius: 4px;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <h1>{req.tool_name}</h1>
    <p>{req.tool_description}</p>
    
    <div class="tool-container">
        <form id="toolForm">
            <!-- Tool inputs will be generated based on requirements -->
            <input type="text" id="input1" placeholder="Enter value...">
            <button type="submit">Generate</button>
        </form>
        
        <div id="result" class="result" style="display: none;"></div>
    </div>
    
    <script>
        document.getElementById('toolForm').addEventListener('submit', function(e) {{
            e.preventDefault();
            // Tool logic will be generated based on requirements
            const result = document.getElementById('result');
            result.style.display = 'block';
            result.textContent = 'Tool functionality to be implemented';
        }});
    </script>
</body>
</html>"""

        return MicroToolResponse(
            success=True,
            tool_name=req.tool_name,
            html_code=html_template,
            css_code=None,
            js_code=None,
            deployment_instructions="Copy the HTML code and embed it in your website. Customize the form inputs and JavaScript logic based on your specific tool requirements.",
            prd_summary=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Micro tool generation failed: {str(e)}")


# ============================================================================
# PRD Generation
# ============================================================================

class PRDRequest(BaseModel):
    product_name: str = Field(..., description="Name of the product/feature")
    product_description: str = Field(..., description="Description of what to build")
    target_users: List[str] = Field(..., description="Target user personas")
    key_features: List[str] = Field(default_factory=list, description="Key features to include")
    include_mvp_scope: bool = Field(True, description="Include MVP scope definition")
    include_user_stories: bool = Field(True, description="Include user stories")


class PRDResponse(BaseModel):
    success: bool
    product_name: str
    prd_content: str
    mvp_scope: Optional[List[str]] = None
    out_of_scope: Optional[List[str]] = None
    user_stories: Optional[List[Dict[str, Any]]] = None


@router.post("/prd", response_model=PRDResponse)
async def generate_prd(req: PRDRequest):
    """
    Generate a Product Requirements Document (PRD) for a feature or product.
    
    This uses the PRD Generator custom mode approach:
    1. Think through the problem
    2. Define user personas and stories
    3. Break down MVP scope
    4. Define out-of-scope items
    5. Create detailed feature breakdown
    """
    try:
        # TODO: Integrate with LLM (Gemini 2.5 or GPT-4o) to generate comprehensive PRD
        
        prd_template = f"""# Product Requirements Document: {req.product_name}

## Executive Summary
{req.product_description}

## Problem Statement
[To be generated based on product description and target users]

## Target Users
{chr(10).join(f"- {user}" for user in req.target_users)}

## User Personas
[Detailed personas to be generated]

## User Stories
[User stories to be generated based on target users]

## MVP Scope
[Features to build first - to be generated]

## Out of Scope
[Features to build later - to be generated]

## Feature Breakdown

### Front-End Features
[To be generated]

### Back-End Features
[To be generated]

## User Flows
[To be generated]

## Technical Requirements
[To be generated]

## Success Metrics
[To be generated]
"""

        return PRDResponse(
            success=True,
            product_name=req.product_name,
            prd_content=prd_template,
            mvp_scope=[],
            out_of_scope=[],
            user_stories=[]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PRD generation failed: {str(e)}")


# ============================================================================
# SEO Content Optimization
# ============================================================================

class SEOOptimizeRequest(BaseModel):
    content: str = Field(..., description="Content to optimize")
    keywords: List[str] = Field(..., description="Keywords to optimize for")
    target_intent: str = Field("informational", description="Content intent (informational, commercial, transactional)")
    include_internal_links: bool = Field(True, description="Suggest internal linking opportunities")


class SEOOptimizeResponse(BaseModel):
    success: bool
    optimized_content: str
    keyword_density: Dict[str, float]
    suggestions: List[str]
    internal_link_suggestions: Optional[List[Dict[str, Any]]] = None


@router.post("/seo-optimize", response_model=SEOOptimizeResponse)
async def optimize_seo_content(req: SEOOptimizeRequest):
    """
    Optimize content for SEO by:
    1. Incorporating keywords naturally
    2. Adjusting for target intent
    3. Suggesting internal links
    4. Improving structure
    """
    try:
        # TODO: Integrate with LLM to optimize content
        
        # Calculate keyword density (placeholder)
        keyword_density = {keyword: 0.0 for keyword in req.keywords}
        
        return SEOOptimizeResponse(
            success=True,
            optimized_content=req.content,  # Would be optimized version
            keyword_density=keyword_density,
            suggestions=[],
            internal_link_suggestions=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SEO optimization failed: {str(e)}")

