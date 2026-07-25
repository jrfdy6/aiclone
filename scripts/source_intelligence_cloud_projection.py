#!/usr/bin/env python3
"""Build the least-privilege source-intelligence snapshot used by Railway.

The local index is intentionally richer than the deployed snapshot.  A source
only crosses the deployment boundary when it carries an explicit sharing
classification or points at a packet whose ``.shared_source_packet.json``
suffix is itself the sharing declaration.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CLOUD_PROJECTION_SCHEMA = "source_intelligence_cloud_projection/v1"
SHAREABLE_CLASSIFICATIONS = frozenset({"cloud", "cloud_safe", "public", "shared"})
SOURCE_STATES = ("raw", "digested", "reviewed", "routed", "promoted", "ignored")
SAFE_SOURCE_FIELDS = (
    "title",
    "summary",
    "published_at",
    "captured_at",
)
SAFE_SOURCE_IDENTIFIER_FIELDS = (
    "source_kind",
    "source_class",
    "source_channel",
    "source_type",
)
SENSITIVE_QUERY_NAMES = frozenset(
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
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,240}$")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_EMBEDDED_POSIX_PATH = re.compile(r"(?:^|[\s=`'\"(\[{])/(?!/)[^\s`'\"<>()\[\]{}]+")
_EMBEDDED_HOME_PATH = re.compile(r"(?:^|[\s=`'\"(\[{])~[\\/][^\s`'\"<>()\[\]{}]+")
_EMBEDDED_WINDOWS_PATH = re.compile(r"(?:^|[\s=`'\"(\[{])[A-Za-z]:[\\/][^\s`'\"<>()\[\]{}]+")
_LOCAL_RELATIVE_PREFIXES = (
    ".codex/",
    "app/",
    "backend/",
    "docs/",
    "frontend/",
    "knowledge/",
    "memory/",
    "scripts/",
    "state/",
    "workspaces/",
)
_LOCAL_FILE_SUFFIXES = (
    ".db",
    ".json",
    ".jsonl",
    ".md",
    ".sqlite",
    ".sqlite3",
    ".txt",
    ".yaml",
    ".yml",
)


def build_cloud_safe_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a content-minimized projection of a local source index.

    Aggregate status counts remain available so the production health surface
    keeps its existing contract.  The ``sources`` collection contains only
    explicitly shareable items, and path-bearing fields are never emitted.
    """

    if not isinstance(payload, dict):
        raise ValueError("Source-intelligence index must be a JSON object.")

    raw_sources = [item for item in (payload.get("sources") or []) if isinstance(item, dict)]
    projected_sources: list[dict[str, Any]] = []
    for source in raw_sources:
        sharing = explicit_shareability(source)
        if sharing is None:
            continue
        projected_sources.append(_project_source(source, sharing=sharing))

    counts = _safe_counts(payload.get("counts"))
    if not counts:
        counts = _count_sources(raw_sources)

    projection: dict[str, Any] = {
        # Keep v1 here because existing backend readers already consume this
        # schema.  The projection contract is identified separately below.
        "schema_version": "source_intelligence_index/v1",
        "generated_at": _safe_text(payload.get("generated_at"), limit=80),
        "states": list(SOURCE_STATES),
        "counts": counts,
        "sources": projected_sources,
        "cloud_projection": {
            "schema_version": CLOUD_PROJECTION_SCHEMA,
            "policy": "explicit_shareability_only",
            "aggregate_source_count": len(raw_sources),
            "shared_source_count": len(projected_sources),
            "withheld_source_count": max(0, len(raw_sources) - len(projected_sources)),
            "paths_included": False,
        },
    }
    if projection["generated_at"] is None:
        projection.pop("generated_at")

    _assert_no_local_paths(projection)
    return projection


def explicit_shareability(source: dict[str, Any]) -> dict[str, str] | None:
    """Return a canonical sharing declaration or ``None``.

    Old local indexes predate the structured ``sharing`` field.  The exact
    ``.shared_source_packet.json`` suffix remains accepted as an explicit,
    backwards-compatible declaration; ordinary JSON, Markdown, and index paths
    never imply shareability.
    """

    sharing = source.get("sharing") if isinstance(source.get("sharing"), dict) else {}
    classification = str(
        sharing.get("classification") or sharing.get("scope") or ""
    ).strip().lower()
    content_shareable = sharing.get("content_shareable")
    content_flag_is_valid = (
        "content_shareable" not in sharing
        or content_shareable is True
    )
    if classification in SHAREABLE_CLASSIFICATIONS and content_flag_is_valid:
        return {
            "classification": classification,
            "basis": "source_classification",
        }

    for field in ("metadata_path", "normalized_path", "digest_path"):
        candidate = str(source.get(field) or "").strip().replace("\\", "/")
        filename = candidate.rsplit("/", 1)[-1].lower()
        if (
            candidate
            and _is_safe_logical_packet_ref(candidate)
            and (
                filename == "shared_source_packet.json"
                or filename.endswith(".shared_source_packet.json")
            )
        ):
            return {
                "classification": "shared",
                "basis": "shared_source_packet",
            }
    return None


