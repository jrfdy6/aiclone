# ✅ Full Production Test Checklist — All 5 Categories

## 1. Pre-Test Environment Verification

### Required Environment Variables
- [ ] `GOOGLE_SEARCH_API_KEY` → Set in Railway
- [ ] `GOOGLE_SEARCH_ENGINE_ID` → Set in Railway
- [ ] Backend (FastAPI) can access these variables
- [ ] Firecrawl optional; pipeline works without it

### How to Verify
1. Check Railway environment variables dashboard
2. Backend logs should NOT show: "Google Custom Search API not configured"
3. Test a simple search to confirm Google API is working

### Optional (but helpful)
- [ ] `FIRECRAWL_API_KEY` → Optional, helps with JS-rendered pages
- [ ] Railway deployment is live and up-to-date

---

## 2. Prepare Test Locations

Choose locations for testing each category:

| Category          | Test Location | Notes                                                 |
|-------------------|---------------|-------------------------------------------------------|
| Pediatricians     | Washington DC | Should trigger 2-hop extraction (Healthgrades/Zocdoc) |
| Psychologists     | Washington DC | Psychology Today extraction verified locally          |
| Treatment Centers | Washington DC | RTC + PHP/IOP programs                                |
| Embassies         | Washington DC | Education Officers / Cultural Attachés                |
| Youth Sports      | Washington DC | Elite youth sports academies, clubs, programs         |

**Note:** Can all use "Washington DC" for consistency, or mix locations to test location handling.

---

## 3. Test Execution Steps

### Step 1: Access Find Prospects Page
- [ ] Open your app's "Find Prospects" page
- [ ] Verify UI is loading correctly
- [ ] Category selection is working

### Step 2: Individual Category Tests
For each category below, repeat these steps:

1. **Select Category**
   - [ ] Pediatricians
   - [ ] Psychologists
   - [ ] Treatment Centers
   - [ ] Embassies
   - [ ] Youth Sports

2. **Set Location**
   - [ ] Enter "Washington DC" (or test location)
   - [ ] Location is recognized

3. **Trigger Search**
   - [ ] Click "Search" button
   - [ ] Loading indicator appears
   - [ ] Search completes (may take 30-90 seconds)

4. **Check Results**
   - [ ] Prospects are displayed
   - [ ] Names are real people names (not garbage)
   - [ ] Titles/roles are accurate
   - [ ] Contact info is present (email/phone when available)
   - [ ] No obvious duplicates

5. **Review Backend Logs** (if accessible)
   - [ ] Check for errors during scraping
   - [ ] Verify Google API calls are working
   - [ ] Check enrichment logs

### Step 3: Category-Specific Validations

#### Pediatricians
- [ ] Verify profile URLs → 2-hop extraction works
- [ ] Phone numbers extracted from Healthgrades/Zocdoc profiles
- [ ] Practice websites are captured
- [ ] Names are formatted correctly (Dr. FirstName LastName)

#### Psychologists
- [ ] Psychology Today profiles are extracted
- [ ] Credentials are in title field (PhD, LCSW, etc.)
- [ ] Phone numbers from profile pages
- [ ] Profile URLs are source URLs

#### Treatment Centers
- [ ] Team/staff pages are found and scraped
- [ ] Leadership roles extracted (Directors, Coordinators)
- [ ] Full titles captured (e.g., "Chief Executive Officer" not just "Chief")
- [ ] Google enrichment fills in missing contacts
- [ ] Organization names match treatment center

#### Embassies
- [ ] Education/cultural pages are scraped
- [ ] Embassy officer roles extracted (Education Officer, Cultural Attaché)
- [ ] Embassy names captured (e.g., "Embassy of France")
- [ ] Email domains are embassy-related (if found)
- [ ] Google enrichment works for missing contacts

#### Youth Sports
- [ ] Coaches/staff pages are found
- [ ] Coach/director roles extracted
- [ ] Organization names captured (e.g., "Elite Soccer Academy")
- [ ] Multiple prospects per organization (coaches are often many)
- [ ] Google enrichment fills missing contacts

### Step 4: Combined Test (All Categories)
- [ ] Select ALL 5 categories at once
- [ ] Set location: "Washington DC"
- [ ] Trigger search
- [ ] Verify mix of all prospect types
- [ ] No conflicts between extraction methods
- [ ] Routing works correctly (right extraction method per URL type)
- [ ] Deduplication works across categories

---

## 4. Success Criteria

### Extraction Rate Targets

| Category          | Names   | Titles  | Emails  | Phones  |
|-------------------|---------|---------|---------|---------|
| Pediatricians     | 90-100% | 95-100% | 30-60%  | 85-95%  |
| Psychologists     | 90-100% | 90-95%  | 30-50%  | 85-95%  |
| Treatment Centers | 60-80%  | 70-80%  | 40-60%  | 50-70%  |
| Embassies         | 70-90%  | 70-90%  | 60-80%  | 50-70%  |
| Youth Sports      | 60-80%  | 70-85%  | 40-60%  | 50-70%  |

### Overall Success Criteria
- [ ] **At least 3-5 prospects per category**
- [ ] **Names extraction rate > 70% overall**
- [ ] **Titles extraction rate > 60% overall**
- [ ] **Contact info (email OR phone) > 40% overall**
- [ ] **No garbage names (< 5% false positives)**
- [ ] **Duplicate rate < 10%**

