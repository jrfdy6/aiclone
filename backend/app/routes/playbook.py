"""
Playbook Routes

API endpoints for playbook-related functionality.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/summary")
async def get_playbook_summary():
    """Get playbook summary information."""
    return {
        "success": True,
        "message": "Playbook summary endpoint",
        "data": {
            "movement": "AI Advantage",
            "audience": "Entrepreneurs and business owners",
            "principles": [
                "Human-first approach",
                "Action-oriented",
                "Clear and practical guidance"
            ]
        }
    }


@router.get("/onboarding")
async def get_onboarding_prompt():
    """Get onboarding prompt template."""
    return {
        "success": True,
        "prompt": """I want to train my AI assistant. Here's my context:

Role: [Your role]
Audience: [Who you work with]
Top 3 Goals: [List your goals]
Biggest Challenge: [Your main challenge]
AI Expectations: [What you want AI to help with]
Tone: [Your preferred communication style]
Content Types: [Types of content you create]
Systems: [Tools/platforms you use]
Dream Outcome: [What success looks like]"""
    }


@router.get("/prompts")
async def get_starter_prompts():
    """Get curated starter prompts."""
    return {
        "success": True,
        "prompts": [
            {
                "id": "remove_bottlenecks",
                "title": "Remove Bottlenecks",
                "prompt": "What are the biggest bottlenecks in my workflow right now?"
            },
            {
                "id": "save_time",
                "title": "Save Time / Automate",
                "prompt": "How can I automate repetitive tasks to save time?"
            },
            {
                "id": "stay_visible",
                "title": "Stay Visible with Less Effort",
                "prompt": "What's the most effective way to stay visible with minimal effort?"
            },
            {
                "id": "improve_focus",
                "title": "Improve Focus / Mindset",
                "prompt": "How can I improve my focus and maintain the right mindset?"
            },
            {
                "id": "elevate_customer",
                "title": "Elevate Customer Experience",
                "prompt": "What changes would most elevate the customer experience?"
            }
        ]
    }
