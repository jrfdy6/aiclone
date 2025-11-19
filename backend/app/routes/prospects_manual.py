"""
Manual Mode Prospect Routes - For testing and tuning before automation
Generates prompts/datasets for manual execution in ChatGPT
"""
import logging
import time
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


class ProspectAnalysis(BaseModel):
    summary: str
    fit_likelihood: str
    suggested_outreach_angle: str
    reasoning: Optional[str] = None
    confidence_score: Optional[float] = None


class ManualAnalysisRequest(BaseModel):
    """Request for manual analysis prompt generation"""
    prospect_ids: List[str] = Field(..., description="List of prospect IDs to analyze")
    user_id: str = Field(..., description="User identifier")
    audience_profile: Optional[AudienceProfile] = None


class ManualAnalysisResult(BaseModel):
    """Manual upload of AI analysis results"""
    prospect_id: str
    analysis: ProspectAnalysis


class BatchManualAnalysisResult(BaseModel):
    """Batch upload of manual analysis results"""
    results: List[ManualAnalysisResult]
    user_id: str


@router.post("/prompts/analyze")
async def generate_analysis_prompt(request: ManualAnalysisRequest) -> Dict[str, Any]:
    """
    Generate prompt for manual prospect analysis.
    Returns a formatted prompt you can copy-paste into ChatGPT.
    """
    try:
        # Fetch prospects from Firestore
        prospects_data = []
        
        for prospect_id in request.prospect_ids:
            try:
                doc_ref = db.collection("prospects").document(prospect_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    prospect_data = doc.to_dict()
                    if prospect_data.get("user_id") == request.user_id:
                        prospects_data.append({**prospect_data, "id": prospect_id})
            except Exception as e:
                logger.warning(f"Error fetching prospect {prospect_id}: {e}")
                # Continue with other prospects
                continue
        
        # If no prospects found in DB, use mock data for testing
        if not prospects_data:
            logger.warning("No prospects found in database, using mock data for prompt generation")
            for prospect_id in request.prospect_ids:
                prospects_data.append({
                    "id": prospect_id,
                    "name": f"Prospect {prospect_id[:8]}",
                    "job_title": "VP Sales",
                    "company": "Company Name",
                    "email": f"prospect{prospect_id[:8]}@company.com",
                    "notes": "Test prospect data",
                    "user_id": request.user_id
                })
        
        if not prospects_data:
            raise HTTPException(status_code=404, detail="No valid prospects found")
        
        # Build system message
        system_message = """You are a B2B sales prospecting expert. Analyze prospects and provide actionable insights."""
        
        # Build user prompt
        user_prompt_parts = ["Analyze these prospects and provide insights for each one:\n"]
        
        if request.audience_profile:
            user_prompt_parts.append("TARGET AUDIENCE CONTEXT:")
            if request.audience_profile.brand_name:
                user_prompt_parts.append(f"Brand: {request.audience_profile.brand_name}")
            if request.audience_profile.brand_voice:
                user_prompt_parts.append(f"Brand Voice: {request.audience_profile.brand_voice}")
            if request.audience_profile.industry_focus:
                user_prompt_parts.append(f"Industry Focus: {request.audience_profile.industry_focus}")
            if request.audience_profile.value_propositions:
                user_prompt_parts.append(f"Value Propositions: {', '.join(request.audience_profile.value_propositions)}")
            if request.audience_profile.target_pain_points:
                user_prompt_parts.append(f"Target Pain Points: {', '.join(request.audience_profile.target_pain_points)}")
            if request.audience_profile.custom_guidelines:
                user_prompt_parts.append(f"Custom Guidelines: {request.audience_profile.custom_guidelines}")
            user_prompt_parts.append("\n")
        
        user_prompt_parts.append("PROSPECTS TO ANALYZE:\n")
        
        for idx, prospect in enumerate(prospects_data, 1):
            user_prompt_parts.append(f"\n--- Prospect {idx} ---")
            user_prompt_parts.append(f"Name: {prospect.get('name', 'Unknown')}")
            user_prompt_parts.append(f"Job Title: {prospect.get('job_title', 'Not provided')}")
            user_prompt_parts.append(f"Company: {prospect.get('company', 'Not provided')}")
            user_prompt_parts.append(f"Email: {prospect.get('email', 'Not provided')}")
            if prospect.get('notes'):
                user_prompt_parts.append(f"Notes: {prospect.get('notes')}")
            if prospect.get('linkedin_url'):
                user_prompt_parts.append(f"LinkedIn: {prospect.get('linkedin_url')}")
            if prospect.get('website'):
                user_prompt_parts.append(f"Website: {prospect.get('website')}")
            user_prompt_parts.append(f"Prospect ID: {prospect.get('id', 'unknown')}")
        
        user_prompt_parts.append("\n\nFor each prospect, provide:")
        user_prompt_parts.append("1. A 1-2 sentence summary of who they are and why they might be relevant")
        user_prompt_parts.append("2. Fit Likelihood: High, Medium, or Low (consider role, company size, industry alignment)")
        user_prompt_parts.append("3. A suggested outreach angle that would resonate with this prospect")
        user_prompt_parts.append("4. Brief reasoning for your assessment")
        user_prompt_parts.append("5. Confidence score (0.0 to 1.0)")
        
        user_prompt_parts.append("\nRespond in JSON format:")
        user_prompt_parts.append("""
{
  "prospects": [
    {
      "prospect_id": "uuid1",
      "summary": "1-2 sentence summary",
      "fit_likelihood": "High|Medium|Low",
      "suggested_outreach_angle": "Specific angle for outreach",
      "reasoning": "Brief explanation",
      "confidence_score": 0.85
    },
    ...
  ]
}""")
        
        user_prompt = "\n".join(user_prompt_parts)
        
        return {
            "success": True,
            "mode": "manual",
            "prospect_ids": request.prospect_ids,
            "prompt": {
                "system_message": system_message,
                "user_prompt": user_prompt,
                "full_prompt": f"System: {system_message}\n\nUser: {user_prompt}",
                "expected_format": {
                    "type": "JSON",
                    "structure": {
                        "prospects": [
                            {
                                "prospect_id": "string",
                                "summary": "string",
                                "fit_likelihood": "High|Medium|Low",
                                "suggested_outreach_angle": "string",
                                "reasoning": "string",
                                "confidence_score": 0.0
                            }
                        ]
                    }
                }
            },
            "instructions": "1. Copy the 'full_prompt' above\n2. Paste into ChatGPT\n3. Get the JSON response\n4. Use POST /api/prospects/manual/upload-analysis to upload results",
            "prospects_count": len(prospects_data)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating analysis prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate prompt: {str(e)}")


@router.post("/upload-analysis")
async def upload_manual_analysis(batch_result: BatchManualAnalysisResult):
    """
    Upload manually generated AI analysis results.
    Use this after running the prompt in ChatGPT and getting results.
    """
    try:
        uploaded_count = 0
        errors = []
        
        for result in batch_result.results:
            try:
                doc_ref = db.collection("prospects").document(result.prospect_id)
                doc = doc_ref.get()
                
                if not doc.exists:
                    errors.append(f"Prospect {result.prospect_id} not found")
                    continue
                
                prospect_data = doc.to_dict()
                if prospect_data.get("user_id") != batch_result.user_id:
                    errors.append(f"Prospect {result.prospect_id} doesn't belong to user")
                    continue
                
                # Update prospect with analysis
                updates = {
                    "status": "analyzed",
                    "analysis": {
                        "summary": result.analysis.summary,
                        "fit_likelihood": result.analysis.fit_likelihood,
                        "suggested_outreach_angle": result.analysis.suggested_outreach_angle,
                        "reasoning": result.analysis.reasoning,
                        "confidence_score": result.analysis.confidence_score
                    },
                    "analysis_method": "manual",
                    "updated_at": time.time()
                }
                doc_ref.update(updates)
                uploaded_count += 1
            
            except Exception as e:
                errors.append(f"Error processing {result.prospect_id}: {str(e)}")
        
        return {
            "success": True,
            "uploaded_count": uploaded_count,
            "total_count": len(batch_result.results),
            "errors": errors
        }
    
    except Exception as e:
        logger.exception(f"Error uploading manual analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload analysis: {str(e)}")

