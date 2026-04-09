#!/usr/bin/env python3
"""Load durable markdown memory relevant to a workspace and recent signal."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
KNOWLEDGE_ROOT = WORKSPACE_ROOT / "knowledge"
WORKSPACES_ROOT = WORKSPACE_ROOT / "workspaces"
QMD_CONFIG_HOME = Path("/Users/neo/.openclaw/agents/main/qmd/xdg-config")
QMD_CACHE_HOME = Path("/Users/neo/.openclaw/agents/main/qmd/xdg-cache")

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
    "shared_ops": ["OpenClaw", "Codex", "shared ops", "canonical memory", "PM board"],
    "shared-ops": ["OpenClaw", "Codex", "shared ops", "canonical memory", "PM board"],
    "linkedin-os": ["linkedin-os", "linkedin content", "FEEZIE", "FEEZIE OS"],
    "fusion-os": ["fusion-os", "Fusion OS", "delegated execution", "workspace execution"],
    "easyoutfitapp": ["easyoutfitapp", "EasyOutfitApp"],
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


def _workspace_rel_path(collection: str, rel_path: str) -> str:
    if collection == "memory-dir-main":
        return f"memory/{rel_path}".replace("//", "/")
    if collection == "knowledge-main":
        return f"knowledge/{rel_path}".replace("//", "/")
    return rel_path


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


def _qmd_env() -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(QMD_CONFIG_HOME)
    env["XDG_CACHE_HOME"] = str(QMD_CACHE_HOME)
    return env


def _parse_qmd_results(raw: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lines = raw.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("qmd://"):
            idx += 1
            continue
        match = re.match(r"^qmd://([^/]+)/(.+?):(\d+)\s+#([a-f0-9]+)$", line)
        if not match:
            idx += 1
            continue
        collection, rel_path, line_number, block_hash = match.groups()
        title = ""
        score = None
        excerpt_lines: list[str] = []
        idx += 1
        while idx < len(lines):
            current = lines[idx]
            stripped = current.strip()
            if stripped.startswith("qmd://"):
                break
            if stripped.startswith("Title:"):
                title = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Score:"):
                score = stripped.split(":", 1)[1].strip()
            elif stripped and not stripped.startswith("@@"):
                excerpt_lines.append(stripped)
            idx += 1
        results.append(
            {
                "collection": collection,
                "relative_path": rel_path,
                "path": _workspace_rel_path(collection, rel_path),
                "title": title or Path(rel_path).stem,
                "score": score,
                "line_number": int(line_number),
                "hash": block_hash,
                "excerpt": _normalize_whitespace(" ".join(excerpt_lines[:6])),
                "source": "qmd",
            }
        )
    return results


def _run_qmd_search(query: str, collection: str, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    command = ["qmd", "search", query, "-c", collection, "-n", str(limit)]
    last_error = None
    for _ in range(3):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=_qmd_env(),
        )
        if result.returncode == 0:
            return _parse_qmd_results(result.stdout), None
        last_error = (result.stderr or result.stdout or "qmd search failed").strip()
        if "database is locked" not in last_error.lower():
            break
    return [], last_error


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
        per_query: list[dict[str, Any]] = []
        for collection in ("memory-dir-main", "knowledge-main"):
            qmd_results, error = _run_qmd_search(query, collection, limit=2)
            per_query.extend(qmd_results)
            if error and error not in warnings:
                warnings.append(error)
        # Workspace research is durable for strategy/content, but it is not in the current QMD collections.
        per_query.extend(
            _scan_markdown_tree(
                WORKSPACES_ROOT,
                "workspaces",
                query,
                limit=2,
            )
        )
        for item in per_query:
            item["query"] = query
        collected.extend(per_query)
        if len(_dedupe_results(collected, max_results)) >= max_results:
            break

    results = _dedupe_results(collected, max_results)
    return {
        "available": bool(results),
        "workspace_key": workspace_key,
        "queries": queries,
        "result_count": len(results),
        "results": results,
        "source_paths": [str(WORKSPACE_ROOT / item["path"]) for item in results],
        "warnings": warnings,
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
