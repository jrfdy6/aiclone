# AI Clone: Frameworks & Mental Models

**Date:** 2025  
**Source:** Multiple files (`philosophy.md`, `JOHNNIE_FIELDS_PERSONA.md`, `audience_communication.md`, content generation code)  
**Purpose:** Complete collection of frameworks and mental models used in the aiclone project

---

## 1. People/Process/Culture Framework

**Core Principle:** "There are only 3 things you can influence: People, Process, and Culture."

### Application
- When analyzing organizational problems, categorize by these three dimensions
- When proposing solutions, address all three areas
- When measuring impact, track changes across all three

### Usage in aiclone
- Used in leadership philosophy documentation
- Applied to team management approaches
- Referenced in content generation for leadership audience

---

## 2. PACER Content Framework

**Purpose:** Structure content for maximum impact

### Components
- **P** - Problem: Start by identifying a specific problem your audience faces
- **A** - Amplify: Amplify the pain - what happens if they don't solve it?
- **C** - Credibility: Establish why you're qualified to speak on this
- **E** - Educate: Provide actionable value and insights
- **R** - Request: End with a clear call-to-action

### Implementation
- Used in content generation API
- Optional elements that can be included in prompts
- Helps structure value-driven content

### Code Reference
```python
pacer_map = {
    "Problem": "Start by identifying a specific problem your audience faces",
    "Amplify": "Amplify the pain - what happens if they don't solve it?",
    "Credibility": "Establish why you're qualified to speak on this",
    "Educate": "Provide actionable value and insights",
    "Request": "End with a clear call-to-action"
}
```

---

## 3. 9/1/1 Content Formula (Chris Do)

**Purpose:** Balance value, sales, and personal content

### Formula
For every 11 pieces of content:
- **9 pieces:** Pure value (teaching, insights, observations — no selling)
- **1 piece:** Sell unabashedly ("I'm building X. Here's how to get involved.")
- **1 piece:** Personal/behind-the-scenes (the real me, struggles included)

### Application
- Used in content generation category system
- Ensures content mix doesn't become too salesy
- Builds trust through value before asking

### Implementation in Code
```python
category_guidance = {
    "value": "VALUE CONTENT (9 out of 11 posts) - Pure value. Teaching, insights, observations. NO selling.",
    "sales": "SALES CONTENT (1 out of 11 posts) - Sell unabashedly. Direct ask. No apologies.",
    "personal": "PERSONAL CONTENT (1 out of 11 posts) - Behind-the-scenes. The real you. Struggles included."
}
```

---

## 4. Gap Theory (Authenticity Framework)

**Core Principle:** Minimize the gap between who you really are and who you show up as online.

### Practices
- Talk about education AND tech AND fashion (all of you)
- Share pivot journey, not just wins
- Be neurodivergent professional helping neurodivergent students
- When selling, sell. When teaching, teach. Don't mix.

### Application
- Used in persona documentation
- Guides content strategy
- Ensures authentic personal brand

---

## 5. Temperature Gauge Leadership

**Philosophy:** Make sure team never cools off — continually operate at a temperature that makes them successful.

### Implementation
- Monitor team energy and engagement
- Intervene before performance drops
- Keep momentum through consistent coaching
- "I want to make sure you're operating at a temperature that makes you successful"

### Usage
- Referenced in team coaching documentation
- Applied to management approach
- Used in audience communication guides

---

## 6. Last to Speak Framework

**Evolution:** Used to dominate conversations → Now makes it his business to be the last person to talk

### Results
- More fruitful exchanges
- Heavier adoption of ideas
- Better relationships
- Less intimidating presence

### Application
- Leadership philosophy
- Team management approach
- Content about communication

---

## 7. Empathy First Framework

**Approach:**
1. Understand perspective
2. Illuminate shared goals
3. Put plan in place

### Core Belief
"I am absolutely fascinated with why people think the way they do."

### Usage
- Stakeholder engagement
- Team coaching
- Conflict resolution
- Content about understanding others

