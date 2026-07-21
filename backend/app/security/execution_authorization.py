from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any


AUTH_FIELD = "_control_plane_authorization"
SECRET_NAME = "CONTROL_PLANE_JOB_SIGNING_SECRET"


def _secret() -> str:
    value = str(os.getenv(SECRET_NAME) or "").strip()
    if value:
        return value
    secret_root = Path(
        os.getenv("AI_CLONE_SECRETS_ROOT")
        or (Path.home() / ".codex" / "ai-clone" / "secrets")
    )
    path = secret_root / "control_plane.env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if stripped.startswith(f"{SECRET_NAME}="):
            return stripped.split("=", 1)[1].strip().strip("\"'")
    return ""


def execution_signing_configured() -> bool:
    """Return whether new work orders can be signed for the local runners."""

    return bool(_secret())


def _canonical_bytes(card_id: str, payload: dict[str, Any]) -> bytes:
    unsigned = dict(payload or {})
    unsigned.pop(AUTH_FIELD, None)
    envelope = {"card_id": str(card_id), "payload": unsigned, "version": 1}
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign_execution_payload(card_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    signed = dict(payload or {})
    secret = _secret()
    if not secret:
        signed.pop(AUTH_FIELD, None)
        return signed
    signature = hmac.new(secret.encode("utf-8"), _canonical_bytes(card_id, signed), hashlib.sha256).hexdigest()
    signed[AUTH_FIELD] = {"version": 1, "algorithm": "hmac-sha256", "signature": signature}
    return signed


def verify_execution_payload(card_id: str, payload: dict[str, Any]) -> bool:
    authorization = payload.get(AUTH_FIELD) if isinstance(payload, dict) else None
    if not isinstance(authorization, dict):
        return False
    supplied = str(authorization.get("signature") or "")
    secret = _secret()
    if not secret or not supplied:
        return False
    expected = hmac.new(secret.encode("utf-8"), _canonical_bytes(card_id, payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)
