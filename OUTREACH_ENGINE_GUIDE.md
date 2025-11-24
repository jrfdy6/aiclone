# 🚀 Outreach Engine - Complete Guide

Complete outreach automation system with prospect segmentation, sequence generation, scoring, engagement tracking, and weekly cadence management.

---

## 📋 Overview

The Outreach Engine divides your audience into segments and generates personalized outreach sequences tailored to each segment:

- **50% Private school admins / mental health / referral network**
- **50% EdTech / AI-savvy leaders**
- **5% Stealth founder / early adopters**

Each segment receives customized messaging, sequences, and engagement tracking.

---

## 🎯 Features

### 1. Prospect Segmentation
Automatically tags prospects with:
- Segment assignment (referral_network, thought_leadership, stealth_founder)
- Industry, role, location
- Engagement potential (0.0-1.0)
- PACER relevance (which content pillars apply)

### 2. Outreach Sequence Design
Generates complete sequences per audience segment:
- **Referral network**: Relationship-building + value-sharing messages
- **Thought leadership**: Insights + engagement hooks
- **Stealth founder**: Subtle mentions, curiosity-driven

### 3. Scoring & Prioritization
Scores prospects by:
- **Fit** (role relevance / audience type)
- **Referral capacity** (likelihood to refer or respond)
- **Signal strength** (engagement / online presence)

Focus manual effort on top-tier prospects.

### 4. Engagement Tracking
Tracks engagement from DMs and follow-ups:
- Replies, meeting bookings, email responses
- Feeds results into learning patterns
- Identifies which messages, formats, or angles get best response per segment

### 5. Calendar & Cadence
Weekly outreach cadence:
- Connection requests: 30-50/week
- Follow-ups: 2-3 rounds per prospect
- Check-ins: Quarterly re-engagement for dormant contacts

---

## 🔌 API Endpoints

### 1. Segment Prospects

**POST** `/api/outreach/segment`

Segment prospects into audience segments with tags.

**Request:**
```json
{
  "user_id": "user123",
  "prospect_ids": ["prospect_1", "prospect_2"],  // Optional: segment all if null
  "target_distribution": {  // Optional: custom distribution
    "referral_network": 0.5,
    "thought_leadership": 0.5,
    "stealth_founder": 0.05
  }
}
```

**Response:**
```json
{
  "success": true,
  "total_prospects": 100,
  "segments": {
    "referral_network": 50,
    "thought_leadership": 48,
    "stealth_founder": 2
  },
  "tagged_prospects": [
    {
      "segment": "referral_network",
      "industry": "Education",
      "role": "School Administrator",
      "location": "New York",
      "engagement_potential": 0.75,
      "pacer_relevance": ["referral"],
      "prospect_id": "prospect_1"
    }
  ]
}
```

---

### 2. Generate Outreach Sequence

**POST** `/api/outreach/sequence/generate`

Generate complete outreach sequence for a prospect with variations.

**Request:**
```json
{
  "user_id": "user123",
  "prospect_id": "prospect_1",
  "sequence_type": "3-step",  // Options: "3-step", "5-step", "7-step", "soft_nudge", "direct_cta"
  "num_variants": 3  // Number of variants per step
}
```

**Response:**
```json
{
  "success": true,
  "prospect_id": "prospect_1",
  "segment": "referral_network",
  "sequence_type": "3-step",
  "sequence": {
    "prospect_id": "prospect_1",
    "segment": "referral_network",
    "connection_request": {
      "variants": [
        {
          "variant": 1,
          "message": "Hi John, I work with schools and partners supporting neurodivergent learners. I'd love to connect..."
        }
      ]
    },
    "initial_dm": {
      "variants": [...]
    },
    "followup_1": {
      "variants": [...]
    },
    "followup_2": {
      "variants": [...]
    },
    "send_dates": {
      "connection_request": 1735123456.0,
      "initial_dm": 1735296256.0,
      "followup_1": 1735555456.0
    },
    "current_step": 0,
    "status": "not_sent"
  },
  "variants": {
    "connection_request": [...],
    "initial_dm": [...],
    "followup_1": [...]
  }
}
```

---

### 3. Prioritize Prospects

**POST** `/api/outreach/prioritize`

Score and prioritize prospects by fit, referral capacity, and signal strength.

