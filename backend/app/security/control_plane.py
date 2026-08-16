from __future__ import annotations

import os
import re
import secrets
from collections.abc import Iterable
from typing import Literal

from fastapi import Request


PUBLIC_PATHS = frozenset({"/", "/health", "/test"})
PUBLIC_PREFIXES = ("/api/neo/guest/",)
PROTECTED_PREFIXES = ("/api", "/openapi.json")
AuthScope = Literal["control_plane", "local_codex_worker"]
CONTROL_PLANE_SCOPE: AuthScope = "control_plane"
LOCAL_CODEX_WORKER_SCOPE: AuthScope = "local_codex_worker"

CONTROL_PLANE_TOKEN_ENV_NAME = "CONTROL_PLANE_SERVICE_TOKEN"
LOCAL_CODEX_TOKEN_ENV_NAMES = (
    "LOCAL_CODEX_BRIDGE_TOKEN",
    "CRON_ACCESS_TOKEN",  # Temporary compatibility fallback for local workers.
)
LOCAL_CODEX_WORKER_PATHS = (
    re.compile(r"^/api/content-generation/codex-jobs/claim-next/?$"),
    re.compile(r"^/api/content-generation/codex-jobs/[^/]+/(?:complete|fail)/?$"),
    re.compile(r"^/api/neo/worker/capabilities/?$"),
    re.compile(r"^/api/neo/worker/v2/jobs/claim-next/?$"),
    re.compile(r"^/api/neo/worker/jobs/claim-next/?$"),
    re.compile(r"^/api/neo/worker/jobs/[^/]+/(?:progress|complete|fail)/?$"),
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def control_plane_auth_required() -> bool:
    """Fail closed automatically on Railway and when explicitly enabled."""

    return _truthy(os.getenv("CONTROL_PLANE_AUTH_REQUIRED")) or bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
    )


def request_auth_scope(path: str, method: str) -> AuthScope:
    if method.upper() == "POST" and any(pattern.fullmatch(path) for pattern in LOCAL_CODEX_WORKER_PATHS):
        return LOCAL_CODEX_WORKER_SCOPE
    return CONTROL_PLANE_SCOPE


def configured_tokens(scope: AuthScope = CONTROL_PLANE_SCOPE) -> tuple[str, ...]:
    if scope == CONTROL_PLANE_SCOPE:
        value = str(os.getenv(CONTROL_PLANE_TOKEN_ENV_NAME) or "").strip()
        return (value,) if value else ()

    # Match the local bridge's existing precedence: the dedicated token wins,
    # and CRON_ACCESS_TOKEN is only a compatibility fallback when it is absent.
    worker_token = next(
        (
            value
            for name in LOCAL_CODEX_TOKEN_ENV_NAMES
            if (value := str(os.getenv(name) or "").strip())
        ),
        "",
    )
    if not worker_token:
        return ()

    control_token = str(os.getenv(CONTROL_PLANE_TOKEN_ENV_NAME) or "").strip()
    if control_token and secrets.compare_digest(worker_token, control_token):
        # Ambiguous credentials cannot be scoped safely. Fail closed until the
        # operator configures distinct service and worker secrets.
        return ()
    return (worker_token,)


def authentication_is_configured() -> bool:
    return bool(
        str(os.getenv(CONTROL_PLANE_TOKEN_ENV_NAME) or "").strip()
        or any(str(os.getenv(name) or "").strip() for name in LOCAL_CODEX_TOKEN_ENV_NAMES)
    )


def request_needs_auth(path: str, method: str) -> bool:
    if method.upper() == "OPTIONS" or path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return False
    return path.startswith(PROTECTED_PREFIXES)


def request_tokens(request: Request, scope: AuthScope | None = None) -> Iterable[str]:
    active_scope = scope or request_auth_scope(request.url.path, request.method)
    if active_scope == CONTROL_PLANE_SCOPE:
        authorization = str(request.headers.get("authorization") or "").strip()
        if authorization.lower().startswith("bearer "):
            value = authorization[7:].strip()
            if value:
                yield value
        value = str(request.headers.get("x-control-plane-token") or "").strip()
        if value:
            yield value
        return

    for name in ("x-local-codex-token", "x-cron-token"):
        value = str(request.headers.get(name) or "").strip()
        if value:
            yield value


def request_is_authorized(request: Request) -> bool:
    scope = request_auth_scope(request.url.path, request.method)
    expected = configured_tokens(scope)
    if not expected:
        return False
    return any(
        secrets.compare_digest(candidate, known)
        for candidate in request_tokens(request, scope)
        for known in expected
    )
