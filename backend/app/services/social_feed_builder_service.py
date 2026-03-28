from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.services.workspace_snapshot_store import get_snapshot_payload
from app.services.social_signal_utils import (
    build_variants,
    normalize_lane,
    normalize_saved_signal,
)


def _candidate_roots() -> list[Path]:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/app/backend"), Path("/")]
    ordered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def discover_linkedin_workspace_root() -> Path:
    patterns = [
        "workspaces/linkedin-content-os",
        "backend/workspaces/linkedin-content-os",
        "linkedin-content-os",
    ]
    for base in _candidate_roots():
        for pattern in patterns:
            candidate = base / pattern
            if candidate.exists() and candidate.is_dir():
                return candidate
    return Path(__file__).resolve().parents[3] / "workspaces" / "linkedin-content-os"


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def _list_strings(value: Any, limit: int = 8) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(str(item))
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _parse_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _placeholder_marker(value: str | None) -> bool:
    if not value:
        return False
    lowered = _clean_text(value).lower()
    return any(
        marker in lowered
        for marker in (
            "placeholder capture for ",
            "# reddit placeholder",
            "# rss placeholder",
            "rss capture for ",
        )
    )


def _is_placeholder_signal(signal: dict[str, Any]) -> bool:
    fields: list[str] = [
        str(signal.get("title") or ""),
        str(signal.get("summary") or ""),
        str(signal.get("body_text") or ""),
        str(signal.get("core_claim") or ""),
        str(signal.get("why_it_matters") or ""),
    ]
    fields.extend(str(item) for item in _list_strings(signal.get("headline_candidates"), 4))
    fields.extend(str(item) for item in _list_strings(signal.get("supporting_claims"), 4))
    return any(_placeholder_marker(field) for field in fields)


def _is_placeholder_item(item: dict[str, Any]) -> bool:
    fields: list[str] = [
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("comment_draft") or ""),
        str(item.get("repost_draft") or ""),
        str(item.get("why_it_matters") or ""),
        str(item.get("core_claim") or ""),
    ]
    for standout in item.get("standout_lines") or []:
        fields.append(str(standout))
    for variant in (item.get("lens_variants") or {}).values():
        if not isinstance(variant, dict):
            continue
        fields.extend(
            [
                str(variant.get("comment") or ""),
                str(variant.get("repost") or ""),
                str(variant.get("short_comment") or ""),
                str(((variant.get("expression_assessment") or {}).get("source_text") or "")),
                str(((variant.get("expression_assessment") or {}).get("output_text") or "")),
            ]
        )
    return any(_placeholder_marker(field) for field in fields)


