# Treatment Center Extraction - Production Testing Guide

## What's Working ✅

The treatment center extraction is **production-ready** and works **without Firecrawl credits** using:
1. **Free scraping** (BeautifulSoup + requests) for static HTML pages
2. **Google Custom Search** for team page discovery and contact enrichment
3. **BeautifulSoup parsing** for extracting names/titles from HTML

## Requirements for Full Functionality

To get the best results, you need:
- ✅ **Google Custom Search API** - for finding team pages and contact enrichment
- ❌ **Firecrawl** - NOT required (graceful fallback if unavailable)

## How to Test in Production

### Option 1: Test via Frontend
1. Go to your app's "Find Prospects" page
2. Select category: **"Treatment Centers"**
3. Enter location: **"Washington DC"** (or any location)
4. Click search
5. Check results for:
   - Names extracted
   - Titles (Admissions Director, Clinical Director, etc.)
   - Contact info (email/phone)

### Option 2: Test via API

```bash
curl -X POST https://your-api-url/api/prospect-discovery/search-free \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-id",
    "categories": ["treatment_centers"],
    "location": "Washington DC",
    "max_results": 10
  }'
```

## Expected Results

| Metric | Expected Rate (with Google Search) |
|--------|-----------------------------------|
| Names  | 60-80%                            |
| Titles | 60-80%                            |
| Emails | 40-60% (via Google enrichment)    |
| Phones | 50-70% (via Google enrichment)    |

## What Happens Without Google Search

If Google Search API isn't configured:
- ✅ Still extracts names from main page static HTML
- ✅ Still extracts from scraped team pages (if accessible)
- ❌ Won't search Google for team pages
- ❌ Won't enrich missing contact info

## Troubleshooting

### No Prospects Found
- **Check**: Is the domain being scraped successfully?
- **Check**: Does the main page have team/staff info in static HTML?
- **Solution**: Try domains with static HTML team pages

### Missing Contact Info
- **Check**: Is Google Search API configured?
- **Check**: Are team pages being found via Google search?
- **Solution**: Ensure Google Custom Search API key is set in environment variables

### Team Pages Not Found
- **Check**: Does the domain have a `/team` or `/staff` page?
- **Solution**: The system will try to find it via Google search if available

## Test Domains

Good test domains (known to have team pages):
- `https://www.newportacademy.com/`
- `https://www.evoketherapy.com/`
- `https://www.talkspace.com/` (mental health)
- `https://www.headspace.com/` (mental health)

## Next Steps

1. **Deploy to Railway** (if not already deployed)
2. **Verify Google Search API key** is configured in Railway environment variables
3. **Test with a treatment center search** in production
4. **Review extracted prospects** for accuracy and contact info
5. **Iterate** based on results

