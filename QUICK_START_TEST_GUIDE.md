# Quick Start Guide — Full 5-Category Production Test

## 🚀 Get Started in 3 Steps

### Step 1: Verify Environment (2 minutes)

**Check Railway Deployment:**
- [ ] Deployment is live and accessible
- [ ] Backend is responding (check health endpoint if available)

**Verify Environment Variables:**
- [ ] `GOOGLE_SEARCH_API_KEY` → Set in Railway
- [ ] `GOOGLE_SEARCH_ENGINE_ID` → Set in Railway
- [ ] (Optional) `FIRECRAWL_API_KEY` → For faster scraping

**How to Check:**
1. Open Railway dashboard
2. Go to your backend service
3. Check "Variables" tab
4. Verify keys are present and have values

---

### Step 2: Locate Test Files (30 seconds)

Find these files in your project:

- **`PRODUCTION_TEST_CHECKLIST.md`** → Detailed manual validation guide
- **`test_production_all_categories.py`** → Automated test script (this one!)
- **`QUICK_START_TEST_GUIDE.md`** → This file

---

### Step 3: Run the Automated Test (3-5 minutes)

**Option A: Run Locally (with API keys set)**
```bash
# Navigate to project directory
cd /path/to/aiclone

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows

# Run the test
python test_production_all_categories.py
```

**Option B: Run in Railway Shell**
```bash
# Open Railway shell/terminal
# Navigate to project
cd /app  # or your project directory

# Run the test
python test_production_all_categories.py
```

**Option C: Run Enhanced Version (saves results to file)**
```bash
# Save results to timestamped files in test_results/ directory
python test_production_all_categories.py --save-results

# Custom location
python test_production_all_categories.py --save-results --location "New York"

# Custom max results
python test_production_all_categories.py --save-results --max-results 5
```

**Output Files:**
- `test_results/test_results_YYYYMMDD_HHMMSS.txt` → Human-readable summary
- `test_results/test_results_YYYYMMDD_HHMMSS.json` → Machine-readable data

---

## 📊 What to Expect

### The Script Tests:

1. ✅ **Pediatricians** → Healthgrades/Zocdoc 2-hop extraction
2. ✅ **Psychologists** → Psychology Today profiles
3. ✅ **Treatment Centers** → Multi-page + Google enrichment
4. ✅ **Embassies** → Education officers, cultural attachés
5. ✅ **Youth Sports** → Coaches, directors, program managers

### Expected Output:

```
====================================================================================================
AUTOMATED PRODUCTION TEST - ALL 5 CATEGORIES
====================================================================================================

Location: Washington DC
Max Results per Category: 10

Testing categories...

  Testing Pediatricians... ✅ 8 prospects
  Testing Psychologists... ✅ 7 prospects
  Testing Treatment Centers... ✅ 5 prospects
  Testing Embassies... ✅ 4 prospects
  Testing Youth Sports... ✅ 6 prospects

====================================================================================================
COMPREHENSIVE TEST RESULTS SUMMARY
====================================================================================================

Category            | Total  | Names  | Titles | Emails | Phones | Rate  | Status
------------------------------------------------------------------------------------
Pediatricians       | 8      | 8      | 8      | 3      | 7      | 75.0% | ✅ PASS
Psychologists       | 7      | 7      | 7      | 2      | 6      | 68.8% | ✅ PASS
Treatment Centers   | 5      | 5      | 5      | 2      | 3      | 60.0% | ✅ PASS
Embassies           | 4      | 4      | 4      | 3      | 2      | 81.3% | ✅ PASS
Youth Sports        | 6      | 6      | 5      | 2      | 4      | 62.5% | ✅ PASS
------------------------------------------------------------------------------------
TOTALS              | 30     | 30     | 29     | 12     | 22     | 71.3% | N/A

📊 Success Summary:
   ✅ Fully Successful: 5/5 categories
   ⚠️  Partially Successful: 0/5 categories
   ❌ Failed: 0/5 categories

✅ OVERALL: PASS - At least 3 categories are working well
```

---

## ✅ Success Criteria

### Minimum Viable:
- ✅ At least 3 categories return prospects
- ✅ Names extraction rate > 70%
- ✅ No critical errors

