"""
Content Topic Library - Pre-built topics for PACER content pillars.

This replaces LinkedIn scraping by providing curated, evergreen topics
that can be used for content generation.
"""

from typing import List, Dict, Any
from app.models.linkedin_content import ContentPillar


# Referral Topics (40% of content)
REFERRAL_TOPICS = [
    "Supporting neurodivergent learners during transition periods",
    "Building stronger K-12 → treatment center partnerships",
    "What mental health teams wish educators understood",
    "The importance of early intervention in student support",
    "Collaborative approaches between schools and mental health professionals",
    "Navigating IEP meetings with empathy and clarity",
    "Supporting students with anxiety in educational settings",
    "The role of school counselors in student success",
    "Building trust between families and educational support teams",
    "Transition planning for students moving between educational settings",
    "The impact of trauma-informed care in schools",
    "Supporting students with ADHD in traditional classrooms",
    "Mental health awareness in private school settings",
    "Creating safe spaces for neurodivergent students",
    "The value of multidisciplinary teams in student support",
    "Supporting families navigating educational challenges",
    "Early identification of learning differences",
    "The importance of communication between educators and therapists",
    "Supporting students with executive functioning challenges",
    "Building resilience in students facing academic and social challenges",
    "The role of accommodations in student success",
    "Supporting students during major life transitions",
    "Mental health resources for private school communities",
    "The intersection of education and mental health support",
    "Building partnerships between schools and external support providers",
    "Supporting students with learning differences",
    "The importance of individualized support plans",
    "Mental health first aid for educators",
    "Supporting students with social-emotional learning needs",
    "The value of early screening and assessment",
    "Creating inclusive environments for all learners",
    "Supporting families in navigating complex support systems",
    "The role of case management in student success",
    "Mental health support for educators themselves",
    "Building bridges between academic and therapeutic support",
    "Supporting students with co-occurring learning and mental health needs",
    "The importance of cultural competency in student support",
    "Supporting students with autism spectrum disorders in school",
    "The value of peer support programs",
    "Building stronger relationships with referring professionals",
    "Supporting students with depression and anxiety",
    "The role of data in tracking student progress",
    "Mental health crisis intervention in schools",
    "Supporting students with eating disorders",
    "The importance of confidentiality in student support",
    "Building community partnerships for student support",
    "Supporting students with substance use challenges",
    "The value of ongoing communication with families",
    "Mental health support during exam periods",
    "Supporting students with grief and loss",
    "The role of mindfulness in educational settings",
]

# Thought Leadership Topics (50% of content)
THOUGHT_LEADERSHIP_TOPICS = [
    "AI's role in student success prediction",
    "Ethical AI guardrails in private schools",
    "How small teams can scale with automation",
    "The future of personalized learning technology",
    "AI-powered early intervention systems",
    "Building ethical AI tools for education",
    "The intersection of AI and mental health support",
    "How EdTech companies can prioritize student privacy",
    "The role of AI in identifying at-risk students",
    "Automation in administrative tasks for educators",
    "AI as a co-teacher in K-12 settings",
    "The future of adaptive learning platforms",
    "Building AI tools that educators actually want to use",
    "The importance of human-in-the-loop AI systems",
    "How AI can support neurodivergent learners",
    "The ethics of predictive analytics in education",
    "AI-powered tools for student engagement",
    "The role of data science in education",
    "How automation can free educators to focus on relationships",
    "Building scalable solutions for small EdTech teams",
    "The future of student data analytics",
    "AI tools for early childhood education",
    "The importance of explainable AI in education",
    "How AI can support differentiated instruction",
    "The role of machine learning in educational assessment",
    "Building AI tools that respect student autonomy",
    "The future of virtual learning assistants",
    "AI-powered tools for reading intervention",
    "How automation can improve educational equity",
    "The role of AI in special education support",
    "Building ethical AI for K-12 education",
    "The future of AI-powered tutoring systems",
    "How small EdTech companies can compete with big tech",
    "The importance of user-centered design in EdTech",
    "AI tools for supporting executive functioning",
    "The role of AI in reducing educator burnout",
    "Building AI systems that learn from educators",
    "The future of AI in curriculum development",
    "How automation can improve student outcomes",
    "The ethics of AI in educational decision-making",
    "AI-powered tools for social-emotional learning",
    "The role of AI in supporting multilingual learners",
    "Building AI tools that prioritize accessibility",
    "The future of AI in educational research",
    "How automation can support personalized learning paths",
    "The importance of AI literacy for educators",
    "AI tools for supporting students with dyslexia",
    "The role of AI in educational equity initiatives",
    "Building AI systems that educators trust",
    "The future of AI-powered learning analytics",
]

