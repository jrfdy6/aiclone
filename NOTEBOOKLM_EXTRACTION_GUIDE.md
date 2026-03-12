# NotebookLM Extraction Guide for AI Clone Project

This guide maps your **aiclone project assets** to the **NotebookLM Compound Intelligence Prompt Pack 2026** extraction prompts.

## 🎯 What You Can Extract

Your aiclone project contains **goldmine assets** that are perfect for NotebookLM extraction:

---

## PHASE I: EXTRACTION

### E1. Prompt Library Extractor

**What to Extract:**
- **System prompts** from `backend/app/routes/content_generation.py` (lines 50-685)
  - `build_content_prompt()` function
  - Anti-AI writing filter rules
  - Voice matching instructions
  - PACER framework guidance
  
- **CustomGPT instructions** from `CUSTOMGPT_INSTRUCTIONS.md`
  - Core persona & tone prompts
  - Onboarding flow prompts
  - API endpoint documentation prompts

- **AI Jumpstart Playbook prompts** from `AI_JUMPSTART_PLAYBOOK.md`
  - 10 starter prompts with intent
  - Onboarding template prompts

**Files to Upload:**
- `backend/app/routes/content_generation.py` (extract prompt sections)
- `CUSTOMGPT_INSTRUCTIONS.md`
- `AI_JUMPSTART_PLAYBOOK.md`

**NotebookLM Prompt:**
```
Act as a Prompt Archaeologist. Scan my aiclone project documentation loaded in source memory.

Identify every prompt structure I have created for:
1. Content generation (anti-AI writing, voice matching, PACER framework)
2. AI assistant onboarding (CustomGPT instructions, Jumpstart Playbook)
3. System prompts for ghostwriting and persona matching

Group them by category (Content Creation, AI Training, System Architecture).
Refine them: Rewrite my prompts into professional, reusable templates with [VARIABLE] placeholders.

**Output Format:**
Provide a Markdown Table: | Category | Prompt Name | Refined Template (Code Block) | Usage Context |
```

---

### E2. Mega-Prompt Constructor

**What to Extract:**
- **Content Generation Mega-Prompt** (`build_content_prompt()` function)
  - Has Persona, Objective, Context, Constraints, Output Format
  - Includes anti-hallucination rules
  - Voice markers and style rules
  - Narrative arc structure

**Files to Upload:**
- `backend/app/routes/content_generation.py` (lines 50-685)

**NotebookLM Prompt:**
```
Act as a Prompt Engineer. Scan my content_generation.py file for the Mega-Prompt structure.

**Task:** Extract the content generation Mega-Prompt that includes:
- Persona definition
- Objective
- Context handling
- Constraints (anti-AI writing, anti-hallucination)
- Output Format (3 options, narrative arc)

For this Mega-Prompt, provide:
1. **Name:** Content Generation System Prompt
2. **Template:** The full copy-paste prompt with [VARIABLE] placeholders
3. **Gatekeeper:** The specific "Stop & Verify" steps to prevent hallucinations
```

---

### E3. Framework Finder

**What to Extract:**
- **People/Process/Culture Framework** (`philosophy.md`, `JOHNNIE_FIELDS_PERSONA.md`)
- **PACER Framework** (from content generation - Problem, Audience, Context, Emotion, Result)
- **9/1/1 Content Formula** (9 value, 1 sell, 1 personal)
- **Gap Theory** (minimize gap between real self and online presence)
- **Temperature Gauge Leadership** (keep team operating at success temperature)
- **Last to Speak Framework** (be last person to talk for better adoption)

**Files to Upload:**
- `philosophy.md`
- `JOHNNIE_FIELDS_PERSONA.md`
- `audience_communication.md`
- `CONTENT_STYLE_GUIDE.md` (if exists)

**NotebookLM Prompt:**
```
Act as a Systems Analyst. Identify every named framework, methodology, or mental model I have created in the aiclone project.

**Output:**
Compile a **Master Framework Index**. For each:
* **Name:** (Create an acronym if I didn't name it)
* **Core Components:** The step-by-step logic
* **Evolution:** How did this idea change from first mention to last?
* **Application:** When exactly should I use this?

Look for:
- People/Process/Culture framework
- PACER content framework
- 9/1/1 content formula
- Gap Theory
- Temperature Gauge Leadership
- Last to Speak framework
- Any other systematic approaches
```

---

### E4. SOP Resurrector

**What to Extract:**
- **Prospect Discovery Pipeline** (`PROSPECT_DISCOVERY_PIPELINE.md`)
- **Content Generation Workflow** (from code: persona chunks → example chunks → prompt building → generation)
- **LinkedIn Intelligence Workflow** (`LINKEDIN_SCRAPING_STRATEGY.md`, `LINKEDIN_INDUSTRY_TARGETING.md`)
- **Topic Intelligence Pipeline** (`TOPIC_INTELLIGENCE_GUIDE.md`)
- **Deployment Workflows** (`RAILWAY_DEPLOYMENT_CHECKLIST.md`, `FRONTEND_DEPLOYMENT_CHECKLIST.md`)
- **Testing Procedures** (`TESTING_GUIDE.md`, `PRODUCTION_TESTING_GUIDE.md`)

