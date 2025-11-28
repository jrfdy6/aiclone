# Comprehensive Prospect Discovery Test Plan

## Overview
Test all 5 production-ready prospect categories to validate the full pipeline end-to-end.

**Categories to Test:**
1. ✅ Pediatricians
2. ✅ Psychologists & Psychiatrists  
3. ✅ Treatment Center Admins/Directors
4. ✅ Embassy Education Contacts
5. ✅ Youth Sports Organizations

---

## Pre-Test Checklist

### Environment Setup
- [ ] Railway deployment is live and up-to-date
- [ ] Google Custom Search API is configured (required for enrichment)
- [ ] Frontend is accessible and connected to backend
- [ ] User account is set up for testing

### API Keys Verified
- [ ] `GOOGLE_SEARCH_API_KEY` - Required for team page discovery + contact enrichment
- [ ] `GOOGLE_SEARCH_ENGINE_ID` - Required for Google Custom Search
- [ ] `FIRECRAWL_API_KEY` - Optional (system works without it)

---

## Test Plan by Category

### Test 1: Pediatricians
**Location:** Washington DC  
**Category:** `pediatricians`  
**Expected Results:**
- **Names:** 90-100% (from Healthgrades/Zocdoc/Vitals profile pages)
- **Titles:** 95-100% (MD, Pediatrician, etc.)
- **Phones:** 85-95% (from profile pages)
- **Emails:** 30-60% (from practice websites via 2-hop extraction)

**What to Validate:**
- ✅ Names are extracted (e.g., "Dr. John Smith")
- ✅ Phone numbers are in format (XXX) XXX-XXXX
- ✅ Organization/practice names are captured
- ✅ No duplicate prospects
- ✅ Fit scores are calculated

**Sample Expected Output:**
```
Dr. Sarah Johnson
Title: Pediatrician, MD
Organization: Children's Medical Center
Phone: (202) 555-1234
Email: sjohnson@childrensmedical.com (if found)
```

---

### Test 2: Psychologists & Psychiatrists
**Location:** Washington DC  
**Category:** `psychologists` or `psychiatrists`  
**Expected Results:**
- **Names:** 90-100% (from Psychology Today profiles)
- **Titles:** 90-95% (PhD, PsyD, LCSW, etc.)
- **Phones:** 85-95% (from profile pages)
- **Emails:** 30-50% (from profile pages)

**What to Validate:**
- ✅ Names with credentials extracted (e.g., "Jane Doe, PhD, LCSW")
- ✅ Phone numbers present
- ✅ Credentials are in title field
- ✅ Psychology Today profile URLs are source URLs

**Sample Expected Output:**
```
Dr. Michael Chen, PhD
Title: Psychologist, PhD, LCSW
Organization: Private Practice
Phone: (703) 555-9876
Email: mchen@psychologypractice.com (if found)
```

---

### Test 3: Treatment Center Admins/Directors
**Location:** Washington DC  
**Category:** `treatment_centers`  
**Expected Results:**
- **Names:** 60-80% (from staff/team pages)
- **Titles:** 70-80% (Admissions Director, Clinical Director, etc.)
- **Emails:** 40-60% (via Google enrichment)
- **Phones:** 50-70% (via Google enrichment)

**What to Validate:**
- ✅ Leadership roles are extracted (Directors, Coordinators)
- ✅ Full titles captured (e.g., "Chief Executive Officer" not just "Chief")
- ✅ Organization names match treatment center
- ✅ Google enrichment fills missing contacts

**Sample Expected Output:**
```
Brian Setzer
Title: Chief Executive Officer
Organization: Newport Academy
Phone: (877) 929-5105 (if found via Google)
Email: bsetzer@newportacademy.com (if found via Google)
```

---

### Test 4: Embassy Education Contacts
**Location:** Washington DC  
**Category:** `embassies`  
**Expected Results:**
- **Names:** 70-90% (from structured embassy pages)
- **Titles:** 70-90% (Education Officer, Cultural Attaché, etc.)
- **Emails:** 60-80% (often on embassy contact pages)
- **Phones:** 50-70% (via contact pages + Google enrichment)

**What to Validate:**
- ✅ Embassy officer roles extracted
- ✅ Embassy names captured (e.g., "France Embassy")
- ✅ Email domains are embassy-related (if found)
- ✅ Google enrichment works for missing contacts

**Sample Expected Output:**
```
Marie Dubois
Title: Education Officer
Organization: Embassy of France
Phone: (202) 555-0000 (if found)
Email: education@ambafrance-us.org (if found)
```

---

### Test 5: Youth Sports Organizations
**Location:** Washington DC  
**Category:** `youth_sports`  
**Expected Results:**
- **Names:** 60-80% (varies by organization structure)
- **Titles:** 70-85% (Coach, Director, Program Director)
- **Emails:** 40-60% (via contact pages + Google enrichment)
- **Phones:** 50-70% (via contact pages + Google enrichment)

**What to Validate:**
- ✅ Coach/director roles extracted
- ✅ Organization names captured (e.g., "Elite Soccer Academy")
- ✅ Multiple prospects per organization (coaches are often many)
- ✅ Google enrichment fills missing contacts

**Sample Expected Output:**
```
John Martinez
Title: Head Coach
Organization: DC Elite Soccer Academy
Phone: (301) 555-2222 (if found)
Email: jmartinez@dcelitesoccer.com (if found)
```

