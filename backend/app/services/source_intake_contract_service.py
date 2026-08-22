from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.integrated_system_store import IntegratedSystemStore
from app.services.source_sharing_policy_service import validate_remote_source_sharing


SUPPORTED_ORIGINS = frozenset(
    {
        "youtube_watchlist",
        "youtube_playlist",
        "manual",
        "rss",
        "reddit",
        "linkedin",
        "podcast",
        "long_form",
        "owner_curated",
        "permitted_discovery",
    }
)
TRACKING_QUERY_KEYS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"})
TRACKING_QUERY_PREFIXES = ("utm_",)
BLOCKED_SCHEMES = frozenset({"file", "data", "javascript"})
SHARED_EXTERNAL_ID_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def canonicalize_external_url(value: str) -> str:
    raw = _clean(value)
    parts = urlsplit(raw)
    if parts.scheme.lower() in BLOCKED_SCHEMES or parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("source URL must use permitted HTTP(S)")
    hostname = (parts.hostname or "").lower().strip(".")
    if not hostname:
        raise ValueError("source URL must include a hostname")
    port = parts.port
    default_port = (parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query_map = dict(parse_qsl(parts.query, keep_blank_values=True))
    if hostname in {"youtu.be", "www.youtu.be"}:
        video_id = path.strip("/").split("/", 1)[0]
        if video_id:
            return f"https://youtube.com/watch?v={video_id}"
    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"} and path == "/watch":
        video_id = _clean(query_map.get("v"))
        if video_id:
            return f"https://youtube.com/watch?v={video_id}"
    if path != "/":
        path = path.rstrip("/")
    query_items = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    query = urlencode(sorted(query_items))
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def normalize_shared_external_id(value: str | None) -> str | None:
    """Normalize an explicit cross-adapter identity without guessing aliases.

    A shared external ID is stronger than a route-local ``external_source_id``:
    adapters may emit it only when two origins refer to the same provider
    object (for example the same feed URL plus episode GUID).  Requiring an
    explicit namespace prevents common opaque IDs such as ``123`` from
    colliding across providers.
    """

    raw = _clean(value)
    if not raw:
        return None
    if len(raw) > 512 or any(ord(char) < 32 for char in raw):
        raise ValueError("shared external source id is invalid")
    namespace, separator, identifier = raw.partition(":")
    namespace = namespace.lower()
    if not separator or not identifier or not SHARED_EXTERNAL_ID_NAMESPACE.fullmatch(namespace):
        raise ValueError("shared external source id must be namespaced")
    return f"{namespace}:{identifier}"


def canonical_source_identity(*, canonical_url: str | None, external_source_id: str | None, content_sha256: str | None) -> str:
    if canonical_url:
        return f"url:{canonicalize_external_url(canonical_url)}"
    if external_source_id and _clean(external_source_id):
        return f"external:{_clean(external_source_id).lower()}"
    if content_sha256 and re.fullmatch(r"[0-9a-fA-F]{64}", content_sha256):
        return f"sha256:{content_sha256.lower()}"
    raise ValueError("source requires a canonical URL, external source id, or SHA-256")


@dataclass(frozen=True)
class NormalizedDiscovery:
    origin: str
    source_kind: str
    discovery_route: str
    idempotency_key: str
    canonical_url: str | None = None
    external_source_id: str | None = None
    shared_external_source_id: str | None = None
    content_sha256: str | None = None
    external_ref: str | None = None
    author_or_publisher: str | None = None
    title: str | None = None
    rights_state: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> "NormalizedDiscovery":
        if self.origin not in SUPPORTED_ORIGINS:
            raise ValueError(f"unsupported source origin: {self.origin}")
        if not _clean(self.source_kind):
            raise ValueError("source_kind is required")
        if not _clean(self.discovery_route):
            raise ValueError("discovery_route is required")
        if not _clean(self.idempotency_key):
            raise ValueError("idempotency_key is required")
        if self.rights_state not in {"unknown", "permitted", "owner_controlled", "restricted", "blocked"}:
            raise ValueError("invalid rights_state")
        canonical_source_identity(
            canonical_url=self.canonical_url,
            external_source_id=self.external_source_id,
            content_sha256=self.content_sha256,
        )
        normalize_shared_external_id(self.shared_external_source_id)
        if "sharing" in self.metadata:
            validate_remote_source_sharing(self.metadata.get("sharing"))
        return self

    @property
    def identity(self) -> str:
        self.validate()
        return canonical_source_identity(
            canonical_url=self.canonical_url,
            external_source_id=self.external_source_id,
            content_sha256=self.content_sha256,
        )

    @property
    def normalized_url(self) -> str | None:
        return canonicalize_external_url(self.canonical_url) if self.canonical_url else None

    @property
    def normalized_shared_external_source_id(self) -> str | None:
        return normalize_shared_external_id(self.shared_external_source_id)


class SourceIntakeContractService:
    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def register(self, discovery: NormalizedDiscovery) -> dict[str, Any]:
        discovery.validate()
        incoming_sharing = (
            validate_remote_source_sharing(discovery.metadata.get("sharing"))
            if "sharing" in discovery.metadata
            else None
        )
        result = self.store.register_source_discovery(
            canonical_identity=discovery.identity,
            source_kind=_clean(discovery.source_kind).lower(),
            origin=discovery.origin,
            discovery_route=_clean(discovery.discovery_route),
            idempotency_key=_clean(discovery.idempotency_key),
            canonical_url=discovery.normalized_url,
            author_or_publisher=_clean(discovery.author_or_publisher) or None,
            title=_clean(discovery.title) or None,
            rights_state=discovery.rights_state,
            external_ref=_clean(discovery.external_ref) or None,
            metadata={
                **dict(discovery.metadata),
                **(
                    {"shared_external_source_id": discovery.normalized_shared_external_source_id}
                    if discovery.normalized_shared_external_source_id
                    else {}
                ),
                "initial_trust_policy": "origin_neutral",
                "expensive_processing_state": "not_started",
            },
        )
        if incoming_sharing is not None:
            with self.store.connection() as connection:
                row = connection.execute(
                    "SELECT * FROM sources WHERE source_id=?",
                    (result["source"]["source_id"],),
                ).fetchone()
                try:
                    source_metadata = json.loads(row["metadata_json"] if row else "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    source_metadata = {}
                # A pre-existing sharing key is an explicit boundary, including
                # a deliberately non-shareable or malformed legacy value.  A
                # duplicate adapter may fill an absent classification but may
                # never silently broaden an existing one.
                if row and "sharing" not in source_metadata:
                    source_metadata["sharing"] = incoming_sharing
                    connection.execute(
                        "UPDATE sources SET metadata_json=? WHERE source_id=?",
                        (
                            json.dumps(
                                source_metadata,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                            row["source_id"],
                        ),
                    )
                    row = connection.execute(
                        "SELECT * FROM sources WHERE source_id=?", (row["source_id"],)
                    ).fetchone()
                if row:
                    result["source"] = dict(row)
        return {
            **result,
            "gate": {
                "registered_cheaply": True,
                "duplicate_source": result["source"]["created_at"] != result["source"]["updated_at"],
                "expensive_processing_authorized": False,
                "initial_trust_policy": "origin_neutral",
            },
        }


def stable_discovery_key(*, origin: str, route: str, external_ref: str) -> str:
    material = f"{origin}\n{_clean(route)}\n{_clean(external_ref)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
