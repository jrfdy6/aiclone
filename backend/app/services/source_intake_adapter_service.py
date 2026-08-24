from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

from app.services.integrated_system_store import IntegratedSystemStore
from app.services.source_authorship_policy_service import (
    AUTHORSHIP_POLICY_VERSION,
    OWNER_AUTHORSHIP_ATTESTATION_KEY,
    OWNER_REQUESTED_ROUTE_KEY,
)
from app.services.source_intake_contract_service import (
    NormalizedDiscovery,
    SourceIntakeContractService,
    stable_discovery_key,
)
from app.services.source_sharing_policy_service import (
    credential_free_public_url,
    public_adapter_source_sharing,
    validate_remote_source_sharing,
)


ADAPTER_ENVELOPE_VERSION = "source_adapter_envelope/v1"
ADAPTER_VERSION = "1.0.0"
_BODY_SHAPED_METADATA_KEYS = frozenset(
    {
        "body",
        "content",
        "description",
        "excerpt",
        "raw",
        "raw_body",
        "summary",
        "text",
        "transcript",
    }
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_kind_for_url(value: str | None, *, fallback: str = "external_content") -> str:
    url = _clean(value)
    if not url:
        return fallback
    hostname = (urlsplit(url).hostname or "").lower().strip(".")
    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}:
        return "youtube_video"
    if hostname == "reddit.com" or hostname.endswith(".reddit.com"):
        return "reddit_post"
    if hostname == "linkedin.com" or hostname.endswith(".linkedin.com"):
        return "linkedin_post"
    return fallback


def _namespaced_external_id(namespace: str, value: str, *, scope: str | None = None) -> str:
    cleaned = _clean(value)
    if not cleaned:
        return ""
    prefix = f"{namespace}:{_sha256_text(_clean(scope))[:16]}" if _clean(scope) else namespace
    return f"{prefix}:{cleaned}"


