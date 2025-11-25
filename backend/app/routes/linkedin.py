"""
LinkedIn Post Search Routes

API endpoints for searching and analyzing LinkedIn posts.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import traceback

from app.models.linkedin import (
    LinkedInSearchRequest,
    LinkedInSearchResponse,
    LinkedInPost
)
from app.services.linkedin_client import get_linkedin_client

router = APIRouter()


@router.post("/search", response_model=LinkedInSearchResponse)
async def search_linkedin_posts(request: LinkedInSearchRequest):
    """
    Search for LinkedIn posts based on query and filters.
    
    This endpoint:
    1. Uses Google Custom Search to find LinkedIn post URLs
    2. Uses Firecrawl to scrape post content
    3. Extracts engagement metrics, author info, and content
    4. Filters and sorts posts based on criteria
    
    Returns high-engaging posts that can be used as models for content creation.
    """
    try:
        print(f"🔍 LinkedIn search request: query='{request.query}', max_results={request.max_results}", flush=True)
        
        linkedin_client = get_linkedin_client()
        
        # Search for posts
        posts = linkedin_client.search_posts(
            query=request.query,
            industry=request.industry,
            include_connections=request.include_connections,
            include_non_connections=request.include_non_connections,
            max_results=request.max_results,
            min_engagement_score=request.min_engagement_score,
            sort_by=request.sort_by,
            filter_by_company=request.filter_by_company,
        )
        
        # If topics are specified, also search by topics
        if request.topics:
            topic_posts = linkedin_client.search_posts_by_topic(
                topics=request.topics,
                industry=request.industry,
                max_results=request.max_results // 2 if request.max_results > 10 else 5,
                min_engagement_score=request.min_engagement_score,
                filter_by_company=request.filter_by_company,
            )
            # Merge and deduplicate by post_id
            existing_ids = {post.post_id for post in posts}
            for post in topic_posts:
                if post.post_id not in existing_ids:
                    posts.append(post)
                    existing_ids.add(post.post_id)
        
        # Sort again after merging
        if request.sort_by == "engagement":
            posts.sort(key=lambda p: p.engagement_score or 0, reverse=True)
        elif request.sort_by == "recent":
            posts.sort(key=lambda p: p.scraped_at, reverse=True)
        
        # Limit to max_results
        posts = posts[:request.max_results]
        
        print(f"✅ Found {len(posts)} LinkedIn posts", flush=True)
        
        return LinkedInSearchResponse(
            success=True,
            query=request.query,
            total_results=len(posts),
            posts=posts,
            search_metadata={
                "search_time": "now",
                "industry": request.industry,
                "filters_applied": {
                    "include_connections": request.include_connections,
                    "include_non_connections": request.include_non_connections,
                    "min_engagement_score": request.min_engagement_score,
                    "topics": request.topics,
                    "filter_by_company": request.filter_by_company,
                },
                "sort_by": request.sort_by,
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration error: {str(e)}. Please ensure GOOGLE_CUSTOM_SEARCH_API_KEY, GOOGLE_CUSTOM_SEARCH_ENGINE_ID, and FIRECRAWL_API_KEY are set."
        )
    except Exception as e:
        print(f"❌ Error in LinkedIn search: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"LinkedIn search failed: {str(e)}"
        )


@router.get("/posts/{post_id}")
async def get_linkedin_post(post_id: str):
    """
    Get a specific LinkedIn post by ID.
    
    Note: This requires the post URL to be known. In a full implementation,
    you would store post URLs in a database.
    """
    raise HTTPException(
        status_code=501,
        detail="Get single post endpoint not yet implemented. Use /search to find posts."
    )


class LinkedInTestRequest(BaseModel):
    """Request model for LinkedIn test endpoint."""
    query: str = Field("AI tools", description="Search query")
    max_results: int = Field(3, ge=1, le=10, description="Maximum results to return")


@router.post("/test")
async def test_linkedin_search(request: LinkedInTestRequest):
    """
    Test endpoint for quick LinkedIn search testing.
    
    This is a simplified endpoint for testing and fine-tuning.
    Returns detailed extraction quality metrics.
    """
    try:
        print(f"🧪 TEST: LinkedIn search test - query='{request.query}', max_results={request.max_results}", flush=True)
        
        linkedin_client = get_linkedin_client()
        
        # Perform search
        posts = linkedin_client.search_posts(
            query=request.query,
            max_results=request.max_results,
            sort_by="engagement",
        )
        
        # Calculate extraction quality metrics
        total = len(posts)
        posts_with_author = sum(1 for p in posts if p.author_name)
        posts_with_engagement = sum(1 for p in posts if p.engagement_score and p.engagement_score > 0)
        posts_with_hashtags = sum(1 for p in posts if p.hashtags)
        posts_with_company = sum(1 for p in posts if p.author_company)
        avg_engagement = sum(p.engagement_score or 0 for p in posts) / total if total > 0 else 0
        
        # Extract scraping metadata from first post (if available)
        scraping_metadata = None
        if posts and posts[0].metadata and "_scraping_metadata" in posts[0].metadata:
            scraping_metadata = posts[0].metadata["_scraping_metadata"]
        
        # Return detailed test results
        return {
            "success": True,
            "test_query": request.query,
            "total_posts_found": total,
            "posts": [
                {
                    "post_id": post.post_id,
                    "url": post.post_url,
                    "author": post.author_name or "Unknown",
                    "title": post.author_title,
                    "company": post.author_company,
                    "content": post.content,  # Full content
                    "content_preview": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                    "content_length": len(post.content),
                    "engagement_score": post.engagement_score,
                    "engagement_metrics": post.engagement_metrics,
                    "hashtags": post.hashtags,
                    "mentions": post.mentions,
                    "scraped_at": post.scraped_at,
                }
                for post in posts
            ],
            "test_metadata": {
                "extraction_quality": {
                    "posts_with_author": posts_with_author,
                    "author_extraction_rate": round(posts_with_author / total * 100, 1) if total > 0 else 0,
                    "posts_with_engagement": posts_with_engagement,
                    "engagement_extraction_rate": round(posts_with_engagement / total * 100, 1) if total > 0 else 0,
                    "posts_with_hashtags": posts_with_hashtags,
                    "hashtag_extraction_rate": round(posts_with_hashtags / total * 100, 1) if total > 0 else 0,
                    "posts_with_company": posts_with_company,
                    "company_extraction_rate": round(posts_with_company / total * 100, 1) if total > 0 else 0,
                },
                "engagement_stats": {
                    "average_engagement": round(avg_engagement, 2),
                    "max_engagement": max((p.engagement_score or 0 for p in posts), default=0),
                    "min_engagement": min((p.engagement_score or 0 for p in posts), default=0),
                },
                "content_stats": {
                    "average_content_length": round(sum(len(p.content) for p in posts) / total, 0) if total > 0 else 0,
                    "posts_with_media": sum(1 for p in posts if p.media_urls),
                }
            },
            "scraping_performance": scraping_metadata if scraping_metadata else {
                "note": "Scraping metadata not available. This may indicate all posts were from Google Search snippets."
            }
        }
        
    except Exception as e:
        print(f"❌ TEST ERROR: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )


@router.post("/analyze")
async def analyze_linkedin_posts(posts: List[LinkedInPost]):
    """
    Analyze a collection of LinkedIn posts to extract patterns and insights.
    
    This can help identify:
    - Common themes in high-engaging posts
    - Best posting times
    - Effective content structures
    - Popular hashtags and topics
    """
    try:
        if not posts:
            raise HTTPException(status_code=400, detail="No posts provided for analysis")
        
        # Calculate aggregate statistics
        total_posts = len(posts)
        total_engagement = sum(p.engagement_score or 0 for p in posts)
        avg_engagement = total_engagement / total_posts if total_posts > 0 else 0
        
        # Extract common hashtags
        all_hashtags = {}
        for post in posts:
            if post.hashtags:
                for tag in post.hashtags:
                    all_hashtags[tag] = all_hashtags.get(tag, 0) + 1
        
        top_hashtags = sorted(
            all_hashtags.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Extract common topics/companies
        all_companies = {}
        for post in posts:
            if post.author_company:
                all_companies[post.author_company] = all_companies.get(post.author_company, 0) + 1
        
        top_companies = sorted(
            all_companies.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Find top performing posts
        top_posts = sorted(
            posts,
            key=lambda p: p.engagement_score or 0,
            reverse=True
        )[:5]
        
        return {
            "success": True,
            "analysis": {
                "total_posts": total_posts,
                "average_engagement_score": round(avg_engagement, 2),
                "total_engagement": round(total_engagement, 2),
                "top_hashtags": [{"tag": tag, "count": count} for tag, count in top_hashtags],
                "top_companies": [{"company": company, "count": count} for company, count in top_companies],
                "top_posts": [
                    {
                        "post_id": post.post_id,
                        "author": post.author_name,
                        "engagement_score": post.engagement_score,
                        "content_preview": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                    }
                    for post in top_posts
                ],
            }
        }
        
    except Exception as e:
        print(f"❌ Error in LinkedIn post analysis: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Post analysis failed: {str(e)}"
        )


@router.get("/industry/{industry}/insights")
async def get_industry_insights(
    industry: str,
    query: Optional[str] = None,
    max_results: int = 30
):
    """
    Get insights about what works in a specific industry.
    
    Analyzes high-engaging posts in the industry to identify:
    - Top hashtags used
    - Top companies posting
    - Common job titles
    - Engagement patterns
    - Content length patterns
    
    This helps you understand what content performs well in your target industry.
    """
    try:
        print(f"🔍 Industry insights request: industry='{industry}', query='{query}'", flush=True)
        
        linkedin_client = get_linkedin_client()
        
        insights = linkedin_client.get_industry_insights(
            industry=industry,
            query=query,
            max_results=max_results,
        )
        
        return {
            "success": True,
            **insights
        }
        
    except Exception as e:
        print(f"❌ Error getting industry insights: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Industry insights failed: {str(e)}"
        )


@router.get("/industries")
async def list_industries():
    """
    Get list of supported industries for targeting.
    """
    from app.services.linkedin_client import LinkedInClient
    
    industries = list(LinkedInClient.INDUSTRY_KEYWORDS.keys())
    
    return {
        "success": True,
        "industries": industries,
        "industry_keywords": {
            industry: keywords[:5]  # Show first 5 keywords
            for industry, keywords in LinkedInClient.INDUSTRY_KEYWORDS.items()
        }
    }

