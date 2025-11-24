from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import logging
from app.models.playbooks import (
    PlaybookListResponse, PlaybookResponse, PlaybookRunRequest,
    PlaybookRunResponse, ExecutionListResponse
)
from app.services.playbook_service import (
    get_playbook, list_playbooks, toggle_favorite,
    record_execution, list_executions
)

logger = logging.getLogger(__name__)
router = APIRouter()

PLAYBOOK_SUMMARY = {
    "movement": "AI Advantage (Tony Robbins & Dean Graziosi) ensures real humans gain confidence, clarity, and momentum with AI.",
    "audience": "Entrepreneurs, coaches, creators, and professionals who need leverage—not hype.",
    "principles": [
        "Human-first: practical, clear, direct, action-oriented guidance.",
        "Workflow-driven: choose one tool, train it, start with the most pressing prompt, iterate.",
        "Confidence through quick wins: curated tools, onboarding, and prompts that create momentum.",
    ],
}

ONBOARDING_PROMPT = (
    "I want you to act as my personal AI assistant starting today. Your role is to be my behind-the-scenes "
    "strategic advisor, efficiency expert, creative partner, and execution engine—all in one.\n\n"
    "From now on, treat every question, task, or request I bring to you with the mindset of a world-class operator "
    "who understands business, marketing, content, systems, and personal development. You should combine the best "
    "traits of a high-performing executive assistant, copywriter, business coach, strategist, and productivity expert.\n\n"
    "You are clear, direct, thoughtful, and deeply practical. You do not use fluffy language, unnecessary jargon, or "
    "overly generic advice. Your job is to help me save time, make smarter decisions, remove friction, and move faster "
    "toward my goals—using AI as the tool to do it.\n\n"
    "Before we begin, I’m going to tell you everything you need to know about me, my goals, & how I want to use AI. "
    "Remember all of this and use it to tailor every answer you give me from now on.\n\n"
    "Right now, I work as a (insert your role) in the (insert your industry) space, or I run a (insert type of business) business. "
    "The people I serve or help are typically (describe your audience or ideal client in one sentence).\n\n"
    "Over the next 6 to 12 months, I have a few big goals I want to accomplish. First, I want to (insert goal #1). I’d also love to "
    "(insert goal #2) and ideally (insert goal #3 if applicable).\n\n"
    "The biggest challenge I’m facing right now is (insert your biggest frustration, bottleneck, or roadblock). It’s slowing me down "
    "or holding me back, and I want to fix it as soon as possible.\n\n"
    "When it comes to using AI, I’m looking for help with (insert the ways you’d like AI to support you—e.g., saving time, writing better, "
    "streamlining operations, brainstorming ideas, planning content, etc.). I don’t need hype—I just want AI to help me work smarter and "
    "get real results. Right now, the tools I use most often are (list tools—e.g., ChatGPT, Google Docs, Canva, Zoom, Notion, Zapier, etc.). "
    "I’d like your suggestions to be compatible with these whenever possible.\n\n"
    "I tend to prefer a (insert your preferred tone—e.g., expert, friendly, concise, storytelling, etc.) communication style. I usually create "
    "things like (list the content types you’re involved in—e.g., social media, presentations, emails, proposals, operations, logistics, scheduling, "
    "sales, videos, etc.) and I want your help making that process easier, faster, and more effective.\n\n"
    "If it helps, I also work within a few systems or routines like (insert systems—e.g., content calendar, launch framework, weekly check-ins, CRM follow-up, etc.).\n\n"
    "If I could take one task off my plate this week, it would be (insert the most draining or repetitive task you’d love to eliminate). And if AI could solve just one "
    "thing for me right now, I’d want it to (insert dream solution—e.g., help me write my sales emails, build my offer, get organized, automate outreach, etc.).\n\n"
    "Now that you know who I am, what I care about, and what I’m trying to build—act accordingly. Be smart. Be strategic. Be fast. Help me move like the most optimized "
    "version of myself."
)

