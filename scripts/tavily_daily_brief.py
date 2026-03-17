#!/usr/bin/env python3
"""Fetch Tavily search results for daily brief topics without external deps."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List
from urllib import request

DEFAULT_QUERIES = [
    "AI scare trade market update",
    "Railway platform status update",
    "memory architecture best practices agents"
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


def fetch(query: str, api_key: str, max_results: int = 5, timeout: int = 30) -> dict:
    payload = json.dumps({"api_key": api_key, "query": query, "max_results": max_results}).encode()
    req = request.Request(TAVILY_ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
        return json.loads(body)


def main(args: List[str]) -> None:
    api_key = load_api_key()
    if not api_key:
        sys.stderr.write("TAVILY_API_KEY is missing. Set the env var or ~/.openclaw/secrets/tavily.key.\n")
        sys.exit(1)

    queries = args or DEFAULT_QUERIES
    results = []
    for query in queries:
        data = fetch(query, api_key)
        hits = data.get("results", [])
        summary = {
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
