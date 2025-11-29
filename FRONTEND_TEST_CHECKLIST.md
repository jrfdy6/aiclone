# ✅ Frontend Test Checklist - Full System Validation

This checklist validates the complete end-to-end system including frontend, backend, extractors, and database.

---

## 🟦 **STEP 1: Full 5-Category Test (Main Workflow)**

### **Setup**
- [ ] Go to prospect discovery page in frontend
- [ ] Select ALL 5 categories:
  - [ ] ✅ Psychologists & Psychiatrists
  - [ ] ✅ Education Consultants
  - [ ] ✅ Youth Sports Programs
  - [ ] ✅ Pediatricians
  - [ ] ✅ Treatment Centers
- [ ] Enter location: `Washington DC`
- [ ] Click "Find Prospects"

### **Expected Results**
- [ ] Search completes in < 90 seconds
- [ ] **At least 7-20 prospects** displayed
- [ ] All 5 categories represented in results
- [ ] Prospects sorted by score (highest first)

### **Prospect Quality Checks**
For each category, verify:
- [ ] **Names** are present (not "Unknown" or garbage)
- [ ] **Company/Organization** names are present
- [ ] **Role/Title** visible
- [ ] **Category tags** match the selected category
- [ ] **Email icons** active (for prospects with emails)
- [ ] **Phone icons** active (for prospects with phones)
- [ ] **View/Save buttons** functional

### **Backend Logs to Check (Railway)**
Search logs for:
- [ ] `"Using PsychologyTodayExtractor for URL..."`
- [ ] `"Using TreatmentCenterExtractor for URL..."`
- [ ] `"Using DoctorDirectoryExtractor for URL..."`
- [ ] `"Using EmbassyExtractor for URL..."`
- [ ] `"Using YouthSportsExtractor for URL..."`
- [ ] `"Using GenericExtractor for URL..."`
- [ ] `"Extracted X prospects from..."`
- [ ] `"[EXTRACTION COMPLETE] Found X prospects"`

### **Issues to Watch For**
- ⚠️ If categories missing → Extractor routing issue
- ⚠️ If org names missing → Organization extractor issue
- ⚠️ If emails missing → Contact enrichment issue
- ⚠️ If garbage names → Name validation issue

---

## 🟦 **STEP 2: Single-Category Precision Tests**

### **Test 1: Psychology Today**
- [ ] Select only: **Psychologists & Psychiatrists**
- [ ] Location: `Washington DC`
- [ ] Click "Find Prospects"

**Expected:**
- [ ] 3-10 therapists found
- [ ] Names like "Dr. Jane Smith" or "John Doe, PhD"
- [ ] Titles include: LCPC, LPC, LMFT, PhD, PsyD
- [ ] Practice names present
- [ ] Phone numbers present
- [ ] Category tag = "Psychologists & Psychiatrists"

---

### **Test 2: Treatment Centers**
- [ ] Select only: **Treatment Centers**
- [ ] Location: `Washington DC`
- [ ] Click "Find Prospects"

**Expected:**
- [ ] 5-15 prospects found
- [ ] Roles like: "Admissions Director", "Clinical Director", "Program Director"
- [ ] Organization names (treatment center names)
- [ ] Phones present
- [ ] Some emails present
- [ ] Category tag = "Treatment Centers"

---

### **Test 3: Pediatricians**
- [ ] Select only: **Pediatricians**
- [ ] Location: `Washington DC`
- [ ] Click "Find Prospects"

**Expected:**
- [ ] Doctors from Healthgrades/Zocdoc directories
- [ ] Names like "Dr. [Name], MD"
- [ ] Phones present
- [ ] Organization = clinic/hospital name
- [ ] Category tag = "Pediatricians"

---

### **Test 4: Youth Sports**
- [ ] Select only: **Youth Sports Programs**
- [ ] Location: `Washington DC`
- [ ] Click "Find Prospects"

**Expected:**
- [ ] Coaches and program directors
- [ ] Names extracted
- [ ] Organization = sports club/academy name
- [ ] Roles like "Head Coach", "Director of Coaching"
- [ ] Category tag = "Youth Sports Programs"

---

### **Test 5: Embassies**
- [ ] Select only: **Embassies & Diplomats**
- [ ] Location: `Washington DC`
- [ ] Click "Find Prospects"

**Expected:**
- [ ] Cultural attachés and education officers
- [ ] Embassy names as organizations
- [ ] Titles like "Education Officer", "Cultural Attaché"
- [ ] Some contact information
- [ ] Category tag = "Embassies & Diplomats"

---

## 🟦 **STEP 3: Frontend Interaction Tests**

### **Pagination Test**
- [ ] If > 10 results, pagination controls appear
- [ ] Can navigate to next page
- [ ] Results update correctly
- [ ] Sorting maintained across pages

### **Profile View Test** (if modal exists)
- [ ] Click "View" button on a prospect
- [ ] Modal/profile opens
- [ ] All fields populated (no blank fields)
- [ ] Email and phone links work
- [ ] Close button works

### **Category Filter Test**
- [ ] Filter by category using tags/filters
- [ ] Results update to show only selected category
- [ ] Count matches filtered results