# Stealth Founder Topics (10% of content - subtle, authentic)
STEALTH_FOUNDER_TOPICS = [
    "What I've learned building tools for overstretched educators",
    "Why I believe personalization will define the next decade of EdTech",
    "Three mistakes I made building my first EdTech product",
    "What I wish I knew before starting an EdTech company",
    "The moment I realized we were building the right thing",
    "Why I left big tech to build for education",
    "What educators taught me about product design",
    "The unexpected challenges of building in EdTech",
    "Why I'm betting on AI in education (even when others aren't)",
    "What I've learned from 100+ conversations with educators",
    "The problem nobody is talking about in EdTech",
    "Why building slowly can be a competitive advantage",
    "What I've learned about building products that actually get used",
    "The importance of building for underserved markets",
    "Why I'm optimistic about the future of EdTech",
    "What I've learned about fundraising as a stealth founder",
    "The problem with 'disrupting' education",
    "Why building for educators is different (and harder)",
    "What I've learned about product-market fit in EdTech",
    "The moment I knew we had something special",
]


def get_topics_for_pillar(pillar: ContentPillar, limit: int = None) -> List[str]:
    """
    Get topics for a specific content pillar.
    
    Args:
        pillar: Content pillar type
        limit: Optional limit on number of topics to return
        
    Returns:
        List of topic strings
    """
    topic_map = {
        ContentPillar.REFERRAL: REFERRAL_TOPICS,
        ContentPillar.THOUGHT_LEADERSHIP: THOUGHT_LEADERSHIP_TOPICS,
        ContentPillar.STEALTH_FOUNDER: STEALTH_FOUNDER_TOPICS,
        ContentPillar.MIXED: THOUGHT_LEADERSHIP_TOPICS + REFERRAL_TOPICS[:20],  # Mix for MIXED pillar
    }
    
    topics = topic_map.get(pillar, [])
    
    if limit:
        topics = topics[:limit]
    
    return topics


def select_topic_for_generation(
    pillar: ContentPillar,
    used_topics: List[str] = None,
    preferred_topics: List[str] = None,
) -> str:
    """
    Select a topic for content generation, avoiding recently used topics.
    
    Args:
        pillar: Content pillar type
        used_topics: List of recently used topics to avoid
        preferred_topics: Optional list of preferred topics (from research/learning)
        
    Returns:
        Selected topic string
    """
    available_topics = get_topics_for_pillar(pillar)
    
    # Filter out recently used topics
    if used_topics:
        available_topics = [t for t in available_topics if t not in used_topics]
    
    # If preferred topics provided, prioritize them
    if preferred_topics:
        preferred_available = [t for t in preferred_topics if t in available_topics]
        if preferred_available:
            # Return a random topic from preferred (for now, just return first)
            # In production, you might want to randomize or weight by learning data
            return preferred_available[0]
    
    # If no available topics after filtering, fall back to all topics
    if not available_topics:
        available_topics = get_topics_for_pillar(pillar)
    
    # Return first available (in production, you might want to randomize)
    return available_topics[0] if available_topics else "Industry insights and trends"


def get_all_topics() -> Dict[str, List[str]]:
    """Get all topics organized by pillar."""
    return {
        "referral": REFERRAL_TOPICS,
        "thought_leadership": THOUGHT_LEADERSHIP_TOPICS,
        "stealth_founder": STEALTH_FOUNDER_TOPICS,
    }