---

## 8. Process Champion Identity

**Core Traits:**
- Keeps things documented
- People rely on him for that
- Values sustainable, repeatable systems

### Application
- Documentation culture
- Knowledge management
- System building
- SOP creation

---

## 9. Team Performance Belief

**Core Statement:** "Teams don't perform because they don't have a clear goal or they don't believe in the plan."

### Application
- Team management
- Project planning
- Content about leadership
- Problem diagnosis

---

## 10. Manager Identity Framework

**Motto:** "I'm the manager who solves problems before they become big."  
**Mindset:** "Let me know if there's something I can help out with — because I love that shit."

### Application
- Proactive problem-solving
- Team support
- Leadership content
- Management philosophy

---

## 11. Stakeholder Engagement Framework

**Approach:** Enter into dialogue to inform, influence, consult — NOT to power move

**Warning:** Power moves damage relationships. Might get job done but breaks trust.

### Application
- Cross-functional collaboration
- Change management
- Content about influence
- Relationship building

---

## 12. Coaching Philosophy

**Priority:** "None of my initiatives matter more than my coaching of other ACs."

**Goal:** "Producing ACs that are better every single day. Culture that continually produces ACs that kick ass and take names."

### Application
- Team development
- Management approach
- Content about mentorship
- Leadership philosophy

---

## 13. Connection Over Content

**Belief:** People remember how you made them feel, not what was on the slide.

**Practice:** Creating space for meaningful dialogue matters more than perfect presentations.

### Application
- Event planning (Coffee & Convo)
- Content strategy
- Relationship building
- Communication approach

---

## 14. Narrative Arc Structure

**Purpose:** Structure content to feel like a story, not a list of facts

### Structure
1. **HOOK/CONTEXT** - Start with something relatable, surprising, or attention-grabbing. Use voice markers.
2. **CHALLENGE/JOURNEY** - Share a real struggle, lesson, or experience from the persona chunks. This is the meat.
3. **REFLECTION/CTA** - Tie it back to the audience with insight or a question. End strong.

### Implementation
- Used in every content generation request
- Ensures content has narrative flow
- Makes posts feel like stories

---

## 15. Weighted Retrieval System

**Purpose:** Automatically prioritize the right persona tags for each content type

### How It Works
- LinkedIn posts → prioritize VOICE_PATTERNS, LINKEDIN_EXAMPLES
- Cold emails → prioritize BIO_FACTS, EXPERIENCES
- Personal content → prioritize STRUGGLES, PHILOSOPHY

### Innovation
- No manual filtering needed
- System automatically fetches most relevant context
- Ensures AI has right information for each content type

---

## 16. Anti-Hallucination Framework

**Core Rule:** ONLY use anecdotes, stories, and facts that appear in the PERSONA section

### Safeguards
- If no relevant anecdote exists, use general reflection instead of fabricating
- Real ventures to reference: DEFINE Socks, Acorn Global Collective, Easy Outfit App
- Real experiences: neurodivergent students, program launches, Salesforce migrations

### Application
- Every content generation request
- Prevents AI from making up stories
- Ensures authenticity

---

## Framework Usage Map

| Framework | Primary Use Case | Implementation |
|-----------|-----------------|----------------|
| People/Process/Culture | Organizational analysis | Philosophy docs |
| PACER | Content structure | Content generation API |
| 9/1/1 Formula | Content mix strategy | Category system |
| Gap Theory | Authenticity | Persona strategy |
| Temperature Gauge | Team management | Coaching approach |
| Last to Speak | Communication | Leadership practice |
| Empathy First | Stakeholder engagement | Relationship building |
| Process Champion | Documentation | System building |
| Narrative Arc | Content structure | Every content request |
| Weighted Retrieval | Context selection | Content generation API |
| Anti-Hallucination | Content authenticity | Every content request |

---

**These frameworks are actively used in the aiclone project and have been refined through real-world application.**
