"""
Comprehensive Content Generator Service

Generates 100+ variations across 20+ content types with support for:
- Human-ready format (copy/paste)
- JSON payloads (backend ingestion)
- Both formats simultaneously
"""

import json
import re
import time
from typing import List, Dict, Any, Optional
from app.models.comprehensive_content import (
    ContentType,
    ContentFormat,
    ContentVariation,
    HookType,
    HashtagCategory,
)
from app.models.linkedin_content import ContentPillar
from app.services.perplexity_client import get_perplexity_client
from app.services.content_topic_library import select_topic_for_generation, get_topics_for_pillar


# Hashtag Sets by Category
HASHTAG_SETS = {
    HashtagCategory.INDUSTRY: [
        "#EdTech", "#Education", "#K12", "#PrivateSchools", "#EdLeaders",
        "#SchoolLeadership", "#EducationInnovation", "#FutureOfEducation",
        "#StudentSuccess", "#EducationalTechnology", "#K12Education",
        "#SchoolManagement", "#EducationTrends", "#EdTechStartup",
    ],
    HashtagCategory.AI_LEADERSHIP: [
        "#AIinEducation", "#ArtificialIntelligence", "#EdTechAI", "#AILeaders",
        "#MachineLearning", "#EdTechInnovation", "#AIforGood",
        "#EducationalAI", "#TechInEducation", "#FutureOfWork",
        "#Automation", "#DigitalTransformation", "#InnovationInEducation",
    ],
    HashtagCategory.REFERRAL_PARTNER: [
        "#ReferralNetwork", "#Partnership", "#MentalHealth", "#TreatmentCenters",
        "#SchoolPartnerships", "#StudentSupport", "#EducationalPartners",
        "#ReferralSystem", "#Collaboration", "#SupportServices",
    ],
    HashtagCategory.NEURODIVERSITY_SUPPORT: [
        "#Neurodiversity", "#SpecialNeeds", "#AutismAwareness", "#ADHDSupport",
        "#InclusiveEducation", "#SpecialEducation", "#LearningDifferences",
        "#StudentSupport", "#IEP", "#Accommodations",
    ],
    HashtagCategory.TRENDING: [
        "#Education", "#Innovation", "#Leadership", "#Growth", "#Learning",
        "#Teaching", "#School", "#Technology", "#Startup", "#Business",
    ],
}

# Engagement Hook Templates
HOOK_TEMPLATES = {
    HookType.CURIOSITY: [
        "What if I told you...",
        "Here's something most people don't know about...",
        "You probably think... but here's what actually happens...",
        "The biggest mistake I see in...",
        "Most people get this wrong about...",
    ],
    HookType.CONTRARIAN: [
        "Everyone's saying... I disagree.",
        "The unpopular truth about...",
        "Stop doing... (do this instead)",
        "The advice everyone gives is wrong. Here's why...",
    ],
    HookType.DATA: [
        "{data_point}% of... but only {smaller}% actually...",
        "Here's the data that changed how I think about...",
        "The numbers don't lie: ...",
        "I analyzed {number} cases and found...",
    ],
    HookType.FOUNDER_LESSONS: [
        "I made {number} mistakes building... Here's what I learned:",
        "The moment I realized... changed everything.",
        "Building {thing} taught me...",
    ],
    HookType.OPERATIONAL_INSIGHTS: [
        "Here's how we reduced {metric} by {percentage}%:",
        "The one operational change that saved us {time/money}:",
        "Most {role}s struggle with... Here's the fix:",
    ],
}


def generate_content_variations(
    content_type: ContentType,
    num_variations: int,
    pillar: Optional[str] = None,
    topic: Optional[str] = None,
    hook_type: Optional[HookType] = None,
    hashtag_category: Optional[HashtagCategory] = None,
    tone: str = "expert, direct, inspiring",
) -> List[ContentVariation]:
    """
    Generate variations of a specific content type.
    
    This is the core generator that creates 100+ variations across all types.
    """
    variations = []
    perplexity_client = get_perplexity_client()
    
    # Select topic if not provided
    if not topic:
        pillar_enum = ContentPillar(pillar) if pillar else ContentPillar.THOUGHT_LEADERSHIP
        topic = select_topic_for_generation(pillar=pillar_enum)
    
    # Build generation prompt based on content type
    prompt = build_content_type_prompt(
        content_type=content_type,
        topic=topic,
        pillar=pillar,
        hook_type=hook_type,
        hashtag_category=hashtag_category,
        tone=tone,
        num_variations=num_variations,
    )
    
    # Generate using LLM (batch generation for efficiency)
    try:
        result = perplexity_client.search(
            query=prompt,
            model="sonar",
            return_sources=False,
        )
        
        # Parse response (should be JSON array of variations)
        answer = result.answer
        json_match = re.search(r'\[.*\]', answer, re.DOTALL)
        
        if json_match:
            variations_data = json.loads(json_match.group())
            for i, var_data in enumerate(variations_data[:num_variations], 1):
                variations.append(ContentVariation(
                    variation_number=i,
                    content=var_data.get("content", ""),
                    suggested_hashtags=var_data.get("suggested_hashtags", []),
                    engagement_hook=var_data.get("engagement_hook"),
                    metadata=var_data.get("metadata", {}),
                ))
        else:
            # Fallback: split response into variations
            content_parts = answer.split("\n\n---\n\n")[:num_variations]
            for i, content in enumerate(content_parts, 1):
                variations.append(ContentVariation(
                    variation_number=i,
                    content=content.strip(),
                    suggested_hashtags=[],
                ))
                
    except Exception as e:
        # Fallback variations
        for i in range(num_variations):
            variations.append(ContentVariation(
                variation_number=i + 1,
                content=f"[{content_type.value} Variation {i+1}]: {topic}\n\nThis is a placeholder. In production, this would be fully generated content.",
                suggested_hashtags=[],
            ))
    
    return variations


