"""
Topic Intelligence Models
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class IntelligenceTheme(str, Enum):
    """The 7 intelligence themes"""
    ENROLLMENT_MANAGEMENT = "enrollment_management"
    NEURODIVERGENT_SUPPORT = "neurodivergent_support"
    AI_IN_EDUCATION = "ai_in_education"
    REFERRAL_NETWORKS = "referral_networks"
    FASHION_TECH = "fashion_tech"
    ENTREPRENEURSHIP_OPS = "entrepreneurship_ops"
    CONTENT_MARKETING = "content_marketing"


# Master Google Dork Templates for each theme
THEME_DORKS: Dict[IntelligenceTheme, List[str]] = {
    IntelligenceTheme.ENROLLMENT_MANAGEMENT: [
        '"enrollment management" "K-12" best practices',
        '"private school admissions" challenges 2024',
        '"independent school" enrollment strategy',
        '"admissions director" interview education',
        '"enrollment funnel" private school',
        'site:nais.org enrollment trends',
        '"boarding school" admissions process',
        '"tuition assistance" private school strategy',
        '"open house" admissions conversion',
        '"yield rate" private school',
        '"enrollment decline" independent school solutions',
        '"waitlist management" admissions',
        '"parent communication" admissions process',
        '"school marketing" enrollment growth',
        '"admissions CRM" education',
        '"re-enrollment" retention strategy school',
        '"financial aid" private school process',
        '"diversity enrollment" independent school',
        '"international student" admissions K-12',
        '"virtual tour" school admissions',
    ],
    IntelligenceTheme.NEURODIVERGENT_SUPPORT: [
        '"neurodivergent students" "private school" support',
        '"one-to-one care model" education',
        '"autism support" learning environment',
        '"ADHD accommodations" school program',
        '"learning differences" private school',
        '"executive function" support education',
        '"sensory friendly" classroom',
        '"IEP" private school implementation',
        '"twice exceptional" education program',
        '"neurodiversity" school culture',
        '"social emotional learning" neurodivergent',
        '"occupational therapy" school integration',
        '"speech therapy" educational setting',
        '"behavioral support" school program',
        '"transition planning" neurodivergent students',
        '"parent advocacy" neurodivergent education',
        '"inclusive classroom" strategies',
        '"differentiated instruction" learning differences',
        '"assistive technology" education',
        '"neurodivergent" "program director" interview',
    ],
    IntelligenceTheme.AI_IN_EDUCATION: [
        '"AI in education" trends 2024',
        '"edtech" artificial intelligence classroom',
        '"personalized learning" AI platform',
        '"adaptive learning" technology education',
        '"AI tutor" student outcomes',
        'site:edsurge.com AI education',
        'site:educause.edu artificial intelligence',
        '"generative AI" classroom policy',
        '"ChatGPT" education use cases',
        '"AI assessment" student learning',
        '"machine learning" education research',
        '"AI literacy" K-12 curriculum',
        '"intelligent tutoring system" effectiveness',
        '"AI ethics" education teaching',
        '"automated grading" AI education',
        '"learning analytics" AI platform',
        '"AI content creation" education',
        '"natural language processing" education',
        '"AI detection" academic integrity',
        '"edtech startup" AI funding',
    ],
    IntelligenceTheme.REFERRAL_NETWORKS: [
        '"educational consultant" referral network',
        '"therapist" "private school" referral',
        '"treatment center" educational placement',
        '"school counselor" referral process',
        '"mental health professional" school partnership',
        'site:psychologytoday.com educational consultant',
        '"wilderness therapy" school transition',
        '"therapeutic boarding school" referral',
        '"IEC" independent educational consultant',
        '"college counselor" referral network',
        '"family therapist" school recommendation',
        '"neuropsychologist" school placement',
        '"educational advocate" services',
        '"transition specialist" education',
        '"case manager" educational services',
        '"outpatient treatment" school coordination',
        '"residential treatment" educational component',
        '"behavioral health" school referral',
        '"special needs" placement consultant',
        '"IECA" member educational consultant',
    ],
    IntelligenceTheme.FASHION_TECH: [
        '"wardrobe app" features review',
        '"outfit coordination" AI technology',
        '"closet organization" app comparison',
        '"fashion tech" startup funding',
        '"virtual closet" user experience',
        '"style recommendation" algorithm',
        '"capsule wardrobe" app',
        '"fashion AI" personalization',
        '"clothing inventory" app features',
        '"outfit planner" technology',
        'site:producthunt.com wardrobe app',
        'site:reddit.com/r/malefashionadvice wardrobe app',
        'site:reddit.com/r/femalefashionadvice closet app',
        '"sustainable fashion" app technology',
        '"color coordination" outfit algorithm',
        '"mix and match" clothing app',
        '"fashion recommendation engine"',
        '"personal stylist" AI app',
        '"wardrobe analytics" features',
        '"outfit tracking" app review',
    ],
    IntelligenceTheme.ENTREPRENEURSHIP_OPS: [
        '"operations scaling" startup best practices',
        '"program management" education sector',
        '"founder operations" playbook',
        '"startup efficiency" frameworks',
        'site:hbr.org operations management',
        '"systems thinking" business operations',
        '"process automation" small business',
        '"operational excellence" education',
        '"team scaling" startup guide',
        '"SOPs" small business creation',
        '"workflow optimization" founder',
        '"delegation framework" entrepreneur',
        '"hiring playbook" startup',
        '"remote operations" management',
        '"KPI dashboard" operations',
        '"business systems" entrepreneur',
        '"lean operations" startup',
        '"operational efficiency" metrics',
        '"founder burnout" prevention operations',
        '"business process" documentation startup',
    ],
    IntelligenceTheme.CONTENT_MARKETING: [
        '"LinkedIn strategy" B2B 2024',
        '"thought leadership" LinkedIn content',
        '"LinkedIn algorithm" best practices',
        '"content marketing" education sector',
        '"personal branding" LinkedIn professional',
        'site:socialmediaexaminer.com LinkedIn strategy',
        'site:hubspot.com LinkedIn marketing',
        '"LinkedIn engagement" tactics',
        '"LinkedIn post" viral formula',
        '"LinkedIn carousel" best practices',
        '"content calendar" LinkedIn',
        '"LinkedIn newsletter" growth',
        '"authority building" content strategy',
        '"LinkedIn hook" writing formulas',
        '"storytelling" LinkedIn posts',
        '"LinkedIn analytics" optimization',
        '"content repurposing" LinkedIn',
        '"LinkedIn video" engagement',
        '"comment strategy" LinkedIn growth',
        '"LinkedIn creator" mode tips',
    ],
}


class TopicIntelligenceRequest(BaseModel):
    """Request to run topic intelligence pipeline"""
    user_id: str = Field(..., description="User ID")
    theme: IntelligenceTheme = Field(..., description="Intelligence theme to research")
    custom_dorks: Optional[List[str]] = Field(None, description="Custom Google dorks to add")
    max_urls: int = Field(20, description="Maximum URLs to scrape", ge=5, le=50)
    generate_content: bool = Field(True, description="Generate content suggestions")
    generate_outreach: bool = Field(True, description="Generate outreach templates")


class ProspectIntelligence(BaseModel):
    """Prospect intelligence extracted from research"""
    target_personas: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    language_patterns: List[str] = Field(default_factory=list)
    decision_triggers: List[str] = Field(default_factory=list)
    objections: List[str] = Field(default_factory=list)


class OutreachTemplate(BaseModel):
    """Generated outreach template"""
    type: str = Field(..., description="Type: dm, email, cold_intro")
    subject: Optional[str] = Field(None, description="Email subject line")
    body: str = Field(..., description="Message body")
    personalization_hooks: List[str] = Field(default_factory=list)


class ContentIdea(BaseModel):
    """Generated content idea"""
    format: str = Field(..., description="Format: post, carousel, thread, video, article")
    headline: str = Field(..., description="Content headline/hook")
    outline: List[str] = Field(default_factory=list, description="Content outline points")
    cta: Optional[str] = Field(None, description="Call to action")


class OpportunityInsight(BaseModel):
    """Market opportunity insight"""
    gap: str = Field(..., description="Market gap identified")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    action: str = Field(..., description="Recommended action")


class TopicIntelligenceResult(BaseModel):
    """Complete topic intelligence result"""
    theme: str
    theme_display: str
    research_id: str
    sources_scraped: int
    summary: str
    prospect_intelligence: ProspectIntelligence
    outreach_templates: List[OutreachTemplate] = Field(default_factory=list)
    content_ideas: List[ContentIdea] = Field(default_factory=list)
    opportunity_insights: List[OpportunityInsight] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    trending_topics: List[str] = Field(default_factory=list)


class TopicIntelligenceResponse(BaseModel):
    """Response from topic intelligence pipeline"""
    success: bool
    research_id: str
    status: str
    result: Optional[TopicIntelligenceResult] = None
    error: Optional[str] = None


# Theme display names
THEME_DISPLAY_NAMES: Dict[IntelligenceTheme, str] = {
    IntelligenceTheme.ENROLLMENT_MANAGEMENT: "Enrollment Management & Admissions",
    IntelligenceTheme.NEURODIVERGENT_SUPPORT: "Neurodivergent Support / One-to-One Care",
    IntelligenceTheme.AI_IN_EDUCATION: "AI in Education / EdTech",
    IntelligenceTheme.REFERRAL_NETWORKS: "Referral Networks: Therapists, Counselors, Treatment Centers",
    IntelligenceTheme.FASHION_TECH: "Fashion Tech App / ClosetAI",
    IntelligenceTheme.ENTREPRENEURSHIP_OPS: "Entrepreneurship / Ops / Scalability",
    IntelligenceTheme.CONTENT_MARKETING: "Content Marketing / LinkedIn Authority",
}


# Best sources by theme (for display/reference)
THEME_SOURCES: Dict[IntelligenceTheme, List[Dict[str, str]]] = {
    IntelligenceTheme.ENROLLMENT_MANAGEMENT: [
        {"source": "Private school websites", "extracts": "Admissions process, pain points, program details"},
        {"source": "K-12 blogs + newsletters", "extracts": "Enrollment trends, parent concerns"},
        {"source": "NAIS.org", "extracts": "Admissions insights, enrollment stats"},
        {"source": "State DOE reports", "extracts": "Public policy + competition"},
        {"source": "Education industry news", "extracts": "Macro trends"},
    ],
    IntelligenceTheme.NEURODIVERGENT_SUPPORT: [
        {"source": "Autism centers & therapy clinics", "extracts": "Terminology, models of care, referral patterns"},
        {"source": "Parent blogs & forums", "extracts": "Pain points, phrases real parents use"},
        {"source": "Private neurodivergent school sites", "extracts": "Curriculum, success metrics"},
        {"source": "Education psychologists", "extracts": "Expertise + language used"},
    ],
    IntelligenceTheme.AI_IN_EDUCATION: [
        {"source": "EdSurge", "extracts": "EdTech trends, adoption data"},
        {"source": "EDUCAUSE", "extracts": "AI frameworks in education"},
        {"source": "Medium & Substack blogs", "extracts": "Real practitioner POV"},
        {"source": "EdTech startup sites", "extracts": "Positioning language"},
    ],
    IntelligenceTheme.REFERRAL_NETWORKS: [
        {"source": "Psychology Today directories", "extracts": "Therapist specialties, bios"},
        {"source": "Treatment center websites", "extracts": "Who they refer, why"},
        {"source": "Mental health associations", "extracts": "Referral models"},
        {"source": "Counselor blogs", "extracts": "Pain points, language"},
    ],
    IntelligenceTheme.FASHION_TECH: [
        {"source": "Reddit fashion communities", "extracts": "What people want from wardrobe apps"},
        {"source": "Product Hunt", "extracts": "Top fashion apps + summaries"},
        {"source": "App Store reviews", "extracts": "Feature gaps, user issues"},
        {"source": "GitHub repos", "extracts": "Architecture ideas"},
    ],
    IntelligenceTheme.ENTREPRENEURSHIP_OPS: [
        {"source": "Harvard Business Review", "extracts": "Ops frameworks"},
        {"source": "SaaS scaling blogs", "extracts": "GTM frameworks"},
        {"source": "Startup accelerator blogs", "extracts": "Leadership principles"},
        {"source": "Project management blogs", "extracts": "Tools, processes"},
    ],
    IntelligenceTheme.CONTENT_MARKETING: [
        {"source": "Social Media Examiner", "extracts": "Content strategy"},
        {"source": "HubSpot blogs", "extracts": "SEO + writing frameworks"},
        {"source": "Copywriting Substacks", "extracts": "Hooks, angles"},
        {"source": "LinkedIn post roundups", "extracts": "Best performing styles"},
    ],
}

