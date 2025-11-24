"""
AI Personas Models
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Persona(BaseModel):
    """AI Persona model"""
    id: str
    user_id: str
    name: str
    is_default: bool = False
    outreach_tone: str = Field(default="professional", description="Outreach communication tone")
    industry_focus: List[str] = Field(default_factory=list, description="Target industries")
    use_cases: List[str] = Field(default_factory=list, description="Use cases/pain points to address")
    writing_style: str = Field(default="clear and concise", description="Writing style preferences")
    user_positioning: str = Field(default="", description="User's own positioning/background")
    brand_voice: str = Field(default="", description="Brand voice guidelines")
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PersonaCreate(BaseModel):
    """Request to create persona"""
    user_id: str = Field(..., description="User identifier")
    name: str = Field(..., description="Persona name")
    outreach_tone: Optional[str] = Field("professional", description="Outreach communication tone")
    industry_focus: Optional[List[str]] = Field(default_factory=list, description="Target industries")
    use_cases: Optional[List[str]] = Field(default_factory=list, description="Use cases/pain points")
    writing_style: Optional[str] = Field("clear and concise", description="Writing style preferences")
    user_positioning: Optional[str] = Field("", description="User's positioning/background")
    brand_voice: Optional[str] = Field("", description="Brand voice guidelines")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class PersonaUpdate(BaseModel):
    """Request to update persona"""
    name: Optional[str] = None
    outreach_tone: Optional[str] = None
    industry_focus: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    writing_style: Optional[str] = None
    user_positioning: Optional[str] = None
    brand_voice: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PersonaListResponse(BaseModel):
    """Response for listing personas"""
    success: bool
    personas: List[Persona]
    total: int


class PersonaResponse(BaseModel):
    """Response for single persona"""
    success: bool
    persona: Persona

