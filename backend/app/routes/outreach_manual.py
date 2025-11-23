"""
Manual Mode Outreach Routes - For testing and tuning before automation
Generates prompts for manual outreach generation in ChatGPT
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.firestore_client import db

logger = logging.getLogger(__name__)

router = APIRouter()


class AudienceProfile(BaseModel):
    brand_name: Optional[str] = None
    brand_voice: Optional[str] = "Professional and friendly"
    target_pain_points: Optional[List[str]] = None
    value_propositions: Optional[List[str]] = None
    industry_focus: Optional[str] = None
    custom_guidelines: Optional[str] = None


class ManualOutreachRequest(BaseModel):
    """Request for manual outreach prompt generation"""
    prospect_id: str = Field(..., description="Prospect ID to generate outreach for")
    user_id: str = Field(..., description="User identifier")
    audience_profile: Optional[AudienceProfile] = None
    preferred_tone: Optional[str] = Field("professional", description="Preferred tone for outreach")
    include_social: bool = Field(True, description="Include social media drafts")


@router.post("/prompts/generate")
async def generate_outreach_prompt(request: ManualOutreachRequest) -> Dict[str, Any]:
    """
    Generate prompt for manual outreach generation.
    Returns a formatted prompt you can copy-paste into ChatGPT.
    """
    try:
        prospect_data = None
        
        # Try to fetch from Firestore
        try:
            doc_ref = db.collection("prospects").document(request.prospect_id)
            doc = doc_ref.get()
            
            if doc.exists:
                prospect_data = doc.to_dict()
                if prospect_data.get("user_id") != request.user_id:
                    raise HTTPException(status_code=403, detail="Prospect does not belong to user")
                
                if prospect_data.get("review_status") != "approved":
                    raise HTTPException(
                        status_code=400,
                        detail="Prospect must be approved before generating outreach"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error fetching prospect: {e}")
            # Will use mock data below
        
        # If not found in DB, use mock data for testing
        if not prospect_data:
            logger.warning(f"Prospect {request.prospect_id} not found in database, using mock data for outreach generation")
            prospect_data = {
                "id": request.prospect_id,
                "name": "Test Prospect",
                "job_title": "VP Sales",
                "company": "Test Company",
                "email": "test@testcompany.com",
                "user_id": request.user_id,
                "review_status": "approved",  # Mock as approved for testing
                "analysis": {
                    "summary": "VP of Sales at Test Company, focused on scaling revenue",
                    "fit_likelihood": "High",
                    "suggested_outreach_angle": "Focus on automation and efficiency",
                    "reasoning": "Role aligns with target audience",
                    "confidence_score": 0.85
                }
            }
        
        # Build system message
        system_message = "You are an expert B2B email copywriter. Create compelling, personalized outreach emails."
        
        # Build user prompt
        prospect_name = prospect_data.get("name", "there")
        company = prospect_data.get("company", "your company")
        job_title = prospect_data.get("job_title", "")
        analysis = prospect_data.get("analysis", {})
        outreach_angle = analysis.get("suggested_outreach_angle", "")
        
        user_prompt_parts = [f"Generate 5 email draft options for reaching out to a prospect.\n"]
        
        user_prompt_parts.append("PROSPECT DETAILS:")
        user_prompt_parts.append(f"- Name: {prospect_name}")
        user_prompt_parts.append(f"- Job Title: {job_title}")
        user_prompt_parts.append(f"- Company: {company}")
        user_prompt_parts.append(f"- Outreach Angle: {outreach_angle}")
        
        if request.audience_profile:
            user_prompt_parts.append("\nBRAND DETAILS:")
            if request.audience_profile.brand_name:
                user_prompt_parts.append(f"- Brand Name: {request.audience_profile.brand_name}")
            if request.audience_profile.brand_voice:
                user_prompt_parts.append(f"- Brand Voice: {request.audience_profile.brand_voice}")
            if request.audience_profile.value_propositions:
                user_prompt_parts.append(f"- Value Propositions: {', '.join(request.audience_profile.value_propositions)}")
            if request.audience_profile.target_pain_points:
                user_prompt_parts.append(f"- Pain Points: {', '.join(request.audience_profile.target_pain_points)}")
            if request.audience_profile.industry_focus:
                user_prompt_parts.append(f"- Industry Focus: {request.audience_profile.industry_focus}")
            if request.audience_profile.custom_guidelines:
                user_prompt_parts.append(f"- Custom Guidelines: {request.audience_profile.custom_guidelines}")
        
        # NEW: Add research insights if available
        if prospect_data.get("linked_research_ids"):
            from app.services.scoring import get_research_insights
            research_list = get_research_insights(request.user_id, prospect_data.get("linked_research_ids", []))
            if research_list:
                research = research_list[0]
                user_prompt_parts.append("\nRESEARCH INSIGHTS:")
                if research.get("summary"):
                    user_prompt_parts.append(f"- Industry Trends: {research.get('summary', '')[:200]}")
                if research.get("keywords"):
                    user_prompt_parts.append(f"- Signal Keywords: {', '.join(research.get('keywords', [])[:5])}")
                if research.get("trending_pains"):
                    user_prompt_parts.append(f"- Trending Pains: {', '.join(research.get('trending_pains', [])[:3])}")
        
        # NEW: Add cached insights if available
        if prospect_data.get("cached_insights"):
            cached = prospect_data.get("cached_insights", {})
            if cached.get("signal_keywords"):
                user_prompt_parts.append(f"\n- Prospect Signal Keywords: {', '.join(cached.get('signal_keywords', [])[:5])}")
        
        user_prompt_parts.append(f"\nTone: {request.preferred_tone}")
        
        user_prompt_parts.append("\nGenerate 5 different email options with:")
        user_prompt_parts.append("1. Subject line (compelling, personalized, not spammy)")
        user_prompt_parts.append("2. Body (concise, value-focused, includes clear CTA)")
        user_prompt_parts.append("\nVary the approaches: some more direct, some more consultative, different angles.")
        
        if request.include_social:
            user_prompt_parts.append("\n\nAlso generate 5 social media post options (LinkedIn/Twitter) with:")
            user_prompt_parts.append("1. Caption (engaging, authentic, not salesy - max 280 chars for Twitter, can be longer for LinkedIn)")
            user_prompt_parts.append("2. Hashtags (3-8 relevant hashtags)")
        
        user_prompt_parts.append("\nRespond in JSON format:")
        
        if request.include_social:
            user_prompt_parts.append("""
{
  "emails": [
    {
      "variant": 1,
      "subject": "subject line",
      "body": "email body text"
    },
    ...
  ],
  "social_posts": [
    {
      "variant": 1,
      "caption": "post caption text",
      "hashtags": ["tag1", "tag2", ...]
    },
    ...
  ]
}""")
        else:
            user_prompt_parts.append("""
{
  "emails": [
    {
      "variant": 1,
      "subject": "subject line",
      "body": "email body text"
    },
    ...
  ]
}""")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        return {
            "success": True,
            "mode": "manual",
            "prospect_id": request.prospect_id,
            "prompt": {
                "system_message": system_message,
                "user_prompt": user_prompt,
                "full_prompt": f"System: {system_message}\n\nUser: {user_prompt}",
                "expected_format": {
                    "type": "JSON",
                    "structure": {
                        "emails": [
                            {
                                "variant": 1,
                                "subject": "string",
                                "body": "string"
                            }
                        ],
                        "social_posts": [
                            {
                                "variant": 1,
                                "caption": "string",
                                "hashtags": ["string"]
                            }
                        ] if request.include_social else None
                    }
                }
            },
            "instructions": "1. Copy the 'full_prompt' above\n2. Paste into ChatGPT\n3. Get the JSON response\n4. Use POST /api/outreach/manual/upload to upload results",
            "include_social": request.include_social
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating outreach prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate prompt: {str(e)}")