**Files to Upload:**
- `PROSPECT_DISCOVERY_PIPELINE.md`
- `TOPIC_INTELLIGENCE_GUIDE.md`
- `LINKEDIN_SCRAPING_STRATEGY.md`
- `TESTING_GUIDE.md`
- `RAILWAY_DEPLOYMENT_CHECKLIST.md`
- `README.md` (architecture section)

**NotebookLM Prompt:**
```
Act as a Process Engineer. Find every instance where I described a workflow in the aiclone project.

**Task:** Format these as formal SOPs.

**Structure:**
1. **Objective:** Goal & Prerequisites
2. **The Process:** Numbered steps
3. **Definition of Done:** How to verify quality (based on my corrections)

Extract workflows for:
- Prospect discovery pipeline
- Content generation workflow
- LinkedIn intelligence gathering
- Topic intelligence research
- Deployment procedures
- Testing protocols
```

---

## PHASE II: COMPOUND INTELLIGENCE

### C1. Consistency Audit

**What to Compare:**
- **Voice patterns** across different persona files
- **Content style rules** vs. actual LinkedIn examples
- **Philosophy statements** vs. implementation in code

**Files to Upload:**
- `JOHNNIE_FIELDS_PERSONA.md`
- `voice_patterns.md`
- `audience_communication.md`
- `philosophy.md`
- `CONTENT_STYLE_GUIDE.md` (if exists)
- LinkedIn example posts from persona file

**NotebookLM Prompt:**
```
Act as a Logic Auditor. Source A is my documented voice/style guidelines. Source B is my actual LinkedIn examples and code implementation.

**Task:** Compare voice consistency across:
1. **Agreement Table:** Where do my guidelines align perfectly with my examples?
2. **Conflict Table:** Where do my documented rules differ from my actual output?
3. **Verdict:** Based on depth of reasoning, which voice patterns are most authentic and why?
```

---

### C3. Routing Guide

**What to Analyze:**
- **When to use different AI models** (ChatGPT vs Claude vs Gemini)
- **When to use different extraction methods** (free scraping vs Firecrawl vs Perplexity)
- **When to use different content generation approaches**

**Files to Upload:**
- `PROSPECT_DISCOVERY_PIPELINE.md`
- `LINKEDIN_SCRAPING_STRATEGY.md`
- `PERPLEXITY_SETUP.md`
- `FIRECRAWL_COST_ANALYSIS.md`
- Code comments about model selection

**NotebookLM Prompt:**
```
Act as a Performance Analyst. Evaluate the tool selection logic in my aiclone project.

**Task:** Create a Routing Guide for my future work:
* "Use **ChatGPT** for..." (List specific task types from my code/docs)
* "Use **Claude** for..." (List specific task types)
* "Use **Gemini** for..." (List tasks requiring large context)
* "Use **Firecrawl** for..." (vs free scraping)
* "Use **Perplexity** for..." (vs Google Search)
```

---

### C5. Gap Analysis

**What to Analyze:**
- **Documented processes** vs. **actual implementation**
- **Planned features** vs. **completed features**
- **Testing plans** vs. **test results**

**Files to Upload:**
- Phase roadmap files (`PHASE_*_ROADMAP.md`)
- Implementation status files (`PHASE_*_COMPLETE.md`)
- Test results vs. test plans

**NotebookLM Prompt:**
```
**System Role:** Lead Strategy Auditor.
**Context:** My historical attempts at building aiclone are in memory (roadmaps, implementation status, test results).

**Task:**
1. **Scan:** How did I try to solve problems before?
2. **Critique:** Identify logical dead ends or loops I got stuck in
3. **Synthesize:** Propose a NEW approach that explicitly avoids those previous pitfalls
```

---

## PHASE III: THE MIRROR

### #1. Cognitive Desire Path

**What to Identify:**
- **Repeated debugging patterns** (checking logs, fixing CORS, Firebase setup issues)
- **Common workflow friction points** (deployment, testing, API integration)
- **Documentation patterns** (creating many status/roadmap files)

**Files to Upload:**
- All `*_FIX.md` files
- `RAILWAY_TROUBLESHOOTING.md`
- `DEBUG_*.md` files
- `*_STATUS.md` files

**NotebookLM Prompt:**
```
Act as an Urban Planner for the mind. Review my aiclone project documentation as traffic patterns.

**Identify:** My "Desire Paths" - workflows where I consistently:
- Hit the same errors (CORS, Firebase, deployment)
- Create similar documentation patterns
- Get stuck in similar debugging loops

**Output:**
1. **Friction Map:** The top 3 struggle points
2. **Paved Road:** Write a new Master Prompt that anticipates these struggles and solves them automatically
```

