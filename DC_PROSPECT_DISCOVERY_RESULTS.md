# DC Prospect Discovery Results

**Search:** Educational Consultants in Washington DC  
**Focus:** Private school placement specialists  
**Date:** November 25, 2025

---

## 🎯 Prospects Found

### 1. Cardinal Education
- **Website:** https://www.cardinaleducation.com/washington-d-c-homepage/
- **Specialty:** Private school admissions consulting
- **Location:** Washington DC

### 2. Carol Kinlan Consulting
- **Website:** https://www.carolkinlanconsulting.com
- **Specialty:** Educational consulting
- **Location:** Washington DC area

### 3. Clare Anderson Consulting
- **Specialty:** Educational consulting
- **Location:** Washington DC area

### 4. Spark Admissions
- **Website:** https://www.sparkadmissions.com/private-school-admissions-consulting/
- **Specialty:** Private school admissions consulting
- **Location:** Washington DC

### 5. Solomon Admissions
- **Specialty:** Admissions consulting
- **Location:** Washington DC

### 6. Carney Sandoe
- **Specialty:** Educational recruitment and consulting
- **Location:** National (serves DC)

---

## 📋 Next Steps

1. **Visit each website** to find specific contact names
2. **Use the scrape-urls endpoint** to extract more details:
   ```bash
   curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospect-discovery/scrape-urls \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "your_user_id",
       "urls": [
         "https://www.cardinaleducation.com/washington-d-c-homepage/",
         "https://www.carolkinlanconsulting.com",
         "https://www.sparkadmissions.com/private-school-admissions-consulting/"
       ]
     }'
   ```

3. **Run Topic Intelligence** on "referral_networks" theme to get language for outreach

---

## 🔄 How to Run More Searches

### AI-Powered Search (Best for finding real people)
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospect-discovery/ai-search \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_id",
    "specialty": "therapist",
    "location": "Washington DC",
    "additional_context": "adolescent therapy, school issues",
    "max_results": 10
  }'
```

### Direct URL Scraping (When you have profile URLs)
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospect-discovery/scrape-urls \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_id",
    "urls": [
      "https://www.psychologytoday.com/us/therapists/jane-doe-123456",
      "https://www.psychologytoday.com/us/therapists/john-smith-789012"
    ]
  }'
```

---

## 📊 System Summary

| Pipeline | Purpose | Best For |
|----------|---------|----------|
| **Topic Intelligence** | Learn language, trends, pain points | Content creation, outreach messaging |
| **AI Prospect Search** | Find real companies/people | Initial discovery |
| **URL Scraping** | Extract details from known profiles | Deep research on specific prospects |