**Request:**
```json
{
  "user_id": "user123",
  "min_fit_score": 70,
  "min_referral_capacity": 60,
  "min_signal_strength": 50,
  "segment": "thought_leadership",  // Optional: filter by segment
  "limit": 50
}
```

**Response:**
```json
{
  "success": true,
  "total_scored": 45,
  "top_tier_count": 12,
  "prospects": [
    {
      "prospect_id": "prospect_1",
      "name": "John Doe",
      "job_title": "VP of EdTech",
      "company": "EdTech Corp",
      "fit_score": 85,
      "referral_capacity": 80,
      "signal_strength": 75,
      "priority_score": 80.25,
      "segment": "thought_leadership"
    }
  ]
}
```

---

### 4. Track Engagement

**POST** `/api/outreach/track-engagement`

Track engagement from outreach (replies, meetings, responses).

**Request:**
```json
{
  "user_id": "user123",
  "prospect_id": "prospect_1",
  "outreach_type": "initial_dm",  // connection_request, initial_dm, followup_1, followup_2, followup_3
  "engagement_status": "replied",  // sent, delivered, opened, replied, meeting_booked, not_interested, no_response
  "engagement_data": {
    "reply_content": "Thanks, I'm interested!",
    "meeting_scheduled": false,
    "response_time_hours": 12
  }
}
```

**Response:**
```json
{
  "success": true,
  "prospect_id": "prospect_1",
  "engagement_status": "replied",
  "learning_patterns_updated": true
}
```

---

### 5. Generate Weekly Cadence

**POST** `/api/outreach/cadence/weekly`

Build weekly outreach cadence with scheduled entries.

**Request:**
```json
{
  "user_id": "user123",
  "week_start_date": 1735123456.0,  // Optional: Unix timestamp (defaults to current Monday)
  "target_connection_requests": 40,
  "target_followups": 30
}
```

**Response:**
```json
{
  "success": true,
  "week_start": "2024-12-23",
  "week_end": "2024-12-29",
  "total_outreach": 70,
  "distribution": {
    "referral_network": 20,
    "thought_leadership": 18,
    "stealth_founder": 2
  },
  "entries": [
    {
      "day": "Monday",
      "date": "2024-12-23",
      "time": "9:00 AM",
      "prospect_id": "prospect_1",
      "prospect_name": "John Doe",
      "segment": "referral_network",
      "outreach_type": "connection_request",
      "sequence_step": 0,
      "message_variant": 1,
      "priority_score": 85.5
    }
  ]
}
```

---

### 6. Get Outreach Metrics

**POST** `/api/outreach/metrics`

Track engagement performance by segment.

**Request:**
```json
{
  "user_id": "user123",
  "date_range_days": 30
}
```

**Response:**
```json
{
  "success": true,
  "date_range_days": 30,
  "total_outreach": 150,
  "connection_requests_sent": 60,
  "dms_sent": 50,
  "followups_sent": 40,
  "replies_received": 25,
  "meetings_booked": 8,
  "reply_rate": 16.67,
  "meeting_rate": 5.33,
  "segment_performance": {
    "referral_network": {
      "total": 75,
      "replies": 15,
      "meetings": 5,
      "reply_rate": 20.0,
      "meeting_rate": 6.67
    },
    "thought_leadership": {
      "total": 70,
      "replies": 9,
      "meetings": 3,
      "reply_rate": 12.86,
      "meeting_rate": 4.29
    }
  },
  "top_performing_sequences": [...]
}
```

---

### 7. Get Sequence

**GET** `/api/outreach/sequence/{prospect_id}?user_id=user123`

Retrieve outreach sequence for a prospect.

---

## 📝 Message Variations by Segment

### Referral Network (50%)

**Connection Request:**
> Hi {name}, I work with schools and partners supporting neurodivergent learners. I'd love to connect and share insights about referral partnerships.

**Initial DM:**
> Hi {name}, thanks for connecting. I work with schools and partners building referral networks. I've been researching best practices in student support transitions — would you be open to a quick 15-min chat to share insights?

**Follow-up:**
> Hi {name}, following up on my previous message. I know you're busy, but thought this might be worth 5 minutes: [specific value]. Still interested?

---

### Thought Leadership (50%)

**Connection Request:**
> Hi {name}, I saw your work in {job_title} at {company}. I'm also focused on AI and EdTech innovation. Would love to connect and share insights.

