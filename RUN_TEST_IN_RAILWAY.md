# How to Run the Test in Railway

## Option 1: Via Railway CLI (Recommended)

1. **Install Railway CLI** (if not already installed):
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway**:
   ```bash
   railway login
   ```

3. **Link to your project**:
   ```bash
   railway link
   ```

4. **Run the test in Railway environment**:
   ```bash
   railway run python test_production_all_categories.py
   ```

   Or with result saving:
   ```bash
   railway run python test_production_all_categories.py --save-results
   ```

---

## Option 2: Via Railway Web Console

1. **Go to Railway Dashboard** → Your Backend Service
2. **Open the "Shell" or "Terminal" tab**
3. **Run the test**:
   ```bash
   cd /app
   python test_production_all_categories.py --save-results
   ```

---

## Option 3: Test via API Endpoint (From Your App)

Instead of running the script, you can test directly from your frontend:

1. **Open your app's "Find Prospects" page**
2. **Select all 5 categories**:
   - Pediatricians
   - Psychologists
   - Treatment Centers
   - Embassies
   - Youth Sports
3. **Set location**: "Washington DC"
4. **Click "Search"**
5. **Review results** on the pipeline page

---

## Quick Verification

Before running the full test, verify API keys are set:

```bash
# In Railway shell
echo $GOOGLE_SEARCH_API_KEY | head -c 20  # Should show first 20 chars
echo $GOOGLE_SEARCH_ENGINE_ID
```

Both should return values (not empty).

---

## Expected Test Duration

- **Per category**: 30-90 seconds
- **Total test time**: 3-5 minutes for all 5 categories

---

## What to Do After Test Runs

1. **Review the summary table** in the console output
2. **Check saved files** (if using `--save-results`):
   - `test_results/test_results_*.txt`
   - `test_results/test_results_*.json`
3. **Verify prospects** are saved to your pipeline
4. **Compare results** against expected rates in the checklist

---

## Troubleshooting

### "Google Custom Search API not configured"
- Check Railway environment variables are set
- Redeploy backend after adding variables
- Verify variable names match exactly

### Test hangs or times out
- Check Google API quota/usage
- Reduce `--max-results` to 5
- Test one category at a time

### No prospects found
- Check Railway logs for errors
- Verify search queries are correct
- Try different location

---

**Ready to test in Railway!** 🚀

