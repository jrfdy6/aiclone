#!/usr/bin/env python3
"""
Re-ingest persona and style guide documents into the knowledge base.
Run this after updating JOHNNIE_FIELDS_PERSONA.md or CONTENT_STYLE_GUIDE.md
"""

import requests
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
USER_ID = "dev-user"

DOCS_TO_INGEST = [
    {
        "path": "JOHNNIE_FIELDS_PERSONA.md",
        "source_type": "persona",
        "metadata": {
            "topic": "persona",
            "extra_tags": ["persona", "voice", "style", "background", "johnnie_fields"]
        }
    },
    {
        "path": "CONTENT_STYLE_GUIDE.md", 
        "source_type": "style_guide",
        "metadata": {
            "topic": "style_guide",
            "extra_tags": ["style", "writing", "content", "guidelines", "voice_patterns"]
        }
    }
]

def ingest_document(doc_config: dict) -> dict:
    """Ingest a single document into the knowledge base."""
    filepath = os.path.join(os.path.dirname(__file__), doc_config["path"])
    
    if not os.path.exists(filepath):
        return {"success": False, "error": f"File not found: {filepath}"}
    
    with open(filepath, "rb") as f:
        files = {"file": (doc_config["path"], f, "text/plain")}
        data = {
            "user_id": USER_ID,
            "source_type": doc_config["source_type"],
            "metadata": str(doc_config["metadata"]).replace("'", '"')
        }
        
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/ingest/upload",
                files=files,
                data=data,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

def main():
    print("=" * 60)
    print("Re-ingesting Persona Documents into Knowledge Base")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"User ID: {USER_ID}")
    print()
    
    results = []
    for doc in DOCS_TO_INGEST:
        print(f"Ingesting: {doc['path']}...")
        result = ingest_document(doc)
        results.append({"file": doc["path"], "result": result})
        
        if result.get("success"):
            print(f"  ✓ Success: {result.get('chunks_created', 0)} chunks created")
        else:
            print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
        print()
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    success_count = sum(1 for r in results if r["result"].get("success"))
    print(f"Ingested: {success_count}/{len(results)} documents")
    
    if success_count == len(results):
        print("\n✓ All documents re-ingested successfully!")
        print("  Content generator will now use the updated persona data.")
    else:
        print("\n✗ Some documents failed to ingest.")
        print("  Make sure the backend is running: cd backend && uvicorn app.main:app --reload")

if __name__ == "__main__":
    main()

