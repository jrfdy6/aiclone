#!/usr/bin/env python3
"""Tavily quota helper for the personal-brand workspace."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

USAGE_PATH = Path(__file__).resolve().parent.parent / "usage" / "tavily_usage.json"
DATE_FMT = "%Y-%m-%d"


def _load_usage() -> dict:
    if not USAGE_PATH.exists():
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        default = {
            "monthly_limit": 900,
            "month_start": None,
            "calls_made": 0,
            "daily": {},
            "history": []
        }
        _save_usage(default)
        return default
    return json.loads(USAGE_PATH.read_text())


def _save_usage(data: dict) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    USAGE_PATH.write_text(json.dumps(data, indent=2))


def _current_month_start() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date().isoformat()


def _reset_if_needed(data: dict) -> dict:
    month_start = _current_month_start()
    if data.get("month_start") != month_start:
        data["month_start"] = month_start
        data["calls_made"] = 0
        data["daily"] = {}
        data.setdefault("history", [])
        _save_usage(data)
    return data


def can_call(calls: int = 1) -> Tuple[bool, dict]:
    data = _reset_if_needed(_load_usage())
    if data.get("calls_made", 0) + calls > data.get("monthly_limit", 900):
        return False, data
    return True, data


def can_call_bucket(bucket_id: str, max_calls_per_day: int) -> bool:
    data = _reset_if_needed(_load_usage())
    today = datetime.now(timezone.utc).date().isoformat()
    bucket_counts = data.setdefault("daily", {}).setdefault(today, {})
    return bucket_counts.get(bucket_id, 0) < max_calls_per_day


def record_call(bucket_id: str, calls: int = 1) -> None:
    allowed, data = can_call(calls)
    if not allowed:
        raise RuntimeError("Tavily monthly quota exceeded")
    today = datetime.now(timezone.utc).date().isoformat()
    bucket_counts = data.setdefault("daily", {}).setdefault(today, {})
    bucket_counts[bucket_id] = bucket_counts.get(bucket_id, 0) + calls
    data["calls_made"] = data.get("calls_made", 0) + calls
    data.setdefault("history", []).append({
        "bucket": bucket_id,
        "calls": calls,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    _save_usage(data)


def remaining_monthly_calls() -> int:
    data = _reset_if_needed(_load_usage())
    return max(0, data.get("monthly_limit", 900) - data.get("calls_made", 0))


def get_daily_usage() -> dict:
    data = _reset_if_needed(_load_usage())
    today = datetime.now(timezone.utc).date().isoformat()
    return data.get("daily", {}).get(today, {})
