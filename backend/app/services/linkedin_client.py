"""
LinkedIn Post Search Client

Searches for LinkedIn posts using Google Custom Search and scrapes content using Firecrawl.
"""

import os
import re
import time
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from app.services.search_client import get_search_client, SearchResult
from app.services.firecrawl_client import get_firecrawl_client, ScrapedContent
from app.models.linkedin import LinkedInPost


class LinkedInClient:
    """Client for searching and scraping LinkedIn posts."""
    
    # Industry-specific keywords and search terms
    INDUSTRY_KEYWORDS = {
        "SaaS": ["SaaS", "software as a service", "cloud software", "subscription software", "B2B software"],
        "FinTech": ["FinTech", "financial technology", "fintech", "banking technology", "payments", "cryptocurrency"],
        "Healthcare": ["healthcare", "health tech", "medical technology", "healthcare innovation", "digital health"],
        "E-commerce": ["e-commerce", "ecommerce", "online retail", "digital commerce", "online shopping"],
        "AI/ML": ["artificial intelligence", "machine learning", "AI", "ML", "deep learning", "neural networks"],
        "Marketing": ["marketing", "digital marketing", "content marketing", "growth marketing", "B2B marketing"],
        "Real Estate": ["real estate", "property", "real estate tech", "proptech", "real estate investment"],
        "Education": ["education", "edtech", "online learning", "educational technology", "e-learning"],
        "Cybersecurity": ["cybersecurity", "cyber security", "information security", "data security", "network security"],
        "Biotech": ["biotech", "biotechnology", "life sciences", "pharmaceutical", "biomedical"],
        "Gaming": ["gaming", "video games", "game development", "esports", "gaming industry"],
        "Energy": ["energy", "renewable energy", "solar", "wind energy", "clean energy", "sustainability"],
    }
    
    def __init__(self):
        self.search_client = get_search_client()
        self.firecrawl_client = get_firecrawl_client()
    
    def _build_industry_query(self, base_query: str, industry: Optional[str] = None) -> str:
        """Build a search query with industry-specific terms."""
        if not industry:
            return base_query
        
        industry_lower = industry.lower()
        
        # Check if industry is in our keyword mapping
        if industry_lower in [k.lower() for k in self.INDUSTRY_KEYWORDS.keys()]:
            # Get the canonical industry name
            canonical_industry = next(
                (k for k in self.INDUSTRY_KEYWORDS.keys() if k.lower() == industry_lower),
                industry
            )
            keywords = self.INDUSTRY_KEYWORDS[canonical_industry]
            # Add industry keywords to query
            industry_terms = " OR ".join(f'"{kw}"' for kw in keywords[:3])  # Use top 3 keywords
            return f'{base_query} ({industry_terms})'
        else:
            # Use industry name directly
            return f'{base_query} "{industry}"'
    
    def _is_industry_relevant(
        self,
        post: LinkedInPost,
        industry: Optional[str] = None,
        filter_by_company: bool = False
    ) -> bool:
        """Check if a post is relevant to the target industry."""
        if not industry:
            return True
        
        industry_lower = industry.lower()
        content_lower = post.content.lower()
        company_lower = (post.author_company or "").lower()
        title_lower = (post.author_title or "").lower()
        
        # Get industry keywords
        if industry_lower in [k.lower() for k in self.INDUSTRY_KEYWORDS.keys()]:
            canonical_industry = next(
                (k for k in self.INDUSTRY_KEYWORDS.keys() if k.lower() == industry_lower),
                industry
            )
            keywords = [kw.lower() for kw in self.INDUSTRY_KEYWORDS[canonical_industry]]
        else:
            keywords = [industry_lower]
        
        # Check if content contains industry keywords
        content_match = any(keyword in content_lower for keyword in keywords)
        
        # Check if company/title matches (if filtering by company)
        company_match = False
        if filter_by_company:
            company_match = any(keyword in company_lower or keyword in title_lower for keyword in keywords)
            return company_match  # If filtering by company, must match company/title
        else:
            # If not filtering by company, content match is enough
            return content_match
    
    def _extract_post_id_from_url(self, url: str) -> Optional[str]:
        """Extract LinkedIn post ID from URL."""
        # LinkedIn post URLs can be in various formats:
        # - https://www.linkedin.com/posts/username_activity-1234567890-abcdef
        # - https://www.linkedin.com/feed/update/urn:li:activity:1234567890
        # - https://www.linkedin.com/posts/topic_activity-1234567890
        
        # Try to extract from activity ID
        activity_match = re.search(r'activity[_-](\d+)', url)
        if activity_match:
            return activity_match.group(1)
        
        # Try to extract from URN
        urn_match = re.search(r'urn:li:activity:(\d+)', url)
        if urn_match:
            return urn_match.group(1)
        
        # Fallback: use URL hash
        return url.split('/')[-1].split('?')[0] if '/' in url else None
    
    def _extract_author_info(self, content: str, url: str) -> Dict[str, Optional[str]]:
        """Extract author information from scraped content."""
        author_info = {
            "author_name": None,
            "author_profile_url": None,
            "author_title": None,
            "author_company": None,
        }
        
        # Try multiple patterns to extract author info
        # Pattern 1: "Name | Title at Company"
        name_pattern1 = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[|•]\s*([^|•\n]+)'
        match = re.search(name_pattern1, content[:1000])
        if match:
            author_info["author_name"] = match.group(1).strip()
            title_company = match.group(2).strip()
            if " at " in title_company.lower():
                parts = re.split(r'\s+at\s+', title_company, flags=re.IGNORECASE)
                author_info["author_title"] = parts[0].strip()
                author_info["author_company"] = parts[1].strip() if len(parts) > 1 else None
            elif " @ " in title_company:
                parts = title_company.split(" @ ", 1)
                author_info["author_title"] = parts[0].strip()
                author_info["author_company"] = parts[1].strip() if len(parts) > 1 else None
            else:
                author_info["author_title"] = title_company
        
        # Pattern 2: Extract from URL if available
        # LinkedIn post URLs sometimes contain username: linkedin.com/posts/username_activity-...
        url_match = re.search(r'linkedin\.com/posts/([^_/]+)', url)
        if url_match and not author_info["author_name"]:
            # Username might be in URL, but we can't get full name from it
            pass
        
        # Pattern 3: Try to extract profile URL from links in content
        profile_patterns = [
            r'linkedin\.com/in/([a-zA-Z0-9\-]+)',
            r'linkedin\.com/feed/update/.*?/([a-zA-Z0-9\-]+)',
        ]
        for pattern in profile_patterns:
            profile_match = re.search(pattern, content)
            if profile_match:
                username = profile_match.group(1)
                author_info["author_profile_url"] = f"https://www.linkedin.com/in/{username}"
                break
        
        # Pattern 4: Look for "Title at Company" pattern even without name
        if not author_info["author_title"]:
            title_company_pattern = r'([A-Z][^|•\n]{10,50})\s+(?:at|@)\s+([A-Z][^|•\n]{5,50})'
            match = re.search(title_company_pattern, content[:1000])
            if match:
                author_info["author_title"] = match.group(1).strip()
                author_info["author_company"] = match.group(2).strip()
        
        return author_info
    
    def _extract_author_info_from_snippet(self, snippet: str, url: str) -> Dict[str, Optional[str]]:
        """Extract author information from Google Search snippet/title."""
        author_info = {
            "author_name": None,
            "author_profile_url": None,
            "author_title": None,
            "author_company": None,
        }
        
        if not snippet:
            return author_info
        
        # Pattern 1: "by Author Name" or "by Author Name and Author Name" (handle multiple authors)
        by_pattern = r'by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+(?:\s+and\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)?)'
        match = re.search(by_pattern, snippet, re.IGNORECASE)
        if match:
            # Get the full author string (may include "and Second Author")
            authors_str = match.group(1).strip()
            # For now, take the first author (can be enhanced to handle multiple)
            if " and " in authors_str:
                authors = authors_str.split(" and ", 1)
                author_info["author_name"] = authors[0].strip()
            else:
                author_info["author_name"] = authors_str
        
        # Pattern 1b: Look for author names after dates (e.g., "Mar 17, 2025 ... by Author Name")
        # This handles cases where "by" might be in the snippet but not immediately visible
        if not author_info["author_name"]:
            # Look for patterns like "... Author Name" after date patterns
            after_date_pattern = r'(?:\.\.\.|…)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s+and\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)?'
            match = re.search(after_date_pattern, snippet)
            if match:
                potential_author = match.group(1).strip()
                # Validate it looks like a name (2-4 words, capitalized)
                words = potential_author.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                    author_info["author_name"] = potential_author
        
        # Pattern 2: "View profile for Author Name" (common in LinkedIn snippets)
        profile_pattern = r'View profile for\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)+)'
        match = re.search(profile_pattern, snippet, re.IGNORECASE)
        if match:
            author_name = match.group(1).strip()
            # Clean up duplicates (e.g., "Bart Banfield. Bart Banfield." -> "Bart Banfield")
            author_name = re.sub(r'^(.+?)(\s+\1)+$', r'\1', author_name)
            if not author_info["author_name"]:
                author_info["author_name"] = author_name
        
        # Pattern 3: "Author Name | Title at Company" or "Author Name. Author Name." (handle duplicates)
        name_title_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)+)\s*[|•]\s*([^|•\n]+)'
        match = re.search(name_title_pattern, snippet)
        if match and not author_info["author_name"]:
            author_name = match.group(1).strip()
            # Clean up duplicates (e.g., "Bart Banfield. Bart Banfield." -> "Bart Banfield")
            author_name = re.sub(r'^(.+?)(\s+\1)+$', r'\1', author_name)
            author_info["author_name"] = author_name
            title_company = match.group(2).strip()
            if " at " in title_company.lower():
                parts = re.split(r'\s+at\s+', title_company, flags=re.IGNORECASE)
                author_info["author_title"] = parts[0].strip()
                author_info["author_company"] = parts[1].strip() if len(parts) > 1 else None
            else:
                author_info["author_title"] = title_company
        
        # Pattern 3b: Handle duplicate author names in snippet (e.g., "Bart Banfield. Bart Banfield.")
        if author_info["author_name"]:
            # Remove duplicate patterns like "Name. Name." or "Name Name"
            author_info["author_name"] = re.sub(r'^(.+?)(\s+\1)+$', r'\1', author_info["author_name"])
            author_info["author_name"] = re.sub(r'^(.+?)\.\s+\1\.?$', r'\1', author_info["author_name"])
        
        # Pattern 4: Extract from URL if it contains profile info
        profile_match = re.search(r'linkedin\.com/in/([a-zA-Z0-9\-]+)', url)
        if profile_match:
            author_info["author_profile_url"] = f"https://www.linkedin.com/in/{profile_match.group(1)}"
        
        # Pattern 5: Look for "Author Name, Title" or "Author Name (Title)" patterns
        if not author_info["author_name"]:
            name_title_comma = r'([A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)+),\s*([^,\.]+)'
            match = re.search(name_title_comma, snippet)
            if match:
                author_info["author_name"] = match.group(1).strip()
                potential_title = match.group(2).strip()
                if " at " in potential_title.lower():
                    parts = re.split(r'\s+at\s+', potential_title, flags=re.IGNORECASE)
                    author_info["author_title"] = parts[0].strip()
                    author_info["author_company"] = parts[1].strip() if len(parts) > 1 else None
                else:
                    author_info["author_title"] = potential_title
        
        return author_info
    
    def _extract_engagement_from_snippet(self, snippet: str) -> Dict[str, int]:
        """Try to extract engagement metrics from Google Search snippet (if mentioned)."""
        metrics = {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "reactions": 0,
        }
        
        if not snippet:
            return metrics
        
        # Look for engagement numbers in snippet (e.g., "123 likes", "45 comments", "12 shares")
        # Pattern 1: "123 likes" or "123 👍"
        likes_patterns = [
            r'(\d+)\s*(?:like|👍|reaction)',  # "123 likes" or "123 👍"
            r'(\d+)\s*Like',  # "123 Like"
            r'Like[:\s]+(\d+)',  # "Like: 123"
        ]
        for pattern in likes_patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                try:
                    metrics["likes"] = max(metrics["likes"], int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # Pattern 2: "45 comments" or "45 Comments"
        comments_patterns = [
            r'(\d+)\s*comment',  # "45 comments"
            r'(\d+)\s*Comment',  # "45 Comment"
            r'Comment[:\s]+(\d+)',  # "Comment: 45"
        ]
        for pattern in comments_patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                try:
                    metrics["comments"] = max(metrics["comments"], int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # Pattern 3: "12 shares" or "12 Shares"
        shares_patterns = [
            r'(\d+)\s*share',  # "12 shares"
            r'(\d+)\s*Share',  # "12 Share"
            r'Share[:\s]+(\d+)',  # "Share: 12"
        ]
        for pattern in shares_patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                try:
                    metrics["shares"] = max(metrics["shares"], int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # Pattern 4: Look for engagement numbers in common formats
        # Sometimes snippets show "123 45 12" where numbers might be likes, comments, shares
        # This is a fallback - not always accurate
        engagement_numbers = re.findall(r'\b(\d{1,6})\b', snippet[:200])  # Look in first 200 chars
        if engagement_numbers and len(engagement_numbers) >= 2:
            # If we found numbers but no specific metrics, try to infer
            # (This is a fallback - not always accurate)
            if metrics["likes"] == 0 and metrics["comments"] == 0:
                try:
                    # Assume first larger number might be likes if it's reasonable
                    potential_likes = int(engagement_numbers[0])
                    if 10 <= potential_likes <= 100000:  # Reasonable range
                        metrics["likes"] = potential_likes
                except (ValueError, IndexError):
                    pass
        
        return metrics
    
    def _extract_engagement_metrics(self, content: str) -> Dict[str, int]:
        """Extract engagement metrics from scraped content."""
        metrics = {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "reactions": 0,
        }
        
        # Enhanced patterns for engagement metrics
        # Look for patterns like "123 likes", "45 comments", "12 shares", etc.
        # Also handle formats like "123" followed by "Like", "Comment", etc.
        
        # Likes - multiple patterns
        likes_patterns = [
            r'(\d+)\s*(?:like|👍|reaction)',  # "123 likes" or "123 👍"
            r'(\d+)\s*Like',  # "123 Like"
            r'Like[:\s]+(\d+)',  # "Like: 123"
        ]
        for pattern in likes_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    metrics["likes"] = max(metrics["likes"], int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # Comments - multiple patterns
        comments_patterns = [
            r'(\d+)\s*comment',  # "45 comments"
            r'(\d+)\s*Comment',  # "45 Comment"
            r'Comment[:\s]+(\d+)',  # "Comment: 45"
        ]
        for pattern in comments_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    metrics["comments"] = max(metrics["comments"], int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # Shares - multiple patterns
        shares_patterns = [
            r'(\d+)\s*share',  # "12 shares"
            r'(\d+)\s*Share',  # "12 Share"
            r'Share[:\s]+(\d+)',  # "Share: 12"
        ]
        for pattern in shares_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    metrics["shares"] = max(metrics["shares"], int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # Try to find engagement numbers in common LinkedIn UI patterns
        # Pattern: "123 45 12" where numbers might be likes, comments, shares
        engagement_numbers = re.findall(r'\b(\d{1,6})\b', content[:500])
        if engagement_numbers and len(engagement_numbers) >= 2:
            # If we found numbers but no specific metrics, try to infer
            # (This is a fallback - not always accurate)
            if metrics["likes"] == 0 and metrics["comments"] == 0:
                try:
                    # Assume first number might be likes if it's larger
                    potential_likes = int(engagement_numbers[0])
                    if potential_likes > 0:
                        metrics["likes"] = potential_likes
                except (ValueError, IndexError):
                    pass
        
        # Calculate total reactions (likes + other reactions)
        metrics["reactions"] = metrics["likes"]
        
        return metrics
    
    def _calculate_engagement_score(
        self,
        likes: int,
        comments: int,
        shares: int,
        reactions: int = 0
    ) -> float:
        """Calculate engagement score for a post."""
        # Weighted scoring: comments and shares are worth more than likes
        score = (
            likes * 1.0 +
            comments * 3.0 +
            shares * 5.0 +
            reactions * 1.0
        )
        return round(score, 2)
    
    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from post content."""
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, content)
        return list(set(hashtags))  # Remove duplicates
    
    def _extract_mentions(self, content: str) -> List[str]:
        """Extract @mentions from post content."""
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, content)
        return list(set(mentions))  # Remove duplicates
    
    def _parse_linkedin_post(
        self,
        url: str,
        scraped: ScrapedContent,
        is_connection: Optional[bool] = None
    ) -> LinkedInPost:
        """Parse scraped LinkedIn content into a LinkedInPost model."""
        post_id = self._extract_post_id_from_url(url) or f"post_{hash(url)}"
        
        # Extract information from scraped content
        author_info = self._extract_author_info(scraped.content, url)
        engagement_metrics = self._extract_engagement_metrics(scraped.content)
        engagement_score = self._calculate_engagement_score(
            engagement_metrics["likes"],
            engagement_metrics["comments"],
            engagement_metrics["shares"],
            engagement_metrics["reactions"]
        )
        
        # Extract post content (clean up markdown and LinkedIn UI elements)
        post_content = scraped.content
        
        # Remove LinkedIn UI elements and navigation
        post_content = re.sub(r'Agree & Join LinkedIn.*?Cookie Policy.*?', '', post_content, flags=re.DOTALL)
        post_content = re.sub(r'Skip to main content.*?\]', '', post_content)
        post_content = re.sub(r'Report this post.*?\]', '', post_content)
        post_content = re.sub(r'\[Sign up.*?\]', '', post_content)
        post_content = re.sub(r'\[Like\].*?\[Comment\].*?', '', post_content)
        post_content = re.sub(r'\[Skip to.*?\]', '', post_content)
        post_content = re.sub(r'\[.*?\]\(https?://.*?\)', '', post_content)  # Remove markdown links
        post_content = re.sub(r'https?://[^\s]+', '', post_content)  # Remove plain URLs
        post_content = re.sub(r'```.*?```', '', post_content, flags=re.DOTALL)  # Remove code blocks
        
        # Remove excessive markdown formatting
        post_content = re.sub(r'#{1,6}\s+', '', post_content)  # Remove headers
        post_content = re.sub(r'\*\*([^*]+)\*\*', r'\1', post_content)  # Remove bold
        post_content = re.sub(r'\*([^*]+)\*', r'\1', post_content)  # Remove italic
        post_content = re.sub(r'`([^`]+)`', r'\1', post_content)  # Remove code formatting
        
        # Clean up whitespace
        post_content = re.sub(r'\n{3,}', '\n\n', post_content)  # Max 2 newlines
        post_content = re.sub(r' {2,}', ' ', post_content)  # Multiple spaces to single
        post_content = post_content.strip()
        
        # Extract hashtags and mentions
        hashtags = self._extract_hashtags(post_content)
        mentions = self._extract_mentions(post_content)
        
        # Extract media URLs from links
        media_urls = []
        if scraped.links:
            for link in scraped.links:
                if any(ext in link.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov']):
                    media_urls.append(link)
        
        return LinkedInPost(
            post_id=post_id,
            post_url=url,
            author_name=author_info["author_name"],
            author_profile_url=author_info["author_profile_url"],
            author_title=author_info["author_title"],
            author_company=author_info["author_company"],
            content=post_content[:5000],  # Limit content length
            engagement_metrics=engagement_metrics,
            engagement_score=engagement_score,
            post_date=None,  # Would need to parse from content
            is_connection=is_connection,
            hashtags=hashtags if hashtags else None,
            mentions=mentions if mentions else None,
            media_urls=media_urls if media_urls else None,
            scraped_at=datetime.utcnow().isoformat() + "Z",
            metadata={
                "title": scraped.title,
                "scraped_url": url,
            }
        )
    
    def search_posts(
        self,
        query: str,
        industry: Optional[str] = None,
        include_connections: bool = True,
        include_non_connections: bool = True,
        max_results: int = 20,
        min_engagement_score: Optional[float] = None,
        sort_by: str = "engagement",
        filter_by_company: bool = False,
    ) -> List[LinkedInPost]:
        """
        Search for LinkedIn posts matching the query.
        
        Args:
            query: Search query
            industry: Target industry (e.g., 'SaaS', 'FinTech', 'Healthcare')
            include_connections: Include posts from connections
            include_non_connections: Include posts from non-connections
            max_results: Maximum number of posts to return
            min_engagement_score: Minimum engagement score filter
            sort_by: Sort order ('engagement', 'recent', 'relevance')
            filter_by_company: Filter to only companies in target industry
            
        Returns:
            List of LinkedInPost objects
        """
        # Build optimized Google search query for LinkedIn posts
        # Best practices: Use multiple query patterns for better results
        query_terms = query.strip()
        
        # Try different LinkedIn post URL patterns for better coverage
        # LinkedIn posts can be at: /posts/, /feed/update/, /activity/
        # Using OR operator to search across different LinkedIn post URL patterns
        base_query = f'site:linkedin.com ("/posts/" OR "/feed/update/" OR "/activity/") "{query_terms}"'
        
        # Build industry-enhanced query (this will add industry terms)
        linkedin_query = self._build_industry_query(base_query, industry)
        
        if industry:
            print(f"  [LinkedIn] Industry targeting: {industry}", flush=True)
        print(f"  [LinkedIn] Searching with query: {linkedin_query}", flush=True)
        
        # Search for LinkedIn post URLs with retry logic
        search_results = []
        try:
            # Try the optimized query first
            search_results = self.search_client.search(
                query=linkedin_query,
                num_results=min(max_results * 3, 50),  # Get more URLs to account for scraping failures
                max_retries=3,  # Enable retry logic
            )
            print(f"  [LinkedIn] Found {len(search_results)} search results", flush=True)
            
            # If no results, try a simpler query pattern
            if len(search_results) == 0:
                print(f"  [LinkedIn] No results with complex query, trying simpler pattern...", flush=True)
                simple_query = f'site:linkedin.com/posts {query_terms}'
                search_results = self.search_client.search(
                    query=simple_query,
                    num_results=min(max_results * 3, 30),
                    max_retries=2,
                )
                print(f"  [LinkedIn] Simple query found {len(search_results)} results", flush=True)
                
        except Exception as e:
            error_msg = str(e)
            # Check for quota/rate limit errors
            if "quotaExceeded" in error_msg or "rateLimitExceeded" in error_msg:
                print(f"  [LinkedIn] ⚠️ Search quota/rate limit reached: {error_msg}", flush=True)
                print(f"  [LinkedIn] Continuing without LinkedIn post inspiration...", flush=True)
            else:
                print(f"  [LinkedIn] Search failed: {e}", flush=True)
            return []
        
        # Filter to only LinkedIn post URLs (multiple patterns) and preserve snippets/titles
        linkedin_urls = []
        url_to_snippet = {}  # Map URLs to their Google Search snippets for preview
        url_to_title = {}  # Map URLs to their Google Search titles for author extraction
        for result in search_results:
            url = result.link
            if any(pattern in url for pattern in [
                'linkedin.com/posts/',
                'linkedin.com/feed/update/',
                'linkedin.com/activity/',
            ]):
                linkedin_urls.append(url)
                # Store snippet and title for use as preview if scraping fails
                if result.snippet:
                    url_to_snippet[url] = result.snippet
                if result.title:
                    url_to_title[url] = result.title
        
        print(f"  [LinkedIn] Filtered to {len(linkedin_urls)} LinkedIn post URLs", flush=True)
        
        if not linkedin_urls:
            return []
        
        # HYBRID SCRAPING STRATEGY (Based on Research Best Practices)
        # Strategy: Scrape first post immediately (fast UX), then 2-3 more with progressive delays,
        # return URLs for the rest to avoid overwhelming LinkedIn's anti-bot systems
        
        posts = []
        successful_scrapes = 0
        failed_scrapes = 0
        urls_without_content = []  # Track URLs we found but couldn't scrape
        
        # Track which scraping approaches succeeded (for testing/optimization)
        scraping_stats = {
            "approach_1_success": 0,  # Basic v2 + auto proxy
            "approach_2_success": 0,  # Scroll actions
            "approach_3_success": 0,  # Extended wait + stealth
            "approach_4_success": 0,  # v1 fallback
            "total_attempts": 0,
            "failed_attempts": 0,
            "content_too_short": 0,
            "no_linkedin_indicators": 0,
        }
        
        # Track consecutive 403 errors to detect systematic blocking (circuit breaker pattern)
        consecutive_403s = 0
        max_consecutive_403s = 2  # Back to 2 - fail faster to avoid timeouts
        
        # Smart scraping limits based on research:
        # - Scrape first post immediately (no delay) for fast UX
        # - Scrape next 2-3 posts with moderate delays (5-10s)
        # - After that, return URLs only (don't waste time on likely failures)
        # INCREASED: Try to scrape more posts to get better success rate
        max_posts_to_scrape = min(3, max_results)  # Reduced to 3 to prevent timeouts while maintaining success rate
        
        # Determine which URLs to actually scrape vs just return
        urls_to_scrape = linkedin_urls[:max_posts_to_scrape]  # Try exact number to avoid timeout
        urls_to_return_only = linkedin_urls[max_posts_to_scrape * 2:]  # Return these as URLs
        
        print(f"  [LinkedIn] Hybrid strategy: Scraping {len(urls_to_scrape)} URLs, returning {len(urls_to_return_only)} as URLs only", flush=True)
        
        for i, url in enumerate(urls_to_scrape, 1):
            try:
                # AGGRESSIVE DELAY STRATEGY (Maximum delays for education queries to avoid blocking)
                # - First post: Longer delay (5-10s) especially for education queries
                # - Posts 2-3: Very long delays (12-20 seconds) - maximum patience
                # - Posts 4+: Skip to prevent timeout (we focus on quality over quantity)
                if i == 1:
                    # First post: longer delay, especially for education queries
                    base_delay = 8.0 if is_education_query else 5.0
                    delay = random.uniform(base_delay, base_delay + 5.0)
                    print(f"  [LinkedIn] Waiting {delay:.1f}s (initial delay for post {i})...", flush=True)
                    time.sleep(delay)
                elif i <= 3:
                    # Next 2 posts: very long delays (12-20 seconds) - maximum patience
                    base_delay = 15.0 if is_education_query else 12.0
                    delay = random.uniform(base_delay, base_delay + 8.0)
                    print(f"  [LinkedIn] Waiting {delay:.1f}s (moderate delay for post {i})...", flush=True)
                    time.sleep(delay)
                else:
                    # Posts 4+: Skip to prevent timeout (focus on first 3 for better success rate)
                    print(f"  [LinkedIn] Skipping post {i} to prevent timeout (focusing on first 3 posts)...", flush=True)
                    urls_without_content.append(url)
                    continue
                
                print(f"  [LinkedIn] Scraping {i}/{len(urls_to_scrape)}: {url[:80]}...", flush=True)
                
                # Use Firecrawl v2 with enhanced anti-bot options for LinkedIn
                # Strategy: Try multiple approaches with increasing complexity
                scraped = None
                last_error = None
                
                # MULTI-STRATEGY APPROACH: Try multiple techniques with increasing complexity
                # This maximizes success rate by trying different methods
                
                scraping_stats["total_attempts"] += 1
                approach_used = None
                
                # Detect if this is an education-related query (more likely to be blocked)
                # Education queries need more aggressive approach
                is_education_query = any(term in query_terms.lower() for term in [
                    "education", "enrollment", "admissions", "k-12", "school", 
                    "neurodivergent", "edtech", "post-secondary", "referral networks"
                ])
                
                # Approach 1: Try v2 with proxy (stealth for education queries, auto for others)
                try:
                    # Use stealth proxy directly for education queries (more aggressive)
                    # Use auto proxy for other queries (cost-effective)
                    proxy_type = "stealth" if is_education_query else "auto"
                    if is_education_query:
                        print(f"  [LinkedIn] Using stealth proxy for education query (more aggressive)...", flush=True)
                    
                    scraped = self.firecrawl_client.scrape_url(
                        url=url,
                        formats=["markdown"],
                        only_main_content=True,
                        exclude_tags=["script", "style", "nav", "footer", "header", "aside", "button", "form", "div[class*='cookie']", "div[class*='popup']"],
                        wait_for=8000 if is_education_query else 7000,  # Longer wait for education queries
                        use_v2=True,  # Use v2 API for better anti-bot features
                        proxy=proxy_type  # Stealth for education, auto for others
                    )
                    approach_used = "approach_1"
                    scraping_stats["approach_1_success"] += 1
                    print(f"  [LinkedIn] ✅ Successfully scraped with Approach 1 (v2 + auto proxy)", flush=True)
                except Exception as e1:
                    last_error = e1
                    print(f"  [LinkedIn] ⚠️ Approach 1 failed: {str(e1)[:100]}", flush=True)
                    
                    # Approach 2: Try with scroll action to trigger lazy loading
                    try:
                        print(f"  [LinkedIn] Retrying with scroll action (triggers lazy loading)...", flush=True)
                        actions = [
                            {"type": "wait", "milliseconds": 3000},  # Initial wait for page load
                            {"type": "scroll", "direction": "down"},  # Scroll to trigger lazy loading
                            {"type": "wait", "milliseconds": 3000},  # Wait after scroll for content
                            {"type": "scroll", "direction": "up"},  # Scroll back up
                            {"type": "wait", "milliseconds": 2000},  # Final wait
                        ]
                        scraped = self.firecrawl_client.scrape_url(
                            url=url,
                            formats=["markdown"],
                            only_main_content=True,
                            exclude_tags=["script", "style", "nav", "footer", "header", "aside", "button", "form"],
                            wait_for=12000,  # Longer wait (increased further)
                            use_v2=True,
                            actions=actions,
                            proxy="auto"  # Auto proxy (tries basic, then stealth)
                        )
                        approach_used = "approach_2"
                        scraping_stats["approach_2_success"] += 1
                        print(f"  [LinkedIn] ✅ Successfully scraped with Approach 2 (scroll actions)", flush=True)
                    except Exception as e2:
                        last_error = e2
                        print(f"  [LinkedIn] ⚠️ Approach 2 failed: {str(e2)[:100]}", flush=True)
                        
                        # Approach 3: Try with even longer wait (some posts need more time)
                        # Add delay before retry
                        time.sleep(random.uniform(3.0, 5.0))  # Delay between approaches
                        try:
                            print(f"  [LinkedIn] Retrying with extended wait time (15s) and stealth proxy...", flush=True)
                            scraped = self.firecrawl_client.scrape_url(
                                url=url,
                                formats=["markdown"],
                                only_main_content=True,
                                exclude_tags=["script", "style", "nav", "footer", "header", "aside", "button", "form"],
                                wait_for=15000,  # Very long wait (15 seconds, increased further)
                                use_v2=True,
                                proxy="stealth"  # Force stealth proxy (last resort - costs 5 credits)
                            )
                            approach_used = "approach_3"
                            scraping_stats["approach_3_success"] += 1
                            print(f"  [LinkedIn] ✅ Successfully scraped with Approach 3 (extended wait + stealth)", flush=True)
                        except Exception as e3:
                            last_error = e3
                            print(f"  [LinkedIn] ⚠️ Approach 3 failed: {str(e3)[:100]}", flush=True)
                            
                            # Approach 4: Fallback to v1 API (sometimes works when v2 doesn't)
                            # Add delay before final retry
                            time.sleep(random.uniform(4.0, 6.0))  # Longer delay before final attempt
                            try:
                                print(f"  [LinkedIn] Retrying with v1 API as final fallback...", flush=True)
                                scraped = self.firecrawl_client.scrape_url(
                                    url=url,
                                    formats=["markdown"],
                                    only_main_content=True,
                                    exclude_tags=["script", "style", "nav", "footer", "header", "aside", "button", "form"],
                                    wait_for=5000,
                                    use_v2=False  # Fallback to v1
                                )
                                approach_used = "approach_4"
                                scraping_stats["approach_4_success"] += 1
                                print(f"  [LinkedIn] ✅ Successfully scraped with Approach 4 (v1 fallback)", flush=True)
                            except Exception as e4:
                                last_error = e4
                                print(f"  [LinkedIn] ❌ All 4 scraping approaches failed", flush=True)
                                raise last_error
                
                if not scraped:
                    raise Exception(f"Failed to scrape after all retry attempts: {str(last_error)}")
                
                # Reset 403 counter on success
                consecutive_403s = 0
                
                # Validate that we got meaningful content
                # LinkedIn posts should have substantial content
                content_length = len(scraped.content.strip()) if scraped.content else 0
                if not scraped.content or content_length < 100:
                    scraping_stats["content_too_short"] += 1
                    print(f"  [LinkedIn] ⚠️ Skipping {url}: content too short ({content_length} chars, minimum 100)", flush=True)
                    failed_scrapes += 1
                    urls_without_content.append(url)
                    continue
                
                # Check if content looks like a LinkedIn post (has engagement indicators or post-like structure)
                content_lower = scraped.content.lower()
                has_linkedin_indicators = any(indicator in content_lower for indicator in [
                    'like', 'comment', 'share', 'reaction', 'follow', 'connection',
                    'linkedin', 'post', 'update', 'activity', 'view', 'profile'
                ])
                
                if not has_linkedin_indicators and content_length < 200:
                    scraping_stats["no_linkedin_indicators"] += 1
                    print(f"  [LinkedIn] ⚠️ Content doesn't look like a LinkedIn post ({content_length} chars, no LinkedIn indicators)", flush=True)
                    # Still try to parse it - might be valid content without indicators
                
                # Parse into LinkedInPost
                post = self._parse_linkedin_post(url, scraped)
                
                # Apply filters
                if min_engagement_score and post.engagement_score:
                    if post.engagement_score < min_engagement_score:
                        print(f"  [LinkedIn] Post {post.post_id} filtered out (score {post.engagement_score} < {min_engagement_score})", flush=True)
                        failed_scrapes += 1
                        urls_without_content.append(url)
                        continue
                
                # Apply industry filter
                if industry and not self._is_industry_relevant(post, industry, filter_by_company):
                    print(f"  [LinkedIn] Post {post.post_id} filtered out (not relevant to {industry})", flush=True)
                    failed_scrapes += 1
                    urls_without_content.append(url)
                    continue
                
                posts.append(post)
                successful_scrapes += 1
                print(f"  [LinkedIn] ✅ Successfully scraped post {post.post_id} (engagement: {post.engagement_score})", flush=True)
                
                # Stop if we have enough posts
                if len(posts) >= max_posts_to_scrape:
                    print(f"  [LinkedIn] Reached target of {max_posts_to_scrape} scraped posts, stopping scraping", flush=True)
                    break
                    
            except Exception as e:
                error_msg = str(e)
                
                # Detect 403 errors specifically
                is_403_error = "403" in error_msg or "Forbidden" in error_msg
                
                if is_403_error:
                    consecutive_403s += 1
                    # EXPONENTIAL BACKOFF for 403 errors (based on research)
                    backoff_delay = (2 ** consecutive_403s) + random.uniform(2, 5)  # 2^1=4-7s, 2^2=6-9s, etc. (increased base)
                    
                    if consecutive_403s >= max_consecutive_403s:
                        print(f"  [LinkedIn] ⚠️ Circuit breaker triggered: {consecutive_403s} consecutive 403 errors. "
                              f"LinkedIn is blocking Firecrawl. Stopping scrape attempts. "
                              f"Will return remaining URLs for manual viewing.", flush=True)
                        # Log current stats before breaking
                        print(f"  [LinkedIn] Stats before circuit breaker: {scraping_stats}", flush=True)
                        # Add all remaining URLs to return list
                        remaining_urls = urls_to_scrape[i-1:] + urls_to_return_only
                        urls_without_content.extend(remaining_urls)
                        break
                
                    print(f"  [LinkedIn] ❌ 403 error ({consecutive_403s}/{max_consecutive_403s}). "
                          f"Exponential backoff: waiting {backoff_delay:.1f}s...", flush=True)
                    time.sleep(backoff_delay)
                else:
                    # Other errors: shorter delay
                    print(f"  [LinkedIn] ❌ Failed to scrape {url}: {error_msg[:150]}", flush=True)
                    time.sleep(random.uniform(2.0, 4.0))
                
                scraping_stats["failed_attempts"] += 1
                failed_scrapes += 1
                urls_without_content.append(url)
                continue
        
        # Calculate success rate and prepare metadata
        total_attempts = scraping_stats["total_attempts"]
        success_rate = (successful_scrapes / total_attempts * 100) if total_attempts > 0 else 0
        
        print(f"  [LinkedIn] Scraping complete: {successful_scrapes} successful, {failed_scrapes} failed", flush=True)
        print(f"  [LinkedIn] Success rate: {success_rate:.1f}% ({successful_scrapes}/{total_attempts})", flush=True)
        print(f"  [LinkedIn] Scraping stats: {scraping_stats}", flush=True)
        
        # Calculate approach success rates
        if total_attempts > 0:
            approach_1_rate = (scraping_stats["approach_1_success"] / total_attempts * 100) if total_attempts > 0 else 0
            approach_2_rate = (scraping_stats["approach_2_success"] / total_attempts * 100) if total_attempts > 0 else 0
            approach_3_rate = (scraping_stats["approach_3_success"] / total_attempts * 100) if total_attempts > 0 else 0
            approach_4_rate = (scraping_stats["approach_4_success"] / total_attempts * 100) if total_attempts > 0 else 0
            print(f"  [LinkedIn] Approach success rates: 1={approach_1_rate:.1f}%, 2={approach_2_rate:.1f}%, 3={approach_3_rate:.1f}%, 4={approach_4_rate:.1f}%", flush=True)
        
        # Warn if we got mostly 403 errors
        if failed_scrapes > 0 and successful_scrapes == 0:
            print(f"  [LinkedIn] ⚠️ Warning: All scraping attempts failed. "
                  f"This may indicate Firecrawl API issues or LinkedIn blocking. "
                  f"Check your FIRECRAWL_API_KEY and Firecrawl account status.", flush=True)
        
        # Store stats in metadata for return
        scraping_metadata = {
            "scraping_stats": scraping_stats,
            "success_rate": round(success_rate, 1),
            "total_attempts": total_attempts,
            "successful_scrapes": successful_scrapes,
            "failed_scrapes": failed_scrapes,
        }
        
        # Add URLs that were meant to be returned only (not scraped)
        urls_without_content.extend(urls_to_return_only)
        
        # Create minimal post objects from URLs we found but couldn't scrape
        # This ensures we always return at least the URLs even if scraping fails
        # Use Google Search snippets as preview when available
        if urls_without_content and len(posts) < max_results:
            print(f"  [LinkedIn] Creating minimal post objects for {len(urls_without_content)} URLs (scraping failed but URLs found via Google Search)...", flush=True)
            
            # Use pre-stored snippets from Google Search results for better preview
            # Try to extract author info from Google Search result titles/snippets
            for url in urls_without_content[:max_results - len(posts)]:
                # Extract post ID from URL
                post_id = self._extract_post_id_from_url(url) or f"post_{hash(url) % 10000000000}"
                
                # Use Google snippet as preview if available
                snippet = url_to_snippet.get(url, "")
                title = url_to_title.get(url, "")
                content_preview = snippet if snippet else f"[Content could not be scraped. View original post: {url}]"
                
                # Try to extract author info from Google Search result title/snippet
                # Google Search results often have format: "Author Name | Title at Company" or "Post Title by Author Name"
                # Combine title and snippet for better extraction
                combined_text = f"{title} {snippet}".strip()
                author_info_from_snippet = self._extract_author_info_from_snippet(combined_text, url)
                
                # Try to extract basic engagement info from snippet (if mentioned)
                engagement_from_snippet = self._extract_engagement_from_snippet(snippet)
                
                # Create minimal LinkedInPost with URL and snippet preview
                minimal_post = LinkedInPost(
                    post_id=str(post_id),
                    post_url=url,
                    author_name=author_info_from_snippet.get("author_name"),
                    author_title=author_info_from_snippet.get("author_title"),
                    author_company=author_info_from_snippet.get("author_company"),
                    author_profile_url=author_info_from_snippet.get("author_profile_url"),
                    content=content_preview,
                    engagement_metrics=engagement_from_snippet,
                    engagement_score=self._calculate_engagement_score(
                        engagement_from_snippet.get("likes", 0),
                        engagement_from_snippet.get("comments", 0),
                        engagement_from_snippet.get("shares", 0),
                        engagement_from_snippet.get("reactions", 0)
                    ) if any(engagement_from_snippet.values()) else None,
                    scraped_at=datetime.utcnow().isoformat() + "Z",
                    metadata={
                        "scrape_failed": True,
                        "has_google_snippet": bool(snippet),
                        "source": "google_search_snippet",
                        "note": "URL found via Google Custom Search. Content scraping was blocked by LinkedIn. "
                               "You can visit the URL manually to view the full post."
                    }
                )
                posts.append(minimal_post)
        
        # Sort posts
        if sort_by == "engagement":
            # Posts with engagement scores first, then minimal posts
            posts.sort(key=lambda p: (p.engagement_score or 0, p.metadata.get("scrape_failed", False) == False), reverse=True)
        elif sort_by == "recent":
            # Would need post_date for proper sorting
            posts.sort(key=lambda p: p.scraped_at, reverse=True)
        # 'relevance' is default order from search
        
        # Store scraping metadata in the first post's metadata (if any posts exist)
        # This allows the API to return stats without changing the return type
        if posts and scraping_metadata:
            if not posts[0].metadata:
                posts[0].metadata = {}
            posts[0].metadata["_scraping_metadata"] = scraping_metadata
        
        return posts[:max_results]
    
    def search_posts_by_topic(
        self,
        topics: List[str],
        industry: Optional[str] = None,
        max_results: int = 20,
        min_engagement_score: Optional[float] = None,
        filter_by_company: bool = False,
    ) -> List[LinkedInPost]:
        """
        Search for LinkedIn posts by topics/keywords.
        
        Args:
            topics: List of topics/keywords to search for
            industry: Target industry for filtering
            max_results: Maximum number of posts to return
            min_engagement_score: Minimum engagement score filter
            filter_by_company: Filter to only companies in target industry
            
        Returns:
            List of LinkedInPost objects
        """
        # Combine topics into search query
        query = " OR ".join(f'"{topic}"' for topic in topics)
        return self.search_posts(
            query=query,
            industry=industry,
            max_results=max_results,
            min_engagement_score=min_engagement_score,
            filter_by_company=filter_by_company,
        )
    
    def get_industry_insights(
        self,
        industry: str,
        query: Optional[str] = None,
        max_results: int = 30,
    ) -> Dict[str, Any]:
        """
        Get insights about what works in a specific industry.
        
        Analyzes high-engaging posts in the industry to identify patterns.
        
        Args:
            industry: Target industry
            query: Optional specific query (defaults to industry keywords)
            max_results: Number of posts to analyze
            
        Returns:
            Dictionary with industry insights
        """
        if not query:
            # Use industry keywords as query
            if industry.lower() in [k.lower() for k in self.INDUSTRY_KEYWORDS.keys()]:
                canonical_industry = next(
                    (k for k in self.INDUSTRY_KEYWORDS.keys() if k.lower() == industry.lower()),
                    industry
                )
                keywords = self.INDUSTRY_KEYWORDS[canonical_industry]
                query = " OR ".join(keywords[:3])
            else:
                query = industry
        
        # Search for posts in the industry
        posts = self.search_posts(
            query=query,
            industry=industry,
            max_results=max_results,
            min_engagement_score=50.0,  # Focus on high-engaging posts
            sort_by="engagement",
        )
        
        if not posts:
            return {
                "industry": industry,
                "total_posts_analyzed": 0,
                "insights": "No posts found for this industry",
            }
        
        # Analyze patterns
        all_hashtags = {}
        all_companies = {}
        all_titles = {}
        engagement_scores = []
        content_lengths = []
        
        for post in posts:
            # Hashtags
            if post.hashtags:
                for tag in post.hashtags:
                    all_hashtags[tag] = all_hashtags.get(tag, 0) + 1
            
            # Companies
            if post.author_company:
                all_companies[post.author_company] = all_companies.get(post.author_company, 0) + 1
            
            # Titles
            if post.author_title:
                all_titles[post.author_title] = all_titles.get(post.author_title, 0) + 1
            
            # Metrics
            if post.engagement_score:
                engagement_scores.append(post.engagement_score)
            content_lengths.append(len(post.content))
        
        # Calculate insights
        top_hashtags = sorted(all_hashtags.items(), key=lambda x: x[1], reverse=True)[:10]
        top_companies = sorted(all_companies.items(), key=lambda x: x[1], reverse=True)[:10]
        top_titles = sorted(all_titles.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "industry": industry,
            "total_posts_analyzed": len(posts),
            "average_engagement_score": round(sum(engagement_scores) / len(engagement_scores), 2) if engagement_scores else 0,
            "average_content_length": round(sum(content_lengths) / len(content_lengths), 0) if content_lengths else 0,
            "top_hashtags": [{"tag": tag, "count": count} for tag, count in top_hashtags],
            "top_companies": [{"company": company, "count": count} for company, count in top_companies],
            "top_job_titles": [{"title": title, "count": count} for title, count in top_titles],
            "engagement_range": {
                "min": min(engagement_scores) if engagement_scores else 0,
                "max": max(engagement_scores) if engagement_scores else 0,
            },
            "sample_posts": [
                {
                    "post_id": post.post_id,
                    "author": post.author_name,
                    "company": post.author_company,
                    "engagement_score": post.engagement_score,
                    "content_preview": post.content[:150] + "..." if len(post.content) > 150 else post.content,
                }
                for post in posts[:5]  # Top 5 posts
            ],
        }


# Singleton instance
_linkedin_client: Optional[LinkedInClient] = None


def get_linkedin_client() -> LinkedInClient:
    """Get or create LinkedIn client instance."""
    global _linkedin_client
    if _linkedin_client is None:
        _linkedin_client = LinkedInClient()
    return _linkedin_client

