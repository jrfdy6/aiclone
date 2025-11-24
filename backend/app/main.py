import os
import traceback
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time

from app.routes import (
    chat, ingest, ingest_drive, knowledge, playbook, 
    prospects_manual, outreach_manual, content_marketing,
    research, prospects, metrics, learning, linkedin, linkedin_content,
    comprehensive_content, enhanced_research, outreach_engine, enhanced_metrics
)


app = FastAPI()

# Log startup info for debugging
print(f"🚀 Starting aiclone backend...", flush=True)
print(f"🔧 Version: 2025-11-23-12:00 (Perplexity timeout fix: 900s)", flush=True)
print(f"📊 PORT environment variable: {os.getenv('PORT', 'NOT SET')}", flush=True)
print(f"📊 FIREBASE_SERVICE_ACCOUNT set: {bool(os.getenv('FIREBASE_SERVICE_ACCOUNT'))}", flush=True)
print(f"📊 GOOGLE_DRIVE_SERVICE_ACCOUNT set: {bool(os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT'))}", flush=True)
print(f"📊 GOOGLE_CUSTOM_SEARCH_API_KEY set: {bool(os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY'))}", flush=True)
print(f"📊 GOOGLE_CUSTOM_SEARCH_ENGINE_ID set: {bool(os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID'))}", flush=True)
print(f"📊 PERPLEXITY_API_KEY set: {bool(os.getenv('PERPLEXITY_API_KEY'))}", flush=True)
print(f"📊 FIRECRAWL_API_KEY set: {bool(os.getenv('FIRECRAWL_API_KEY'))}", flush=True)

# Startup verification - test Firebase connection
print(f"🔍 Verifying Firebase connection...", flush=True)
try:
    from app.services.firestore_client import db
    print(f"✅ Firebase/Firestore client initialized successfully", flush=True)
    firestore_available = True
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}", flush=True)
    traceback.print_exc()
    firestore_available = False

# CORS configuration - can be extended via environment variable
# Note: Port 3000 is used by closetgptrenew, so we only allow 3002 for aiclone
default_cors_origins = [
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "https://aiclone-production-32dc.up.railway.app",
]

# Allow additional CORS origins via environment variable (comma-separated)
additional_origins = os.getenv("CORS_ADDITIONAL_ORIGINS", "")
if additional_origins:
    default_cors_origins.extend([origin.strip() for origin in additional_origins.split(",")])

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"🌐 {request.method} {request.url.path} - Request received", flush=True)
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"✅ {request.method} {request.url.path} - {response.status_code} - {process_time:.2f}s", flush=True)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"❌ {request.method} {request.url.path} - Error after {process_time:.2f}s: {e}", flush=True)
        raise


# Exception handler middleware for request-level errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and log them."""
    error_msg = f"❌ Unhandled exception in {request.method} {request.url.path}: {exc}"
    print(error_msg, flush=True)
    traceback.print_exc()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "path": str(request.url.path),
            "error": str(exc),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    print(f"❌ Validation error in {request.method} {request.url.path}: {exc}", flush=True)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "errors": exc.errors(),
        },
    )

app.include_router(chat.router, prefix="/api/chat")
app.include_router(ingest.router, prefix="/api/ingest")
app.include_router(knowledge.router, prefix="/api/knowledge")
app.include_router(ingest_drive.router, prefix="/api")
app.include_router(playbook.router, prefix="/api/playbook")
app.include_router(prospects_manual.router, prefix="/api/prospects/manual")
app.include_router(outreach_manual.router, prefix="/api/outreach/manual")
app.include_router(content_marketing.router, prefix="/api/content")

# New prospecting workflow routes
app.include_router(research.router, prefix="/api/research")
app.include_router(enhanced_research.router, prefix="/api/research/enhanced")
app.include_router(prospects.router, prefix="/api/prospects")
app.include_router(metrics.router, prefix="/api/metrics")
app.include_router(learning.router, prefix="/api/learning")

# LinkedIn post search routes
app.include_router(linkedin.router, prefix="/api/linkedin")

# LinkedIn content management routes (PACER strategy)
app.include_router(linkedin_content.router, prefix="/api/linkedin/content")

# Comprehensive content generation routes (100+ variations, 20+ types)
app.include_router(comprehensive_content.router, prefix="/api/content")

# Outreach Engine routes (segmentation, sequences, scoring, cadence)
app.include_router(outreach_engine.router, prefix="/api/outreach")

# Enhanced Metrics & Learning routes (content metrics, prospect metrics, learning patterns, weekly reports)
app.include_router(enhanced_metrics.router, prefix="/api/metrics/enhanced")


@app.on_event("startup")
async def startup_event():
    """Log when the app is fully ready to accept requests."""
    print(f"✅ FastAPI app is ready to accept requests", flush=True)
    print(f"📡 Listening on 0.0.0.0:{os.getenv('PORT', '8080')}", flush=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Log when the app is shutting down."""
    print(f"🛑 FastAPI app is shutting down", flush=True)


@app.get("/")
def root():
    return {"status": "aiclone backend running"}


@app.get("/test")
def test():
    """Simple test endpoint to verify the app is responding."""
    return {"status": "ok", "message": "App is responding", "timestamp": "now"}


@app.get("/health")
def health():
    """Health check endpoint for Railway - simple status check without dependencies."""
    return {
        "status": "healthy",
        "service": "aiclone-backend",
        "firestore": "available" if firestore_available else "unavailable",
    }