def build_content_type_prompt(
    content_type: ContentType,
    topic: str,
    pillar: Optional[str] = None,
    hook_type: Optional[HookType] = None,
    hashtag_category: Optional[HashtagCategory] = None,
    tone: str = "expert, direct, inspiring",
    num_variations: int = 1,
) -> str:
    """Build a specialized prompt for each content type."""
    
    content_specs = {
        # LinkedIn Posts
        ContentType.LINKEDIN_POST: {
            "template": "LinkedIn post (1500-3000 chars, professional, valuable)",
            "structure": "Hook -> Insight -> Practical takeaways (1-3 bullets) -> CTA",
        },
        ContentType.LINKEDIN_STORY_POST: {
            "template": "LinkedIn story-style post (personal narrative, authentic, vulnerable)",
            "structure": "Personal story -> Lesson learned -> Universal application",
        },
        ContentType.LINKEDIN_DATA_POST: {
            "template": "Data-driven LinkedIn post (stats, research, insights)",
            "structure": "Data point -> Context -> Implications -> Question",
        },
        ContentType.LINKEDIN_CAROUSEL_SCRIPT: {
            "template": "LinkedIn carousel script (10-15 slides, each with headline + 1-2 bullets)",
            "structure": "Slide 1: Hook, Slides 2-14: Content, Slide 15: CTA",
        },
        
        # Video Scripts
        ContentType.REELS_7SEC_HOOK: {
            "template": "7-second Reels hook (attention-grabbing, compelling)",
            "structure": "Hook -> Quick value statement -> Visual direction",
        },
        ContentType.REELS_30SEC_VALUE: {
            "template": "30-second Reels value drop (concise, actionable)",
            "structure": "Hook (3s) -> Value (20s) -> CTA (7s)",
        },
        
        # Email
        ContentType.EMAIL_NEWSLETTER_WEEKLY: {
            "template": "Weekly newsletter email (value-focused, engaging)",
            "structure": "Subject line -> Opening -> 3-5 insights -> CTA",
        },
        
        # Outreach
        ContentType.OUTREACH_CONNECTION_REQUEST: {
            "template": "LinkedIn connection request (personalized, brief)",
            "structure": "Personal connection point -> Value proposition -> Request",
        },
    }
    
    spec = content_specs.get(content_type, {
        "template": f"{content_type.value} content",
        "structure": "Standard format",
    })
    
    prompt_parts = [
        f"Generate {num_variations} variations of {content_type.value}.",
        f"Template: {spec['template']}",
        f"Structure: {spec['structure']}",
        f"Topic: {topic}",
    ]
    
    if pillar:
        prompt_parts.append(f"Pillar: {pillar}")
    
    prompt_parts.extend([
        f"Tone: {tone}",
        "",
        "Output JSON array:",
        "[",
        "  {",
        '    "content": "...",',
        '    "suggested_hashtags": ["#..."],',
        '    "engagement_hook": "...",',
        '    "metadata": {}',
        "  },",
        "  ...",
        "]",
    ])
    
    return "\n".join(prompt_parts)


def format_as_human_readable(
    content_type: ContentType,
    variations: List[ContentVariation],
) -> str:
    """Format variations as human-readable, copy-paste ready content."""
    
    output_parts = [
        f"=== {content_type.value.replace('_', ' ').title()} ===",
        f"Generated {len(variations)} variations",
        "",
    ]
    
    for var in variations:
        output_parts.extend([
            f"--- Variation {var.variation_number} ---",
            var.content,
            "",
        ])
        
        if var.suggested_hashtags:
            output_parts.append(f"Hashtags: {', '.join(var.suggested_hashtags)}")
            output_parts.append("")
        
        if var.engagement_hook:
            output_parts.append(f"Engagement Hook: {var.engagement_hook}")
            output_parts.append("")
        
        output_parts.append("---")
        output_parts.append("")
    
    return "\n".join(output_parts)


def format_as_json_payloads(
    content_type: ContentType,
    variations: List[ContentVariation],
    user_id: str,
) -> List[Dict[str, Any]]:
    """Format variations as JSON payloads ready for backend ingestion."""
    
    payloads = []
    
    for var in variations:
        payload = {
            "content_type": content_type.value,
            "variation_number": var.variation_number,
            "content": var.content,
            "suggested_hashtags": var.suggested_hashtags,
            "engagement_hook": var.engagement_hook,
            "metadata": var.metadata,
            "user_id": user_id,
            "created_at": time.time(),
        }
        payloads.append(payload)
    
    return payloads


def generate_hashtag_set(category: HashtagCategory, num: int = 10) -> List[str]:
    """Generate hashtag set for a specific category."""
    hashtags = HASHTAG_SETS.get(category, [])
    return hashtags[:num]


def generate_engagement_hooks(hook_type: HookType, num: int = 5, topic: Optional[str] = None) -> List[str]:
    """Generate engagement hooks of a specific type."""
    templates = HOOK_TEMPLATES.get(hook_type, [])
    
    # In production, these would be filled by LLM
    hooks = []
    for i, template in enumerate(templates[:num]):
        if topic:
            hook = template.replace("{topic}", topic)
        else:
            hook = template
        hooks.append(hook)
    
    return hooks if hooks else [f"[{hook_type.value} hook {i+1}]" for i in range(num)]

