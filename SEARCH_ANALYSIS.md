# Prospect Search Results Analysis

## What to Analyze After Each Search

### 1. **Category Distribution** 📊
Check how many prospects were found per category:
- Education Consultants
- Pediatricians  
- Psychologists & Psychiatrists
- Treatment Centers
- Embassies & Diplomats
- Youth Sports Programs
- Mom Groups & Parent Networks
- International Student Services

**Expected:** Even distribution across all 8 categories (if all selected)

**Current Issue:** Mostly seeing "Psychologists & Psychiatrists" - category tagging not fully working

---

### 2. **Data Quality Metrics** ✅

#### Contact Information
- **Emails:** % of prospects with email addresses
- **Phones:** % of prospects with phone numbers  
- **Organizations:** % of prospects with organization names

**Target:** 
- Emails: 60-80%
- Phones: 70-90%
- Organizations: 80-100%

#### Name Validation
- Are there any garbage names? (e.g., "Janak", "Capitol Heights", "Goebel played")
- Are DC neighborhoods preserved? (e.g., "Capitol Heights" should be allowed if it's a real person)

---

### 3. **Organization Names** 🏢

**Issues to Check:**
- Template phrases: "where children come first", "in the United States"
- Generic names: "Psychologytoday", "Healthgrades"
- Missing organizations (showing "—")

**Expected:** Real organization names extracted from pages

---

### 4. **Category Tagging Accuracy** 🏷️

**Check:**
- Does each prospect have the correct category tag?
- Or are they all tagged the same (e.g., all "Psychologists")?
- Does the tag match the category that found them?

**Expected:** Each prospect tagged with the category that initiated the search

---

### 5. **Search Results Per Category** 🔍

**From Logs, Check:**
- Which categories returned Google search results?
- Which categories had "No search results, skipping"?
- How many URLs were scraped per category?

**Current Issues:**
- Treatment Centers: "No search results, skipping"
- Embassies: "No search results, skipping"

This means the Google queries aren't finding relevant URLs for these categories.

---

### 6. **Extraction Success Rate** 📈

**Check:**
- How many prospects found vs. saved?
- What percentage were filtered out?
- Why were they filtered? (check logs for "Filtering out invalid prospect")

**Expected:**
- 70-90% of found prospects should be valid
- Validation should catch garbage names

---

## Common Issues & Fixes

### Issue: All prospects tagged same category
**Fix:** Category parameter not being passed to extraction methods
**Status:** ✅ Fixed - removed incorrect imports

### Issue: Garbage names getting through
**Fix:** Strengthened validation filters
**Status:** ✅ Improved - added DC neighborhoods allowlist

### Issue: Missing organizations
**Fix:** Enhanced organization extraction
**Status:** ✅ Improved - multiple extraction sources

### Issue: No search results for some categories
**Fix:** Need to improve Google search queries for Treatment Centers, Embassies
**Status:** ⚠️ Needs work - search queries not finding URLs

---

## Next Steps

1. **Share Results:** What do you see in the UI?
   - How many prospects found?
   - What categories are they tagged with?
   - Any garbage names?
   - Missing organizations?

2. **Check Logs:** Look for these log messages:
   - `[CATEGORY: X]` - Shows category processing
   - `[SAVE SUMMARY]` - Shows filtering stats
   - `[CATEGORY BREAKDOWN]` - Shows per-category counts

3. **Improve Search Queries:** If categories return no results, refine Google queries