### Optimal Results
- [ ] 5-10+ prospects per category
- [ ] Names extraction rate > 85%
- [ ] Titles extraction rate > 75%
- [ ] Contact info (email OR phone) > 60%

---

## 5. Data Quality Checks

### Names Validation
- [ ] No generic terms ("Educational", "Patient Experience", etc.)
- [ ] No location names ("Washington DC", "Montgomery County")
- [ ] Real person names (First Last format)
- [ ] Proper capitalization

### Titles Validation
- [ ] Titles match category (pediatrician → MD, psychologist → PhD, etc.)
- [ ] Full titles captured (not truncated)
- [ ] Credentials included where applicable

### Contact Validation
- [ ] Email format is valid (contains @ and domain)
- [ ] Phone format is valid (XXX) XXX-XXXX or similar
- [ ] No generic emails (info@, contact@, etc.)
- [ ] Phone numbers have valid area codes

### Organization Validation
- [ ] Organization names make sense for category
- [ ] No HTML tags or special characters
- [ ] Properly formatted

---

## 6. Pipeline Validation

### Frontend Checks
- [ ] Prospects display correctly in pipeline
- [ ] Fit scores show properly (0-100 scale)
- [ ] Sorting by fit score works
- [ ] Filtering works (by status, tags, etc.)
- [ ] Contact info displays correctly
- [ ] Source URLs are clickable

### Backend Checks
- [ ] All extraction methods called correctly
- [ ] Google enrichment working
- [ ] Deduplication working (no duplicate emails/names)
- [ ] Firestore saves successful
- [ ] Error handling graceful (no crashes)

### Performance Checks
- [ ] Search completes in reasonable time (30-90 seconds)
- [ ] No timeout errors
- [ ] Google API quota not exceeded
- [ ] Memory usage reasonable

---

## 7. Troubleshooting Guide

### Issue: Missing Contacts
**Possible Causes:**
- Google Search API not configured
- Google enrichment not running
- Contact info not on scraped pages

**Solutions:**
- Verify Google API keys are set
- Check enrichment logs in backend
- Manually verify if contacts exist on source pages
- Check Google API quota/usage

### Issue: No Pages Found
**Possible Causes:**
- Search query too restrictive
- Location query issues
- Google API errors

**Solutions:**
- Verify search query in logs
- Try broader location (e.g., "DC" instead of "Washington DC")
- Check Google API response
- Review search query building logic

### Issue: Extraction Fails
**Possible Causes:**
- HTML structure changed
- Name validation too strict
- BeautifulSoup parsing issues

**Solutions:**
- Check scraped HTML content
- Review extraction patterns
- Verify name validation rules
- Check for HTML structure changes

### Issue: Duplicate Prospects
**Possible Causes:**
- Same person found in multiple categories
- Deduplication logic not working
- Email matching issues

**Solutions:**
- Check deduplication by email/name
- Review if duplicates are legitimate (same person, different roles)
- Verify deduplication is applied before saving

### Issue: Garbage Names
**Possible Causes:**
- Name validation too loose
- HTML parsing extracting non-name text
- Bad content from scraped pages

**Solutions:**
- Check name validation logic
- Review scraped content quality
- Improve bad_name_words filter
- Tighten name pattern matching

---

## 8. Test Results Template

```
TEST SESSION: [DATE]
Tester: [NAME]
Environment: Production (Railway)

CATEGORY: Pediatricians
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Location: Washington DC
Results:
  Total Found: [NUMBER]
  With Names: [NUMBER] ([%])
  With Titles: [NUMBER] ([%])
  With Emails: [NUMBER] ([%])
  With Phones: [NUMBER] ([%])

Sample Prospects:
1. [Name] - [Title] - [Org] - Email: [Yes/No] - Phone: [Yes/No]
2. [Name] - [Title] - [Org] - Email: [Yes/No] - Phone: [Yes/No]
3. [Name] - [Title] - [Org] - Email: [Yes/No] - Phone: [Yes/No]

Issues Found:
- [List any issues]

Status: ✅ PASS / ⚠️ PARTIAL / ❌ FAIL

---
[Repeat for each category]
```

---

## 9. Post-Test Actions

### If All Tests Pass ✅
- [ ] Document any edge cases found
- [ ] Optimize extraction rates if needed
- [ ] Consider adding Mom Groups category
- [ ] Production deployment confirmed

### If Issues Found ⚠️
- [ ] Prioritize fixes by impact
- [ ] Fix high-impact issues first (garbage names, routing failures)
- [ ] Re-test affected categories
- [ ] Document workarounds if needed

### Next Steps
- [ ] Run automated test script (if created)
- [ ] Compare automated vs manual results
- [ ] Update extraction logic based on findings
- [ ] Plan next category additions

---

## 10. Quick Reference

### API Endpoints (if testing via API)
```
POST /api/prospect-discovery/search-free
{
  "user_id": "your-user-id",
  "categories": ["pediatricians"],
  "location": "Washington DC",
  "max_results": 10
}
```

### Log Locations
- Railway logs: Check deployment logs dashboard
- Backend logs: Look for extraction method calls
- Google API logs: Check API usage dashboard

### Key Files
- `backend/app/services/prospect_discovery_service.py` - Main extraction logic
- `backend/app/routes/prospect_discovery.py` - API routes
- Frontend: Prospect discovery page

---

**Ready to test!** 🚀

Follow this checklist systematically and document results. Use the automated test script for quick validation, then do manual checks for data quality.

