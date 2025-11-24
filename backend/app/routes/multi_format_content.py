"""
Multi-Format Content Generation Routes
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Body
from app.services.multi_format_content_service import (
    generate_blog_post, generate_email,
    generate_video_script, generate_white_paper
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/blog", response_model=Dict[str, Any])
async def generate_blog_post_endpoint(
    topic: str = Body(..., description="Blog topic"),
    length: str = Body("medium", description="Length: short, medium, long"),
    tone: str = Body("professional", description="Tone: professional, casual, authoritative, conversational")
) -> Dict[str, Any]:
    """Generate a blog post"""
    try:
        blog_post = generate_blog_post(topic, length, tone)
        return {"success": True, "blog_post": blog_post}
    except Exception as e:
        logger.exception(f"Error generating blog post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate blog post: {str(e)}")


@router.post("/email", response_model=Dict[str, Any])
async def generate_email_endpoint(
    subject: str = Body(..., description="Email subject"),
    recipient_type: str = Body("prospect", description="Recipient type"),
    purpose: str = Body("introduction", description="Email purpose"),
    tone: str = Body("professional", description="Email tone")
) -> Dict[str, Any]:
    """Generate an email"""
    try:
        email = generate_email(subject, recipient_type, purpose, tone)
        return {"success": True, "email": email}
    except Exception as e:
        logger.exception(f"Error generating email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate email: {str(e)}")


@router.post("/video-script", response_model=Dict[str, Any])
async def generate_video_script_endpoint(
    topic: str = Body(..., description="Video topic"),
    duration: str = Body("short", description="Duration: short, medium, long"),
    style: str = Body("educational", description="Style: educational, entertaining, promotional, storytelling")
) -> Dict[str, Any]:
    """Generate a video script"""
    try:
        script = generate_video_script(topic, duration, style)
        return {"success": True, "video_script": script}
    except Exception as e:
        logger.exception(f"Error generating video script: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate video script: {str(e)}")


@router.post("/white-paper", response_model=Dict[str, Any])
async def generate_white_paper_endpoint(
    topic: str = Body(..., description="White paper topic"),
    sections: List[str] = Body(default_factory=list, description="Optional custom sections")
) -> Dict[str, Any]:
    """Generate a white paper"""
    try:
        white_paper = generate_white_paper(topic, sections if sections else None)
        return {"success": True, "white_paper": white_paper}
    except Exception as e:
        logger.exception(f"Error generating white paper: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate white paper: {str(e)}")

