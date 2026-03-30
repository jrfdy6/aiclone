from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.services.workspace_snapshot_store import get_snapshot_payload
from app.services.social_signal_utils import (
    build_variants,
    infer_response_modes,
    infer_source_class,
    infer_unit_kind,
    normalize_lane,
    normalize_response_modes,
    normalize_saved_signal,
    normalize_source_class,
    normalize_unit_kind,
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


def _workspace_root_priority(candidate: Path) -> tuple[int, int, int, str]:
    posix = candidate.as_posix()
    is_backend_copy = "/backend/workspaces/linkedin-content-os" in posix
    has_feed_artifact = (candidate / "plans" / "social_feed.json").exists()
    return (
        1 if is_backend_copy else 0,
        0 if has_feed_artifact else 1,
        len(candidate.parts),
        posix,
    )


def _workspace_root_matches() -> list[Path]:
    patterns = [
        "workspaces/linkedin-content-os",
        "backend/workspaces/linkedin-content-os",
        "linkedin-content-os",
    ]
    matches: list[Path] = []
    seen: set[Path] = set()
    for base in _candidate_roots():
        for pattern in patterns:
            candidate = (base / pattern).resolve()
            if not candidate.exists() or not candidate.is_dir() or candidate in seen:
                continue
            seen.add(candidate)
            matches.append(candidate)
    return sorted(matches, key=_workspace_root_priority)


def discover_linkedin_workspace_root() -> Path:
    matches = _workspace_root_matches()
    if matches:
        return matches[0]
    return Path(__file__).resolve().parents[3] / "workspaces" / "linkedin-content-os"


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def _lowered_text(value: str | None) -> str:
    return _clean_text(value).lower()


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
    filtered_items = [_ensure_source_contract(item) for item in items if isinstance(item, dict) and not _is_placeholder_item(item)]
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
    filtered_items = [_ensure_source_contract(item) for item in items if isinstance(item, dict) and not _is_placeholder_item(item)]
    if not filtered_items:
        return None
    payload = dict(payload)
    payload["items"] = filtered_items
    return payload


def _load_alternate_feeds(workspace_root: Path) -> list[dict[str, Any]]:
    feeds: list[dict[str, Any]] = []
    resolved_workspace_root = workspace_root.resolve()
    for candidate in _workspace_root_matches():
        if candidate == resolved_workspace_root:
            continue
        feed = _load_existing_feed(candidate)
        if feed:
            feeds.append(feed)
    return feeds


def _item_fingerprint(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _clean_text(item.get("platform") or ""),
        _clean_text(item.get("source_url") or ""),
        _clean_text(item.get("title") or "").lower(),
    )


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_phrase_list(value: Any) -> list[str]:
    return [item for item in (_lowered_text(str(entry)) for entry in _list_strings(value, limit=32)) if item]


def _normalize_weight_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, raw in value.items():
        label = _lowered_text(str(key))
        if not label:
            continue
        normalized[label] = _coerce_float(raw, 0.0)
    return normalized


def _normalize_phrase_weights(value: Any) -> list[tuple[str, float]]:
    if isinstance(value, dict):
        return [(phrase, weight) for phrase, weight in _normalize_weight_map(value).items() if phrase]
    if not isinstance(value, list):
        return []
    normalized: list[tuple[str, float]] = []
    for entry in value:
        if isinstance(entry, dict):
            phrase = _lowered_text(str(entry.get("phrase") or entry.get("term") or entry.get("value") or ""))
            if not phrase:
                continue
            normalized.append((phrase, _coerce_float(entry.get("weight"), 0.0)))
            continue
        phrase = _lowered_text(str(entry))
        if phrase:
            normalized.append((phrase, 0.0))
    return normalized


def _item_text_blob(item: dict[str, Any]) -> str:
    parts: list[str] = [
        str(item.get("title") or ""),
        str(item.get("author") or ""),
        str(item.get("summary") or ""),
        str(item.get("why_it_matters") or ""),
        str(item.get("core_claim") or ""),
        str(item.get("comment_draft") or ""),
        str(item.get("repost_draft") or ""),
    ]
    parts.extend(str(value) for value in item.get("standout_lines") or [])
    parts.extend(str(value) for value in item.get("supporting_claims") or [])
    parts.extend(str(value) for value in item.get("topic_tags") or [])
    parts.extend(str(value) for value in item.get("notes") or [])
    return _lowered_text(" ".join(parts))


def _lane_labels(item: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for lane in item.get("lenses") or []:
        normalized = _lowered_text(str(lane))
        if normalized and normalized not in labels:
            labels.append(normalized)
    belief_lane = _lowered_text(str(((item.get("belief_assessment") or {}).get("belief_used")) or ""))
    if belief_lane and belief_lane not in labels:
        labels.append(belief_lane)
    return labels


def _platform_key(item: dict[str, Any]) -> str:
    return _lowered_text(str(item.get("platform") or "unknown")) or "unknown"


def _curation_config(watchlist: dict[str, Any]) -> dict[str, Any]:
    filters = watchlist.get("filters") if isinstance(watchlist.get("filters"), dict) else {}
    curation = watchlist.get("curation") if isinstance(watchlist.get("curation"), dict) else {}
    return {
        "min_total_score": _coerce_float(curation.get("min_total_score"), 0.0),
        "target_feed_size": _coerce_int(curation.get("target_feed_size"), 12),
        "platform_limits": {key: _coerce_int(value, 0) for key, value in _normalize_weight_map(curation.get("platform_limits")).items()},
        "platform_boosts": _normalize_weight_map(curation.get("platform_boosts")),
        "lane_boosts": _normalize_weight_map(curation.get("lane_boosts")),
        "keyword_boosts": _normalize_phrase_weights(curation.get("keyword_boosts")),
        "blocked_phrases": _clean_phrase_list(curation.get("blocked_phrases")),
        "demoted_phrases": _normalize_phrase_weights(curation.get("demoted_phrases")),
        "legacy_prioritize": _clean_phrase_list(filters.get("prioritize")),
        "legacy_avoid": _clean_phrase_list(filters.get("avoid")),
    }


def _evaluate_curation(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    base_total = _coerce_float((item.get("ranking") or {}).get("total"), 0.0)
    text_blob = _item_text_blob(item)
    platform = _platform_key(item)
    lanes = _lane_labels(item)

    matched_boosts: list[str] = []
    matched_penalties: list[str] = []
    blocked_by: list[str] = []
    score_adjustment = 0.0

    platform_boost = _coerce_float(config["platform_boosts"].get(platform), 0.0)
    if platform_boost:
        score_adjustment += platform_boost
        matched_boosts.append(f"platform:{platform}")

    lane_boost = 0.0
    lane_match: str | None = None
    for lane in lanes:
        current = _coerce_float(config["lane_boosts"].get(lane), 0.0)
        if current > lane_boost:
            lane_boost = current
            lane_match = lane
    if lane_boost and lane_match:
        score_adjustment += lane_boost
        matched_boosts.append(f"lane:{lane_match}")

    for phrase, weight in config["keyword_boosts"]:
        if phrase and phrase in text_blob:
            applied = weight if weight else 6.0
            score_adjustment += applied
            matched_boosts.append(f"keyword:{phrase}")

    for phrase in config["legacy_prioritize"]:
        if phrase and phrase in text_blob:
            score_adjustment += 4.0
            matched_boosts.append(f"priority:{phrase}")

    for phrase, weight in config["demoted_phrases"]:
        if phrase and phrase in text_blob:
            applied = weight if weight else 8.0
            score_adjustment -= applied
            matched_penalties.append(f"demote:{phrase}")

    for phrase in config["legacy_avoid"]:
        if phrase and phrase in text_blob:
            score_adjustment -= 12.0
            matched_penalties.append(f"avoid:{phrase}")

    for phrase in config["blocked_phrases"]:
        if phrase and phrase in text_blob:
            blocked_by.append(phrase)

    curated_total = round(base_total + score_adjustment, 1)
    keep = not blocked_by and curated_total >= _coerce_float(config["min_total_score"], 0.0)

    return {
        "keep": keep,
        "base_total": round(base_total, 1),
        "curated_total": curated_total,
        "score_adjustment": round(score_adjustment, 1),
        "blocked_by": blocked_by,
        "matched_boosts": matched_boosts,
        "matched_penalties": matched_penalties,
        "platform": platform,
    }


def _apply_feed_curation(items: list[dict[str, Any]], watchlist: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = _curation_config(watchlist)
    evaluated: list[dict[str, Any]] = []
    rejected_count = 0
    rejected_titles: list[str] = []

    for item in items:
        curated_item = dict(item)
        ranking = dict(curated_item.get("ranking") or {})
        curation = _evaluate_curation(curated_item, config)
        curated_item["curation"] = curation
        ranking["base_total"] = curation["base_total"]
        ranking["curation"] = curation["score_adjustment"]
        ranking["total"] = curation["curated_total"]
        curated_item["ranking"] = ranking
        if not curation["keep"]:
            rejected_count += 1
            title = _clean_text(curated_item.get("title") or "")
            if title:
                rejected_titles.append(title)
            continue
        evaluated.append(curated_item)

    evaluated.sort(key=lambda item: _coerce_float((item.get("ranking") or {}).get("total"), 0.0), reverse=True)

    platform_limits = {key: value for key, value in config["platform_limits"].items() if value > 0}
    selected: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    target_size = max(1, config["target_feed_size"])

    for item in evaluated:
        platform = _platform_key(item)
        limit = platform_limits.get(platform)
        current = counts.get(platform, 0)
        if limit is not None and current >= limit:
            overflow.append(item)
            continue
        selected.append(item)
        counts[platform] = current + 1

    if len(selected) < target_size:
        for item in overflow:
            selected.append(item)
            if len(selected) >= target_size:
                break

    selected = selected[:target_size]
    selected_counts: dict[str, int] = {}
    for item in selected:
        platform = _platform_key(item)
        selected_counts[platform] = selected_counts.get(platform, 0) + 1

    summary = {
        "target_feed_size": target_size,
        "min_total_score": config["min_total_score"],
        "platform_limits": platform_limits,
        "selected_count": len(selected),
        "rejected_count": rejected_count + max(0, len(evaluated) - len(selected)),
        "selected_platform_mix": selected_counts,
        "rejected_titles": rejected_titles[:8],
    }
    return selected, summary


def _ensure_source_contract(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    source_metadata = dict(enriched.get("source_metadata") or {})
    source_channel = _clean_text(enriched.get("platform") or source_metadata.get("source_channel") or "manual")
    source_type = _clean_text(enriched.get("source_type") or source_metadata.get("source_type") or "post")
    capture_method = _clean_text(enriched.get("capture_method") or source_metadata.get("capture_method") or "saved_signal")
    extraction_method = _clean_text(source_metadata.get("extraction_method") or capture_method or "saved_signal")
    raw_text = "\n\n".join(
        part
        for part in [
            _clean_text(enriched.get("core_claim")),
            _clean_text(enriched.get("summary")),
            "\n".join(_list_strings(enriched.get("standout_lines"), 2)),
        ]
        if part
    )
    source_class = normalize_source_class(enriched.get("source_class")) or infer_source_class(
        source_channel=source_channel,
        source_type=source_type,
        capture_method=capture_method,
        extraction_method=extraction_method,
    )
    unit_kind = normalize_unit_kind(enriched.get("unit_kind")) or infer_unit_kind(
        source_class=source_class,
        source_type=source_type,
        capture_method=capture_method,
        raw_text=raw_text,
    )
    response_modes = normalize_response_modes(enriched.get("response_modes")) or infer_response_modes(
        source_class=source_class,
        unit_kind=unit_kind,
    )
    source_metadata.setdefault("extraction_method", extraction_method)
    source_metadata["source_class"] = source_class
    source_metadata["unit_kind"] = unit_kind
    source_metadata["response_modes"] = response_modes
    enriched["source_type"] = source_type
    enriched["source_class"] = source_class
    enriched["unit_kind"] = unit_kind
    enriched["response_modes"] = response_modes
    enriched["source_metadata"] = source_metadata
    return enriched


def _preserve_existing_real_items(items: list[dict[str, Any]], *feeds: dict[str, Any] | None) -> list[dict[str, Any]]:
    merged = list(items)
    seen = {_item_fingerprint(item) for item in merged}
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        for item in feed.get("items") or []:
            if not isinstance(item, dict):
                continue
            fingerprint = _item_fingerprint(item)
            if fingerprint in seen:
                continue
            merged.append(_ensure_source_contract(item))
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
        "source_type": normalized.get("source_type", "post"),
        "source_class": normalized.get("source_class", "short_form"),
        "unit_kind": normalized.get("unit_kind", "full_post"),
        "response_modes": normalized.get("response_modes", []),
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
    alternate_feeds = _load_alternate_feeds(resolved_root)
    if signals:
        items = [_normalize_signal(signal, watchlist) for signal in signals]
        items = _preserve_existing_real_items(items, existing_feed, persisted_feed, *alternate_feeds)
    elif existing_feed:
        items = [_ensure_source_contract(item) for item in existing_feed.get("items") or [] if isinstance(item, dict)]
    else:
        fallback_feed = next((feed for feed in alternate_feeds if feed), None) or persisted_feed
        if fallback_feed:
            items = [_ensure_source_contract(item) for item in fallback_feed.get("items") or [] if isinstance(item, dict)]
        else:
            items = []

    if not items:
        if existing_feed:
            return existing_feed
        for alternate_feed in alternate_feeds:
            if alternate_feed:
                return alternate_feed
        if persisted_feed:
            return persisted_feed

    items, curation_summary = _apply_feed_curation(items, watchlist)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": "linkedin-content-os",
        "strategy_mode": "production",
        "curation_summary": curation_summary,
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
    curation_summary = feed.get("curation_summary") or {}
    if curation_summary:
        lines.extend(
            [
                "## Curation",
                f"- target size: {curation_summary.get('target_feed_size', '-')}",
                f"- selected count: {curation_summary.get('selected_count', '-')}",
                f"- rejected count: {curation_summary.get('rejected_count', '-')}",
                "",
            ]
        )
    for item in feed.get("items", []):
        lines.append(f"- {item['platform']} · {item['title']} ({item['author']})")
        if item.get("source_url"):
            lines.append(f"  - {item['source_url']}")
        lines.append(f"  - score: {item['ranking']['total']:.1f}")
        curation = item.get("curation") or {}
        if curation.get("score_adjustment"):
            lines.append(f"  - curation: {curation['score_adjustment']:+.1f}")
    md_path.write_text("\n".join(lines), encoding="utf-8")
