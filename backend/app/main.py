import os
import traceback
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time

from app.routes import chat, ingest, ingest_drive, knowledge, playbook, prospects, prospects_manual, outreach_manual, calendar, notifications, research_tasks, activity, templates, vault, personas, system_logs, automations, websocket, analytics, auth, webhooks, predictive, recommendations, nlp, content_optimization, bi, advanced_reporting, predictive_insights, multi_format_content, content_library, cross_platform_analytics, linkedin, topic_intelligence


app = FastAPI(
    title="AI Clone API",
    description="Comprehensive AI-powered platform for knowledge management, prospecting, and content marketing",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Log startup info for debugging
print(f"🚀 Starting aiclone backend...", flush=True)
print(f"🔧 Version: 2025-11-24 (Phase 5 - Production Excellence)", flush=True)
print(f"📊 PORT environment variable: {os.getenv('PORT', 'NOT SET')}", flush=True)
print(f"📊 FIREBASE_SERVICE_ACCOUNT set: {bool(os.getenv('FIREBASE_SERVICE_ACCOUNT'))}", flush=True)
print(f"📊 GOOGLE_DRIVE_SERVICE_ACCOUNT set: {bool(os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT'))}", flush=True)

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
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://aiclone-production-32dc.up.railway.app",
    "https://aiclone-frontend-production.up.railway.app",
    # Railway frontend URLs (wildcard pattern - will be added via environment variable)
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
app.include_router(playbook.router, prefix="/api/playbooks")
app.include_router(prospects.router, prefix="/api/prospects")
app.include_router(prospects_manual.router, prefix="/api/prospects/manual")
app.include_router(outreach_manual.router, prefix="/api/outreach/manual")
app.include_router(calendar.router, prefix="/api/calendar")
app.include_router(notifications.router, prefix="/api/notifications")
app.include_router(research_tasks.router, prefix="/api/research-tasks")
app.include_router(activity.router, prefix="/api/activity")
app.include_router(templates.router, prefix="/api/templates")
app.include_router(vault.router, prefix="/api/vault")
app.include_router(personas.router, prefix="/api/personas")
app.include_router(system_logs.router, prefix="/api/system/logs")
app.include_router(automations.router, prefix="/api/automations")
app.include_router(websocket.router, prefix="/api")
app.include_router(analytics.router, prefix="/api/analytics")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(webhooks.router, prefix="/api/webhooks")
app.include_router(predictive.router, prefix="/api/predictive")
app.include_router(recommendations.router, prefix="/api/recommendations")
app.include_router(nlp.router, prefix="/api/nlp")
app.include_router(content_optimization.router, prefix="/api/content-optimization")
app.include_router(bi.router, prefix="/api/bi")
app.include_router(advanced_reporting.router, prefix="/api/reporting")
app.include_router(predictive_insights.router, prefix="/api/predictive-insights")
app.include_router(multi_format_content.router, prefix="/api/content/generate")
app.include_router(content_library.router, prefix="/api/content-library")
app.include_router(cross_platform_analytics.router, prefix="/api/analytics/cross-platform")
app.include_router(linkedin.router, prefix="/api/linkedin")
app.include_router(topic_intelligence.router, prefix="/api/topic-intelligence")


@app.on_event("startup")
async def startup_event():
    """Log when the app is fully ready to accept requests."""
    print(f"✅ FastAPI app is ready to accept requests", flush=True)
    print(f"📡 Listening on 0.0.0.0:{os.getenv('PORT', '8080')}", flush=True)
    print(f"📚 API Documentation available at /api/docs", flush=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Log when the app is shutting down."""
    print(f"🛑 FastAPI app is shutting down", flush=True)


@app.get("/")
def root():
    return {
        "status": "aiclone backend running",
        "version": "2.0.0",
        "docs": "/api/docs"
    }


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
        "version": "2.0.0",
        "firestore": "available" if firestore_available else "unavailable",
    }
