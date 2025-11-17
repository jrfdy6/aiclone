import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chat, ingest, ingest_drive, knowledge, playbook


app = FastAPI()

# Log startup info for debugging
print(f"🚀 Starting aiclone backend...", flush=True)
print(f"📊 PORT environment variable: {os.getenv('PORT', 'NOT SET')}", flush=True)
print(f"📊 FIREBASE_SERVICE_ACCOUNT set: {bool(os.getenv('FIREBASE_SERVICE_ACCOUNT'))}", flush=True)
print(f"📊 GOOGLE_DRIVE_SERVICE_ACCOUNT set: {bool(os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT'))}", flush=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://aiclone-production-32dc.up.railway.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(chat.router, prefix="/api/chat")
app.include_router(ingest.router, prefix="/api/ingest")
app.include_router(knowledge.router, prefix="/api/knowledge")
app.include_router(ingest_drive.router, prefix="/api")
app.include_router(playbook.router, prefix="/api/playbook")


@app.get("/")
def root():
    return {"status": "aiclone backend running"}


@app.get("/health")
def health():
    """Health check endpoint for Railway."""
    try:
        # Test Firebase connection
        from app.services.firestore_client import db
        # Just check if db is accessible, don't make a query
        return {"status": "healthy", "service": "aiclone-backend", "firestore": "connected"}
    except Exception as e:
        print(f"❌ Health check failed: {e}", flush=True)
        return {"status": "unhealthy", "error": str(e)}, 503
