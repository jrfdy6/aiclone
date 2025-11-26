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
    audience: str = Field("general", description="Target audience: general, education_admissions, tech_ai, fashion, leadership, neurodivergent, entrepreneurs")


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
    example_chunks: List[Dict],
    audience: str = "general"
) -> str:
    """Build the prompt for content generation."""
    
    # Extract persona info (key is 'chunk' not 'text')
    persona_text = "\n".join([c.get("chunk", "") for c in persona_chunks[:3]])
    
    # Extract example content
    examples_text = "\n---\n".join([c.get("chunk", "")[:500] for c in example_chunks[:3]])
    
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
4. "Thanksgiving has a funny way of reminding us what actually shapes people. For me, it's always been education and style — two worlds everyone thinks are separate, but they're not."
5. "Style isn't vanity — it's a form of self-belief."
6. "Your outfit tells a story long before you say a word."

CRITICAL STYLE RULES:
- Open with a HOOK that creates tension or reframes a common belief
- Use short, punchy sentences for emphasis
- Break lines for rhythm and visual impact
- Be specific and concrete, not abstract
- End with a question that invites engagement
- NO soft openings like "Thanksgiving isn't just about..." or "For me, it's..."
- NO generic statements like "It's a chance to reflect"
- Lead with INSIGHT, not setup
"""

    # Channel-specific examples
    channel_examples = {
        "linkedin_post": """
EXAMPLE LINKEDIN POST (match this style EXACTLY):
---
Thanksgiving has a funny way of reminding us what actually shapes people.
For me, it's always been education and style — two worlds everyone thinks are separate, but they're not.

In education, I've seen something simple but powerful:
when a student feels good in what they wear, they show up differently.
More confidence. More presence. More voice.

Style isn't vanity — it's a form of self-belief.

And as we head into the holiday season, I'm grateful for the way fashion gives people permission to become a louder version of themselves… and the way education gives them the space to grow into it.

Your outfit tells a story long before you say a word.
This Thanksgiving, I'm thankful we all get to write our own.

Which story are you wearing into the next season?
---

STYLE NOTES:
- Hook opens with unexpected angle ("funny way of reminding us")
- Short lines for rhythm and punch
- Concrete observation ("when a student feels good... they show up differently")
- Bold statement in its own line ("Style isn't vanity — it's a form of self-belief")
- Ends with engaging question
- NO generic openings, NO soft transitions, NO "In today's world"
""",
        "cold_email": """
EXAMPLE EMAIL (match this style):
---
Subject: Your outreach is 80% friction — here's the 20% that matters

Hi {Name},

Reaching out because I built a tool that solves a problem everyone running sales or content deals with:

Prospecting takes forever because you're stuck doing research, rewriting messages, and personalizing everything manually.

So I built an AI Clone that handles that entire layer automatically — using your tone and your content.

Teams are using it to:
• reduce research time by 70%
• get personalized outreach drafts instantly
• repurpose posts into emails, DMs, and scripts
• track competitor chatter online

If you're open to testing it, I can run your website or LinkedIn profile through it and send a sample.

Worth a look?
---
""",
        "linkedin_dm": """
EXAMPLE LINKEDIN DM (match this style):
---
Hey {Name} — saw your recent post about {topic}.
Loved your take on it.

Quick note: I'm testing something new called an AI Clone that mirrors your writing style and automates the annoying parts of prospecting (research, rewrites, message drafts, intel summaries).

People are using it to speed up outreach without sounding like a template.

If you want to try it on your own content, I can generate a sample for you.
Would you like me to run your LinkedIn profile through it?
---
""",
        "instagram_post": """
EXAMPLE INSTAGRAM CAPTION (match this style):
---
I got tired of spending hours rewriting the same message 10 different ways…

so I built an AI Clone of myself 🤖✨

It studies your writing, your posts, your style —
and drafts content + outreach exactly like you.

Creators and founders are using it to:
• repurpose posts
• prep outreach
• speed up client responses
• write captions that actually convert

If you want your own AI Clone, drop "CLONE" in the comments or DM me 👇
---
"""
    }
    
    channel_example = channel_examples.get(content_type, "")
    
    # Audience-specific guidance
    audience_guidance = {
        "general": "Write for a general professional audience.",
        "education_admissions": """TARGET AUDIENCE: Education & Admissions professionals
- Use language familiar to enrollment management, admissions counselors, program directors
- Reference challenges like yield optimization, pipeline management, student recruitment
- Avoid teaching/classroom language - focus on BUSINESS of education
- Speak to people who manage teams, hit enrollment targets, work with families""",
        "tech_ai": """TARGET AUDIENCE: Tech & AI professionals
- Use technical language appropriately but don't over-jargon
- Reference building, shipping, automation, efficiency
- Speak to builders, founders, operators who use AI as a tool
- Focus on practical applications, not hype""",
        "fashion": """TARGET AUDIENCE: Fashion & Style enthusiasts
- Use visual, sensory language
- Reference personal style, wardrobe, looking good
- Speak to people who care about presentation and self-expression
- Keep it relatable, not high-fashion exclusive""",
        "leadership": """TARGET AUDIENCE: Leaders & Managers
- Use language of team dynamics, decision-making, influence
- Reference coaching, developing people, driving results
- Speak to people who manage teams and navigate organizational complexity
- Focus on practical leadership, not theoretical""",
        "neurodivergent": """TARGET AUDIENCE: Neurodivergent community & supporters
