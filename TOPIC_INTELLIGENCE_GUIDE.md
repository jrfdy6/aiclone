# Topic Intelligence Pipeline Guide

Your AI Clone now includes a **Topic Intelligence Pipeline** — a complete "Prospect + Authority + Content Intelligence Engine" that powers outreach, insights, and content creation *without scraping LinkedIn*.

## 🎯 The 7 Intelligence Themes

| Theme | ID | Description |
|-------|-----|-------------|
| **A** | `enrollment_management` | Enrollment Management & Admissions |
| **B** | `neurodivergent_support` | Neurodivergent Support / One-to-One Care |
| **C** | `ai_in_education` | AI in Education / EdTech |
| **D** | `referral_networks` | Referral Networks: Therapists, Counselors, Treatment Centers |
| **E** | `fashion_tech` | Fashion Tech App / ClosetAI |
| **F** | `entrepreneurship_ops` | Entrepreneurship / Ops / Scalability |
| **G** | `content_marketing` | Content Marketing / LinkedIn Authority |

---

## 🚀 API Endpoints

### Get All Themes
```bash
GET /api/topic-intelligence/themes
```

Returns all themes with their sources and dork counts.

### Get Dorks for a Theme
```bash
GET /api/topic-intelligence/themes/{theme_id}/dorks
```

Returns all 20 Google dorks for a specific theme.

### Run Full Pipeline
```bash
POST /api/topic-intelligence/run
```

**Request:**
```json
{
  "user_id": "user123",
  "theme": "enrollment_management",
  "max_urls": 20,
  "generate_content": true,
  "generate_outreach": true,
  "custom_dorks": ["optional custom search queries"]
}
```

**Response includes:**
- `prospect_intelligence` - Target personas, pain points, language patterns
- `outreach_templates` - DM, email, and cold intro templates
- `content_ideas` - Posts, carousels, threads, videos
- `opportunity_insights` - Market gaps and actions
- `keywords` and `trending_topics`

### Store MCP-Generated Intelligence
```bash
POST /api/topic-intelligence/store
```

Store research done via Cursor MCPs (recommended for avoiding timeouts).

### Get User's Intelligence
```bash
GET /api/topic-intelligence/user/{user_id}
GET /api/topic-intelligence/user/{user_id}/{research_id}
```

---

## 📋 Master Google Dork List (20 per Theme)

### Theme A: Enrollment Management & Admissions

```
"enrollment management" "K-12" best practices
"private school admissions" challenges 2024
"independent school" enrollment strategy
"admissions director" interview education
"enrollment funnel" private school
site:nais.org enrollment trends
"boarding school" admissions process
"tuition assistance" private school strategy
"open house" admissions conversion
"yield rate" private school
"enrollment decline" independent school solutions
"waitlist management" admissions
"parent communication" admissions process
"school marketing" enrollment growth
"admissions CRM" education
"re-enrollment" retention strategy school
"financial aid" private school process
"diversity enrollment" independent school
"international student" admissions K-12
"virtual tour" school admissions
```

### Theme B: Neurodivergent Support

```
"neurodivergent students" "private school" support
"one-to-one care model" education
"autism support" learning environment
"ADHD accommodations" school program
"learning differences" private school
"executive function" support education
"sensory friendly" classroom
"IEP" private school implementation
"twice exceptional" education program
"neurodiversity" school culture
"social emotional learning" neurodivergent
"occupational therapy" school integration
"speech therapy" educational setting
"behavioral support" school program
"transition planning" neurodivergent students
"parent advocacy" neurodivergent education
"inclusive classroom" strategies
"differentiated instruction" learning differences
"assistive technology" education
"neurodivergent" "program director" interview
```

### Theme C: AI in Education / EdTech

```
"AI in education" trends 2024
"edtech" artificial intelligence classroom
"personalized learning" AI platform
"adaptive learning" technology education
"AI tutor" student outcomes
site:edsurge.com AI education
site:educause.edu artificial intelligence
"generative AI" classroom policy
"ChatGPT" education use cases
"AI assessment" student learning
"machine learning" education research
"AI literacy" K-12 curriculum
"intelligent tutoring system" effectiveness
"AI ethics" education teaching
"automated grading" AI education
"learning analytics" AI platform
"AI content creation" education
"natural language processing" education
"AI detection" academic integrity
"edtech startup" AI funding
```

### Theme D: Referral Networks

```
"educational consultant" referral network
"therapist" "private school" referral
"treatment center" educational placement
"school counselor" referral process
"mental health professional" school partnership
site:psychologytoday.com educational consultant
"wilderness therapy" school transition
"therapeutic boarding school" referral
"IEC" independent educational consultant
"college counselor" referral network
"family therapist" school recommendation
"neuropsychologist" school placement
"educational advocate" services
"transition specialist" education
"case manager" educational services
"outpatient treatment" school coordination
"residential treatment" educational component
"behavioral health" school referral
"special needs" placement consultant
"IECA" member educational consultant
```

