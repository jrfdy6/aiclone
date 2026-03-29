import os
import traceback
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.utils import env_loader  # noqa: F401
from app.routes import (
    analytics,
    automations,
    brain,
    build_reviews,
    briefs,
    calendar,
    capture,
    content_generation,
    ingest_drive,
    knowledge,
    notifications,
    open_brain,
    persona,
    playbook,
    pm_board,
    prospects,
    prospects_manual,
    social_feedback,
    standups,
    system_logs,
    timeline,
    workspace,
    topic_intelligence,
)

app = FastAPI(
    title="AI Clone API",
    description="Comprehensive AI-powered platform for knowledge management, prospecting, and content marketing",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

print("🚀 Starting aiclone backend...", flush=True)
print(f"🔧 Version: 2025-11-24", flush=True)
print(f"📊 PORT environment variable: {os.getenv('PORT', 'NOT SET')}", flush=True)
print(f"📊 FIREBASE_SERVICE_ACCOUNT set: {bool(os.getenv('FIREBASE_SERVICE_ACCOUNT'))}", flush=True)
print(f"📊 GOOGLE_DRIVE_SERVICE_ACCOUNT set: {bool(os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT'))}", flush=True)

print("🔍 Verifying Firebase connection...", flush=True)
try:
    from app.services.firestore_client import get_firestore_client

    firestore_available = get_firestore_client() is not None
    if firestore_available:
        print("✅ Firebase/Firestore client initialized successfully", flush=True)
    else:
        print("⚠️ Firestore credentials missing", flush=True)
except Exception as e:
    print(f"❌ Firebase initialization failed: {e}", flush=True)
    traceback.print_exc()
    firestore_available = False

default_cors_origins = [
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://aiclone-production-32dc.up.railway.app",
    "https://aiclone-frontend-production.up.railway.app",
]
additional_origins = os.getenv("CORS_ADDITIONAL_ORIGINS", "")
if additional_origins:
    default_cors_origins.extend([origin.strip() for origin in additional_origins.split(",") if origin.strip()])


def _cors_headers_for_request(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin", "").strip()
    if not origin or origin not in default_cors_origins:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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
        headers=_cors_headers_for_request(request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"❌ Validation error in {request.method} {request.url.path}: {exc}", flush=True)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "errors": exc.errors(),
        },
        headers=_cors_headers_for_request(request),
    )


app.include_router(knowledge.router, prefix="/api/knowledge")
app.include_router(capture.router, prefix="/api/capture")
app.include_router(content_generation.router, prefix="/api/content-generation")
app.include_router(ingest_drive.router, prefix="/api")
app.include_router(automations.router, prefix="/api/automations")
app.include_router(briefs.router)
app.include_router(playbook.router, prefix="/api/playbooks")
app.include_router(prospects.router, prefix="/api/prospects")
app.include_router(prospects_manual.router, prefix="/api/prospects/manual")
app.include_router(calendar.router, prefix="/api/calendar")
app.include_router(notifications.router, prefix="/api/notifications")
app.include_router(system_logs.router, prefix="/api/system/logs")
app.include_router(analytics.router, prefix="/api/analytics")
app.include_router(brain.router)
app.include_router(build_reviews.router)
app.include_router(open_brain.router)
app.include_router(persona.router)
app.include_router(pm_board.router)
app.include_router(social_feedback.router)
app.include_router(workspace.router)
app.include_router(standups.router)
app.include_router(timeline.router)
app.include_router(topic_intelligence.router, prefix="/api/topic-intelligence")


@app.on_event("startup")
async def startup_event():
    print("✅ FastAPI app is ready to accept requests", flush=True)
    print(f"📡 Listening on 0.0.0.0:{os.getenv('PORT', '8080')}", flush=True)
    print("📚 API Documentation available at /api/docs", flush=True)


@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 FastAPI app is shutting down", flush=True)


@app.get("/")
def root():
    return {"status": "aiclone backend running", "version": "2.0.0", "docs": "/api/docs"}


@app.get("/test")
def test():
    return {"status": "ok", "message": "App is responding", "timestamp": "now"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "aiclone-backend",
        "version": "2.0.0",
        "firestore": "available" if firestore_available else "unavailable",
    }