STARTER_PROMPTS = [
    {
        "id": "remove_roadblocks_fast",
        "title": "Remove Roadblocks Fast",
        "description": "Identify bottlenecks AI can eliminate this week.",
        "prompt": "What are 3 bottlenecks in my [business type] that AI could help remove this week? Prioritize quick wins that would give me more time or momentum. Ask me any questions you have if you need more context.",
    },
    {
        "id": "reclaim_your_time",
        "title": "Reclaim Your Time",
        "description": "Automate a weekly workflow to save 3+ hours.",
        "prompt": "Based on my business model, recommend one AI automation that would save me 3+ hours weekly. Walk me through how to set it up step by step, and feel free to ask me clarifying questions if you need more info.",
    },
    {
        "id": "stay_visible_without_burnout",
        "title": "Stay Visible Without Burnout",
        "description": "Low-effort content plan (<2 hours per week).",
        "prompt": "Create a content plan using AI that keeps me consistent and visible online, without spending more than 2 hours per week. Make it simple to follow and check in if you need details about my audience or style.",
    },
    {
        "id": "personal_focus_coach",
        "title": "Personal Focus Coach",
        "description": "Improve focus, prioritization, and time management.",
        "prompt": "I struggle with focus and staying organized. What AI tools and workflows can help me prioritize better, reduce distractions, & manage my time better?",
    },
    {
        "id": "mindset_reset",
        "title": "Mindset Reset For AI Confidence",
        "description": "Shift beliefs that block consistent AI use.",
        "prompt": "Act as a mindset coach. What beliefs might be holding me back from using AI consistently, and how can I shift my thinking to feel more confident and in control?",
    },
    {
        "id": "elevate_customer_experience",
        "title": "Elevate Customer Experience",
        "description": "Delight clients with affordable AI-powered improvements.",
        "prompt": "Give me 3 ways I can improve the experience of my clients or customers using free or low-cost AI tools. Prioritize fast and affordable options. Feel free to ask me clarifying questions if you need more info.",
    },
    {
        "id": "content_that_converts",
        "title": "Content That Converts (Faster)",
        "description": "Boost offer clarity, urgency, and trust.",
        "prompt": "I want to improve conversions for my offer [insert offer]. Analyze it and give me 3 ways to improve clarity, urgency, or trust using AI prompts or feedback loops. Ask questions if you need more context.",
    },
    {
        "id": "make_smarter_decisions",
        "title": "Make Smarter Business Decisions",
        "description": "Use AI to evaluate a key decision this week.",
        "prompt": "Based on my current business goals and challenges, what’s one decision I could use AI to help me make smarter or faster this week? Give me an example of how to use a tool to do it.",
    },
    {
        "id": "streamline_repetitive_tasks",
        "title": "Streamline Repetitive Tasks",
        "description": "Delegate draining tasks to AI with concrete steps.",
        "prompt": "What are 3 repetitive tasks I do each week that I could delegate to AI? Suggest the right tools and give me steps to set one up now. Ask me follow-up questions if needed.",
    },
    {
        "id": "futureproof_skills",
        "title": "Future-Proof Your Skills",
        "description": "Identify high-impact AI skills to learn next.",
        "prompt": "Act as a career coach: based on current trends, what 3 AI skills should I learn to become irreplaceable in my field or industry?",
    },
    {
        "id": "bonus_power_prompt",
        "title": "Bonus: Conversation That Changes Everything",
        "description": "Invite the AI to propose bold ideas tailored to the user.",
        "prompt": "Based on everything you know about me, my business, and my goals, what are some of the most powerful ways you believe AI could support me right now? Don’t hold back—give me ideas I might not have considered, ask me clarifying questions if needed, and help me uncover opportunities to save time, grow faster, or improve my day-to-day flow.",
    },
]


@router.get("/summary")
async def get_playbook_summary():
    return PLAYBOOK_SUMMARY


@router.get("/onboarding")
async def get_onboarding_prompt():
    return {"prompt": ONBOARDING_PROMPT}


@router.get("/prompts")
async def get_starter_prompts():
    return {"prompts": STARTER_PROMPTS}


# Enhanced endpoints

@router.get("", response_model=PlaybookListResponse)
async def list_playbooks_endpoint(
    user_id: Optional[str] = Query(None, description="User identifier"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
) -> Dict[str, Any]:
    """List all playbooks."""
    try:
        playbooks = list_playbooks(user_id=user_id, is_favorite=is_favorite)
        return PlaybookListResponse(
            success=True,
            playbooks=playbooks,
            total=len(playbooks)
        )
    except Exception as e:
        logger.exception(f"Error listing playbooks: {e}")
        return PlaybookListResponse(success=True, playbooks=[], total=0)


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook_endpoint(
    playbook_id: str,
    user_id: Optional[str] = Query(None, description="User identifier")
) -> Dict[str, Any]:
    """Get a playbook by ID."""
    playbook = get_playbook(playbook_id, user_id=user_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return PlaybookResponse(success=True, playbook=playbook)


@router.post("/{playbook_id}/favorite", response_model=PlaybookResponse)
async def toggle_playbook_favorite(
    playbook_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Toggle favorite status of a playbook."""
    new_status = toggle_favorite(playbook_id, user_id)
    if new_status is None:
        raise HTTPException(status_code=500, detail="Failed to toggle favorite")
    
    playbook = get_playbook(playbook_id, user_id=user_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    return PlaybookResponse(success=True, playbook=playbook)


@router.post("/{playbook_id}/run", response_model=PlaybookRunResponse)
async def run_playbook(
    playbook_id: str,
    request: PlaybookRunRequest
) -> Dict[str, Any]:
    """Run a playbook with input."""
    playbook = get_playbook(playbook_id, user_id=request.user_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    # For now, return the input as output (would use LLM in production)
    output = f"Playbook '{playbook.name}' executed with input: {request.input[:100]}..."
    
    # Record execution
    execution_id = record_execution(
        playbook_id=playbook_id,
        user_id=request.user_id,
        input_text=request.input,
        output_text=output,
        metadata=request.metadata
    )
    
    return PlaybookRunResponse(
        success=True,
        execution_id=execution_id,
        output=output,
        playbook_id=playbook_id,
        playbook_name=playbook.name
    )


@router.get("/{playbook_id}/executions", response_model=ExecutionListResponse)
async def get_playbook_executions(
    playbook_id: str,
    user_id: Optional[str] = Query(None, description="User identifier"),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    """Get execution history for a playbook."""
    playbook = get_playbook(playbook_id, user_id=user_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    executions = list_executions(playbook_id=playbook_id, user_id=user_id, limit=limit)
    return ExecutionListResponse(
        success=True,
        executions=executions,
        total=len(executions)
    )


@router.get("/favorites/list", response_model=PlaybookListResponse)
async def get_favorite_playbooks(
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get favorited playbooks for a user."""
    playbooks = list_playbooks(user_id=user_id, is_favorite=True)
    return PlaybookListResponse(
        success=True,
        playbooks=playbooks,
        total=len(playbooks)
    )
