import asyncio
import os
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.utils import env_loader  # noqa: F401
from app.security.control_plane import (
    authentication_is_configured,
    configured_tokens,
    control_plane_auth_required,
    request_auth_scope,
    request_is_authorized,
    request_needs_auth,
)
from app.routes import (
    analytics,
    automations,
    brain,
    brain_docs,
    brief_reactions,
    build_reviews,
    briefs,
    calendar,
    capture,
    content_generation,
    email_ops,
    executive,
    firestore_readiness,
    ingest_drive,
    knowledge,
    lab,
    notifications,
    neo_guest,
    open_brain,
    persona,
    playbook,
    pm_board,
    prospect_discovery,
    prospects,
    prospects_manual,
    railway_retention,
    social_assist,
    social_feedback,
    standups,
    system_logs,
    timeline,
    workspace,
    owner_day,
    topic_intelligence,
)
from app.services import open_brain_db

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
    print(f"❌ Firebase initialization failed [{type(e).__name__}]", flush=True)
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
async def enforce_control_plane_auth(request: Request, call_next):
    if not request_needs_auth(request.url.path, request.method):
        return await call_next(request)
    required = control_plane_auth_required()
    scope = request_auth_scope(request.url.path, request.method)
    configured = configured_tokens(scope)
    if not required and not authentication_is_configured():
        # Local development remains usable when it is not running on Railway
        # and the operator has not enabled the control-plane boundary.
        return await call_next(request)
    if not configured:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "message": "Control plane authentication is not configured."},
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    if not request_is_authorized(request):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Authentication required."},
            headers={
                "Cache-Control": "no-store, max-age=0",
                "WWW-Authenticate": "Bearer",
            },
        )
    return await call_next(request)


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
        print(
            f"❌ {request.method} {request.url.path} - Error after {process_time:.2f}s "
            f"[{type(e).__name__}]",
            flush=True,
        )
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = (
        f"❌ Unhandled exception in {request.method} {request.url.path} "
        f"[{type(exc).__name__}]"
    )
    print(error_msg, flush=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "path": str(request.url.path),
        },
        headers=_cors_headers_for_request(request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_error_types = sorted(
        {
            str(item.get("type") or "validation_error")[:80]
            for item in exc.errors()
            if isinstance(item, dict)
        }
    )[:16]
    print(
        f"❌ Validation error in {request.method} {request.url.path}: "
        f"count={len(exc.errors())} types={','.join(safe_error_types)}",
        flush=True,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "errors": [{"type": error_type} for error_type in safe_error_types],
        },
        headers=_cors_headers_for_request(request),
    )


app.include_router(knowledge.router, prefix="/api/knowledge")
app.include_router(lab.router)
app.include_router(capture.router, prefix="/api/capture")
app.include_router(content_generation.router, prefix="/api/content-generation")
app.include_router(email_ops.router)
app.include_router(executive.router)
app.include_router(firestore_readiness.router)
app.include_router(railway_retention.router)
app.include_router(ingest_drive.router, prefix="/api")
app.include_router(automations.router, prefix="/api/automations")
app.include_router(briefs.router)
app.include_router(brief_reactions.router)
app.include_router(playbook.router, prefix="/api/playbooks")
app.include_router(prospect_discovery.router, prefix="/api/prospect-discovery")
app.include_router(prospects.router, prefix="/api/prospects")
app.include_router(prospects_manual.router, prefix="/api/prospects/manual")
app.include_router(calendar.router, prefix="/api/calendar")
app.include_router(notifications.router, prefix="/api/notifications")
app.include_router(neo_guest.router)
app.include_router(system_logs.router, prefix="/api/system/logs")
app.include_router(analytics.router, prefix="/api/analytics")
app.include_router(brain.router)
app.include_router(brain_docs.router)
app.include_router(build_reviews.router)
app.include_router(open_brain.router)
app.include_router(persona.router)
app.include_router(pm_board.router)
app.include_router(social_assist.router)
app.include_router(social_feedback.router)
app.include_router(workspace.router)
app.include_router(owner_day.router)
app.include_router(standups.router)
app.include_router(timeline.router)
app.include_router(topic_intelligence.router, prefix="/api/topic-intelligence")


@app.on_event("startup")
async def startup_event():
    if open_brain_db.database_configured():
        # Apply schema migrations before Railway marks the process ready. This
        # keeps cold GET requests read-only and prevents their request timeout
        # from abandoning migration work in a background thread.
        await asyncio.wait_for(asyncio.to_thread(open_brain_db.get_pool), timeout=30.0)
        from app.services.workspace_snapshot_service import workspace_snapshot_service

        inventory_redaction = await asyncio.wait_for(
            asyncio.to_thread(workspace_snapshot_service.redact_persisted_private_inventories),
            timeout=30.0,
        )
        print(
            "🔒 Browser snapshot privacy redaction: "
            f"checked={inventory_redaction['checked']} "
            f"redacted={inventory_redaction['redacted']} "
            f"already_safe={inventory_redaction['already_safe']}",
            flush=True,
        )
        grounding_refresh = await asyncio.wait_for(
            asyncio.to_thread(workspace_snapshot_service.refresh_persisted_source_grounding_state),
            timeout=90.0,
        )
        source_assets = grounding_refresh.get("source_assets") or {}
        source_asset_total = int(((source_assets.get("counts") or {}).get("total")) or 0)
        print(
            "🧭 FEEZIE source grounding materialized: "
            f"snapshots={len(grounding_refresh)} "
            f"source_assets={source_asset_total}",
            flush=True,
        )
        print("✅ Durable Brain database initialized", flush=True)
    print("✅ FastAPI app is ready to accept requests", flush=True)
    print(f"📡 Listening on 0.0.0.0:{os.getenv('PORT', '8080')}", flush=True)
    print("📚 API Documentation available at /api/docs", flush=True)


@app.on_event("shutdown")
async def shutdown_event():
    await asyncio.to_thread(open_brain_db.close_pool)
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
