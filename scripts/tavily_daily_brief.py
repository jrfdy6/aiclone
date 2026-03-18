#!/usr/bin/env python3
"""Fetch Tavily search results for daily brief topics without external deps."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from urllib import request

BASE_DIR = Path(__file__).resolve().parent
PERSONAL_BRAND_DIR = BASE_DIR / "personal-brand"
CONFIG_PATH = Path(os.environ.get(
    "TAVILY_SOURCES_PATH",
    PERSONAL_BRAND_DIR / "configs" / "daily_brief_sources.json"
))

if PERSONAL_BRAND_DIR.exists():
    sys.path.append(str(PERSONAL_BRAND_DIR / "lib"))  # for quota helper
try:
    import quota  # type: ignore
except Exception:  # pragma: no cover
    quota = None

DEFAULT_QUERIES = [
    {
        "id": "macro",
        "label": "Macro AI scare trade",
        "query": "AI scare trade market update",
        "platform": "news",
        "angle": "systems risk",
        "max_calls_per_day": 3,
        "enabled": True,
    }
]

TAVILY_ENDPOINT = "https://api.tavily.com/search"


def load_api_key() -> str | None:
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key
    key_path = Path.home() / ".openclaw" / "secrets" / "tavily.key"
    if key_path.exists():
        return key_path.read_text().strip()
    return None


def load_sources() -> List[Dict[str, Any]]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return DEFAULT_QUERIES


def fetch(query: str, api_key: str, max_results: int = 5, timeout: int = 30) -> dict:
    payload = json.dumps({"api_key": api_key, "query": query, "max_results": max_results}).encode()
    req = request.Request(TAVILY_ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
        return json.loads(body)


def allowed_to_call(bucket: Dict[str, Any]) -> bool:
    if not quota:
        return True
    max_calls = bucket.get("max_calls_per_day", 1)
    bucket_id = bucket.get("id", "default")
    if not quota.can_call_bucket(bucket_id, max_calls):
        return False
    allowed, _ = quota.can_call()
    return allowed


def record_call(bucket_id: str) -> None:
    if quota:
        quota.record_call(bucket_id)


def main(args: List[str]) -> None:
    api_key = load_api_key()
    if not api_key:
        sys.stderr.write("TAVILY_API_KEY is missing. Set the env var or ~/.openclaw/secrets/tavily.key.\n")
        sys.exit(1)

    sources = load_sources()
    manual_queries = args or None
    results = []

    if manual_queries:
        buckets = [{"id": f"manual_{i}", "query": q, "label": q, "platform": "manual", "angle": "", "enabled": True, "max_calls_per_day": 999} for i, q in enumerate(manual_queries)]
    else:
        buckets = [s for s in sources if s.get("enabled", True)]

    for bucket in buckets:
        query = bucket.get("query")
        if not query:
            continue
        bucket_id = bucket.get("id", query)
        if not manual_queries and not allowed_to_call(bucket):
            continue
        try:
            data = fetch(query, api_key)
        except Exception as exc:  # pragma: no cover
            sys.stderr.write(f"Tavily request failed for {bucket_id}: {exc}\n")
            continue
        record_call(bucket_id)
        hits = data.get("results", [])
        summary = {
            "id": bucket_id,
            "label": bucket.get("label", bucket_id),
            "platform": bucket.get("platform", "news"),
            "angle": bucket.get("angle", ""),
            "query": query,
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("content") or item.get("snippet"),
                }
                for item in hits[:3]
            ],
        }
        results.append(summary)

    print(json.dumps({"queries": results}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
