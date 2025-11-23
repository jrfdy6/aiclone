# Add Your Google Custom Search API Key

## Step 1: Add API Key to .env File

Add this line to your `backend/.env` file:

```bash
GOOGLE_CUSTOM_SEARCH_API_KEY=your-api-key-here
```

Replace `your-api-key-here` with the actual API key you just created.

## Step 2: Get Your Search Engine ID

You still need the **Google Custom Search Engine ID**:

1. Go to: https://programmablesearchengine.google.com/
2. Click **"Add"** to create a new search engine
3. **Sites to search**: Enter `*` (asterisk) - this allows searching the entire web
4. Click **"Create"**
5. Copy the **Search Engine ID** (looks like: `017576662512468239146:omuauf_lfve`)

## Step 3: Add Search Engine ID to .env

Add this line to your `backend/.env` file:

```bash
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your-search-engine-id-here
```

## Step 4: Add Other API Keys (If Needed)

You'll also need:

```bash
PERPLEXITY_API_KEY=your-perplexity-key
FIRECRAWL_API_KEY=your-firecrawl-key
```

## Quick Command to Add Keys

You can add them all at once:

```bash
cd backend
cat >> .env << 'EOF'

# Prospecting Workflow API Keys
GOOGLE_CUSTOM_SEARCH_API_KEY=your-google-api-key-here
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your-search-engine-id-here
PERPLEXITY_API_KEY=your-perplexity-key-here
FIRECRAWL_API_KEY=your-firecrawl-key-here
EOF
```

Then edit the file to replace the placeholder values with your actual keys.

## After Adding Keys

1. **Load the environment variables:**
   ```bash
   source backend/.env
   # or
   export $(cat backend/.env | xargs)
   ```

2. **Restart your backend server** to pick up the new variables

3. **Check startup logs** - you should see:
   ```
   📊 GOOGLE_CUSTOM_SEARCH_API_KEY set: True
   📊 GOOGLE_CUSTOM_SEARCH_ENGINE_ID set: True
   ```

## Test Your Setup

Once you have both the API key and Search Engine ID:

```bash
curl -X POST http://localhost:8080/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "industry": "SaaS", "max_results": 5}'
```

---

**Note**: Your API key is restricted to Railway's public networking address, which is perfect for production! For local testing, you might need to temporarily remove the restriction or add your local IP.


