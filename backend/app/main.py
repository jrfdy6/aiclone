import os
import traceback
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time

from app.routes import chat, ingest, ingest_drive, knowledge, playbook


app = FastAPI()

# Log startup info for debugging
print(f"🚀 Starting aiclone backend...", flush=True)
print(f"🔧 Version: 2025-11-17-07:20 (with Firestore get() fix)", flush=True)
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
