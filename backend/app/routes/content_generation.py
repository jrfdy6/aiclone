"""
AI-Powered Content Generation Routes

Generates content using:
1. User's persona and style from knowledge base
2. High-performing content examples
3. Topic intelligence data
4. PACER/Chris Do frameworks
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import json

from app.services.embedders import embed_text
from app.services.retrieval import retrieve_similar

router = APIRouter()


class ContentGenerationRequest(BaseModel):
    user_id: str = Field(..., description="User ID for knowledge base lookup")
    topic: str = Field(..., description="Content topic")
    context: Optional[str] = Field(None, description="Additional context")
    content_type: str = Field("linkedin_post", description="Type: linkedin_post, cold_email, linkedin_dm, instagram_post")
    category: str = Field("value", description="Chris Do category: value, sales, personal")
    pacer_elements: List[str] = Field(default_factory=list, description="PACER elements to include: Problem, Amplify, Credibility, Educate, Request")
    tone: str = Field("expert_direct", description="Tone: expert_direct, inspiring, conversational")


class ContentGenerationResponse(BaseModel):
    success: bool
    options: List[str]
    persona_context: Optional[str] = None
    examples_used: List[str] = []


def get_openai_client():
    """Get OpenAI client for content generation."""
    import openai
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return openai.OpenAI(api_key=api_key)


def build_content_prompt(
    topic: str,
    context: str,
    content_type: str,
    category: str,
    pacer_elements: List[str],
    tone: str,
    persona_chunks: List[Dict],
    example_chunks: List[Dict]
) -> str:
    """Build the prompt for content generation."""
    
    # Extract persona info
    persona_text = "\n".join([c.get("text", "") for c in persona_chunks[:3]])
    
    # Extract example content
    examples_text = "\n---\n".join([c.get("text", "")[:500] for c in example_chunks[:3]])
    
    # Anti-AI writing filter
    anti_ai_rules = """
## CRITICAL WRITING RULES - FOLLOW STRICTLY

NEVER use generic LLM patterns such as:
- "In today's world", "In today's fast-paced", "In the realm of"
- "Furthermore", "Moreover", "Additionally", "However"
- "Let's dive into", "Let's explore", "Let's unpack"
- "This is important because", "It's worth noting"
- "At the end of the day", "When it comes to"
- "I'm excited to", "I'm thrilled to", "I'm passionate about"
- "Game-changer", "Leverage", "Synergy", "Paradigm shift"
- Corporate buzzwords and emotionally flat summaries
- Obvious transitional phrases

Emulate human writing style:
- Direct, clear, and confident
- Short sentences when emphasizing key ideas
- Precise and concrete language
- No filler transitions
- Vary sentence length to feel human
- Lead with insight, not recap
- Avoid AI cadence

TONE EXAMPLES TO MATCH:
1. "Leadership isn't about authority. It's about clarity, direction, and decisions made when the room goes quiet."
2. "Most operational problems aren't mysteries. They're patterns. When you track them honestly, solutions become obvious."
3. "I used to dominate conversations. Now I make it my business to be the last person to talk. The result? Better relationships, heavier adoption of my ideas."
"""
    
    # Category guidance (Chris Do 911)
    category_guidance = {
        "value": "Pure value content. Teaching, insights, observations. NO selling. Make them smarter.",
        "sales": "Sell unashedly. 'I'm building X. Here's how to get involved.' Direct ask.",
        "personal": "Personal/behind-the-scenes. The real you, struggles included. Vulnerability builds trust."
    }
    
    # Content type formats
    type_formats = {
        "linkedin_post": "LinkedIn post format. Hook in first line. Short paragraphs. Emoji sparingly. End with engagement question or CTA.",
        "cold_email": "Cold email format. Subject line + body. Personal, not templated. Clear ask.",
        "linkedin_dm": "LinkedIn DM format. Short, personal, specific. No pitch in first message.",
        "instagram_post": "Instagram caption format. Visual hook reference. Hashtags at end."
    }
    
    # PACER elements
    pacer_guidance = ""
    if pacer_elements:
        pacer_map = {
            "Problem": "Start by identifying a specific problem your audience faces",
            "Amplify": "Amplify the pain - what happens if they don't solve it?",
            "Credibility": "Establish why you're qualified to speak on this",
            "Educate": "Provide actionable value and insights",
            "Request": "End with a clear call-to-action"
        }
        pacer_guidance = "Include these PACER elements:\n" + "\n".join([f"- {p}: {pacer_map.get(p, '')}" for p in pacer_elements])
    
    prompt = f"""{anti_ai_rules}

