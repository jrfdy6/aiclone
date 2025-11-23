"""
Perplexity API Client

Provides search and research capabilities using Perplexity API.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PerplexitySearchResult:
    """Result from Perplexity search."""
    answer: str
    sources: List[Dict[str, str]]
    query: str


class PerplexityClient:
    """Client for interacting with Perplexity API."""
    
    BASE_URL = "https://api.perplexity.ai"
    
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "PERPLEXITY_API_KEY environment variable not set. "
                "Get your API key from https://www.perplexity.ai/settings/api"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def search(
        self,
        query: str,
        model: str = "sonar",  # Default to base sonar for cost efficiency
        return_sources: bool = True,
        return_images: bool = False,
        return_related_questions: bool = False,
    ) -> PerplexitySearchResult:
        """
        Search using Perplexity API.
        
        Args:
            query: Search query
            model: Model to use (default: sonar for cost efficiency)
                   Options: 
                   - "sonar" (base, cheapest, good for research/summarization)
                   - "sonar-pro" (advanced, better for complex queries)
                   - "sonar-reasoning-pro" (best quality, highest cost)
            return_sources: Whether to return source URLs
            return_images: Whether to return images
            return_related_questions: Whether to return related questions
            
        Returns:
            PerplexitySearchResult with answer and sources
        """
        url = f"{self.BASE_URL}/chat/completions"
        
        # Perplexity API uses standard OpenAI format
        # Note: return_sources, return_images, return_related_questions are not direct parameters
        # Sources are returned in the response metadata
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Be precise and concise. Provide accurate, up-to-date information with sources."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "temperature": 0.2,
            "max_tokens": 4000,
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Extract answer
            choices = data.get("choices", [])
            if choices:
                answer = choices[0].get("message", {}).get("content", "")
            else:
                answer = data.get("message", {}).get("content", "") if "message" in data else ""
            
            # Extract sources
            sources = []
            if return_sources:
                # Perplexity returns citations in the response
                # Check multiple possible locations for citations
                citations = data.get("citations", [])
                
                # Also check in choices[0].message if available
                if not citations and choices:
                    message_data = choices[0].get("message", {})
                    citations = message_data.get("citations", [])
                
                # Check response metadata
                if not citations:
                    citations = data.get("response_metadata", {}).get("citations", [])
                
                for citation in citations:
                    if isinstance(citation, dict):
                        sources.append({
                            "url": citation.get("url", ""),
                            "title": citation.get("title", citation.get("name", "")),
                        })
                    elif isinstance(citation, str):
                        sources.append({"url": citation, "title": ""})
            
            return PerplexitySearchResult(
                answer=answer,
                sources=sources,
                query=query
            )
        except requests.exceptions.RequestException as e:
            raise Exception(f"Perplexity API request failed: {str(e)}")
    
    def research_topic(
        self,
        topic: str,
        num_results: int = 10,
        include_comparison: bool = True,
        model: Optional[str] = None,  # Allow override for specific research needs
    ) -> Dict[str, Any]:
        """
        Research a topic comprehensively.
        
        Args:
            topic: Topic to research
            num_results: Number of results to gather
            include_comparison: Whether to include comparison information
            model: Optional model override (default: uses instance default "sonar")
                   Use "sonar-pro" or "sonar-reasoning-pro" for deeper research
            
        Returns:
            Dictionary with research results
        """
        # Build comprehensive query
        query = f"Research {topic}. Provide a comprehensive overview including: "
        query += "1. Summary of the topic, 2. Top tools/products/services in this space, "
        query += "3. Key features and benefits of each, 4. Pricing information if available, "
        
        if include_comparison:
            query += "5. Comparison of different options. "
        
        query += f"Focus on the most relevant and current information. Provide {num_results} key items."
        
        # Use provided model or default to "sonar" for cost efficiency
        search_model = model if model is not None else "sonar"
        result = self.search(query, model=search_model, return_sources=True, return_related_questions=True)
        
        # Get related questions for deeper research
        # Note: Perplexity may return related questions in the response metadata
        related_queries = []
        
        return {
            "topic": topic,
            "summary": result.answer,
            "sources": result.sources,
            "related_questions": related_queries,
            "num_sources": len(result.sources),
        }


# Singleton instance
_perplexity_client: Optional[PerplexityClient] = None


def get_perplexity_client() -> PerplexityClient:
    """Get or create Perplexity client instance."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = PerplexityClient()
    return _perplexity_client

