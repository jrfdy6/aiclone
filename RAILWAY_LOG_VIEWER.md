# Railway Backend Log Viewer Guide

## Quick Commands

### View All Logs (Streaming)
```bash
railway logs --service aiclone-backend --follow
```

### Filter by Category Processing
```bash
railway logs --service aiclone-backend --follow | grep -E "\[CATEGORY:|Category|category"
```

### Filter by Extraction
```bash
railway logs --service aiclone-backend --follow | grep -E "\[EXTRACTION START\]|Extracted.*prospects"
```

### Filter by Save Summary
```bash
railway logs --service aiclone-backend --follow | grep -E "\[SAVE SUMMARY\]|CATEGORY BREAKDOWN|Successfully saved"
```

### Filter Errors/Warnings
```bash
railway logs --service aiclone-backend --follow | grep -E "ERROR|WARN|Failed|failed"
```

### Last 100 Lines (Non-streaming)
```bash
railway logs --service aiclone-backend --tail 100
```

## Using the Script

Run the interactive script:
```bash
./view_railway_logs.sh
```

## Log Tags to Look For

### Category Processing
- `[CATEGORY: X]` - Shows which category is being processed
- `=== PROCESSING CATEGORY: X ===` - Start of category processing
- `[CATEGORY: X] ✅ Extracted N prospects` - Results per category

### Extraction
- `[EXTRACTION START]` - When extraction begins for a URL
- `Extracted N prospects from URL` - Number of prospects found
- `Extracted organization 'X' for Name` - Organization extraction results

### Saving
- `[SAVE]` - Individual prospect being saved (shows category, org, email, phone)
- `=== SAVE SUMMARY ===` - Summary of all saved prospects
- `=== CATEGORY BREAKDOWN ===` - Breakdown by category tag

### Errors
- `Failed to scrape` - URL scraping failed
- `Firecrawl failed` - Firecrawl API issue (usually 402 Payment Required)
- `Filtering out invalid prospect` - Validation filtering in action

## Troubleshooting

### Only seeing one category's prospects?
- Check logs for `[CATEGORY: X]` to see which categories are being processed
- Look for `Category 'X' returned 0 results` - that category got no Google results

### Missing organization names?
- Look for `Extracted organization 'X'` - shows when org extraction succeeds
- Look for `No organization found for Name` - extraction failed

### Wrong category tags?
- Check `Tagging prospects with category: X (from category: Y)` - shows category being used
- Check `No category provided for extraction` - category wasn't passed correctly

### Low prospect count?
- Check `=== SAVE SUMMARY ===` - shows filtered vs saved counts
- Check `Filtering out invalid prospect` - shows why prospects are being filtered
- Check `Category 'X': Extracted N prospects` - shows extraction per category

## Installation

If Railway CLI is not installed:
```bash
npm i -g @railway/cli
railway login
```

