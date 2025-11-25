"""
Topic Intelligence Service

Orchestrates the Topic Intelligence Pipeline:
1. Generate Google dorks for theme
2. Search and scrape top URLs
3. Extract prospect intelligence, pain points, language
4. Generate outreach templates
5. Generate content ideas
6. Identify market opportunities
"""

import logging
import time
from typing import List, Dict, Any, Optional

from app.models.topic_intelligence import (
    IntelligenceTheme,
    THEME_DORKS,
    THEME_DISPLAY_NAMES,
    TopicIntelligenceRequest,
    TopicIntelligenceResult,
    ProspectIntelligence,
    OutreachTemplate,
    ContentIdea,
    OpportunityInsight,
)
from app.services.perplexity_client import get_perplexity_client
from app.services.firecrawl_client import get_firecrawl_client
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


class TopicIntelligenceService:
    """Service for running topic intelligence pipeline"""
    
    def __init__(self):
        self.perplexity = None
        self.firecrawl = None
    
    def _init_clients(self):
        """Lazy init clients"""
        if self.perplexity is None:
            self.perplexity = get_perplexity_client()
        if self.firecrawl is None:
            self.firecrawl = get_firecrawl_client()
    
    def get_dorks_for_theme(
        self, 
        theme: IntelligenceTheme, 
        custom_dorks: Optional[List[str]] = None
    ) -> List[str]:
        """Get Google dorks for a theme, optionally adding custom ones"""
        dorks = THEME_DORKS.get(theme, []).copy()
        if custom_dorks:
            dorks.extend(custom_dorks)
        return dorks
    
    async def run_pipeline(
        self, 
        request: TopicIntelligenceRequest
    ) -> TopicIntelligenceResult:
        """
        Run the full topic intelligence pipeline.
        
        Steps:
        1. Get dorks for theme
        2. Use Perplexity to research each dork query
        3. Scrape top URLs with Firecrawl
        4. Synthesize into prospect intelligence
        5. Generate outreach templates
        6. Generate content ideas
        7. Identify opportunities
        8. Store in Firestore
        """
        self._init_clients()
        
        theme = request.theme
        theme_display = THEME_DISPLAY_NAMES.get(theme, theme.value)
        dorks = self.get_dorks_for_theme(theme, request.custom_dorks)
        
        logger.info(f"Running topic intelligence for theme: {theme_display}")
        logger.info(f"Using {len(dorks)} Google dorks")
        
        # Step 1: Research with Perplexity using top dorks
        all_research = []
        all_sources = []
        
        # Use top 5 dorks to avoid timeout
        for dork in dorks[:5]:
            try:
                research = self.perplexity.research_topic(
                    topic=dork,
                    num_results=5,
                    include_comparison=False
                )
                all_research.append(research.get("summary", ""))
                all_sources.extend(research.get("sources", []))
            except Exception as e:
                logger.warning(f"Failed to research dork '{dork}': {e}")
                continue
        
        # Step 2: Scrape top unique URLs
        unique_urls = list(set(s.get("url", "") for s in all_sources if s.get("url")))[:request.max_urls]
        scraped_content = []
        
        for url in unique_urls[:10]:  # Limit to 10 for speed
            try:
                scraped = self.firecrawl.scrape_url(url)
                scraped_content.append({
                    "url": url,
                    "title": scraped.title,
                    "content": scraped.content[:2000],
                })
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")
                continue
        
        # Step 3: Combine all content
        combined_text = "\n\n".join(all_research)
        for sc in scraped_content:
            combined_text += f"\n\n{sc.get('content', '')}"
        
        # Step 4: Extract prospect intelligence
        prospect_intel = self._extract_prospect_intelligence(combined_text, theme)
        
        # Step 5: Generate outreach templates
        outreach_templates = []
        if request.generate_outreach:
            outreach_templates = self._generate_outreach_templates(prospect_intel, theme)
        
        # Step 6: Generate content ideas
        content_ideas = []
        if request.generate_content:
            content_ideas = self._generate_content_ideas(prospect_intel, theme, combined_text)
        
        # Step 7: Identify opportunities
        opportunities = self._identify_opportunities(combined_text, theme)
        
        # Step 8: Extract keywords and trends
        keywords = self._extract_keywords(combined_text)
        trending = self._extract_trends(combined_text)
        
        # Build summary
        summary = f"Analyzed {len(scraped_content)} sources for {theme_display}. "
        summary += f"Identified {len(prospect_intel.pain_points)} pain points, "
        summary += f"{len(prospect_intel.target_personas)} target personas, "
        summary += f"and {len(opportunities)} market opportunities."
        
        # Create result
        research_id = f"topic_intel_{theme.value}_{int(time.time())}"
        
        result = TopicIntelligenceResult(
            theme=theme.value,
            theme_display=theme_display,
            research_id=research_id,
            sources_scraped=len(scraped_content),
            summary=summary,
            prospect_intelligence=prospect_intel,
            outreach_templates=outreach_templates,
            content_ideas=content_ideas,
            opportunity_insights=opportunities,
            keywords=keywords,
            trending_topics=trending,
        )
        
        # Store in Firestore
        self._store_result(request.user_id, result)
        
        return result
    
    def _extract_prospect_intelligence(
        self, 
        text: str, 
        theme: IntelligenceTheme
    ) -> ProspectIntelligence:
        """Extract prospect intelligence from combined research text"""
        text_lower = text.lower()
        
        # Target personas by theme
        persona_keywords = {
            IntelligenceTheme.ENROLLMENT_MANAGEMENT: [
                "admissions director", "enrollment manager", "head of school",
                "principal", "dean of admissions", "marketing director"
            ],
            IntelligenceTheme.NEURODIVERGENT_SUPPORT: [
                "special education director", "learning specialist", "school psychologist",
                "parent", "therapist", "occupational therapist", "speech therapist"
            ],
            IntelligenceTheme.AI_IN_EDUCATION: [
                "edtech founder", "curriculum director", "technology coordinator",
                "instructional designer", "chief learning officer"
            ],
            IntelligenceTheme.REFERRAL_NETWORKS: [
                "educational consultant", "therapist", "counselor", "treatment center director",
                "case manager", "family therapist", "neuropsychologist"
            ],
            IntelligenceTheme.FASHION_TECH: [
                "fashion enthusiast", "minimalist", "professional", "busy parent",
                "style conscious", "sustainable shopper"
            ],
            IntelligenceTheme.ENTREPRENEURSHIP_OPS: [
                "founder", "ceo", "coo", "operations manager", "program director",
                "startup founder", "entrepreneur"
            ],
            IntelligenceTheme.CONTENT_MARKETING: [
                "content creator", "linkedin creator", "thought leader",
                "marketing director", "personal brand builder", "consultant"
            ],
        }
        
        # Pain point indicators
        pain_indicators = [
            "struggle", "challenge", "difficult", "problem", "issue", "pain",
            "frustrat", "overwhelm", "confus", "time-consuming", "expensive",
            "inefficient", "manual", "tedious", "complex"
        ]
        
        # Extract personas found
        target_personas = []
        for persona in persona_keywords.get(theme, []):
            if persona.lower() in text_lower:
                target_personas.append(persona.title())
        
        # Extract pain points (sentences containing pain indicators)
        pain_points = []
        sentences = text.replace("\n", ". ").split(". ")
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(ind in sentence_lower for ind in pain_indicators):
                clean = sentence.strip()[:200]
                if len(clean) > 20 and clean not in pain_points:
                    pain_points.append(clean)
        
        # Extract language patterns (common phrases)
        language_patterns = self._extract_phrases(text, theme)
        
        # Decision triggers
        trigger_keywords = ["roi", "results", "outcomes", "success", "growth", "efficiency", "save time", "reduce cost"]
        decision_triggers = [kw for kw in trigger_keywords if kw in text_lower]
        
        # Common objections
        objection_keywords = ["too expensive", "not enough time", "already have", "not sure", "need approval", "budget"]
        objections = [obj for obj in objection_keywords if obj in text_lower]
        
        return ProspectIntelligence(
            target_personas=target_personas[:10],
            pain_points=pain_points[:10],
            language_patterns=language_patterns[:10],
            decision_triggers=decision_triggers[:10],
            objections=objections[:10],
        )
    
    def _extract_phrases(self, text: str, theme: IntelligenceTheme) -> List[str]:
        """Extract common phrases used in the domain"""
        # Theme-specific phrases to look for
        theme_phrases = {
            IntelligenceTheme.ENROLLMENT_MANAGEMENT: [
                "yield rate", "enrollment funnel", "open house", "campus visit",
                "financial aid", "tuition assistance", "re-enrollment"
            ],
            IntelligenceTheme.NEURODIVERGENT_SUPPORT: [
                "individualized support", "one-to-one", "learning differences",
                "executive function", "sensory needs", "social emotional"
            ],
            IntelligenceTheme.AI_IN_EDUCATION: [
                "personalized learning", "adaptive", "AI-powered", "data-driven",
                "student outcomes", "learning analytics"
            ],
            IntelligenceTheme.REFERRAL_NETWORKS: [
                "referral network", "placement", "therapeutic", "treatment",
                "educational consultant", "case management"
            ],
            IntelligenceTheme.FASHION_TECH: [
                "capsule wardrobe", "outfit coordination", "style recommendation",
                "virtual closet", "mix and match"
            ],
            IntelligenceTheme.ENTREPRENEURSHIP_OPS: [
                "scalable systems", "operational efficiency", "process automation",
                "team building", "delegation"
            ],
            IntelligenceTheme.CONTENT_MARKETING: [
                "thought leadership", "personal brand", "content strategy",
                "engagement", "algorithm", "hook"
            ],
        }
        
        text_lower = text.lower()
        found = [phrase for phrase in theme_phrases.get(theme, []) if phrase in text_lower]
        return found
    
    def _generate_outreach_templates(
        self, 
        intel: ProspectIntelligence, 
        theme: IntelligenceTheme
    ) -> List[OutreachTemplate]:
        """Generate outreach templates based on prospect intelligence"""
        templates = []
        
        # DM Template
        pain = intel.pain_points[0] if intel.pain_points else "common challenges"
        persona = intel.target_personas[0] if intel.target_personas else "professional"
        
        dm_template = OutreachTemplate(
            type="dm",
            body=f"Hi [Name],\n\nI noticed you're a {persona} - I've been researching {THEME_DISPLAY_NAMES[theme]} and found some interesting insights about {pain[:50]}...\n\nWould love to share what I've learned. Open to a quick chat?",
            personalization_hooks=[
                "Reference their recent post",
                "Mention mutual connection",
                "Reference their company's recent news"
            ]
        )
        templates.append(dm_template)
        
        # Email Template
        email_template = OutreachTemplate(
            type="email",
            subject=f"Quick question about {THEME_DISPLAY_NAMES[theme].split('/')[0].strip()}",
            body=f"Hi [Name],\n\nI've been diving deep into {THEME_DISPLAY_NAMES[theme]} and noticed that many {persona}s struggle with {pain[:100]}.\n\nI've put together some research that might help. Would you be open to a 15-minute call to discuss?\n\nBest,\n[Your Name]",
            personalization_hooks=[
                "Reference specific company challenge",
                "Mention industry trend affecting them",
                "Reference their published content"
            ]
        )
        templates.append(email_template)
        
        # Cold Intro Template
        cold_template = OutreachTemplate(
            type="cold_intro",
            body=f"[Mutual connection] suggested I reach out. I specialize in helping {persona}s with {THEME_DISPLAY_NAMES[theme].lower()}. Given your work at [Company], I thought there might be some synergy. Worth a conversation?",
            personalization_hooks=[
                "Name the mutual connection",
                "Reference their specific role",
                "Mention relevant company initiative"
            ]
        )
        templates.append(cold_template)
        
        return templates
    
    def _generate_content_ideas(
        self, 
        intel: ProspectIntelligence, 
        theme: IntelligenceTheme,
        research_text: str
    ) -> List[ContentIdea]:
        """Generate content ideas based on research"""
        ideas = []
        theme_display = THEME_DISPLAY_NAMES[theme]
        
        # LinkedIn Post idea
        if intel.pain_points:
            ideas.append(ContentIdea(
                format="post",
                headline=f"The #1 challenge in {theme_display.split('/')[0].strip()} (and how to solve it)",
                outline=[
                    "Hook: State the pain point directly",
                    "Agitate: Why this matters now",
                    "Solution: Your unique approach",
                    "Proof: Quick example or stat",
                    "CTA: Ask for engagement"
                ],
                cta="What's your biggest challenge with this? Drop a comment."
            ))
        
        # Carousel idea
        if intel.language_patterns:
            ideas.append(ContentIdea(
                format="carousel",
                headline=f"7 Terms Every {intel.target_personas[0] if intel.target_personas else 'Professional'} Should Know",
                outline=[
                    f"Slide 1: Hook - '{theme_display} jargon decoded'",
                    *[f"Slide {i+2}: {term}" for i, term in enumerate(intel.language_patterns[:5])],
                    "Final Slide: CTA to follow for more"
                ],
                cta="Save this for later and follow for more insights."
            ))
        
        # Thread idea
        ideas.append(ContentIdea(
            format="thread",
            headline=f"I spent 20 hours researching {theme_display}. Here's what I learned:",
            outline=[
                "Tweet 1: Hook with specific insight",
                "Tweet 2-5: Key findings with examples",
                "Tweet 6: Contrarian take",
                "Tweet 7: Actionable takeaway",
                "Tweet 8: CTA + retweet ask"
            ],
            cta="If this was helpful, retweet the first tweet to help others."
        ))
        
        # Video idea
        ideas.append(ContentIdea(
            format="video",
            headline=f"Why {intel.pain_points[0][:50] if intel.pain_points else theme_display} is broken",
            outline=[
                "0-3s: Pattern interrupt hook",
                "3-15s: State the problem",
                "15-45s: Your solution/framework",
                "45-60s: CTA"
            ],
            cta="Follow for more insights on {theme_display}"
        ))
        
        return ideas
    
    def _identify_opportunities(
        self, 
        text: str, 
        theme: IntelligenceTheme
    ) -> List[OpportunityInsight]:
        """Identify market opportunities from research"""
        opportunities = []
        text_lower = text.lower()
        
        # Gap indicators
        gap_phrases = [
            ("no one", "Unserved market segment"),
            ("missing", "Feature gap"),
            ("wish there was", "Unmet need"),
            ("frustrating", "Pain point opportunity"),
            ("outdated", "Modernization opportunity"),
            ("manual", "Automation opportunity"),
            ("expensive", "Cost disruption opportunity"),
            ("complicated", "Simplification opportunity"),
        ]
        
        for phrase, gap_type in gap_phrases:
            if phrase in text_lower:
                # Find context around the phrase
                idx = text_lower.find(phrase)
                context = text[max(0, idx-50):min(len(text), idx+100)]
                
                opportunities.append(OpportunityInsight(
                    gap=gap_type,
                    evidence=[context.strip()],
                    action=f"Explore {gap_type.lower()} in {THEME_DISPLAY_NAMES[theme]}"
                ))
        
        return opportunities[:5]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        text_lower = text.lower()
        
        common_keywords = [
            "growth", "scaling", "revenue", "efficiency", "automation",
            "engagement", "retention", "acquisition", "conversion",
            "strategy", "framework", "system", "process", "workflow",
            "personalization", "analytics", "insights", "data-driven"
        ]
        
        found = [kw for kw in common_keywords if kw in text_lower]
        return found[:15]
    
    def _extract_trends(self, text: str) -> List[str]:
        """Extract trending topics from text"""
        text_lower = text.lower()
        
        trend_phrases = [
            "trending", "growing", "emerging", "rising", "2024",
            "new approach", "innovative", "disrupting", "transforming"
        ]
        
        trends = []
        sentences = text.split(". ")
        for sentence in sentences:
            if any(trend in sentence.lower() for trend in trend_phrases):
                clean = sentence.strip()[:100]
                if len(clean) > 20:
                    trends.append(clean)
        
        return trends[:10]
    
    def _store_result(self, user_id: str, result: TopicIntelligenceResult):
        """Store result in Firestore"""
        doc_data = {
            "research_id": result.research_id,
            "theme": result.theme,
            "theme_display": result.theme_display,
            "sources_scraped": result.sources_scraped,
            "summary": result.summary,
            "prospect_intelligence": result.prospect_intelligence.dict(),
            "outreach_templates": [t.dict() for t in result.outreach_templates],
            "content_ideas": [c.dict() for c in result.content_ideas],
            "opportunity_insights": [o.dict() for o in result.opportunity_insights],
            "keywords": result.keywords,
            "trending_topics": result.trending_topics,
            "created_at": time.time(),
        }
        
        doc_ref = db.collection("users").document(user_id).collection("topic_intelligence").document(result.research_id)
        doc_ref.set(doc_data)
        
        logger.info(f"Stored topic intelligence: {result.research_id}")


# Singleton
_service: Optional[TopicIntelligenceService] = None


def get_topic_intelligence_service() -> TopicIntelligenceService:
    """Get or create service instance"""
    global _service
    if _service is None:
        _service = TopicIntelligenceService()
    return _service

