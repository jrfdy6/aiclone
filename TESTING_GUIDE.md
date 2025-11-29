# 🧪 Testing Guide - Complete System Validation

## ✅ **What We Have**

1. **Automated Backend Test** (`test_extractor_system.py`)
   - Validates extractor factory routing
   - Tests each extractor's extraction logic
   - Validates prospect structure
   - Tests category tagging
   - Tests error handling

2. **Manual Frontend Checklist** (`FRONTEND_TEST_CHECKLIST.md`)
   - Step-by-step frontend test plan
   - Covers all 5 categories
   - UI interaction tests
   - Stress testing

---

## 🚀 **Quick Start: Run the Frontend Test**

### **Step 1: Run the 5-Category Test**

1. Open your frontend application
2. Navigate to prospect discovery page
3. Select ALL 5 categories:
   - ✅ Psychologists & Psychiatrists
   - ✅ Education Consultants
   - ✅ Youth Sports Programs
   - ✅ Pediatricians
   - ✅ Treatment Centers
4. Enter location: `Washington DC`
5. Click "Find Prospects"
6. Wait for results (should take 60-90 seconds)

### **What to Look For:**

✅ **Success Indicators:**
- At least 7-20 prospects returned
- All 5 categories represented
- Names are real person names (not "Unknown" or garbage)
- Company/organization names present
- Email and phone icons visible for some prospects
- Prospects sorted by score (highest first)

❌ **Issues to Watch:**
- No results → Check Railway logs for errors
- Missing categories → Extractor routing issue
- Garbage names → Name validation needs tuning
- Missing org names → Organization extractor needs improvement
- No contact info → Enrichment not working

---

## 🔍 **Railway Logs to Monitor**

While running the test, watch Railway logs for:

### **Factory Routing:**
```
[EXTRACTION START] URL: ... | Category: ... | Source: ...
Using PsychologyTodayExtractor for ...
Using TreatmentCenterExtractor for ...
Using GenericExtractor for ...
```

### **Extraction Results:**
```
[EXTRACTION COMPLETE] URL: ... | Found X prospects
Extracted prospect: [Name] | email: ... | phone: ...
```

### **Errors:**
```
[EXTRACTION ERROR] Failed to extract prospects from ...: ...
```

---

## 🐛 **Common Issues & Quick Fixes**

### **Issue: "No prospects found"**

**Check:**
1. Railway logs for Google Search API errors
2. Firecrawl credits available
3. Network connectivity

**Fix:**
- Check API keys in Railway environment variables
- Verify Google Search Engine ID is correct

---

### **Issue: "Missing organization names"**

**Check:**
- Organization extractor logs
- Meta tags in scraped HTML

**Fix:**
- Organization extractor may need tuning
- Some sites may not have clear org names

---

### **Issue: "Garbage names like 'Help You' or 'Contact Me'"**

**Check:**
- Name validation logs
- Bad words filter

**Fix:**
- Already filtered in validation - check if filter is working
- May need to add more bad words to constants

---

### **Issue: "Wrong category tags"**

**Check:**
- Category parameter passed correctly
- Category tagging in extractor

**Fix:**
- Verify category is passed from frontend
- Check extractor uses category for tagging

---

## 📊 **Expected Results by Category**

### **Psychologists:**
- 3-10 prospects
- Titles: LCPC, LPC, LMFT, PhD, PsyD
- Practice names present
- Phones present

### **Treatment Centers:**
- 5-15 prospects
- Roles: Admissions Director, Clinical Director
- Center names as organizations
- Phones + some emails

### **Pediatricians:**
- 5-10 prospects
- Names: "Dr. [Name], MD"
- Clinic/hospital names
- Phones present

### **Youth Sports:**
- 3-8 prospects
- Coaches and directors
- Sports club/academy names
- Some contact info

### **Embassies:**
- 2-5 prospects
- Education officers, cultural attachés
- Embassy names as organizations
- Some contact info

---

## ✅ **Success Criteria**

Your system passes if:

1. ✅ **All 5 categories return results**
2. ✅ **Prospect quality is high** (real names, orgs, contacts)
3. ✅ **Frontend displays correctly** (table, buttons, pagination)
4. ✅ **No errors in Railway logs**
5. ✅ **Repeated runs are stable** (no crashes, consistent results)

---

## 🎯 **Next Steps After Testing**

1. **If tests pass:** Deploy to production! 🚀
2. **If issues found:** 
   - Check Railway logs for specific errors
   - Review extractor code for that category
   - Adjust validation rules if needed
   - Re-run test after fixes

3. **Monitor production:**
   - Watch first few searches
   - Check prospect quality
   - Gather user feedback

---

## 📝 **Test Results Template**

```
Date: ___________
Tester: ___________

✅ 5-Category Test: Pass / Fail
   - Total prospects: _____
   - Categories found: _____
   
✅ Single-Category Tests:
   - Psychology: Pass / Fail (___ prospects)
   - Treatment: Pass / Fail (___ prospects)
   - Pediatricians: Pass / Fail (___ prospects)
   - Youth Sports: Pass / Fail (___ prospects)
   - Embassies: Pass / Fail (___ prospects)
   
✅ Frontend Interactions: Pass / Fail
✅ Stress Test (5 runs): Pass / Fail

Overall: ✅ Ready for Production / ❌ Needs Fixes
```

---

## 🚀 **Ready to Test?**

1. **Run automated backend test first:**
   ```bash
   python test_extractor_system.py
   ```

2. **Then run frontend test:**
   - Follow `FRONTEND_TEST_CHECKLIST.md`
   - Monitor Railway logs
   - Document results

3. **Share results:**
   - Let me know what you find
   - I'll help fix any issues
   - We'll iterate until everything works!

**Good luck! 🎉**

