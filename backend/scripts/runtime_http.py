#!/usr/bin/env python3
"""Authenticated HTTP helpers for local Codex workers.

Credentials are read from the process environment first and, for launchd jobs
that do not embed secrets in plists, from the private Codex runtime.
"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping


TOKEN_NAME = "CONTROL_PLANE_SERVICE_TOKEN"
DEFAULT_SECRET_ROOT = Path.home() / ".codex" / "ai-clone" / "secrets"
SECRET_FILES = ("control_plane.env", "railway.env")
PRODUCTION_CONTROL_PLANE_HOSTS = frozenset({"aiclone-production-32dc.up.railway.app"})
LOCAL_CONTROL_PLANE_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ControlPlaneURLSecurityError(ValueError):
    """Raised before credentials are attached to an untrusted destination."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _parse_env_value(path: Path, name: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        return value.strip().strip("\"'")
    return ""


def runtime_secret_value(name: str, *, filenames: tuple[str, ...] = SECRET_FILES) -> str:
    """Read one named runtime secret without loading the surrounding env file."""

    value = str(os.getenv(name) or "").strip()
    if value:
        return value
    secret_root = Path(
        os.getenv("AI_CLONE_SECRETS_ROOT")
        or (Path(os.getenv("AI_CLONE_RUNTIME_ROOT") or DEFAULT_SECRET_ROOT.parent) / "secrets")
    ).expanduser()
    for filename in filenames:
        value = _parse_env_value(secret_root / filename, name)
        if value:
            return value
    return ""


def control_plane_token() -> str:
    return runtime_secret_value(TOKEN_NAME)


def control_plane_headers(base: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = dict(base or {})
    token = control_plane_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def validate_control_plane_url(url: str) -> str:
    """Allow only the production backend or an explicit loopback endpoint."""

    normalized = str(url or "").strip()
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ControlPlaneURLSecurityError("Control-plane URL is invalid.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ControlPlaneURLSecurityError("Control-plane URL port is invalid.") from exc
    hostname = parsed.hostname.lower()
    if hostname in PRODUCTION_CONTROL_PLANE_HOSTS:
        if parsed.scheme != "https" or port not in {None, 443}:
            raise ControlPlaneURLSecurityError("Production control-plane requests require HTTPS on port 443.")
    elif hostname not in LOCAL_CONTROL_PLANE_HOSTS:
        raise ControlPlaneURLSecurityError("Control-plane URL host is not allowlisted.")
    if parsed.fragment:
        raise ControlPlaneURLSecurityError("Control-plane URL must not contain a fragment.")
    return normalized


def open_control_plane_request(request: urllib.request.Request, *, timeout: int = 30) -> Any:
    """Open one validated request without forwarding credentials through redirects."""

    validate_control_plane_url(request.full_url)
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)
