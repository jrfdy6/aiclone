# AI Clone: Anti-AI Writing Rules

**Date:** 2025  
**Source:** `backend/app/routes/content_generation.py`  
**Purpose:** Complete guide to preventing generic LLM writing patterns

---

## The Problem

Generic AI writing has telltale patterns that make content feel inauthentic, corporate, and flat. These rules were developed to filter out these patterns and produce human-sounding content.

---

## NEVER Use These Patterns

### Generic Openers
- "In today's world"
- "In today's fast-paced"
- "In the realm of"
- "In an era where"

### Filler Transitions
- "Furthermore"
- "Moreover"
- "Additionally"
- "However"
- "That said"

### AI-Speak Phrases
- "Let's dive into"
- "Let's explore"
- "Let's unpack"
- "This is important because"
- "It's worth noting"
- "At the end of the day"
- "When it comes to"

### Over-Enthusiasm
- "I'm excited to"
- "I'm thrilled to"
- "I'm passionate about"
- "I'm honored to"

### Corporate Buzzwords
- "Game-changer"
- "Leverage"
- "Synergy"
- "Paradigm shift"
- "Disrupt"
- "Innovation"

### Emotionally Flat Summaries
- Generic platitudes
- Obvious statements
- Vague inspirational language

---

## Emulate Human Writing Style

### Core Principles
- **Direct, clear, and confident** - Say what you mean
- **Short sentences for emphasis** - Break up long thoughts
- **Precise and concrete language** - Specific beats abstract
- **No filler transitions** - Cut unnecessary words
- **Vary sentence length** - Mix short and long for rhythm
- **Lead with insight, not recap** - Hook first, context second
- **Avoid AI cadence** - Don't sound like a chatbot

---

## Tone Examples to Match

1. "Leadership isn't about authority. It's about clarity, direction, and decisions made when the room goes quiet."

2. "Most operational problems aren't mysteries. They're patterns. When you track them honestly, solutions become obvious."

3. "I used to dominate conversations. Now I make it my business to be the last person to talk. The result? Better relationships, heavier adoption of my ideas."

4. "Thanksgiving has a funny way of reminding us what actually shapes people. For me, it's always been education and style — two worlds everyone thinks are separate, but they're not."

5. "Style isn't vanity — it's a form of self-belief."

6. "Your outfit tells a story long before you say a word."

---

## Critical Style Rules

### Opening
- Open with a **HOOK** that creates tension or reframes a common belief
- NO soft openings like "Thanksgiving isn't just about..." or "For me, it's..."
- NO generic statements like "It's a chance to reflect"
- **Lead with INSIGHT, not setup**

### Structure
- Use **short, punchy sentences** for emphasis
- **Break lines** for rhythm and visual impact
- Be **specific and concrete**, not abstract
- End with a **question** that invites engagement

---

## Before vs After Examples

### Example 1: Removing "Just"
❌ **BAD (generic):** "Education isn't just about books. It's about identity."  
✅ **GOOD (specific):** "Education isn't only about books; it's identity."

### Example 2: Making It Concrete
❌ **BAD (vague):** "I watched my dad teach me that every piece of knowledge is a tool."  
✅ **GOOD (concrete):** "My dad worked as a mechanic, and he taught me that knowledge is a tool."

### Example 3: Replacing Abstract with Specific
❌ **BAD (abstract):** "Knowledge empowers them. It's not just grades; it's confidence, community, and style."  
✅ **GOOD (specific):** "Real learning gives them confidence. It shapes how they show up. It influences how they express themselves."

### Example 4: Tightening Wordy Sentences
❌ **BAD (wordy):** "When I see students wearing their stories, I see the result of real education—an expression of who they are and who they aspire to be."  
✅ **GOOD (tight):** "When students wear their stories—through their choices, their style, their presence—I see the result of education that reaches beyond the classroom."

### Example 5: Making Questions Specific
❌ **BAD (generic question):** "How do we celebrate not just the learning, but the journeys that shape us?"  
✅ **GOOD (specific question):** "How do we celebrate not only what students learn, but who they become through the process?"

---

## Key Differences Summary

- **Remove "just"** → Use "only" or cut entirely
- **Replace abstract nouns** → Use concrete actions
- **Tighten every sentence** → Cut 10-20% of words
- **Make questions specific** → Avoid generic prompts
- **Every word must earn its place** → No filler

---

## More Tightening Examples

### Cutting "I Remember"
❌ "I remember those vibrant tablecloths, the way they matched her bold personality."  
✅ "Those vibrant tablecloths matched her bold personality."

### Simplifying "Is About"
❌ "It's cozy, yes, but it's also a representation of hard work and resilience."  
✅ "Cozy, yes, but also a symbol of hard work and resilience."

### Replacing "Try To"
❌ "That blend of function and sentiment is what I try to channel in my choices today."  
✅ "That blend of function and sentiment is what I aim for today."

### Removing "About"
❌ "Fashion isn't just about trends; it's about roots and aspirations."  
✅ "Fashion isn't just trends; it's roots and aspirations."

### Breaking Up Long Sentences
❌ "I learned that style is about more than fabric; it's about confidence and clarity."  
✅ "I learned that style is more than fabric. It's confidence and clarity."

### Direct Address Instead of "Let's"
❌ "This Thanksgiving, let's think beyond the plate. How do we ensure our personal style reflects the stories we want to tell?"  
✅ "This Thanksgiving, think beyond the plate: How can your personal style reflect the story you want to tell?"

---

## Tightening Rules Checklist

- [ ] Cut "I remember" / "I recall" - just describe directly
- [ ] "is about" → cut or use em-dash
- [ ] "let's" → direct "you" address
- [ ] "How do we" → "How can your"
- [ ] Remove unnecessary "that" and "the way"
- [ ] "try to" → "aim for" or cut
- [ ] Semicolons → periods or colons for clarity

---

## Application in Code

These rules are embedded in the `build_content_prompt()` function as the `anti_ai_rules` constant. They're prepended to every content generation request to ensure the AI follows them.

### Integration Point
```python
anti_ai_rules = """
## CRITICAL WRITING RULES - FOLLOW STRICTLY
[Full rules text here]
"""
```

This ensures every generated piece of content is filtered through these rules before being returned to the user.

---

**These rules are battle-tested and have been refined through actual content generation. They prevent the "AI voice" that makes content feel generic and inauthentic.**