def _load_watchlist(workspace_root: Path) -> dict[str, Any]:
    watchlist_path = workspace_root / "research" / "watchlists.yaml"
    if not watchlist_path.exists():
        return {}
    with watchlist_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _read_saved_signals(workspace_root: Path) -> list[dict[str, Any]]:
    research_root = workspace_root / "research" / "market_signals"
    if not research_root.exists():
        return []

    signals: list[dict[str, Any]] = []
    for path in sorted(research_root.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        text = path.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        parts = text.split("---", 2)
        body_text = parts[2].strip() if len(parts) >= 3 else ""
        meta["source_path"] = path.relative_to(workspace_root).as_posix()
        meta["id"] = path.stem
        meta["body_text"] = body_text
        if _is_placeholder_signal(meta):
            continue
        signals.append(meta)
    return signals


def _load_existing_feed(workspace_root: Path) -> dict[str, Any] | None:
    plans_path = workspace_root / "plans" / "social_feed.json"
    if not plans_path.exists():
        return None
    try:
        payload = json.loads(plans_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None
    filtered_items = [item for item in items if isinstance(item, dict) and not _is_placeholder_item(item)]
    if filtered_items:
        payload["items"] = filtered_items
    else:
        return None
    first_item = payload["items"][0] if payload["items"] else {}
    if not isinstance(first_item, dict) or not first_item.get("lens_variants"):
        return None
    return payload


def _load_persisted_feed() -> dict[str, Any] | None:
    try:
        payload = get_snapshot_payload("linkedin-content-os", "social_feed")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None
    filtered_items = [item for item in items if isinstance(item, dict) and not _is_placeholder_item(item)]
    if not filtered_items:
        return None
    payload = dict(payload)
    payload["items"] = filtered_items
    return payload


def _item_fingerprint(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _clean_text(item.get("platform") or ""),
        _clean_text(item.get("source_url") or ""),
        _clean_text(item.get("title") or "").lower(),
    )


def _preserve_linkedin_items(items: list[dict[str, Any]], *feeds: dict[str, Any] | None) -> list[dict[str, Any]]:
    merged = list(items)
    seen = {_item_fingerprint(item) for item in merged}
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        for item in feed.get("items") or []:
            if not isinstance(item, dict):
                continue
            if _clean_text(item.get("platform")) != "linkedin":
                continue
            fingerprint = _item_fingerprint(item)
            if fingerprint in seen:
                continue
            merged.append(item)
            seen.add(fingerprint)
    return merged


def _normalize_signal(signal: dict[str, Any], watchlist: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_saved_signal(
        signal,
        signal_id=signal.get("id"),
        source_path=signal.get("source_path"),
        raw_text=signal.get("body_text"),
    )
    now = datetime.now(timezone.utc)
    created_dt = _parse_datetime(normalized.get("captured_at")) or now
    age_hours = max(0, round((now - created_dt).total_seconds() / 3600))
    topics = normalized.get("topic_tags") or []
    lenses: list[str] = []
    priority_people = watchlist.get("priority_people", [])
    priority_weight = 0.5

    author = normalized.get("author", "Unknown")
    for person in priority_people:
        if person.get("name") and person["name"].lower() in str(author).lower():
            priority_weight = max(priority_weight, person.get("priority_weight", 0.6))
            lenses.extend(person.get("lenses", []))

    if priority_lane := normalized.get("priority_lane"):
        lenses.append(normalize_lane(priority_lane))

    topic_match = len(set(topics) & set(watchlist.get("topics", [])))
    source_platform = normalized.get("source_channel", "linkedin")
    source_quality = 40 if source_platform == "linkedin" else 5
    if normalized.get("standout_lines"):
        source_quality += 10
    if normalized.get("source_type") == "post":
        source_quality += 5

    ranking = {
        "priority_network": round(priority_weight * 100, 1),
        "topic_match": topic_match * 10,
        "recency": max(0, 100 - age_hours),
        "engagement": normalized.get("engagement", {}).get("likes", 0) * 0.1,
        "persona_fit": 10 if normalized.get("role_alignment") else 0,
        "source_quality": source_quality,
    }
    ranking["total"] = sum(ranking.values())

    title = normalized.get("title") or "Untitled"
    lens_variants = build_variants(normalized)
    default_lane = normalize_lane(normalized.get("priority_lane"))
    default_variant = lens_variants.get(default_lane) or lens_variants["current-role"]
    belief_assessment = {
        "stance": default_variant["stance"],
        "agreement_level": default_variant["agreement_level"],
        "belief_used": default_variant["belief_used"],
        "belief_summary": default_variant["belief_summary"],
        "experience_anchor": default_variant["experience_anchor"],
        "experience_summary": default_variant["experience_summary"],
        "role_safety": default_variant["role_safety"],
    }
    technique_assessment = {
        "techniques": default_variant["techniques"],
        "emotional_profile": default_variant["emotional_profile"],
        "reason": default_variant["technique_reason"],
    }
    expression_assessment = default_variant["expression_assessment"]

    return {
        "id": f"{normalized.get('source_channel', 'unknown')}__{normalized.get('signal_id')}",
        "platform": normalized.get("source_channel", "linkedin"),
        "source_lane": normalized.get("source_lane", "market_signal"),
        "capture_method": normalized.get("capture_method", "saved_signal"),
        "title": title,
        "author": author,
        "source_url": normalized.get("source_url"),
        "source_path": normalized.get("source_path"),
        "published_at": normalized.get("published_at"),
        "captured_at": normalized.get("captured_at"),
        "summary": normalized.get("summary"),
        "standout_lines": normalized.get("standout_lines", []),
        "engagement": normalized.get("engagement", {"likes": 0, "comments": 0, "shares": 0}),
        "ranking": ranking,
        "lenses": list(dict.fromkeys(lenses)),
        "comment_draft": default_variant["comment"],
        "repost_draft": default_variant["repost"],
        "lens_variants": lens_variants,
        "why_it_matters": normalized.get("why_it_matters"),
        "notes": normalized.get("language_patterns", []),
        "core_claim": normalized.get("core_claim"),
        "supporting_claims": normalized.get("supporting_claims", []),
        "topic_tags": normalized.get("topic_tags", []),
        "trust_notes": normalized.get("trust_notes", []),
        "source_metadata": normalized.get("source_metadata", {}),
        "belief_assessment": belief_assessment,
        "technique_assessment": technique_assessment,
        "expression_assessment": expression_assessment,
        "evaluation": default_variant["evaluation"],
    }


def build_feed(workspace_root: Path | None = None) -> dict[str, Any]:
    resolved_root = workspace_root or discover_linkedin_workspace_root()
    watchlist = _load_watchlist(resolved_root)
    signals = _read_saved_signals(resolved_root)
    existing_feed = _load_existing_feed(resolved_root)
    persisted_feed = _load_persisted_feed()
    if not signals:
        if existing_feed:
            return existing_feed
        if persisted_feed:
            return persisted_feed
    items = [_normalize_signal(signal, watchlist) for signal in signals]
    items = _preserve_linkedin_items(items, existing_feed, persisted_feed)
    items.sort(key=lambda item: item["ranking"]["total"], reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "strategy_mode": "production",
        "items": items,
    }


def write_feed_artifacts(feed: dict[str, Any], workspace_root: Path | None = None) -> None:
    resolved_root = workspace_root or discover_linkedin_workspace_root()
    plans_root = resolved_root / "plans"
    plans_root.mkdir(parents=True, exist_ok=True)

    json_path = plans_root / "social_feed.json"
    md_path = plans_root / "social_feed.md"
    json_path.write_text(json.dumps(feed, indent=2), encoding="utf-8")

    lines = ["# LinkedIn Social Feed", f"Updated {feed['generated_at']}", ""]
    for item in feed.get("items", []):
        lines.append(f"- {item['platform']} · {item['title']} ({item['author']})")
        if item.get("source_url"):
            lines.append(f"  - {item['source_url']}")
        lines.append(f"  - score: {item['ranking']['total']:.1f}")
    md_path.write_text("\n".join(lines), encoding="utf-8")