def _compact_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    compact = {str(key): value for key, value in metadata.items() if value not in (None, "", [], {})}
    for key, value in compact.items():
        if key.lower() in _BODY_SHAPED_METADATA_KEYS:
            raise ValueError(f"adapter metadata must not contain source bodies: {key}")
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"adapter metadata values must be compact scalar facts: {key}")
    encoded = json.dumps(compact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 4096:
        raise ValueError("adapter metadata exceeds the compact event limit")
    return compact


def _authorship_metadata(
    *, owner_requested_route: bool, owner_authorship_attested: bool
) -> dict[str, Any]:
    return {
        "authorship_policy_version": AUTHORSHIP_POLICY_VERSION,
        OWNER_REQUESTED_ROUTE_KEY: bool(owner_requested_route),
        OWNER_AUTHORSHIP_ATTESTATION_KEY: bool(owner_authorship_attested),
    }


def _owner_routed_rights(
    rights_state: str | None, *, owner_authorship_attested: bool
) -> str:
    effective = _clean(rights_state).lower() or (
        "owner_controlled" if owner_authorship_attested else "permitted"
    )
    if effective == "owner_controlled" and not owner_authorship_attested:
        raise ValueError(
            "owner_controlled sources require an explicit owner_authorship_attested=true"
        )
    return effective


@dataclass(frozen=True)
class SourceAdapterEnvelope:
    origin: str
    adapter_name: str
    source_kind: str
    discovery_route: str
    external_ref: str
    canonical_url: str | None = None
    external_source_id: str | None = None
    shared_external_source_id: str | None = None
    content_sha256: str | None = None
    title: str | None = None
    author_or_publisher: str | None = None
    rights_state: str = "unknown"
    adapter_version: str = ADAPTER_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_sharing: Mapping[str, Any] | None = None

    def to_discovery(self) -> NormalizedDiscovery:
        adapter_name = _clean(self.adapter_name)
        adapter_version = _clean(self.adapter_version)
        external_ref = _clean(self.external_ref)
        if not adapter_name or not adapter_version:
            raise ValueError("adapter name and version are required")
        if not external_ref:
            raise ValueError("adapter external_ref is required")
        metadata = _compact_metadata(self.metadata)
        if self.source_sharing is not None:
            metadata["sharing"] = validate_remote_source_sharing(self.source_sharing)
        return NormalizedDiscovery(
            origin=self.origin,
            source_kind=_clean(self.source_kind),
            discovery_route=_clean(self.discovery_route),
            idempotency_key=stable_discovery_key(
                origin=self.origin,
                route=self.discovery_route,
                external_ref=external_ref,
            ),
            canonical_url=_clean(self.canonical_url) or None,
            external_source_id=_clean(self.external_source_id) or None,
            shared_external_source_id=_clean(self.shared_external_source_id) or None,
            content_sha256=_clean(self.content_sha256) or None,
            external_ref=external_ref,
            author_or_publisher=_clean(self.author_or_publisher) or None,
            title=_clean(self.title) or None,
            rights_state=self.rights_state,
            metadata={
                **metadata,
                "adapter_schema": ADAPTER_ENVELOPE_VERSION,
                "adapter_name": adapter_name,
                "adapter_version": adapter_version,
            },
        )


class SourceIntakeAdapterService:
    """Executes platform envelopes through the one canonical intake contract."""

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.intake = SourceIntakeContractService(store)

    def register(self, envelope: SourceAdapterEnvelope) -> dict[str, Any]:
        result = self.intake.register(envelope.to_discovery())
        return {
            **result,
            "adapter": {
                "schema_version": ADAPTER_ENVELOPE_VERSION,
                "name": envelope.adapter_name,
                "version": envelope.adapter_version,
                "origin": envelope.origin,
            },
        }


def _public_adapter_sharing(
    *, share_public_content: bool, rights_state: str, canonical_url: str | None
) -> dict[str, Any] | None:
    if not share_public_content:
        return None
    if rights_state != "permitted":
        raise ValueError(
            "public adapter sharing requires an explicitly permitted source"
        )
    credential_free_public_url(canonical_url)
    return public_adapter_source_sharing()


def youtube_discovery_envelope(
    *,
    origin: str,
    url: str,
    video_id: str | None,
    discovery_route: str,
    title: str | None = None,
    author: str | None = None,
    published_at: str | None = None,
    priority_lane: str | None = None,
    share_public_content: bool = False,
) -> SourceAdapterEnvelope:
    if origin not in {"youtube_watchlist", "youtube_playlist"}:
        raise ValueError("YouTube adapter origin must be watchlist or playlist")
    external_ref = _clean(video_id) or _clean(url)
    return SourceAdapterEnvelope(
        origin=origin,
        adapter_name="youtube_feed",
        source_kind="youtube_video",
        discovery_route=discovery_route,
        external_ref=external_ref,
        canonical_url=url,
        external_source_id=_namespaced_external_id("youtube", video_id or "") or None,
        shared_external_source_id=_namespaced_external_id("youtube", video_id or "") or None,
        title=title,
        author_or_publisher=author,
        rights_state="permitted",
        source_sharing=_public_adapter_sharing(
            share_public_content=share_public_content,
            rights_state="permitted",
            canonical_url=url,
        ),
        metadata={
            "observed_url": _clean(url),
            "published_at": _clean(published_at),
            "priority_lane": _clean(priority_lane),
        },
    )


def rss_discovery_envelope(
    *, feed_url: str, entry_url: str | None, entry_id: str, title: str | None = None,
    publisher: str | None = None, published_at: str | None = None, rights_state: str = "permitted",
    share_public_content: bool = False,
) -> SourceAdapterEnvelope:
    return SourceAdapterEnvelope(
        origin="rss", adapter_name="rss_feed", source_kind=_source_kind_for_url(entry_url),
        discovery_route=f"rss:{_clean(feed_url)}", external_ref=_clean(entry_id) or _clean(entry_url),
        canonical_url=entry_url, external_source_id=None if _clean(entry_url) else _namespaced_external_id("rss", entry_id, scope=feed_url),
        shared_external_source_id=_namespaced_external_id("feed_item", entry_id, scope=feed_url) or None,
        title=title, author_or_publisher=publisher, rights_state=rights_state,
        source_sharing=_public_adapter_sharing(
            share_public_content=share_public_content,
            rights_state=rights_state,
            canonical_url=entry_url,
        ),
        metadata={"feed_url": _clean(feed_url), "published_at": _clean(published_at)},
    )


def reddit_discovery_envelope(
    *, subreddit: str, reddit_id: str, canonical_url: str | None = None, title: str | None = None,
    author: str | None = None, discovery_surface: str = "subreddit_feed", rights_state: str = "permitted",
    share_public_content: bool = False,
) -> SourceAdapterEnvelope:
    return SourceAdapterEnvelope(
        origin="reddit", adapter_name="reddit_permitted_feed", source_kind="reddit_post",
        discovery_route=f"reddit:{_clean(discovery_surface)}:{_clean(subreddit).lower()}", external_ref=_clean(reddit_id),
        canonical_url=canonical_url, external_source_id=None if _clean(canonical_url) else _namespaced_external_id("reddit", reddit_id),
        shared_external_source_id=_namespaced_external_id("reddit", reddit_id) or None,
        title=title, author_or_publisher=author, rights_state=rights_state,
        source_sharing=_public_adapter_sharing(
            share_public_content=share_public_content,
            rights_state=rights_state,
            canonical_url=canonical_url,
        ),
        metadata={"subreddit": _clean(subreddit), "discovery_surface": _clean(discovery_surface)},
    )


def linkedin_discovery_envelope(
    *, discovery_surface: str, post_url: str | None, activity_urn: str, author: str | None = None,
    title: str | None = None, rights_state: str = "permitted",
    share_public_content: bool = False,
) -> SourceAdapterEnvelope:
    return SourceAdapterEnvelope(
        origin="linkedin", adapter_name="linkedin_assisted_browser", source_kind="linkedin_post",
        discovery_route=f"linkedin:{_clean(discovery_surface)}", external_ref=_clean(activity_urn) or _clean(post_url),
        canonical_url=post_url, external_source_id=None if _clean(post_url) else _namespaced_external_id("linkedin", activity_urn),
        shared_external_source_id=_namespaced_external_id("linkedin", activity_urn) or None,
        title=title, author_or_publisher=author, rights_state=rights_state,
        source_sharing=_public_adapter_sharing(
            share_public_content=share_public_content,
            rights_state=rights_state,
            canonical_url=post_url,
        ),
        metadata={"discovery_surface": _clean(discovery_surface)},
    )


def manual_discovery_envelope(
    *, submission_id: str, canonical_url: str | None = None, submitted_text: str | None = None,
    title: str | None = None, author: str | None = None, rights_state: str | None = None,
    owner_authorship_attested: bool = False,
    shared_external_source_id: str | None = None,
    source_sharing: Mapping[str, Any] | None = None,
) -> SourceAdapterEnvelope:
    body = str(submitted_text or "")
    if not _clean(canonical_url) and not body.strip():
        raise ValueError("manual submission requires a URL or submitted text")
    effective_rights = _owner_routed_rights(
        rights_state, owner_authorship_attested=owner_authorship_attested
    )
    return SourceAdapterEnvelope(
        origin="manual", adapter_name="manual_owner_submission", source_kind=_source_kind_for_url(canonical_url) if _clean(canonical_url) else "owner_material",
        discovery_route="manual:owner_submission", external_ref=_clean(submission_id), canonical_url=canonical_url,
        content_sha256=_sha256_text(body) if body.strip() and not _clean(canonical_url) else None,
        shared_external_source_id=shared_external_source_id,
        title=title, author_or_publisher=author, rights_state=effective_rights,
        source_sharing=source_sharing,
        metadata={
            "submission_id": _clean(submission_id),
            "has_submitted_text": bool(body.strip()),
            **_authorship_metadata(
                owner_requested_route=True,
                owner_authorship_attested=owner_authorship_attested,
            ),
        },
    )


def podcast_discovery_envelope(
    *, feed_url: str, episode_guid: str, episode_url: str | None = None, title: str | None = None,
    publisher: str | None = None, published_at: str | None = None, rights_state: str = "permitted",
    owner_requested_route: bool = False, owner_authorship_attested: bool = False,
    share_public_content: bool = False,
) -> SourceAdapterEnvelope:
    effective_rights = _owner_routed_rights(
        rights_state, owner_authorship_attested=owner_authorship_attested
    ) if owner_requested_route or rights_state == "owner_controlled" else rights_state
    return SourceAdapterEnvelope(
        origin="podcast", adapter_name="podcast_feed",
        source_kind=_source_kind_for_url(episode_url, fallback="external_content") if _clean(episode_url) else "podcast_episode",
        discovery_route=f"podcast:{_clean(feed_url)}", external_ref=_clean(episode_guid) or _clean(episode_url),
        canonical_url=episode_url, external_source_id=None if _clean(episode_url) else _namespaced_external_id("podcast", episode_guid, scope=feed_url),
        shared_external_source_id=_namespaced_external_id("feed_item", episode_guid, scope=feed_url) or None,
        title=title, author_or_publisher=publisher, rights_state=effective_rights,
        source_sharing=_public_adapter_sharing(
            share_public_content=share_public_content,
            rights_state=effective_rights,
            canonical_url=episode_url,
        ),
        metadata={
            "feed_url": _clean(feed_url),
            "episode_guid": _clean(episode_guid),
            "published_at": _clean(published_at),
            **_authorship_metadata(
                owner_requested_route=owner_requested_route,
                owner_authorship_attested=owner_authorship_attested,
            ),
        },
    )


def long_form_discovery_envelope(
    *, capture_route: str, external_ref: str, canonical_url: str | None = None, content_sha256: str | None = None,
    title: str | None = None, author: str | None = None, rights_state: str | None = None,
    owner_authorship_attested: bool = False,
    shared_external_source_id: str | None = None,
    source_sharing: Mapping[str, Any] | None = None,
) -> SourceAdapterEnvelope:
    effective_rights = _owner_routed_rights(
        rights_state, owner_authorship_attested=owner_authorship_attested
    )
    return SourceAdapterEnvelope(
        origin="long_form", adapter_name="long_form_capture", source_kind=_source_kind_for_url(canonical_url, fallback="external_content") if _clean(canonical_url) else "long_form_document",
        discovery_route=f"long_form:{_clean(capture_route)}", external_ref=_clean(external_ref),
        canonical_url=canonical_url, content_sha256=content_sha256,
        shared_external_source_id=shared_external_source_id, title=title,
        author_or_publisher=author, rights_state=effective_rights,
        source_sharing=source_sharing,
        metadata={
            "capture_route": _clean(capture_route),
            **_authorship_metadata(
                owner_requested_route=True,
                owner_authorship_attested=owner_authorship_attested,
            ),
        },
    )
