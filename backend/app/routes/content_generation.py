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
from app.services.retrieval import retrieve_similar, retrieve_weighted

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
    
    # Extract persona info with tag labels for context
    # Group chunks by tag for better organization in the prompt
    persona_sections = {}
    for c in persona_chunks[:7]:
        tag = c.get("persona_tag", "GENERAL")
        chunk_text = c.get("chunk", "")
        if chunk_text:
            if tag not in persona_sections:
                persona_sections[tag] = []
            persona_sections[tag].append(chunk_text)
    
    # Build persona text with section labels
    persona_parts = []
    # Order chunks for narrative flow: voice → struggles → experiences → philosophy
    tag_order = ["VOICE_PATTERNS", "STRUGGLES", "EXPERIENCES", "PHILOSOPHY", "VENTURES", "BIO_FACTS", "LINKEDIN_EXAMPLES"]
    for tag in tag_order:
        if tag in persona_sections:
            persona_parts.append(f"### {tag.replace('_', ' ').title()}\n" + "\n".join(persona_sections[tag]))
    # Add any remaining tags
    for tag, chunks in persona_sections.items():
        if tag not in tag_order:
            persona_parts.append(f"### {tag.replace('_', ' ').title()}\n" + "\n".join(chunks))
    
    persona_text = "\n\n".join(persona_parts)
    
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

BEFORE vs AFTER EXAMPLES:

❌ BAD (generic): "Education isn't just about books. It's about identity."
✅ GOOD (specific): "Education isn't only about books; it's identity."

❌ BAD (vague): "I watched my dad teach me that every piece of knowledge is a tool."
✅ GOOD (concrete): "My dad worked as a mechanic, and he taught me that knowledge is a tool."

❌ BAD (abstract): "Knowledge empowers them. It's not just grades; it's confidence, community, and style."
✅ GOOD (specific): "Real learning gives them confidence. It shapes how they show up. It influences how they express themselves."

❌ BAD (wordy): "When I see students wearing their stories, I see the result of real education—an expression of who they are and who they aspire to be."
✅ GOOD (tight): "When students wear their stories—through their choices, their style, their presence—I see the result of education that reaches beyond the classroom."

❌ BAD (generic question): "How do we celebrate not just the learning, but the journeys that shape us?"
✅ GOOD (specific question): "How do we celebrate not only what students learn, but who they become through the process?"

KEY DIFFERENCES:
- Remove "just" and use "only" or cut entirely
- Replace abstract nouns with concrete actions
- Tighten every sentence by 10-20%
- Make questions more specific
- Every word must earn its place

MORE BEFORE/AFTER TIGHTENING:

❌ "I remember those vibrant tablecloths, the way they matched her bold personality."
✅ "Those vibrant tablecloths matched her bold personality."

❌ "It's cozy, yes, but it's also a representation of hard work and resilience."
✅ "Cozy, yes, but also a symbol of hard work and resilience."

❌ "That blend of function and sentiment is what I try to channel in my choices today."
✅ "That blend of function and sentiment is what I aim for today."

❌ "Fashion isn't just about trends; it's about roots and aspirations."
✅ "Fashion isn't just trends; it's roots and aspirations."

❌ "I learned that style is about more than fabric; it's about confidence and clarity."
✅ "I learned that style is more than fabric. It's confidence and clarity."

❌ "This Thanksgiving, let's think beyond the plate. How do we ensure our personal style reflects the stories we want to tell?"
✅ "This Thanksgiving, think beyond the plate: How can your personal style reflect the story you want to tell?"

TIGHTENING RULES:
- Cut "I remember" / "I recall" - just describe directly
- "is about" → cut or use em-dash
- "let's" → direct "you" address
- "How do we" → "How can your"
- Remove unnecessary "that" and "the way"
- "try to" → "aim for" or cut
- Semicolons → periods or colons for clarity
"""

    # Channel-specific examples - USE REAL POSTS FROM PERSONA, not fabricated stories
    channel_examples = {
        "linkedin_post": """
