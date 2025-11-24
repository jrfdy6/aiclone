"""
Multi-Format Content Generation Service
Generate content in various formats: blogs, emails, video scripts, white papers
"""
import logging
from typing import Dict, Any, Optional, List
from app.services.perplexity_client import get_perplexity_client

logger = logging.getLogger(__name__)


def generate_blog_post(topic: str, length: str = "medium", tone: str = "professional") -> Dict[str, Any]:
    """
    Generate a blog post on a given topic.
    
    length: "short" (500-800 words), "medium" (800-1500), "long" (1500+)
    tone: "professional", "casual", "authoritative", "conversational"
    """
    try:
        perplexity = get_perplexity_client()
        
        length_guidance = {
            "short": "500-800 words",
            "medium": "800-1500 words",
            "long": "1500+ words"
        }
        
        prompt = f"""
        Write a comprehensive blog post about: {topic}
        
        Requirements:
        - Length: {length_guidance.get(length, "800-1500 words")}
        - Tone: {tone}
        - Include: Introduction, main points with examples, conclusion with call-to-action
        - Format: Markdown with headers, bullet points, and paragraphs
        - SEO-friendly: Include natural keyword usage
        
        Generate the full blog post content.
        """
        
        response = perplexity.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.7
        )
        
        content = response.get("content", "")
        
        return {
            "format": "blog_post",
            "topic": topic,
            "content": content,
            "word_count": len(content.split()),
            "tone": tone,
            "length": length
        }
        
    except Exception as e:
        logger.error(f"Error generating blog post: {e}")
        return {}


def generate_email(
    subject: str,
    recipient_type: str = "prospect",
    purpose: str = "introduction",
    tone: str = "professional"
) -> Dict[str, Any]:
    """
    Generate an email.
    
    recipient_type: "prospect", "client", "partner"
    purpose: "introduction", "follow_up", "pitch", "thank_you"
    """
    try:
        perplexity = get_perplexity_client()
        
        prompt = f"""
        Write a professional email with the following specifications:
        
        Subject: {subject}
        Recipient Type: {recipient_type}
        Purpose: {purpose}
        Tone: {tone}
        
        Requirements:
        - Clear, concise message
        - Professional but friendly tone
        - Include a clear call-to-action
        - Length: 150-300 words
        - Format as email (Subject line, greeting, body, closing)
        
        Generate the complete email.
        """
        
        response = perplexity.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        
        content = response.get("content", "")
        
        return {
            "format": "email",
            "subject": subject,
            "content": content,
            "recipient_type": recipient_type,
            "purpose": purpose,
            "tone": tone
        }
        
    except Exception as e:
        logger.error(f"Error generating email: {e}")
        return {}


def generate_video_script(topic: str, duration: str = "short", style: str = "educational") -> Dict[str, Any]:
    """
    Generate a video script.
    
    duration: "short" (30-60s), "medium" (1-3min), "long" (3-5min)
    style: "educational", "entertaining", "promotional", "storytelling"
    """
    try:
        perplexity = get_perplexity_client()
        
        duration_guidance = {
            "short": "30-60 seconds (2-4 sentences per scene)",
            "medium": "1-3 minutes (4-8 sentences per scene)",
            "long": "3-5 minutes (8-12 sentences per scene)"
        }
        
        prompt = f"""
        Write a video script about: {topic}
        
        Requirements:
        - Duration: {duration_guidance.get(duration, "1-3 minutes")}
        - Style: {style}
        - Format: Scene-by-scene with dialogue/narration
        - Include: Hook, main content, call-to-action
        - Engaging and visual language
        
        Generate the complete video script with scene descriptions.
        """
        
        response = perplexity.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7
        )
        
        content = response.get("content", "")
        
        return {
            "format": "video_script",
            "topic": topic,
            "content": content,
            "duration": duration,
            "style": style,
            "estimated_duration_seconds": _estimate_video_duration(duration)
        }
        
    except Exception as e:
        logger.error(f"Error generating video script: {e}")
        return {}


def generate_white_paper(topic: str, sections: Optional[List[str]] = None) -> Dict[str, Any]:
    """Generate a white paper on a topic"""
    try:
        perplexity = get_perplexity_client()
        
        default_sections = [
            "Executive Summary",
            "Introduction",
            "Problem Statement",
            "Solution Overview",
            "Methodology",
            "Results/Findings",
            "Conclusion",
            "References"
        ]
        
        sections_to_use = sections or default_sections
        
        prompt = f"""
        Write a comprehensive white paper about: {topic}
        
        Sections to include:
        {', '.join(sections_to_use)}
        
        Requirements:
        - Professional, authoritative tone
        - Well-researched content with data and examples
        - Length: 2000-3000 words
        - Format: Markdown with clear section headers
        - Include references where appropriate
        
        Generate the complete white paper.
        """
        
        response = perplexity.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.6
        )
        
        content = response.get("content", "")
        
        return {
            "format": "white_paper",
            "topic": topic,
            "content": content,
            "sections": sections_to_use,
            "word_count": len(content.split())
        }
        
    except Exception as e:
        logger.error(f"Error generating white paper: {e}")
        return {}


def _estimate_video_duration(duration: str) -> int:
    """Estimate video duration in seconds"""
    duration_map = {
        "short": 45,
        "medium": 120,
        "long": 240
    }
    return duration_map.get(duration, 120)

