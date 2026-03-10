# Testing AI Clone Prospecting/Retrieval

This guide will help you test the AI Clone's knowledge retrieval and prospecting functionality.

## Current Setup Status

✅ **Frontend**: Running on http://localhost:3002  
✅ **Backend**: Running on http://127.0.0.1:8080  
✅ **Backend Health**: API endpoints are responding  
✅ **Data**: Firestore contains knowledge chunks (test query returned results)

## Testing Methods

### Method 1: Browser Testing (Recommended)

1. **Open the Frontend**:
   - Navigate to: http://localhost:3002
   - You should see the main chat interface

2. **Test Chat Retrieval**:
   - Enter a User ID (e.g., "dev-user")
   - Type a query in the chat input (e.g., "What is the onboarding prompt?")
   - Click send
   - You should see:
     - A user message
     - An assistant response showing number of chunks found
     - A "Retrieved Context" section with matching chunks and similarity scores

3. **Test Knowledge Inspector**:
   - Navigate to: http://localhost:3002/knowledge
   - Enter User ID: "dev-user"
   - Enter a search query (e.g., "AI training process")
   - Set Top K Results (default: 5)
   - Click "Search Knowledge"
   - Review the returned chunks with similarity scores

4. **Test Jumpstart Playbook**:
   - Navigate to: http://localhost:3002/jumpstart
   - View the playbook principles, onboarding prompt, and starter prompts
   - Test ingesting a Google Drive folder (if you have one)

### Method 2: Command Line Testing

#### Test Chat Retrieval Endpoint
```bash
curl -X POST http://127.0.0.1:8080/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "dev-user",
    "query": "What is the onboarding process?",
    "top_k": 5
  }' | python3 -m json.tool
```

#### Test Knowledge Search Endpoint
```bash
curl -X POST http://127.0.0.1:8080/api/knowledge/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "dev-user",
    "search_query": "starter prompts",
    "top_k": 10
  }' | python3 -m json.tool
```

#### Test Playbook Endpoints
```bash
# Get playbook summary
curl http://127.0.0.1:8080/api/playbook/summary | python3 -m json.tool

# Get onboarding prompt
curl http://127.0.0.1:8080/api/playbook/onboarding | python3 -m json.tool

# Get starter prompts
curl http://127.0.0.1:8080/api/playbook/prompts | python3 -m json.tool
```

### Method 3: Using the Test Script

Run the existing test script:
```bash
cd /Users/johnniefields/Desktop/Cursor/aiclone
./test_frontend_connection.sh
```

**Note**: The script expects frontend on port 3000, but yours is on 3002. You may need to update the script or test manually.

## What to Look For

### Successful Retrieval
- ✅ Returns `"success": true`
- ✅ `results` array contains chunks with:
  - `source_id`: Document identifier
  - `chunk_index`: Position in document
  - `chunk`: Text content
  - `similarity_score`: Relevance score (higher = more relevant)
  - `metadata`: File name, folder ID, timestamps, etc.

### Empty Results
- If no chunks match, you'll get an empty `results` array
- This means either:
  - No data has been ingested for that user_id
  - The query doesn't match any stored content
  - Try a different query or ingest more data

## Sample Test Queries

Try these queries to test different aspects:

1. **General Knowledge**:
   - "What is the AI Jumpstart Playbook?"
   - "Tell me about onboarding prompts"

2. **Specific Content**:
   - "What are the starter prompts?"
   - "How do I train my AI assistant?"

3. **Metadata Search**:
   - "Show me content from PDF files"
   - "What documents are in folder 1sZQZ9r3kfxgSR5A7HOFtU159B-HhvJRH"

## Troubleshooting

### Frontend Not Connecting to Backend
If the frontend shows "NEXT_PUBLIC_API_URL is not configured":
1. Check if `.env.local` or `.env` exists in `frontend/`
2. Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8080` for local testing
3. Restart the frontend dev server

### No Results Returned
- Verify data exists in Firestore for the user_id
- Check backend logs for errors
- Try a more general query
- Verify Firestore connection in backend logs

### CORS Errors
- Backend CORS is configured for localhost:3000 and localhost:3002
- If you see CORS errors, check backend `main.py` CORS settings

## Next Steps

1. **Ingest More Data**: Use the Jumpstart page to ingest a Google Drive folder
2. **Test Different Queries**: Try various search terms to see retrieval quality
3. **Check Similarity Scores**: Higher scores indicate better matches
4. **Review Metadata**: Check file names, folder IDs, and other metadata in results


