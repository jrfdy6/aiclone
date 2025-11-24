"""
Content Post Templates - LinkedIn post frameworks and patterns.

This replaces LinkedIn scraping by providing proven post structures
that perform well on LinkedIn.
"""

from typing import Dict, Any, List, Optional
import random


# Post Template Library - 30+ proven LinkedIn post frameworks
POST_TEMPLATES = [
    {
        "id": "template_1",
        "name": "Shift + Insight + Question",
        "structure": """There's a major shift happening in {industry}.

Most leaders aren't ready for it.

Here's what I'm seeing:

1. {insight_1}
2. {insight_2}
3. {insight_3}

What's one transition your team is navigating right now?""",
        "pillars": ["thought_leadership", "referral"],
        "tone": "observational",
    },
    {
        "id": "template_2",
        "name": "Story + Lesson + CTA",
        "structure": """Last week, I spoke with a {role}.

One thing stood out:

{key_insight}

Here's the part we don't talk about enough:

{reflection}

Curious — have you seen something similar?""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "conversational",
    },
    {
        "id": "template_3",
        "name": "Data Point → Narrative → Reflection",
        "structure": """{data_point} — that's the number that got me thinking this week.

Here's why it matters:

{context}

But here's what the data doesn't show:

{deeper_insight}

What's your take on this?""",
        "pillars": ["thought_leadership"],
        "tone": "analytical",
    },
    {
        "id": "template_4",
        "name": "Contrarian Take + Reasoning",
        "structure": """Everyone's saying {common_belief}.

I disagree.

Here's why:

1. {reason_1}
2. {reason_2}
3. {reason_3}

The real opportunity is {alternative_perspective}.

What do you think?""",
        "pillars": ["thought_leadership", "stealth_founder"],
        "tone": "bold",
    },
    {
        "id": "template_5",
        "name": "Problem + Solution Framework",
        "structure": """{problem_statement}

I see this all the time in {industry}.

The solution isn't {common_solution}.

It's {better_approach}:

• {step_1}
• {step_2}
• {step_3}

What's worked for you?""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "helpful",
    },
    {
        "id": "template_6",
        "name": "Personal Anecdote + Universal Lesson",
        "structure": """{personal_story_or_experience}

At first, I thought {initial_assumption}.

Then I realized {key_learning}.

This applies to {broader_context}:

{application}

Anyone else experience this?""",
        "pillars": ["stealth_founder", "referral"],
        "tone": "authentic",
    },
    {
        "id": "template_7",
        "name": "Industry Shift + Opportunity",
        "structure": """{industry} is changing.

Fast.

Three trends I'm watching:

1. {trend_1} → {opportunity_1}
2. {trend_2} → {opportunity_2}
3. {trend_3} → {opportunity_3}

The organizations that adapt will {outcome}.

Which trend are you prioritizing?""",
        "pillars": ["thought_leadership"],
        "tone": "forward-thinking",
    },
    {
        "id": "template_8",
        "name": "Question + Framework + Engagement",
        "structure": """How do you {key_question}?

I've been thinking about this a lot lately.

Here's the framework I use:

{framework_steps}

It's not perfect, but it works.

What framework do you use?""",
        "pillars": ["thought_leadership", "referral"],
        "tone": "collaborative",
    },
    {
        "id": "template_9",
        "name": "Mistake + Learning",
        "structure": """I made a mistake.

{describe_mistake}

Here's what I learned:

1. {learning_1}
2. {learning_2}
3. {learning_3}

Now I {new_approach}.

Mistakes are teachers. What's one you've learned from recently?""",
        "pillars": ["stealth_founder", "thought_leadership"],
        "tone": "vulnerable",
    },
    {
        "id": "template_10",
        "name": "Observation + Pattern Recognition",
        "structure": """I've noticed something interesting:

{observation}

After {time_period/context}, a pattern emerged:

{pattern_description}

The organizations doing this well {positive_outcome}.

The ones struggling {challenge}.

What patterns are you seeing?""",
        "pillars": ["thought_leadership"],
        "tone": "observational",
    },
    {
        "id": "template_11",
        "name": "Before/After Transformation",
        "structure": """Before: {old_state}

After: {new_state}

The difference? {key_change}

Here's how we got there:

{process}

It wasn't easy, but it was worth it.

What transformation are you working on?""",
        "pillars": ["thought_leadership", "stealth_founder"],
        "tone": "inspiring",
    },
    {
        "id": "template_12",
        "name": "Myth Busting",
        "structure": """Myth: {common_myth}

Reality: {truth}

Here's why this matters:

{importance}

The real challenge is {actual_challenge}.

Here's what actually works:

{solution}

What myths have you debunked?""",
        "pillars": ["thought_leadership"],
        "tone": "clarifying",
    },
    {
        "id": "template_13",
        "name": "Connection Request Story",
        "structure": """I received a message from {person_type}.

They said {key_message}.

It got me thinking about {reflection}.

Here's what I've learned about {topic}:

{insights}

How do you approach {related_question}?""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "relational",
    },
    {
        "id": "template_14",
        "name": "Listicle: Top Insights",
        "structure": """{number} things I've learned about {topic}:

1. {insight_1}
2. {insight_2}
3. {insight_3}
4. {insight_4}
5. {insight_5}

The one that surprised me most? {surprising_insight}

Which resonates with you?""",
        "pillars": ["thought_leadership", "referral"],
        "tone": "informative",
    },
    {
        "id": "template_15",
        "name": "Future Vision",
        "structure": """In {timeframe}, I believe {bold_prediction}.

Here's why:

{reasoning}

This will mean {implications}:

• {implication_1}
• {implication_2}
• {implication_3}

The time to prepare is now.

What's your vision for {topic}?""",
        "pillars": ["thought_leadership"],
        "tone": "visionary",
    },
    {
        "id": "template_16",
        "name": "Behind the Scenes",
        "structure": """Most people see {final_result}.

They don't see {hidden_process}.

Here's what actually goes into {topic}:

{behind_scenes_details}

The reality is {honest_truth}.

Anyone else building something? What's your hidden process?""",
        "pillars": ["stealth_founder"],
        "tone": "transparent",
    },
    {
        "id": "template_17",
        "name": "Comparison: Then vs Now",
        "structure": """Then: {old_approach}

Now: {new_approach}

What changed? {key_shifts}

The impact:

{impact_description}

What's different about how you approach {topic} today?""",
        "pillars": ["thought_leadership"],
        "tone": "reflective",
    },
    {
        "id": "template_18",
        "name": "Unpopular Opinion",
        "structure": """Unpopular opinion: {controversial_take}

Hear me out:

{reasoning}

The common wisdom says {common_belief}.

But I've found {alternative_truth}:

{evidence}

What's an unpopular opinion you hold in {industry}?""",
        "pillars": ["thought_leadership", "stealth_founder"],
        "tone": "provocative",
    },
    {
        "id": "template_19",
        "name": "Resource Sharing",
        "structure": """I've been asked about {topic} a lot lately.

Here's what I share:

{resource_or_framework}

Key takeaways:

• {takeaway_1}
• {takeaway_2}
• {takeaway_3}

Hope this helps.

What resources have been game-changers for you?""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "generous",
    },
    {
        "id": "template_20",
        "name": "Challenge + Invitation",
        "structure": """{challenge_statement}

This week, I challenge you to {action}:

{action_steps}

Why? Because {benefit}.

Who's with me?

{engagement_question}""",
        "pillars": ["thought_leadership"],
        "tone": "motivational",
    },
    {
        "id": "template_21",
        "name": "Lesson from Failure",
        "structure": """{failure_description}

It taught me {key_lesson}.

I used to think {old_belief}.

Now I know {new_understanding}:

{insights}

Failure is feedback.

What's a failure that taught you something valuable?""",
        "pillars": ["stealth_founder", "thought_leadership"],
        "tone": "humble",
    },
    {
        "id": "template_22",
        "name": "Trend Analysis",
        "structure": """{trend} is accelerating.

Here's what's happening:

{trend_description}

Why this matters:

{importance}

For {audience}, this means {implications}.

The question is: {strategic_question}

How are you thinking about {trend}?""",
        "pillars": ["thought_leadership"],
        "tone": "analytical",
    },
    {
        "id": "template_23",
        "name": "Gratitude + Reflection",
        "structure": """{gratitude_statement}

{context}

What I've learned:

{lessons}

The biggest takeaway? {key_lesson}

{personal_reflection}

What are you grateful for in {context}?""",
        "pillars": ["referral", "stealth_founder"],
        "tone": "grateful",
    },
    {
        "id": "template_24",
        "name": "Hypothesis Testing",
        "structure": """I had a hypothesis:

{hypothesis}

So I tested it:

{test_description}

Results: {results}

What I learned: {learnings}

Next test: {next_hypothesis}

What hypotheses are you testing?""",
        "pillars": ["thought_leadership", "stealth_founder"],
        "tone": "experimental",
    },
    {
        "id": "template_25",
        "name": "Value Proposition Story",
        "structure": """{problem_statement}

We've all been there.

{personal_connection}

The solution isn't {wrong_approach}.

It's {right_approach}:

{value_proposition}

Here's what that looks like:

{examples}

What's your approach to {problem}?""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "helpful",
    },
    {
        "id": "template_26",
        "name": "Industry Call-Out",
        "structure": """{industry}, we need to talk.

{issue_statement}

Here's the problem:

{problem_breakdown}

The solution starts with {solution_start}:

{actionable_steps}

Who's ready to {positive_action}?

{engagement_question}""",
        "pillars": ["thought_leadership"],
        "tone": "direct",
    },
    {
        "id": "template_27",
        "name": "Seasonal/Event-Based",
        "structure": """{event/season} is a time for {reflection}.

In {context}, we often {common_behavior}.

But this year, let's {better_approach}:

{suggestions}

{personal_connection}

What are you focusing on during {event/season}?""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "timely",
    },
    {
        "id": "template_28",
        "name": "Case Study Lite",
        "structure": """{brief_case_description}

Context: {context}

Challenge: {challenge}

Approach: {approach}

Outcome: {outcome}

Key takeaway: {takeaway}

What would you have done differently?""",
        "pillars": ["thought_leadership", "referral"],
        "tone": "educational",
    },
    {
        "id": "template_29",
        "name": "Question Thread",
        "structure": """Quick questions for {audience}:

1. {question_1}
2. {question_2}
3. {question_3}

Answer any/all that resonate.

I'll share my thoughts in the comments.

{engagement_encouragement}""",
        "pillars": ["referral", "thought_leadership"],
        "tone": "engaging",
    },
    {
        "id": "template_30",
        "name": "Stealth Founder Journey",
        "structure": """{timeframe} ago, I started building {what}.

Most people said {common_response}.

I persisted because {why}.

Here's what I've learned:

{learnings}

The journey isn't {misconception}.

It's {reality}.

{personal_reflection}

Anyone else building something? What's your why?""",
        "pillars": ["stealth_founder"],
        "tone": "authentic",
    },
]


def get_template_for_pillar(pillar: str, used_templates: List[str] = None) -> Dict[str, Any]:
    """
    Get a random template suitable for a content pillar.
    
    Args:
        pillar: Content pillar type (referral, thought_leadership, stealth_founder)
        used_templates: List of template IDs to avoid
        
    Returns:
        Template dictionary
    """
    # Filter templates by pillar compatibility
    suitable_templates = [
        t for t in POST_TEMPLATES
        if pillar in t.get("pillars", []) or pillar == "mixed"
    ]
    
    # Filter out recently used templates
    if used_templates:
        suitable_templates = [t for t in suitable_templates if t["id"] not in used_templates]
    
    # If no suitable templates left, use all templates
    if not suitable_templates:
        suitable_templates = POST_TEMPLATES
    
    # Return random template (in production, you might want to weight by performance)
    return random.choice(suitable_templates)


def get_all_templates() -> List[Dict[str, Any]]:
    """Get all available post templates."""
    return POST_TEMPLATES


def get_template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific template by ID."""
    for template in POST_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None