You are a content ghostwriter for a specific person. Generate content that sounds authentically like them.

## THEIR PERSONA & VOICE (from their knowledge base):
{persona_text if persona_text else "No persona data available - use a professional, authentic voice."}

## EXAMPLES OF THEIR HIGH-PERFORMING CONTENT:
{examples_text if examples_text else "No examples available - write in an engaging, value-driven style."}

## CONTENT REQUEST:
- **Topic:** {topic}
- **Context:** {context or "General"}
- **Type:** {content_type} - {type_formats.get(content_type, "")}
- **Category:** {category.upper()} - {category_guidance.get(category, "")}
- **Tone:** {tone.replace("_", " ").title()}

{pacer_guidance}

## INSTRUCTIONS:
1. Write AS this person, not ABOUT them. Use their actual experiences, stories, and perspectives.
2. Apply the topic/context to their unique background - don't just repeat bio facts.
3. Make it specific and actionable, not generic advice.
4. Match their voice patterns from the examples.
5. Generate 3 different options with varying hooks/angles.

## VOICE AUDIT (do this before finalizing):
- Remove any generic AI phrasing
- Remove unnecessary transitions
- Remove hedges ("I think", "maybe", "perhaps")
- Remove repetition
- Tighten wording by 10-20%
- Adjust sentence rhythm to human patterns
- Ensure it sounds like a real person wrote this, not an AI

Generate 3 content options, separated by "---OPTION---":
"""
    
    return prompt


@router.post("/generate", response_model=ContentGenerationResponse)
async def generate_content(req: ContentGenerationRequest):
    """
    Generate AI-powered content using persona and examples from knowledge base.
    """
    try:
        # Step 1: Retrieve persona information from knowledge base
        persona_query = "persona voice tone style background experience professional identity"
        persona_embedding = embed_text(persona_query)
        persona_chunks = retrieve_similar(
            user_id=req.user_id,
            query_embedding=persona_embedding,
            top_k=5,
        )
        
        # Step 2: Retrieve high-performing content examples
        examples_query = f"high performing content example {req.content_type} {req.category} {req.topic}"
        examples_embedding = embed_text(examples_query)
        example_chunks = retrieve_similar(
            user_id=req.user_id,
            query_embedding=examples_embedding,
            top_k=5,
        )
        
        # Step 3: Build prompt with all context
        prompt = build_content_prompt(
            topic=req.topic,
            context=req.context or "",
            content_type=req.content_type,
            category=req.category,
            pacer_elements=req.pacer_elements,
            tone=req.tone,
            persona_chunks=persona_chunks,
            example_chunks=example_chunks
        )
        
        # Step 4: Generate content with OpenAI
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert content ghostwriter. Generate authentic, engaging content that matches the person's voice."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000,
        )
        
        # Step 5: Parse options
        raw_content = response.choices[0].message.content
        
        # Try multiple separator patterns
        if "---OPTION 1---" in raw_content:
            # Split by numbered options
            import re
            options = re.split(r'---OPTION \d+---', raw_content)
            options = [opt.strip() for opt in options if opt.strip()]
        elif "---OPTION---" in raw_content:
            options = [opt.strip() for opt in raw_content.split("---OPTION---") if opt.strip()]
        else:
            # No separator found, treat as single option
            options = [raw_content.strip()]
        
        return ContentGenerationResponse(
            success=True,
            options=options[:3],  # Max 3 options
            persona_context=persona_chunks[0].get("text", "")[:200] if persona_chunks else None,
            examples_used=[c.get("source", "")[:50] for c in example_chunks[:3]]
        )
        
    except Exception as e:
        print(f"Content generation error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")


@router.post("/quick-generate")
async def quick_generate(
    topic: str,
    content_type: str = "linkedin_post",
    category: str = "value",
    user_id: str = "default"
):
    """Quick endpoint for simple content generation."""
    req = ContentGenerationRequest(
        user_id=user_id,
        topic=topic,
        content_type=content_type,
        category=category,
    )
    return await generate_content(req)