---

### #3. Voice Fingerprint

**What to Analyze:**
- **Your actual writing voice** from persona files
- **Documentation style** across all markdown files
- **Code comments** and inline documentation

**Files to Upload:**
- `JOHNNIE_FIELDS_PERSONA.md`
- `voice_patterns.md`
- `audience_communication.md`
- `philosophy.md`
- Sample markdown documentation files

**NotebookLM Prompt:**
```
Act as a Computational Linguist. Analyze my writing in the aiclone project documentation.

**Decode:** My Voice Fingerprint:
- Burstiness (sentence length variation)
- Vocabulary (signature phrases, technical terms)
- Tone (direct, practical, vulnerable, confident)
- Structure (how I organize information)

**Output:** A "Style Guide" system prompt I can paste into any AI to make it write exactly like me.
```

---

### #10. Fine-Tuning Formatter

**What to Extract:**
- **Successful content generation examples** (if you have input/output pairs)
- **Effective prompt/response pairs** from your chat history
- **Persona matching examples** (topic → persona chunks → generated content)

**Files to Upload:**
- Your processed AI exports (the 22 NotebookLM-ready files)
- Any saved prompt/response examples
- Content generation test results

**NotebookLM Prompt:**
```
Act as a Data Scientist. Extract Question/Answer pairs from my aiclone project that resulted in successful, high-quality outcomes.

**Output:**
Format them into a clean **JSONL structure** for fine-tuning:

{"messages": [{"role": "user", "content": "[INPUT]"}, {"role": "assistant", "content": "[IDEAL OUTPUT]"}]}

Focus on:
- Content generation prompts that produced authentic voice
- System prompts that prevented hallucinations
- Workflow prompts that led to successful implementations
```

---

## FINAL SYNTHESIS

### #16. The Master Architect

**What to Synthesize:**
- **Consciousness:** Your habits (documentation, testing, deployment patterns)
- **Environment:** Your assets (frameworks, prompts, SOPs, code)
- **Vision:** Your goals (from roadmaps, README, project structure)

**Files to Upload:**
- **ALL** of the above files
- `README.md`
- Key phase completion summaries
- Your processed AI chat exports

**NotebookLM Prompt:**
```
**Role:** Act as the Chief Architect.

**Context:** We have completed analysis of Consciousness (habits), Environment (assets), and Vision (goals) from the aiclone project.

**Task:** Synthesize all insights into **The 2026 Blueprint for AI Clone Development**.

**Output Format:** Markdown Document.

**Sections:**
1. **The User Kernel:** A system prompt describing how to prompt me (my biases, shortcuts, preferred style)
2. **The Asset Registry:** A list of the recovered SOPs, frameworks, and IP we found
3. **The Horizon Line:** Predicted risks and "Kill Strategies" for upcoming aiclone features
4. **The Initialization Block:** A single Master System Prompt I can paste into a fresh AI instance to load this entire context instantly
```

---

## 📋 RECOMMENDED UPLOAD ORDER

### Week 1: Core Assets
1. `JOHNNIE_FIELDS_PERSONA.md`
2. `philosophy.md`
3. `audience_communication.md`
4. `CUSTOMGPT_INSTRUCTIONS.md`
5. `AI_JUMPSTART_PLAYBOOK.md`

### Week 2: Technical Assets
1. Extract prompt sections from `backend/app/routes/content_generation.py`
2. `PROSPECT_DISCOVERY_PIPELINE.md`
3. `TOPIC_INTELLIGENCE_GUIDE.md`
4. `LINKEDIN_SCRAPING_STRATEGY.md`
5. `README.md`

### Week 3: Process & Workflows
1. All `PHASE_*_ROADMAP.md` and `PHASE_*_COMPLETE.md` files
2. `TESTING_GUIDE.md`
3. `RAILWAY_DEPLOYMENT_CHECKLIST.md`
4. Troubleshooting and fix documentation

### Week 4: Synthesis
1. Upload your processed AI chat exports (22 files from `~/Downloads/notebooklm_ready`)
2. Run Master Architect prompt
3. Create your 2026 Blueprint

---

## 🎯 Expected Outcomes

After running these extractions, you'll have:

1. **Reusable Prompt Library** - All your system prompts, content generation prompts, and AI training prompts in one place
2. **Framework Documentation** - Your People/Process/Culture, PACER, 9/1/1, and other frameworks clearly defined
3. **SOP Library** - Step-by-step workflows for prospect discovery, content generation, deployment, testing
4. **Voice Style Guide** - A system prompt that makes any AI write like you
5. **Master Blueprint** - A single initialization prompt that loads your entire context into any new AI session

This transforms your aiclone project from "code + docs" into **compound intelligence assets** that compound over time.
