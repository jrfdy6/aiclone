from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel


_RELATIVE_ANCHORS = (
    "agents",
    "automations",
    "backend",
    "deliverables",
    "docs",
    "frontend",
    "interview-prep",
    "knowledge",
    "memory",
    "scripts",
    "skills",
    "SOPs",
    "workspaces",
)
_RELATIVE_ANCHOR_PATTERN = "|".join(re.escape(anchor) for anchor in _RELATIVE_ANCHORS)

# These identifiers are credentials, not useful product context. Keep the
# matcher suffix-based so ordinary fields such as ``model_name`` and
# ``max_tokens`` remain readable.
_CREDENTIAL_NAME_PATTERN = r"(?:[A-Z][A-Z0-9_]*_(?:API_KEY|API_TOKEN|ACCESS_TOKEN|SERVICE_TOKEN|AUTH_TOKEN|BEARER_TOKEN|TOKEN|JOB_SIGNING_SECRET|CLIENT_SECRET|SESSION_SECRET|WEBHOOK_SECRET|SIGNING_SECRET|SECRET|PRIVATE_KEY|SECRET_KEY|PASSWORD|DATABASE_PASSWORD)|API_KEY|API_TOKEN|ACCESS_TOKEN|SERVICE_TOKEN|AUTH_TOKEN|BEARER_TOKEN|TOKEN|SECRET|PASSWORD)"
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    rf"(?<![A-Za-z0-9_])(?P<quote>[\"']?){_CREDENTIAL_NAME_PATTERN}(?P=quote)(?![A-Za-z0-9_])\s*(?:=|:)\s*(?:\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s,;}}]+)",
    flags=re.IGNORECASE,
)
_CREDENTIAL_NAME_RE = re.compile(
    rf"(?<![A-Za-z0-9_]){_CREDENTIAL_NAME_PATTERN}(?![A-Za-z0-9_])"
)
_CREDENTIAL_KEY_RE = re.compile(rf"^{_CREDENTIAL_NAME_PATTERN}$", flags=re.IGNORECASE)

# Token-shape redaction is deliberately narrow. It catches common provider and
# bearer credentials if a log accidentally contains a value without its env
# name, without rewriting normal prose or UUIDs.
_TOKEN_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", flags=re.IGNORECASE),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
)

_FILE_URI_RE = re.compile(
    r"file://(?P<path>/(?:Users|home|root|app|Volumes|private|var|tmp|opt|Library|Applications|System|usr|bin|sbin|etc)/[^\s`\"'<>]+)"
)
_ABSOLUTE_LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9:])(?P<path>/(?:Users|home|root|app|Volumes|private|var|tmp|opt|Library|Applications|System|usr|bin|sbin|etc)/[^\s`\"'<>]+)"
)
_HIDDEN_RUNTIME_PATH_RE = re.compile(
    r"(?P<path>(?:~/?|(?<![A-Za-z0-9_-]))\.(?:openclaw|codex)(?:/[^\s`\"'<>]+)?)",
    flags=re.IGNORECASE,
)
_TRAILING_PATH_PUNCTUATION = ".,;:!?)]}"


def _split_trailing_punctuation(value: str) -> tuple[str, str]:
    core = value
    trailing = ""
    while core and core[-1] in _TRAILING_PATH_PUNCTUATION:
        trailing = core[-1] + trailing
        core = core[:-1]
    return core, trailing


def _relative_anchor(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    match = re.search(rf"(?:^|/)(?P<relative>(?:{_RELATIVE_ANCHOR_PATTERN})(?:/.*)?)$", normalized)
    if match is None:
        return None
    return match.group("relative")


def _contains_private_location(path: str) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(path).parts)
    if "secrets" in parts:
        return True
    return any(part == ".env" or part.endswith(".env") for part in parts)


def _safe_path_reference(raw_path: str) -> str:
    path, trailing = _split_trailing_punctuation(raw_path)
    normalized = path.replace("\\", "/")
    lowered = normalized.lower()

    if _contains_private_location(normalized):
        return "[private-runtime]" + trailing

    relative = _relative_anchor(normalized)
    if relative:
        return relative + trailing

    if lowered in {".openclaw", "~/.openclaw"} or "/.openclaw/" in lowered or lowered.startswith((".openclaw/", "~/.openclaw/")):
        return "[retired-runtime]" + trailing
    if lowered in {".codex", "~/.codex"} or "/.codex/" in lowered or lowered.startswith((".codex/", "~/.codex/")):
        return "[local-runtime]" + trailing

    if lowered.endswith("/ai-clone"):
        return "[project-root]" + trailing

    name = PurePosixPath(normalized.rstrip("/")).name
    return (f"[local-path]/{name}" if name else "[local-path]") + trailing


def sanitize_brain_text(value: str) -> str:
    """Remove machine-local and credential details from Brain-facing text.

    Repository paths are reduced to stable relative anchors whenever possible,
    so the operator keeps useful artifact context without exposing a username,
    home directory, retired runtime, or private credential location.
    """

    sanitized = _CREDENTIAL_ASSIGNMENT_RE.sub("[credential]=[redacted]", str(value))
    sanitized = _CREDENTIAL_NAME_RE.sub("[credential]", sanitized)
    for pattern in _TOKEN_VALUE_PATTERNS:
        sanitized = pattern.sub("[credential-value]", sanitized)
    sanitized = _FILE_URI_RE.sub(lambda match: _safe_path_reference(match.group("path")), sanitized)
    sanitized = _ABSOLUTE_LOCAL_PATH_RE.sub(lambda match: _safe_path_reference(match.group("path")), sanitized)
    sanitized = _HIDDEN_RUNTIME_PATH_RE.sub(lambda match: _safe_path_reference(match.group("path")), sanitized)
    return sanitized


def sanitize_brain_payload(value: Any) -> Any:
    """Recursively sanitize a payload immediately before Brain serialization."""

    if isinstance(value, str):
        return sanitize_brain_text(value)
    if isinstance(value, BaseModel):
        return sanitize_brain_payload(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        sanitized: dict[Any, Any] = {}
        credential_key_index = 0
        for key, item in value.items():
            if isinstance(key, str) and _CREDENTIAL_KEY_RE.fullmatch(key):
                credential_key_index += 1
                sanitized[f"[credential-{credential_key_index}]"] = "[redacted]"
                continue
            safe_key: Any = sanitize_brain_text(key) if isinstance(key, str) else key
            sanitized[safe_key] = sanitize_brain_payload(item)
        return sanitized
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize_brain_payload(item) for item in value]
    return value