---

## Test Execution Steps

### Step 1: Clear Previous Prospects (Optional)
```bash
# Via API or frontend
DELETE /api/prospects/clear-all?user_id=dev-user
```

### Step 2: Run Search for Each Category
**Via Frontend:**
1. Go to "Find Prospects" page
2. Select category (one at a time for clarity)
3. Enter location: "Washington DC"
4. Click "Search"
5. Wait for results (may take 30-60 seconds)

**Via API:**
```bash
POST /api/prospect-discovery/search-free
{
  "user_id": "dev-user",
  "categories": ["pediatricians"],
  "location": "Washington DC",
  "max_results": 10
}
```

### Step 3: Review Results
For each category, check:
- [ ] Prospects are returned (count > 0)
- [ ] Names are real people names (not garbage)
- [ ] Titles are accurate
- [ ] Contact info is present (email/phone when available)
- [ ] Organization names are correct
- [ ] No duplicates

### Step 4: Check Pipeline Page
1. Go to "Prospects" page
2. Verify all prospects are saved
3. Check fit scores are calculated
4. Verify sorting works

---

## Combined Test (All Categories at Once)

### Test: "Search All DC Influencers"
**Location:** Washington DC  
**Categories:** All 5 selected  
**Expected:** Mix of all prospect types

**What to Validate:**
- ✅ All categories contribute prospects
- ✅ No conflicts between extraction methods
- ✅ Routing works correctly (right extraction method per URL type)
- ✅ Deduplication works across categories
- ✅ Total prospect count is reasonable (20-50 for DC area)

---

## Success Criteria

### Minimum Viable Results
- ✅ At least 3-5 prospects per category
- ✅ Names extraction rate > 70% overall
- ✅ Titles extraction rate > 60% overall
- ✅ Contact info (email OR phone) > 40% overall

### Optimal Results
- ✅ 5-10+ prospects per category
- ✅ Names extraction rate > 85%
- ✅ Titles extraction rate > 75%
- ✅ Contact info (email OR phone) > 60%

---

## Common Issues & Troubleshooting

### Issue: No Prospects Found
**Possible Causes:**
- Google Search API not configured
- Location query too restrictive
- Category search terms not matching results
- URLs found but extraction failed

**Solutions:**
- Check Railway logs for errors
- Verify Google Search API key is set
- Try broader location (e.g., "DC" instead of "Washington DC")
- Check if URLs are being scraped successfully

### Issue: Garbage Names
**Possible Causes:**
- Name validation too loose
- HTML parsing extracting non-name text
- Bad content from scraped pages

**Solutions:**
- Check name validation logic
- Review scraped content quality
- Improve bad_name_words filter

### Issue: Missing Contact Info
**Possible Causes:**
- Contact info not on scraped pages
- Google enrichment not running
- Email/phone not near extracted names

**Solutions:**
- Verify Google Search API is working
- Check enrichment logs
- Manually verify if contacts exist on source pages

### Issue: Duplicate Prospects
**Possible Causes:**
- Same person found in multiple categories
- Deduplication logic not working

**Solutions:**
- Check deduplication by email/name
- Review if duplicates are legitimate (same person, different roles)

---

## Metrics to Track

### Extraction Metrics (Per Category)
- Total prospects found
- Names extracted (count)
- Titles extracted (count)
- Emails found (count)
- Phones found (count)
- Organizations captured (count)

### Quality Metrics
- Garbage names rate (< 5% is good)
- Duplicate rate (< 10% is good)
- Missing contact rate (expected 40-60% depending on category)

### Performance Metrics
- Average search time per category
- Time per prospect extracted
- Google API calls used

---

## Test Results Template

```
CATEGORY: Pediatricians
Date: [DATE]
Location: Washington DC

Results:
- Total Found: [NUMBER]
- With Names: [NUMBER] ([%])
- With Titles: [NUMBER] ([%])
- With Emails: [NUMBER] ([%])
- With Phones: [NUMBER] ([%])

Issues:
- [List any issues found]

Sample Prospects:
1. [Name] - [Title] - [Org] - Email: [Yes/No] - Phone: [Yes/No]

---
[Repeat for each category]
```

---

## Next Steps After Testing

### If All Tests Pass ✅
1. Document any edge cases found
2. Optimize extraction rates if needed
3. Add Mom Groups category
4. Production deployment

### If Issues Found ⚠️
1. Prioritize fixes by impact
2. Fix high-impact issues first (garbage names, routing failures)
3. Re-test affected categories
4. Document workarounds if needed

---

## Post-Test Validation

### Frontend Validation
- [ ] Prospects display correctly in pipeline
- [ ] Fit scores show properly
- [ ] Sorting/filtering works
- [ ] Contact info displays correctly

### Backend Validation
- [ ] All extraction methods called correctly
- [ ] Google enrichment working
- [ ] Deduplication working
- [ ] Firestore saves successful

### Data Quality Validation
- [ ] No obvious garbage data
- [ ] Contact info is valid format
- [ ] Organizations make sense for category
- [ ] Source URLs are correct

---

**Ready to test!** 🚀

Run through this systematically and document results. Once validated, we can tackle Mom Groups or optimize based on findings.