### Theme E: Fashion Tech / ClosetAI

```
"wardrobe app" features review
"outfit coordination" AI technology
"closet organization" app comparison
"fashion tech" startup funding
"virtual closet" user experience
"style recommendation" algorithm
"capsule wardrobe" app
"fashion AI" personalization
"clothing inventory" app features
"outfit planner" technology
site:producthunt.com wardrobe app
site:reddit.com/r/malefashionadvice wardrobe app
site:reddit.com/r/femalefashionadvice closet app
"sustainable fashion" app technology
"color coordination" outfit algorithm
"mix and match" clothing app
"fashion recommendation engine"
"personal stylist" AI app
"wardrobe analytics" features
"outfit tracking" app review
```

### Theme F: Entrepreneurship / Ops

```
"operations scaling" startup best practices
"program management" education sector
"founder operations" playbook
"startup efficiency" frameworks
site:hbr.org operations management
"systems thinking" business operations
"process automation" small business
"operational excellence" education
"team scaling" startup guide
"SOPs" small business creation
"workflow optimization" founder
"delegation framework" entrepreneur
"hiring playbook" startup
"remote operations" management
"KPI dashboard" operations
"business systems" entrepreneur
"lean operations" startup
"operational efficiency" metrics
"founder burnout" prevention operations
"business process" documentation startup
```

### Theme G: Content Marketing / LinkedIn

```
"LinkedIn strategy" B2B 2024
"thought leadership" LinkedIn content
"LinkedIn algorithm" best practices
"content marketing" education sector
"personal branding" LinkedIn professional
site:socialmediaexaminer.com LinkedIn strategy
site:hubspot.com LinkedIn marketing
"LinkedIn engagement" tactics
"LinkedIn post" viral formula
"LinkedIn carousel" best practices
"content calendar" LinkedIn
"LinkedIn newsletter" growth
"authority building" content strategy
"LinkedIn hook" writing formulas
"storytelling" LinkedIn posts
"LinkedIn analytics" optimization
"content repurposing" LinkedIn
"LinkedIn video" engagement
"comment strategy" LinkedIn growth
"LinkedIn creator" mode tips
```

---

## 🔄 Recommended Workflow

### Option 1: Full API Pipeline (30-60s)
```bash
curl -X POST https://your-backend/api/topic-intelligence/run \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "theme": "enrollment_management"
  }'
```

### Option 2: MCP + Store (Recommended)

1. **In Cursor**, use Perplexity MCP to research dorks:
```
Research: "enrollment management" "K-12" best practices
```

2. **Use Firecrawl MCP** to scrape top URLs

3. **Store via API**:
```bash
curl -X POST https://your-backend/api/topic-intelligence/store \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "theme": "enrollment_management",
    "summary": "Your research summary...",
    "prospect_intelligence": {
      "target_personas": ["Admissions Director", "Head of School"],
      "pain_points": ["Declining enrollment", "Parent communication"],
      "language_patterns": ["yield rate", "enrollment funnel"]
    }
  }'
```

---

## 📊 What You Get

### Prospect Intelligence
- **Target Personas**: Who to reach out to
- **Pain Points**: What they struggle with
- **Language Patterns**: How they talk about problems
- **Decision Triggers**: What makes them buy
- **Objections**: What holds them back

### Outreach Templates
- **DM Template**: LinkedIn/social direct messages
- **Email Template**: Cold email with subject line
- **Cold Intro Template**: Mutual connection referral

### Content Ideas
- **Posts**: Single LinkedIn posts with hooks
- **Carousels**: Multi-slide educational content
- **Threads**: Twitter/X style threads
- **Videos**: Short-form video outlines

### Opportunity Insights
- Market gaps identified
- Supporting evidence
- Recommended actions

---

## 🎯 Use Cases

1. **Before Outreach Campaign**: Run pipeline to understand prospect language
2. **Content Planning**: Generate a month of content ideas
3. **Market Research**: Identify gaps and opportunities
4. **Competitive Analysis**: Understand industry positioning
5. **Authority Building**: Create thought leadership content

---

## 🛠 Technical Notes

- **Files Created**:
  - `backend/app/models/topic_intelligence.py` - Data models and dork lists
  - `backend/app/services/topic_intelligence_service.py` - Pipeline orchestration
  - `backend/app/routes/topic_intelligence.py` - API endpoints

- **Dependencies**: Uses existing Perplexity and Firecrawl clients

- **Storage**: Results stored in Firestore under `users/{user_id}/topic_intelligence/`