**Initial DM:**
> Hi {name}, I've been researching {outreach_angle} and found some interesting patterns. Your perspective as {job_title} at {company} would be valuable. Worth a quick call?

**Follow-up:**
> Hi {name}, I know inboxes get full. If this isn't the right time, no worries. But I wanted to share this one insight that might be relevant for {company}: [insight].

---

### Stealth Founder (5%)

**Connection Request:**
> Hi {name}, I'm also building in the EdTech space. Would love to connect with fellow founders.

**Initial DM:**
> Hi {name}, fellow builder here. I'm working on tools for educators and curious about your experience building {company}. Open to a quick chat?

**Follow-up:**
> Hi {name}, I understand this might not be a priority right now. If that changes, I'm here. Otherwise, I'll respect your time and step back.

---

## 🔄 Workflow Example

### Step 1: Discover & Approve Prospects
```bash
POST /api/prospects/discover
POST /api/prospects/approve
```

### Step 2: Score Prospects
```bash
POST /api/prospects/score
```

### Step 3: Segment Prospects
```bash
POST /api/outreach/segment
```

### Step 4: Prioritize Prospects
```bash
POST /api/outreach/prioritize
```

### Step 5: Generate Sequences for Top Prospects
```bash
POST /api/outreach/sequence/generate
# Repeat for each top prospect
```

### Step 6: Generate Weekly Cadence
```bash
POST /api/outreach/cadence/weekly
```

### Step 7: Execute Outreach
Manually send connection requests and DMs from cadence entries.

### Step 8: Track Engagement
```bash
POST /api/outreach/track-engagement
# Track as responses come in
```

### Step 9: Review Metrics
```bash
POST /api/outreach/metrics
# Weekly review of performance
```

---

## 🎯 Best Practices

1. **Start Small**: Test with 10-20 prospects before scaling
2. **Personalize**: Always review and customize generated messages
3. **Track Everything**: Log all engagement to improve learning patterns
4. **Segment Balance**: Maintain 50/50/5 distribution for best results
5. **Follow Up**: Don't give up after first attempt — use 2-3 follow-ups
6. **Monitor Metrics**: Review weekly metrics to identify what works

---

## 🔗 Integration with Other Systems

### Content Generation
Outreach sequences reference research insights from `/api/research/enhanced/complete-workflow` for context.

### Learning Patterns
Engagement data automatically feeds into `/api/learning/update-patterns` to improve future outreach.

### Prospect Discovery
Segmented prospects integrate with `/api/prospects/discover` and `/api/prospects/score`.

---

## 📊 Weekly Cadence Schedule

**Monday**
- 9:00 AM: Connection requests (high priority)
- 2:00 PM: Follow-ups (round 1)

**Tuesday**
- 9:00 AM: Connection requests (referral network)
- 2:00 PM: Follow-ups (round 2)
- 4:00 PM: DMs (thought leadership)

**Wednesday**
- 9:00 AM: Connection requests (thought leadership)
- 2:00 PM: Follow-ups (round 3)

**Thursday**
- 9:00 AM: Connection requests (stealth founder)
- 1:00 PM: DMs (referral network)
- 3:00 PM: Follow-ups (final)

**Friday**
- 9:00 AM: Connection requests (catch-up)
- 2:00 PM: Weekly review & metrics

---

## 🚀 Next Steps

1. **Test Segmentation**: Run `/api/outreach/segment` on your existing prospects
2. **Generate Sequences**: Create sequences for your top 10 prospects
3. **Build Cadence**: Generate your first weekly cadence
4. **Track Engagement**: Log responses as they come in
5. **Review Metrics**: Analyze performance weekly

---

## 📚 Related Documentation

- [PROSPECTING_WORKFLOW_API_DOCS.md](./PROSPECTING_WORKFLOW_API_DOCS.md) - Prospect discovery and scoring
- [ENHANCED_RESEARCH_PIPELINE.md](./ENHANCED_RESEARCH_PIPELINE.md) - Research insights that feed outreach
- [LINKEDIN_CONTENT_GUIDE.md](./DAILY_PACER_CONTENT_COMMAND.md) - Content strategy alignment

---

**Questions?** Check the API endpoints or review the code in `backend/app/routes/outreach_engine.py`.