- Use respectful, informed language about neurodivergence
- Reference different learning styles, accommodations, finding the right fit
- Speak to families, professionals, and neurodivergent individuals
- Be authentic - draw from personal experience as a neurodivergent professional""",
        "entrepreneurs": """TARGET AUDIENCE: Entrepreneurs & Founders
- Use language of building, scaling, problem-solving
- Reference hustle, pivoting, shipping, customer discovery
- Speak to people building something from scratch
- Focus on action and results, not theory"""
    }
    
    audience_context = audience_guidance.get(audience, audience_guidance["general"])
    
    # Category guidance (Chris Do 911)
    category_guidance = {
        "value": "Pure value content. Teaching, insights, observations. NO selling. Make them smarter.",
        "sales": "Sell unashedly. 'I'm building X. Here's how to get involved.' Direct ask.",
        "personal": "Personal/behind-the-scenes. The real you, struggles included. Vulnerability builds trust."
    }
    
    # Channel-specific system prompts
    channel_prompts = {
        "linkedin_post": """You write LinkedIn posts with clarity, authority, and human rhythm.
Follow the Content Style Guide strictly:
- no banned words
- no banned phrases
- no LLM patterns
- no corporate jargon
- no filler transitions
- no symmetric paragraphs
- no fluff

Tone:
- confident
- direct
- practical
- grounded in experience
- warm but not sentimental
- professional but not corporate

Writing rules:
- lead with a strong insight, not a recap
- vary sentence length to feel human
- keep each paragraph 1–3 sentences max
- reference concrete examples from real work
- use specificity over general positivity
- avoid over-explaining concepts
- speak to the reader ("you"), not the room

Before you finalize the post, perform a voice audit:
- remove hedging words
- tighten sentences
- cut filler transitions
- ensure rhythm is human
- remove any phrase that "sounds like AI"
- ensure insight is front-loaded""",

        "cold_email": """You write emails that are professional, concise, and easy to read.
Follow the Content Style Guide strictly.

Tone:
- direct
- calm
- confident
- clean and human

Structure:
- strong opening sentence (sets purpose immediately)
- short paragraphs
- clean formatting
- one clear CTA
- no fluff sentences

Rules:
- remove corporate language completely
- avoid stacked hedging ("may potentially")
- avoid long build-up explanations
- prioritize clarity over formality
- write at an 8th–10th grade reading level
- avoid LLM cadence and transitions

Voice audit:
- remove filler
- remove over-politeness
- tighten every sentence by 10–20%
- ensure the CTA stands out logically
- remove clichés ("circle back," "touch base," "I hope this finds you well")""",

        "linkedin_dm": """You write outreach messages that feel personal, informed, and respectful of time.
Follow the Content Style Guide strictly.

Tone:
- concise
- confident
- warm but not chatty
- never salesy
- always personalized to the recipient's context

Writing rules:
- keep messages short; remove everything unnecessary
- no paragraphs over 2 sentences
- lead with a personalized reference or relevant insight
- ask one clear question or make one clear offer
- anchor messages in the recipient's world, not yours
- no lists, no emojis unless explicitly asked
- remove every piece of filler ("just," "wanted to," "reaching out because")

Voice audit before finalizing:
- delete any generic outreach language
- remove over-politeness
- replace vague phrases with specifics
- ensure message can be read in under 7 seconds
- ensure the ask is clear and light""",

        "instagram_post": """You write Instagram captions that are clean, warm, and human.
Follow the Content Style Guide strictly.

Tone:
- casual but thoughtful
- conversational without slang
- personal but not emotional dumping
- confident, warm, and visually descriptive

Writing rules:
- short paragraphs, lots of white space
- open with a hook or vivid moment
- keep language concrete, visual, and sensory
- avoid hashtags unless asked
- avoid "inspirational quote" tone
- avoid corporate language entirely
- do not sound like a brand

Voice audit:
- tighten every sentence
- remove filler transitions
- adjust rhythm
- ensure the caption sounds like a human moment, not marketing
- remove clichés"""
    }
    
    channel_prompt = channel_prompts.get(content_type, channel_prompts["linkedin_post"])
    
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

{channel_prompt}

{channel_example}

---

{audience_context}

---

## PERSONA (write AS this person):
{persona_text if persona_text else "No persona data available - use a professional, authentic voice."}

## EXAMPLES FROM THEIR KNOWLEDGE BASE:
{examples_text if examples_text else "No additional examples available."}

## CONTENT REQUEST:
- **Topic:** {topic}
- **Context:** {context or "General"}
- **Audience:** {audience.replace('_', ' ').title()}
- **Category:** {category.upper()} - {category_guidance.get(category, "")}

{pacer_guidance}

## INSTRUCTIONS:
1. Write AS this person using their actual experiences and perspectives.
2. Apply the topic/context to their background - don't repeat bio facts.
3. Be specific and actionable, not generic.
4. Generate 3 different options with varying hooks/angles.

Output only the content. No notes, no explanations.

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
            example_chunks=example_chunks,
            audience=req.audience
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
            persona_context=persona_chunks[0].get("chunk", "")[:200] if persona_chunks else None,
            examples_used=[c.get("metadata", {}).get("source", "")[:50] for c in example_chunks[:3]]
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