REAL LINKEDIN POST EXAMPLES FROM THIS PERSON (match this voice EXACTLY):

EXAMPLE 1 (Life Update - 2,348 impressions):
---
🔔 Life Update

A couple weeks ago, I got word that my position was being eliminated. Tell you what tho, I'm feeling thankful. Thankful for the space it gave me to reset, and for the lessons I learned about leadership and navigating challenges with grace.

I'm especially grateful for the colleagues who encouraged me, challenged me, and made the journey meaningful.

Today, I'm excited to share that I've started my new role as Director of Admissions at Fusion Academy. I'm energized, aligned, and ready to grow.

#stayready #education #technology #leadership #turnoverchain
---

EXAMPLE 2 (Event Recap - 1,767 impressions):
---
Wrapping up an incredible Season of Coffee & Convo with the final event of 2025 being hosted at Fusion Academy DC!

Yall we had a DYNAMIC conversation around pervasive drive for autonomy (PDA). Say it with me:

🗣️ Pervasive Drive for Autonomy!

A huge thank you to our amazing panelists:
Natalie Morton – Director of Education at Fusion DC
Kaitlyn Tiplady – Licensed Clinical Psychologist, Georgetown Psychology
Elizabeth Sokolov – Founder of NeuroPossible

And a big shout-out to our cosponsor, Newport Healthcare. This event would not have been the same without your partnership!

Coffee & Convo has been about creating space for meaningful dialogue and collaboration. We're so grateful to everyone who joined us and contributed to these conversations. We'll be back in 2026 with fresh topics and opportunities to connect... Stay tuned!
---

EXAMPLE 3 (Commentary - 782 impressions):
---
Just read Krugman's piece on how the U.S. is pushing away international students. As someone who worked with them daily, this one hit home.

They bring talent, drive, fresh perspective and billions to the economy. Turning our backs? Makes no sense. Period.
---

VOICE RULES (MANDATORY - preserve these patterns):
- Use "Yall" naturally as casual opener
- "Tell you what tho" as conversational pivot
- "Say it with me: 🗣️" for engagement hooks
- "Big shout-out to..." for recognition
- "Makes no sense. Period." for punchy closers
- Short, punchy sentences for emphasis
- **Bold** key insight statements
- Tag people with their title/org
- Hashtags grouped at end (5-7 max)
- 🔔 for announcements, 💜 for Fusion content, 📸 before photos
""",
        "cold_email": """
