# Prospect Discovery Pipeline

## How It Fits With Topic Intelligence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YOUR AI CLONE SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: TOPIC INTELLIGENCE          STEP 2: PROSPECT DISCOVERY            │
│  ─────────────────────────           ──────────────────────────            │
│  "Learn the language"                "Find the people"                     │
│                                                                             │
│  ┌─────────────────────┐             ┌─────────────────────┐               │
│  │ Research articles   │             │ Psychology Today    │               │
│  │ Industry trends     │             │ School directories  │               │
│  │ Pain point language │────────────▶│ NAIS member lists   │               │
│  │ Content ideas       │  Informs    │ Treatment centers   │               │
│  │ Outreach templates  │  targeting  │ Consultant profiles │               │
│  └─────────────────────┘             └──────────┬──────────┘               │
│                                                 │                          │
│                                                 ▼                          │
│                                      ┌─────────────────────┐               │
│                                      │ ACTUAL PROSPECTS    │               │
│                                      │ • Name              │               │
│                                      │ • Title             │               │
│                                      │ • Organization      │               │
│                                      │ • Specialty         │               │
│                                      │ • Location          │               │
│                                      │ • Contact info      │               │
│                                      └──────────┬──────────┘               │
│                                                 │                          │
│                                                 ▼                          │
│                                      ┌─────────────────────┐               │
│                                      │ /api/prospects      │               │
│                                      │ Score & prioritize  │               │
│                                      │ Personalized outreach│              │
│                                      └─────────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prospect Discovery Sources by Theme

### Theme D: Referral Networks (Therapists, Counselors, Treatment Centers)

| Source | URL Pattern | What to Extract |
|--------|-------------|-----------------|
| **Psychology Today** | `site:psychologytoday.com/us/therapists` | Name, specialty, location, bio, contact |
| **IECA Directory** | `site:iecaonline.com/quick-search` | Educational consultants by specialty |
| **GoodTherapy** | `site:goodtherapy.org/therapists` | Therapist profiles |
| **Treatment Centers** | `"therapeutic boarding school" "admissions"` | Admissions contacts |
| **NATSAP Members** | `site:natsap.org` | Treatment program directories |

**Site-Specific Dorks:**
```
site:psychologytoday.com "educational consultant" "private school"
site:psychologytoday.com "adolescent" "school placement" California
site:iecaonline.com "learning differences" consultant
site:goodtherapy.org "family therapy" "school issues"
"therapeutic boarding school" "admissions director" contact
"wilderness therapy" "educational consultant" referral
"residential treatment" "school liaison" email
```

---

### Theme A: Enrollment Management (Private School Admissions)

| Source | URL Pattern | What to Extract |
|--------|-------------|-----------------|
| **NAIS Member Schools** | `site:nais.org/member-schools` | School names, contacts |
| **School Websites** | `"admissions director" "private school"` | Name, email, phone |
| **BoardingSchoolReview** | `site:boardingschoolreview.com` | School profiles |
| **Private School Review** | `site:privateschoolreview.com` | School directories |

**Site-Specific Dorks:**
```
site:nais.org "member school" "admissions"
"admissions director" "independent school" email California
"head of enrollment" "private school" contact
"director of admissions" site:*.edu "K-12"
"enrollment management" "private school" "contact us"
site:boardingschoolreview.com "admissions office"
```

---

### Theme B: Neurodivergent Support Schools

| Source | URL Pattern | What to Extract |
|--------|-------------|-----------------|
| **NAIS LD Schools** | Schools with LD programs | Admissions, program directors |
| **Understood.org** | School finder | School profiles |
| **GreatSchools** | Special ed ratings | Contact info |

**Site-Specific Dorks:**
```
"learning differences" "private school" "admissions" contact
"neurodivergent" "program director" school email
"special education director" "independent school"
"one-to-one" "learning support" school "contact"
site:understood.org school finder
"twice exceptional" school "admissions office"
```

---

### Theme E: Fashion Tech (For ClosetAI - Find Beta Users/Influencers)

| Source | URL Pattern | What to Extract |
|--------|-------------|-----------------|
| **Instagram** (via Google) | Fashion micro-influencers | Profile links |
| **YouTube** | Fashion/style creators | Channel info |
| **Reddit** | Active community members | Usernames for outreach |

**Site-Specific Dorks:**
```
site:instagram.com "capsule wardrobe" "link in bio"
site:youtube.com "closet organization" "subscribe"
site:reddit.com/r/femalefashionadvice "wardrobe app" recommendation
"fashion blogger" "outfit planning" contact
"style influencer" "wardrobe" email collaboration
```

---

## API Design: Prospect Discovery Endpoint

### `POST /api/prospect-discovery/search`

**Request:**
```json
{
  "user_id": "user123",
  "theme": "referral_networks",
  "source": "psychology_today",
  "filters": {
    "specialty": "educational consultant",
    "location": "California",
    "keywords": ["private school", "learning differences"]
  },
  "max_results": 20
}
```

**Response:**
```json
{
  "success": true,
  "prospects": [
    {
      "name": "Dr. Jane Smith",
      "title": "Educational Consultant",
      "organization": "Smith Educational Consulting",
      "specialty": ["Private School Placement", "Learning Differences"],
      "location": "Los Angeles, CA",
      "source_url": "https://psychologytoday.com/...",
      "contact": {
        "email": "jane@smitheducation.com",
        "phone": "(310) 555-1234",
        "website": "smitheducation.com"
      },
      "bio_snippet": "I help families find the right school fit...",
      "fit_score": 85
    }
  ],
  "total_found": 20,
  "source": "psychology_today"
}
```

---

## Implementation Plan

### Phase 1: Source-Specific Scrapers
1. **Psychology Today scraper** - Extract therapist/consultant profiles
2. **School directory scraper** - Extract admissions contacts
3. **IECA directory scraper** - Extract educational consultants

### Phase 2: Prospect Extraction
1. Parse scraped HTML for structured data
2. Extract: Name, Title, Organization, Specialty, Location, Contact
3. Clean and normalize data

### Phase 3: Integration
1. Feed prospects into `/api/prospects` 
2. Auto-score based on fit criteria
3. Generate personalized outreach using Topic Intelligence language

---

## Key Differences

| Topic Intelligence | Prospect Discovery |
|-------------------|-------------------|
| Finds articles *about* your market | Finds *actual people* in your market |
| Learns language & pain points | Gets names, titles, contacts |
| Generic industry research | Specific prospect profiles |
| Content & outreach inspiration | Outreach targets |
| Run occasionally for research | Run regularly to build pipeline |

---

## Recommended Workflow

1. **Weekly:** Run Topic Intelligence to stay current on language/trends
2. **Daily:** Run Prospect Discovery to find new targets
3. **Combine:** Use Topic Intelligence language in Prospect Discovery outreach

---

## Next Steps

1. Build Psychology Today scraper (highest value for referral networks)
2. Build school directory scraper (for enrollment management)
3. Create unified prospect extraction service
4. Connect to existing `/api/prospects` for scoring