def _is_safe_logical_packet_ref(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    if (
        not normalized
        or normalized.startswith(("/", "~/"))
        or _WINDOWS_DRIVE_PATH.match(normalized)
        or ".." in normalized.split("/")
        or "file://" in normalized.lower()
    ):
        return False
    return True


def project_source_intelligence_file(input_path: Path, output_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid source-intelligence JSON: {input_path}") from exc
    projection = build_cloud_safe_projection(payload)
    _atomic_write_json(output_path, projection)
    return projection


def _project_source(source: dict[str, Any], *, sharing: dict[str, str]) -> dict[str, Any]:
    projected: dict[str, Any] = {
        "source_id": _safe_source_id(source.get("source_id")),
        "sharing": {
            "classification": sharing["classification"],
            "content_shareable": True,
            "basis": sharing["basis"],
        },
    }
    for field in SAFE_SOURCE_IDENTIFIER_FIELDS:
        safe_value = _safe_identifier(source.get(field))
        if safe_value is not None:
            projected[field] = safe_value
    for field in SAFE_SOURCE_FIELDS:
        safe_value = _safe_text(source.get(field), limit=2_000 if field == "summary" else 500)
        if safe_value is not None:
            projected[field] = safe_value

    status = str(source.get("status") or "").strip().lower()
    projected["status"] = status if status in SOURCE_STATES else "raw"

    source_url = _safe_public_url(source.get("source_url"))
    if source_url is not None:
        projected["source_url"] = source_url

    route_decision = source.get("route_decision")
    if isinstance(route_decision, dict):
        safe_route: dict[str, Any] = {}
        workspace_key = _safe_identifier(route_decision.get("workspace_key"))
        if workspace_key:
            safe_route["workspace_key"] = workspace_key
        affordances = route_decision.get("route_affordances")
        if isinstance(affordances, dict):
            safe_affordances = {
                key: value
                for raw_key, value in affordances.items()
                if isinstance(value, bool)
                and (key := _safe_identifier(raw_key))
            }
            if safe_affordances:
                safe_route["route_affordances"] = safe_affordances
        if safe_route:
            projected["route_decision"] = safe_route
    return projected


def _safe_source_id(value: Any) -> str:
    text = str(value or "").strip()
    if _SAFE_IDENTIFIER.fullmatch(text):
        return text
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"source-{digest}"


def _safe_identifier(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if _SAFE_IDENTIFIER.fullmatch(text) else None


def _safe_text(value: Any, *, limit: int) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = " ".join(str(value).replace("\xa0", " ").split()).strip()
    if not text or _contains_local_path(text):
        return None
    return text[:limit]


def _safe_public_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or _contains_local_path(text):
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.hostname or parsed.username or parsed.password:
        return None
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        return None
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return None
    safe_query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.strip().lower() not in SENSITIVE_QUERY_NAMES
        and not _contains_local_path(item)
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path,
            urlencode(safe_query, doseq=True),
            "",
        )
    )


def _contains_local_path(value: str) -> bool:
    text = str(value or "")
    lowered = text.lower()
    if "file://" in lowered or ".codex/ai-clone" in lowered or ".codex\\ai-clone" in lowered:
        return True
    if (
        _EMBEDDED_POSIX_PATH.search(text)
        or _EMBEDDED_HOME_PATH.search(text)
        or _EMBEDDED_WINDOWS_PATH.search(text)
    ):
        return True
    configured_state = str(os.getenv("AI_CLONE_STATE_ROOT") or "").strip()
    if configured_state and configured_state in text:
        return True
    for raw_token in text.split():
        token = raw_token.strip("`'\"()[]{}<>,;")
        if not token:
            continue
        normalized = token.replace("\\", "/").lower()
        if normalized.startswith(("./", "../")):
            return True
        if normalized.startswith(_LOCAL_RELATIVE_PREFIXES):
            return True
        if "/" in normalized and normalized.endswith(_LOCAL_FILE_SUFFIXES):
            return True
        if token.startswith("~/") or token.startswith("~\\"):
            return True
        if token.startswith("/") and len(token) > 1:
            return True
        if _WINDOWS_DRIVE_PATH.match(token) or PureWindowsPath(token).is_absolute():
            return True
    return False


def _safe_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts: dict[str, int] = {}
    for key in ("total", *SOURCE_STATES):
        raw = value.get(key)
        if isinstance(raw, bool):
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        counts[key] = max(0, number)
    return counts


def _count_sources(sources: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(sources), **{state: 0 for state in SOURCE_STATES}}
    for source in sources:
        status = str(source.get("status") or "raw").strip().lower()
        counts[status if status in SOURCE_STATES else "raw"] += 1
    return counts


def _assert_no_local_paths(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower().endswith("_path") or str(key).lower().endswith("_paths"):
                raise ValueError(f"Cloud projection cannot contain path field: {key}")
            _assert_no_local_paths(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_no_local_paths(item)
        return
    if isinstance(value, str) and _contains_local_path(value):
        raise ValueError("Cloud projection contains a local path.")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise RuntimeError(f"Cloud projection target must not be a symlink: {target}")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project a private source-intelligence index into a cloud-safe snapshot."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    projection = project_source_intelligence_file(args.input, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "shared_sources": projection["cloud_projection"]["shared_source_count"],
                "withheld_sources": projection["cloud_projection"]["withheld_source_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