EMAIL STYLE RULES (based on this person's voice):

Structure:
- Personal connection in opening
- Short paragraphs, easy to skim
- Reflective tone, not salesy
- One clear CTA
- "Warmly" or similar human closing

Voice markers to include:
- Direct, confident language
- Reference real experiences (Fusion Academy, Coffee & Convo events, neurodivergent students)
- NO corporate jargon
- Authentic, not overly polished

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
""",
        "linkedin_dm": """
LINKEDIN DM STYLE (based on this person's voice):

Structure:
- Opens casual ("Hey —" or similar)
- Short, under 10 seconds to read
- Personal detail from REAL experiences
- Ends with genuine question
- NO pitch, NO ask for a call

Voice markers:
- Casual but professional
- Can use "Yall" if appropriate
- Reference real work (Fusion Academy, neurodivergent students, Coffee & Convo)
- Feels like a message from a friend

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
""",
        "instagram_post": """
INSTAGRAM STYLE (based on this person's voice):

Structure:
- Opens with short punchy line
- **Bold** key statements
- Stacked short phrases for rhythm
- Emoji sparingly at end (🙏, 💜, ✨)
- Ends with question or reflection

Voice markers:
- Casual, warm, authentic
- "Yall" acceptable
- Reference real experiences
- Personal but not oversharing

PULL REAL ANECDOTES FROM PERSONA DATA - do not fabricate stories.
"""
    }
    
    channel_example = channel_examples.get(content_type, "")
    
    # Audience-specific guidance with examples
    audience_guidance = {
        "general": """TARGET AUDIENCE: General professional audience
- Write for smart professionals across industries
- Use clear, accessible language
- Focus on universal themes: growth, reflection, connection
- Avoid niche jargon""",

        "education_admissions": """TARGET AUDIENCE: Education & Admissions professionals
- Speak to enrollment managers, admissions counselors, program directors
- Reference: yield optimization, pipeline management, student recruitment, family conversations
- Focus on BUSINESS of education, not teaching/classroom
- You manage teams, hit enrollment targets, work with families

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Education is changing rapidly in today's world."
✅ "Enrollment season taught me something about pipeline management that applies everywhere."

❌ "Students need more support than ever."
✅ "When a family walks into your office unsure if their kid belongs, your first 60 seconds matter more than your brochure."

SPECIFIC STORIES TO DRAW FROM:
- Managing $34M portfolios at 2U
- Launching Fordham MSW, Howard MSW programs
- Salesforce migrations across 3 instances
- Fusion Academy: 1:1 school for neurodivergent students
- The "temperature gauge" approach to team management""",

        "tech_ai": """TARGET AUDIENCE: Tech & AI professionals
- Speak to builders, founders, operators who use AI as a tool
- Reference: shipping, automation, building in public, efficiency
- Focus on practical applications, not hype
- You build things, you ship, you iterate

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "AI is revolutionizing the way we work."
✅ "I shipped an AI clone of myself last week. Here's what broke."

❌ "Technology can help us be more productive."
✅ "Most AI tools promise 10x productivity. Reality: 2x on good days, if you know what to automate."

SPECIFIC STORIES TO DRAW FROM:
- Building Easy Outfit app
- Georgetown Data Science certificate
- USC Master's in Tech/Business/Design
- Years of Salesforce, Tableau, automation work
- Using Cursor, Perplexity, ChatGPT to actually build""",

        "fashion": """TARGET AUDIENCE: Fashion & Style enthusiasts
- Use visual, sensory language
- Reference: personal style, wardrobe, self-expression, confidence
- Keep it relatable, not high-fashion exclusive
- Style is identity, not vanity

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Fashion is an important form of self-expression."
✅ "That oversized jacket from my dad, a mechanic, taught me more about style than any magazine."

❌ "What you wear matters."
✅ "Clothes aren't just clothes. They're memories. They're roots."

SPECIFIC STORIES TO DRAW FROM:
- Dad's mechanic jacket worn on cold school mornings
- Fell in love with fashion in a random textile course
- Building Easy Outfit app to solve your own styling problem
- Buying clothes every weekend trying to figure out style""",

        "leadership": """TARGET AUDIENCE: Leaders & Managers
- Speak to people who manage teams and navigate organizational complexity
- Reference: coaching, developing people, driving results, decision-making
- Focus on practical leadership, not theoretical
- You've managed teams, hit targets, built culture

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Leadership is about inspiring others."
✅ "I used to dominate conversations. Now I make it my business to be the last person to talk."

❌ "Good managers support their teams."
✅ "Teams don't perform because they don't have a clear goal or they don't believe in the plan. That's it."

SPECIFIC STORIES TO DRAW FROM:
- Managing teams of 15+ at 2U
- "Temperature gauge" approach: never let the team cool off
- "Process Champion" identity: keeping things documented
- The defer process story: getting buy-in before formally suggesting
- Coaching struggling ACs: taking him to lunch as a peer, not a manager""",

        "neurodivergent": """TARGET AUDIENCE: Neurodivergent community & supporters
- Speak to families, professionals, and neurodivergent individuals
- Reference: different learning styles, finding the right fit, accommodations
- Be authentic: you're neurodivergent yourself
- This isn't just work; it's personal

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Neurodivergent students face unique challenges."
✅ "I'm neurodivergent. This isn't just a job. It's personal."

❌ "We need to support different learning styles."
✅ "When a student finally finds an environment where 'different' is the norm, you see the shift immediately."

SPECIFIC STORIES TO DRAW FROM:
- Being neurodivergent yourself
- Fusion Academy: 1:1 school serving neurodivergent students
- Understanding what it's like to learn differently
- Helping families find the right fit for their kids
- The moment when students feel seen, not just academically""",

        "entrepreneurs": """TARGET AUDIENCE: Entrepreneurs & Founders
- Speak to people building something from scratch
- Reference: shipping, pivoting, customer discovery, building in public
- Focus on action and results, not theory
- You're building Easy Outfit, pivoting into tech

EXAMPLE HOOKS FOR THIS AUDIENCE:
❌ "Entrepreneurship requires persistence and vision."
✅ "I'm building an app to solve my own problem. That's the only validation that matters early on."

❌ "Starting a business is challenging but rewarding."
✅ "I've spent 10+ years in education. Now I'm pivoting into tech. You're witnessing the messy middle."

SPECIFIC STORIES TO DRAW FROM:
- Building Easy Outfit app
- Pivoting from education into tech
- Founded InspireSTL nonprofit out of college
- "I can't be put in a box" identity
- Building in public, sharing the journey"""
    }
    
    audience_context = audience_guidance.get(audience, audience_guidance["general"])
    
    # Category guidance (Chris Do 911) with examples
    category_guidance = {
        "value": """VALUE CONTENT (9 out of 11 posts)
Pure value. Teaching, insights, observations. NO selling. Make them smarter.

PURPOSE: Build authority and trust. Give without asking.

EXAMPLE VALUE HOOKS:
❌ "Here are 5 tips for better leadership."
✅ "Teams don't perform because they don't have a clear goal or they don't believe in the plan. That's it."

❌ "Communication is key in management."
✅ "I used to dominate conversations. Now I make it my business to be the last person to talk. Results: more fruitful exchanges, heavier adoption of my ideas."

❌ "Here's what I learned about enrollment management."
✅ "Enrollment season taught me something: your first 60 seconds with a family matter more than your brochure."

VALUE CONTENT RULES:
- Lead with the insight, not the setup
- Share frameworks, not platitudes
- Use specific numbers and outcomes
- End with reflection or question, NOT a pitch
- NO "DM me" or "link in bio" on value posts""",

        "sales": """SALES CONTENT (1 out of 11 posts)
Sell unabashedly. Direct ask. No apologies.

PURPOSE: Convert attention into action. You've earned the right to ask.

EXAMPLE SALES HOOKS:
❌ "I'm excited to announce my new project."
✅ "I'm building Easy Outfit. It solves a problem I've had for years. Here's how to get early access."

❌ "If you're interested in learning more about my services..."
✅ "I consult on enrollment management and program launches. 10+ years experience. $34M portfolios. If you need help, let's talk."

❌ "I'd love to connect with anyone who might benefit from this."
✅ "Looking for beta testers. DM me if you want in. No pitch deck, just building."

SALES CONTENT RULES:
- State what you're building/offering in the first 2 lines
- Be specific about who it's for
- Clear CTA: DM, comment, link
- No hedging ("might be interested", "could potentially")
- Confidence, not arrogance
- You've given 9 value posts. You've earned this ask.""",

        "personal": """PERSONAL CONTENT (1 out of 11 posts)
Behind-the-scenes. The real you. Struggles included. Vulnerability builds trust.

PURPOSE: Humanize yourself. Let people connect with the person, not just the professional.

EXAMPLE PERSONAL HOOKS:
❌ "I want to share a personal story with you today."
✅ "I can't be put into a box. Son of a mechanic from St. Louis. Fell in love with fashion in a random textile course. 10+ years in education. Now pivoting into tech."

❌ "I've learned a lot on my journey."
✅ "I used to dominate conversations. I'd talk over people. Interrupt. Make sure my point was heard. It made me appear intimidating. And honestly? It hurt my relationships."

❌ "Thanksgiving is a time for gratitude."
✅ "That oversized jacket from my dad, a mechanic, taught me more about style than any magazine. Cozy, yes, but also a symbol of hard work and resilience."

PERSONAL CONTENT RULES:
- Specific details: names, places, objects, moments
- Show the struggle, not just the win
- Vulnerability, not oversharing
- Connect personal story to broader meaning
- End with reflection or question that invites others to share"""
    }
    
    # Channel-specific system prompts - PRESERVE AUTHENTIC VOICE
    channel_prompts = {
        "linkedin_post": """You write LinkedIn posts that sound like THIS SPECIFIC PERSON - casual, warm, punchy.

VOICE PRESERVATION (CRITICAL):
- Keep casual markers: "Yall", "Tell you what tho", "I'm here for it"
- Keep punchy rhythm: short sentences, stacked phrases
- Keep engagement hooks: "Say it with me: 🗣️"
- Keep recognition patterns: "Big shout-out to..."
- DO NOT over-polish or remove casual language
- DO NOT make it sound corporate or generic

Tone:
- confident and direct
- warm and casual (NOT stiff or formal)
- grounded in real experience
- punchy, not verbose

Writing rules:
- lead with insight or hook, not setup
- vary sentence length
- short paragraphs (1-3 sentences)
- use REAL stories from persona data
- end with question or reflection
- hashtags grouped at end

Voice audit:
- Does it sound like the real LinkedIn examples?
- Are casual markers preserved?
- Is the rhythm punchy, not flat?
- Would this person actually post this?""",

        "cold_email": """You write emails that are professional but still sound like THIS PERSON.

VOICE PRESERVATION:
- Keep direct, confident language
- Can include casual warmth
- Reference real experiences from persona
- NO corporate jargon

Tone:
- direct and confident
- warm but professional
- clean and human

Structure:
- strong opening
- short paragraphs
- one clear CTA
- human closing ("Warmly" etc.)

Voice audit:
- Does it sound authentic to this person?
- Is it direct without being cold?""",

        "linkedin_dm": """You write DMs that feel like messages from a friend, not a salesperson.

VOICE PRESERVATION:
- Casual openers OK ("Hey —")
- Can use "Yall" if fits context
- Short and punchy
- Reference real work from persona

Tone:
- casual and warm
- confident, not salesy
- conversational

Rules:
- under 10 seconds to read
- one question or insight
- NO pitch language
- feels personal

Voice audit:
- Would you send this to a friend?
- Is it too formal or stiff?""",

        "instagram_post": """You write Instagram captions that are casual, warm, and authentic.

VOICE PRESERVATION:
- Casual language OK ("Yall" etc.)
- Emojis sparingly (🙏 💜 ✨)
- Punchy rhythm, stacked phrases
- Personal but not oversharing

Tone:
- casual and thoughtful
- warm and authentic
- visually descriptive

Rules:
- short paragraphs, white space
- open with hook
- end with question or reflection
- NO brand voice, NO corporate

Voice audit:
- Does it sound like a real person?
- Is the rhythm natural?"""
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

## NARRATIVE ARC (follow this structure):
1. **HOOK/CONTEXT** - Start with something relatable, surprising, or attention-grabbing. Use voice markers.
2. **CHALLENGE/JOURNEY** - Share a real struggle, lesson, or experience from the persona chunks. This is the meat.
3. **REFLECTION/CTA** - Tie it back to the audience with insight or a question. End strong.

## INSTRUCTIONS:
1. Write AS this person using their actual experiences and perspectives.
2. Follow the 3-part narrative arc above - each post should feel like a story, not a list of facts.
3. Apply the topic/context to their background - don't just repeat bio facts.
4. Be specific and actionable, not generic.
5. Generate 3 different options with varying hooks/angles.

## ANTI-HALLUCINATION RULES (CRITICAL):
- ONLY use anecdotes, stories, and facts that appear in the PERSONA section above
- If you need a personal story, pick one from: DEFINE Socks, Coffee & Convo, Fusion Academy, 2U, InspireSTL, Georgetown data science, USC projects
- NEVER invent stories about family members, objects, or experiences not in the persona
- If no relevant anecdote exists, use a general reflection instead of fabricating
- Real ventures to reference: DEFINE Socks, Acorn Global Collective, Easy Outfit App, Coffee & Convo events
- Real experiences: neurodivergent students, program launches, Salesforce migrations, team coaching

## VOICE MARKERS TO USE:
- "Yall" / "Y'all" as casual opener
- "Tell you what tho" as pivot
- "Say it with me: 🗣️" for engagement
- "Big shout-out to..." for recognition
- "Makes no sense. Period." for punchy closer
- "I'm here for it" for endorsement
- "#stayready" "#staytuned" for hashtags

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
        # Step 1: Use WEIGHTED retrieval based on category + channel
        # This automatically prioritizes the right tags for each content type
        persona_query = f"persona voice style {req.topic} {req.category} content writing"
        persona_embedding = embed_text(persona_query)
        
        persona_chunks = retrieve_weighted(
            user_id=req.user_id,
            query_embedding=persona_embedding,
            category=req.category,  # value, sales, or personal
            channel=req.content_type,  # linkedin_post, linkedin_dm, cold_email, instagram_post
            top_k=7,  # Get more chunks since they're now properly weighted
        )
        
        # Log what tags were retrieved for debugging
        if persona_chunks:
            tag_summary = {}
            for chunk in persona_chunks:
                tag = chunk.get("persona_tag", "UNKNOWN")
                tag_summary[tag] = tag_summary.get(tag, 0) + 1
            print(f"[content_gen] Retrieved persona chunks by tag: {tag_summary}", flush=True)
        
        # Step 2: Retrieve high-performing content examples (still use standard retrieval)
        examples_query = f"high performing content example {req.content_type} {req.category} {req.topic}"
        examples_embedding = embed_text(examples_query)
        example_chunks = retrieve_similar(
            user_id=req.user_id,
            query_embedding=examples_embedding,
            top_k=3,
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
        
        system_message = """You are a ghostwriter who perfectly mimics a specific person's voice.

CRITICAL RULES:
1. Use the EXACT voice patterns from the persona data (casual phrases, rhythm, signature expressions)
2. ONLY use stories, anecdotes, and facts EXPLICITLY mentioned in the persona data below
3. NEVER invent or fabricate stories - if no relevant story exists, speak generally about the topic
4. DO NOT make up family stories, childhood memories, or personal details not in the persona
5. Preserve casual markers like "Yall", "Tell you what tho", "Say it with me"
6. Keep punchy rhythm - short sentences, stacked phrases
7. DO NOT over-polish or make it sound generic/corporate
8. Stay focused on the user's TOPIC and CONTEXT - don't drift to unrelated subjects

ANTI-HALLUCINATION: If you cannot find a relevant real story in the persona data, write value-driven content about the topic WITHOUT inventing personal anecdotes. Generic insights are better than fake stories.

CONTEXTUAL RELEVANCE: Only include personal details when they're relevant to the topic:
- "Son of a mechanic" - ONLY use if topic relates to family, work ethic, blue collar values, or personal background
- "Can't be put in a box" - ONLY use if topic relates to identity, career pivots, or being multifaceted
- Don't shoehorn personal details into unrelated topics (e.g., don't mention mechanic dad in a post about supply chains)
- Each option should feel fresh and directly address the user's topic/context

If the persona uses casual language, USE IT. Do not "clean it up" into formal English."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,  # Slightly higher for more natural variation
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