### **Email Button Test**
- [ ] Click email icon on prospect with email
- [ ] Default mail client opens
- [ ] `mailto:` link correctly formatted
- [ ] Email address is correct

### **Phone Button Test**
- [ ] Click phone icon on prospect with phone
- [ ] Phone dialer opens (or tel: link works)
- [ ] `tel:` link correctly formatted
- [ ] Phone number is correct

### **Save Button Test**
- [ ] Click "Save" on a prospect
- [ ] Button changes to "Saved" or shows confirmation
- [ ] Check Firestore database:
  - [ ] Document created in `users/{user_id}/prospects`
  - [ ] Fields present: name, organization, source, category
  - [ ] Contact info saved
  - [ ] Score saved

---

## 🟦 **STEP 4: Stress Test (Multi-Run Stability)**

### **Repeat Test**
- [ ] Run 5-category search **5 times in a row**
- [ ] Wait for each to complete before starting next

### **Expected Results**
- [ ] No 500 errors
- [ ] No empty results (at least 1 prospect per run)
- [ ] Each run completes in < 90 seconds
- [ ] Results vary slightly (Google SERP changes)
- [ ] No duplicate entries across runs
- [ ] No memory leaks or slowdowns

### **Watch For**
- ⚠️ Errors on repeated runs → Race condition or resource leak
- ⚠️ Increasing response times → Performance issue
- ⚠️ Identical results → Caching issue

---

## 🟦 **STEP 5: Coverage Validation**

### **Component Checklist**

| Component | Tested | Status | Notes |
|-----------|--------|--------|-------|
| Google Search Query Generation | ✅ | Pass/Fail | Multi-category queries work |
| Extractor Factory Routing | ✅ | Pass/Fail | Correct extractor selected |
| PsychologyTodayExtractor | ✅ | Pass/Fail | Therapists extracted |
| DoctorDirectoryExtractor | ✅ | Pass/Fail | Doctors extracted |
| TreatmentCenterExtractor | ✅ | Pass/Fail | Staff extracted |
| EmbassyExtractor | ✅ | Pass/Fail | Officers extracted |
| YouthSportsExtractor | ✅ | Pass/Fail | Coaches extracted |
| GenericExtractor | ✅ | Pass/Fail | Fallback works |
| HTML Parsing | ✅ | Pass/Fail | BeautifulSoup working |
| Email/Phone Enrichment | ✅ | Pass/Fail | Contact info found |
| Organization Extraction | ✅ | Pass/Fail | Org names present |
| Prospect Validation | ✅ | Pass/Fail | No garbage names |
| Scoring Algorithm | ✅ | Pass/Fail | Scores calculated |
| Firestore Save | ✅ | Pass/Fail | Data persisted |
| Frontend Table Rendering | ✅ | Pass/Fail | Prospects displayed |
| Email/Phone Buttons | ✅ | Pass/Fail | Links work |
| Save Button | ✅ | Pass/Fail | Persists to DB |
| Pagination | ✅ | Pass/Fail | Pages work |
| Category Filters | ✅ | Pass/Fail | Filtering works |

---

## 🟦 **Common Issues & Solutions**

### **Issue: No prospects found**
**Check:**
- Railway logs for errors
- Google Search API key valid
- Firecrawl credits available
- Network connectivity

### **Issue: Missing organization names**
**Check:**
- Organization extractor logs
- Meta tags present in HTML
- Template text filtering too aggressive

### **Issue: Garbage names**
**Check:**
- Name validation logs
- Bad words list too restrictive
- Extractor pattern matching

### **Issue: Missing emails/phones**
**Check:**
- Contact enrichment logs
- Google enrichment working
- Email/phone regex patterns

### **Issue: Wrong categories**
**Check:**
- Category parameter passed correctly
- Category tagging in extractors
- Frontend category selection

---

## 📊 **Test Results Template**

```
Date: ___________
Tester: ___________

STEP 1: 5-Category Test
- Total prospects: _____
- Categories found: _____
- Status: ✅ / ❌

STEP 2: Single-Category Tests
- Psychology: ✅ / ❌ (___ prospects)
- Treatment: ✅ / ❌ (___ prospects)
- Pediatricians: ✅ / ❌ (___ prospects)
- Youth Sports: ✅ / ❌ (___ prospects)
- Embassies: ✅ / ❌ (___ prospects)

STEP 3: Frontend Interactions
- Pagination: ✅ / ❌
- Profile View: ✅ / ❌
- Email Button: ✅ / ❌
- Phone Button: ✅ / ❌
- Save Button: ✅ / ❌

STEP 4: Stress Test
- All 5 runs passed: ✅ / ❌
- Average time: _____ seconds

STEP 5: Coverage
- Components tested: ___ / 19
- Overall Status: ✅ / ❌
```

---

## ✅ **Success Criteria**

Your system is **production-ready** if:
- ✅ All 5 categories return results
- ✅ Prospect quality is high (names, orgs, contacts)
- ✅ Frontend interactions work smoothly
- ✅ No errors on repeated runs
- ✅ All components tested and working

---

## 🚀 **Next Steps After Testing**

1. **Fix any issues found**
2. **Run automated backend test**: `python test_extractor_system.py`
3. **Deploy to production**
4. **Monitor Railway logs** for first few searches
5. **Gather user feedback** on prospect quality

