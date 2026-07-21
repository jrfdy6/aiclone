#!/usr/bin/env python3
"""Load durable markdown memory relevant to a workspace and recent signal."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from codex_memory_index import search_index
from runtime_paths import PROJECT_ROOT

WORKSPACE_ROOT = PROJECT_ROOT
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
KNOWLEDGE_ROOT = WORKSPACE_ROOT / "knowledge"
WORKSPACES_ROOT = WORKSPACE_ROOT / "workspaces"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "its",
    "need",
    "now",
    "of",
    "on",
    "or",
    "the",
    "their",
    "this",
    "to",
    "was",
    "with",
}

WORKSPACE_HINTS = {
    "shared_ops": ["AI Clone", "Codex", "shared ops", "canonical memory", "PM board"],
    "shared-ops": ["AI Clone", "Codex", "shared ops", "canonical memory", "PM board"],
    "linkedin-os": ["linkedin-os", "linkedin content", "FEEZIE", "FEEZIE OS"],
    "fusion-os": ["fusion-os", "Fusion OS", "delegated execution", "workspace execution"],
    "easyoutfitapp": ["easyoutfitapp", "Easy Outfit App", "EasyOutfitApp"],
    "ai-swag-store": ["ai-swag-store", "AI Swag Store"],
    "agc": ["agc"],
}

EXCLUDED_MEMORY_PREFIXES = (
    "memory/standup-prep/",
    "memory/runner-memos/",
    "memory/runner-results/",
    "memory/runner-inputs/",
    "memory/runner-recommendations/",
)


def _normalize_whitespace(value: str) -> str:
    return " ".join(str(value or "").replace("\u2014", "-").split()).strip()


def _condense_query(value: str) -> str:
    text = _normalize_whitespace(value)
    if not text:
        return ""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text)
    cleaned: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in STOPWORDS:
            continue
        if len(token) < 3 and not token.isupper():
            continue
        cleaned.append(token)
        if len(cleaned) >= 6:
            break
    if not cleaned:
        cleaned = tokens[:6]
    return " ".join(cleaned).strip()


def _unique_queries(workspace_key: str, raw_queries: Iterable[str]) -> list[str]:
    candidates = list(WORKSPACE_HINTS.get(workspace_key, [])) + list(raw_queries)
    seen: set[str] = set()
    normalized: list[str] = []
    for candidate in candidates:
        query = _condense_query(candidate)
        key = query.lower()
        if not query or key in seen:
            continue
        seen.add(key)
        normalized.append(query)
    return normalized[:8]


def _is_durable_result(path_str: str) -> bool:
    rel = path_str.replace("\\", "/").lstrip("/")
    if rel.startswith("knowledge/"):
        return True
    if rel.startswith("workspaces/") and "/research/" in rel:
        return True
    if not rel.startswith("memory/"):
        return False
    if rel.startswith(EXCLUDED_MEMORY_PREFIXES):
        return False
    if rel.startswith("memory/reports/"):
        name = Path(rel).name.lower()
        if "latest" in name or "verification" in name:
            return False
    return True


def _run_codex_index_search(query: str, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    try:
        raw_results = search_index(query, limit=limit)
    except Exception as exc:  # pragma: no cover - fallback is deliberately broad
        return [], f"Codex memory index search failed: {exc}"
    results: list[dict[str, Any]] = []
    for item in raw_results:
        path = str(item.get("path") or "")
        if not _is_durable_result(path):
            continue
        path_parts = Path(path).parts
        collection = path_parts[0] if path_parts else "project"
        results.append(
            {
                "collection": collection,
                "relative_path": "/".join(path_parts[1:]) if len(path_parts) > 1 else path,
                "path": path,
                "title": str(item.get("title") or Path(path).stem),
                "score": item.get("score"),
                "line_number": None,
                "hash": None,
                "excerpt": _normalize_whitespace(str(item.get("excerpt") or "")),
                "source": "codex_memory_index",
            }
        )
    return results, None


def _extract_title_from_markdown(text: str, path: Path) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem.replace("_", " ")


def _scan_markdown_tree(root: Path, rel_prefix: str, query: str, limit: int) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    lowered_query = query.lower()
    hits: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        rel_path = f"{rel_prefix}/{path.relative_to(root).as_posix()}"
        if not _is_durable_result(rel_path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        idx = lowered.find(lowered_query)
        if idx == -1:
            continue
        excerpt = _normalize_whitespace(text[max(0, idx - 120) : idx + 260])
        hits.append(
            {
                "collection": rel_prefix,
                "relative_path": path.relative_to(root).as_posix(),
                "path": rel_path,
                "title": _extract_title_from_markdown(text, path),
                "score": None,
                "line_number": None,
                "hash": None,
                "excerpt": excerpt,
                "source": "filesystem",
            }
        )
        if len(hits) >= limit:
            break
    return hits


def _dedupe_results(results: Iterable[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in results:
        path = str(item.get("path") or "")
        excerpt = str(item.get("excerpt") or "")
        key = (path, excerpt[:160])
        if not path or key in seen or not _is_durable_result(path):
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max_results:
            break
    return deduped


def build_durable_memory_context(
    workspace_key: str,
    raw_queries: Iterable[str],
    *,
    max_results: int = 6,
) -> dict[str, Any]:
    queries = _unique_queries(workspace_key, raw_queries)
    warnings: list[str] = []
    collected: list[dict[str, Any]] = []

    for query in queries:
        per_query, error = _run_codex_index_search(query, limit=4)
        if error and error not in warnings:
            warnings.append(error)
        if not per_query:
            for root, prefix in (
                (MEMORY_ROOT, "memory"),
                (KNOWLEDGE_ROOT, "knowledge"),
                (WORKSPACES_ROOT, "workspaces"),
            ):
                per_query.extend(_scan_markdown_tree(root, prefix, query, limit=2))
        for item in per_query:
            item["query"] = query
        collected.extend(per_query)
        if len(_dedupe_results(collected, max_results)) >= max_results:
            break

    results = _dedupe_results(collected, max_results)
    index_result_count = sum(1 for item in results if item.get("source") == "codex_memory_index")
    filesystem_result_count = sum(1 for item in results if item.get("source") == "filesystem")
    fallback_reasons: list[str] = []
    if warnings:
        fallback_reasons.append("codex_memory_index_warning")
    if filesystem_result_count:
        fallback_reasons.append("filesystem_scan")
    if warnings and filesystem_result_count:
        retrieval_mode = "codex_index_warning+filesystem_fallback"
    elif warnings and index_result_count:
        retrieval_mode = "codex_index_warning"
    elif warnings:
        retrieval_mode = "warning_only"
    elif filesystem_result_count and index_result_count:
        retrieval_mode = "codex_index+filesystem_fallback"
    elif filesystem_result_count:
        retrieval_mode = "filesystem_fallback"
    elif index_result_count:
        retrieval_mode = "codex_index_only"
    else:
        retrieval_mode = "empty"
    return {
        "available": bool(results),
        "workspace_key": workspace_key,
        "queries": queries,
        "result_count": len(results),
        "results": results,
        "source_paths": [str(WORKSPACE_ROOT / item["path"]) for item in results],
        "warnings": warnings,
        "index_result_count": index_result_count,
        "memory_index_result_count": index_result_count,
        "filesystem_result_count": filesystem_result_count,
        "retrieval_mode": retrieval_mode,
        "fallback_active": bool(fallback_reasons),
        "fallback_reasons": fallback_reasons,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--max-results", type=int, default=6)
    args = parser.parse_args()
    payload = build_durable_memory_context(args.workspace_key, args.query, max_results=args.max_results)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
