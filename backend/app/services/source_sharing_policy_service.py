from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit


REMOTE_SOURCE_SHARING_SCHEMA = "integrated_source_remote_sharing/v1"
REMOTE_SHAREABLE_CLASSIFICATIONS = frozenset(
    {"cloud", "cloud_safe", "public", "shared"}
)
REMOTE_SHARING_BASES = frozenset(
    {
        "owner_explicit",
        "shared_source_packet",
        "source_classification",
        "isolated_synthetic_fixture",
        "public_adapter_explicit",
    }
)
REMOTE_SOURCE_SHARING_FIELDS = frozenset(
    {"schema_version", "classification", "content_shareable", "basis"}
)
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "key",
        "password",
        "secret",
        "signature",
        "sig",
        "token",
    }
)
_INTERNAL_HOST_SUFFIXES = (
    ".example",
    ".home.arpa",
    ".invalid",
    ".internal",
    ".lan",
    ".local",
    ".localdomain",
    ".localhost",
    ".onion",
    ".test",
)


def validate_remote_source_sharing(raw: Any) -> dict[str, Any]:
    """Validate the one closed declaration that permits remote source text.

    Rights and admissibility answer whether content may be used.  They never
    answer whether captured bytes may leave the local canonical store.  Remote
    projection or generation therefore requires this separate, explicit
    declaration and rejects aliases, extra fields, and normalized guesses.
    """

    if not isinstance(raw, Mapping) or set(raw) != REMOTE_SOURCE_SHARING_FIELDS:
        raise ValueError(
            "remote source text requires an explicit closed source sharing declaration"
        )
    classification = raw.get("classification")
    basis = raw.get("basis")
    if (
        raw.get("schema_version") != REMOTE_SOURCE_SHARING_SCHEMA
        or not isinstance(classification, str)
        or classification not in REMOTE_SHAREABLE_CLASSIFICATIONS
        or raw.get("content_shareable") is not True
        or not isinstance(basis, str)
        or basis not in REMOTE_SHARING_BASES
    ):
        raise ValueError("source text is not explicitly classified for remote use")
    return {
        "schema_version": REMOTE_SOURCE_SHARING_SCHEMA,
        "classification": classification,
        "content_shareable": True,
        "basis": basis,
    }


def remote_source_sharing_from_metadata(metadata: Any) -> dict[str, Any] | None:
    """Return a verified declaration from source metadata, otherwise fail closed."""

    if isinstance(metadata, Mapping):
        parsed = dict(metadata)
    else:
        try:
            parsed = json.loads(str(metadata or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    if not isinstance(parsed, dict) or "sharing" not in parsed:
        return None
    try:
        return validate_remote_source_sharing(parsed.get("sharing"))
    except ValueError:
        return None


def source_remote_sharing(source: Any) -> dict[str, Any] | None:
    """Read verified sharing policy from a SQL row or source-shaped mapping."""

    try:
        metadata = source["metadata_json"]
    except (KeyError, IndexError, TypeError):
        if isinstance(source, Mapping):
            metadata = source.get("metadata")
        else:
            return None
    declaration = remote_source_sharing_from_metadata(metadata)
    if declaration is None:
        return None
    basis = declaration["basis"]
    classification = declaration["classification"]
    if classification == "public" or basis in {
        "public_adapter_explicit",
        "source_classification",
        "isolated_synthetic_fixture",
    }:
        try:
            canonical_url = source["canonical_url"]
        except (KeyError, IndexError, TypeError):
            return None
        try:
            credential_free_public_url(canonical_url)
        except ValueError:
            return None
    return declaration


def public_adapter_source_sharing() -> dict[str, Any]:
    """Build the declaration an adapter may opt into after observing public text."""

    return {
        "schema_version": REMOTE_SOURCE_SHARING_SCHEMA,
        "classification": "public",
        "content_shareable": True,
        "basis": "public_adapter_explicit",
    }


def source_classification_sharing() -> dict[str, Any]:
    """Build the declaration used by an explicit post-hoc policy classification."""

    return {
        "schema_version": REMOTE_SOURCE_SHARING_SCHEMA,
        "classification": "public",
        "content_shareable": True,
        "basis": "source_classification",
    }


def credential_free_public_url(value: Any) -> str:
    """Return one public HTTP(S) URL or reject local/private/credentialed hosts."""

    raw = str(value or "").strip()
    if not raw:
        raise ValueError("public source URL is required")
    try:
        parsed = urlsplit(raw)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
    except ValueError as exc:
        raise ValueError("public source URL is malformed") from exc
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(key.casefold() in _SENSITIVE_QUERY_KEYS for key, _ in query)
        or hostname == "localhost"
        or hostname.endswith(_INTERNAL_HOST_SUFFIXES)
    ):
        raise ValueError("source URL is not credential-free and public")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname or re.fullmatch(r"[0-9.]+", hostname):
            raise ValueError("source URL host is not publicly qualified")
    else:
        if not address.is_global:
            raise ValueError("source URL IP host is not globally routable")
    return raw


def is_credential_free_public_url(value: Any) -> bool:
    try:
        credential_free_public_url(value)
    except ValueError:
        return False
    return True
