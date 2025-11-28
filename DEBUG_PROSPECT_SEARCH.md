# Debugging Prospect Search Results

## Current Status
- **Prospects Found**: 2 (expected more for 5 categories)
- **Categories Represented**: Education Consultants (1), Psychologists (1)
- **Missing Categories**: Pediatricians, Treatment Centers, Embassies, Youth Sports
- **Missing Data**: Company names, Contact info (email/phone)

## What to Check in Railway Logs

### 1. Search Query Generation
Look for:
```
Categories selected: ['pediatricians', 'psychologists', ...]
Google Search (FREE): [full query]
```

**Expected**: Should show all 5 categories in the query

### 2. Google Search Results
Look for:
```
Google search returned X results
```

**Issue if**: X < 10 (not enough results found)

### 3. URL Scraping
Look for:
```
Filtered X results to Y scrapeable URLs
Scraping: [URL]
```

**Issues to check**:
- Many 403 Forbidden errors (sites blocking scraping)
- Many 402 Payment Required (Firecrawl out of credits)
- "Free scrape failed" messages

### 4. Extraction Results
Look for:
```
Extracted Y prospects from [URL]
```

**Issue if**: Most URLs show "Extracted 0 prospects" (extraction failing)

### 5. Extraction Summary
Look for:
```
=== EXTRACTION SUMMARY ===
Total prospects found: X
URLs scraped: Y
```

**Expected**: Should show > 2 prospects if extraction is working

## Common Issues & Fixes

### Issue 1: Google Returns Few Results
**Symptoms**: "Google search returned 2 results"
**Possible Causes**:
- Query too specific/narrow
- Google API rate limit
- Search query syntax issue

**Fix**: 
- Try with fewer categories first (1-2 categories)
- Check if Google Search API key is configured
- Verify search query syntax

### Issue 2: URLs Can't Be Scraped
**Symptoms**: Many "403 Forbidden" or "Free scrape failed" messages
**Possible Causes**:
- Sites blocking automated scraping
- Firecrawl credits exhausted
- User-Agent headers not working

**Fix**:
- Already using free scraping fallback
- May need to prioritize sites that allow scraping
- Consider using more directory sites (Healthgrades, Psychology Today)

### Issue 3: Extraction Finds No Prospects
**Symptoms**: "Extracted 0 prospects from [URL]" for many URLs
**Possible Causes**:
- Name validation too strict (filtering out valid names)
- HTML structure doesn't match extraction patterns
- Content is JavaScript-rendered (not in static HTML)

**Fix**:
- Check if URLs are directory pages vs profile pages
- Verify extraction patterns match site structure
- Consider using LLM fallback for complex pages

### Issue 4: Missing Company Names
**Symptoms**: Organization shows as "—" in UI
**Possible Causes**:
- Organization extraction only checks page title
- Title extraction failing
- Organization not extracted in all extraction methods

**Fix Needed**:
- Improve organization extraction (check meta tags, h1, etc.)
- Extract from bio snippets
- Use Google enrichment to find organization

### Issue 5: Missing Contact Info
**Symptoms**: No email/phone buttons or they're disabled
**Possible Causes**:
- Contact enrichment not running
- Google contact search failing
- Email/phone extraction patterns not matching

**Fix Needed**:
- Verify Google contact enrichment is being called
- Check if enrichment is finding results
- Improve contact extraction patterns

## Quick Test Recommendations

### Test 1: Single Category (Pediatricians)
1. Select ONLY "Pediatricians"
2. Location: "Washington DC"
3. Max Results: 5
4. Check logs: Should see Healthgrades URLs and extraction

**Expected**: 3-5 prospects with names and potentially phones

### Test 2: Single Category (Psychologists)
1. Select ONLY "Psychologists & Psychiatrists"
2. Location: "Washington DC"
3. Max Results: 5
4. Check logs: Should see Psychology Today URLs

**Expected**: 3-5 prospects from Psychology Today profiles

### Test 3: Check Specific Directory Sites
Try searching directly on:
- Healthgrades.com (pediatricians)
- PsychologyToday.com (therapists)
- Verify these sites return results in Google search

## Next Steps

1. **Check Railway Logs** - Share the logs from your last search
2. **Run Single Category Tests** - Test each category individually
3. **Share Log Output** - Copy the relevant log sections so we can debug
4. **Check Google Search API** - Verify it's working and not rate-limited

## What to Share for Debugging

Please provide:
1. Full Railway log output from the search (especially lines with "Google search", "Extracted", "=== EXTRACTION SUMMARY ===")
2. Screenshot of the prospects in Pipeline (showing the missing data)
3. Which categories you selected
4. Any error messages you see

This will help identify the exact failure point in the pipeline.