### Optimal Results:
- ✅ All 5 categories return prospects
- ✅ Extraction rate > 60% overall
- ✅ Contact info (email OR phone) > 40%

---

## 🔍 Understanding the Results

### Status Indicators:
- **✅ PASS** → 3+ prospects found, good extraction rate
- **⚠️ PARTIAL** → Some prospects found but below expected
- **❌ FAIL** → No prospects or errors

### Metrics Explained:
- **Total** → Number of prospects found
- **Names** → Prospects with valid names extracted
- **Titles** → Prospects with job titles/roles
- **Emails** → Prospects with email addresses
- **Phones** → Prospects with phone numbers
- **Rate** → Overall extraction quality (0-100%)

---

## 🛠️ Troubleshooting

### Issue: "Google Custom Search API not configured"

**Solution:**
1. Check Railway environment variables
2. Verify `GOOGLE_SEARCH_API_KEY` is set
3. Verify `GOOGLE_SEARCH_ENGINE_ID` is set
4. Redeploy backend if variables were just added

### Issue: "No prospects found" for a category

**Possible Causes:**
- Search query too restrictive
- Location query issues
- Extraction patterns need adjustment

**Solution:**
- Check backend logs for errors
- Verify search query in logs
- Try different location (e.g., "DC" instead of "Washington DC")
- Review extraction patterns for that category

### Issue: Low extraction rates

**Possible Causes:**
- Contact info not on scraped pages
- Google enrichment not working
- HTML structure changed

**Solution:**
- Check if contacts exist on source pages manually
- Verify Google enrichment is running (check logs)
- Review extraction patterns

### Issue: Test hangs or times out

**Possible Causes:**
- Network issues
- Google API rate limits
- Scraping taking too long

**Solution:**
- Check network connectivity
- Reduce `MAX_RESULTS` in test script
- Check Google API quota/usage
- Review scraping timeouts

---

## 📝 Optional: Manual Validation

After automated test passes, you can do deeper validation:

1. Open `PRODUCTION_TEST_CHECKLIST.md`
2. Review each category's sample prospects
3. Validate:
   - Names are real people (not garbage)
   - Titles are accurate
   - Contact info is valid
   - Organizations make sense
4. Check pipeline page in your app
5. Verify prospects are saved correctly

---

## 📈 Next Steps After Testing

### If All Tests Pass ✅
1. Document any edge cases found
2. Consider adding Mom Groups category
3. Optimize extraction rates if needed
4. Production deployment confirmed ✅

### If Issues Found ⚠️
1. Prioritize fixes by impact
   - High: Garbage names, routing failures
   - Medium: Missing contacts, low extraction rates
   - Low: Formatting, minor validation issues
2. Fix high-priority issues first
3. Re-test affected categories
4. Document workarounds if needed

---

## 🎯 Quick Reference

### Test Script Options
```bash
# Basic test
python test_production_all_categories.py

# Save results to file
python test_production_all_categories.py --save-results

# Custom location
LOCATION="New York" python test_production_all_categories.py

# Custom max results
MAX_RESULTS=5 python test_production_all_categories.py
```

### Key Files Location
- Test script: `test_production_all_categories.py`
- Checklist: `PRODUCTION_TEST_CHECKLIST.md`
- Extraction logic: `backend/app/services/prospect_discovery_service.py`

### API Endpoints (if testing manually)
```bash
POST /api/prospect-discovery/search-free
{
  "user_id": "your-user-id",
  "categories": ["pediatricians"],
  "location": "Washington DC",
  "max_results": 10
}
```

---

## 💡 Pro Tips

1. **Run tests during off-peak hours** to avoid rate limits
2. **Check Google API quota** before running full test suite
3. **Start with one category** if testing for the first time
4. **Save results to file** for comparison across test runs
5. **Review logs** if anything fails - they contain detailed error info

---

## 🚀 Ready to Test!

Run this command:
```bash
python test_production_all_categories.py
```

Then review the summary table and detailed samples. If all looks good, you're production-ready! 🎉

---

**Questions?** Check:
- `PRODUCTION_TEST_CHECKLIST.md` for detailed validation steps
- Backend logs for error details
- Google API dashboard for quota/usage

