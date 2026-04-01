#!/usr/bin/env python3
"""Check the local OpenClaw runtime override contract."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

CONFIG_PATH = pathlib.Path.home() / ".openclaw" / "openclaw.json"
MIN_RESERVE = 40000
MIN_SOFT = 4000


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except FileNotFoundError:
        sys.stderr.write(f"Config not found: {CONFIG_PATH}\n")
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Invalid JSON in {CONFIG_PATH}: {exc}\n")
        raise SystemExit(3)


def build_summary() -> dict:
    data = load_config()
    compaction = data.get("agents", {}).get("defaults", {}).get("compaction", {})
    flush = compaction.get("memoryFlush", {})
    reserve = compaction.get("reserveTokensFloor")
    soft = flush.get("softThresholdTokens")
    enabled = flush.get("enabled")

    summary = {
        "config_path": str(CONFIG_PATH),
        "reserveTokensFloor": reserve,
        "softThresholdTokens": soft,
        "flush_enabled": enabled,
        "reserve_ok": isinstance(reserve, (int, float)) and reserve >= MIN_RESERVE,
        "soft_ok": isinstance(soft, (int, float)) and soft >= MIN_SOFT,
        "flush_ok": enabled is True,
    }
    summary["status"] = "OK" if all(
        (summary["reserve_ok"], summary["soft_ok"], summary["flush_ok"])
    ) else "WARN"
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local OpenClaw runtime overrides.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text")
    args = parser.parse_args()

    summary = build_summary()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("Local Runtime Overrides")
        print(f"  config_path: {summary['config_path']}")
        print(f"  reserveTokensFloor: {summary['reserveTokensFloor']}")
        print(f"  softThresholdTokens: {summary['softThresholdTokens']}")
        print(f"  flush.enabled: {summary['flush_enabled']}")
        print(
            "  status: "
            f"reserve={'OK' if summary['reserve_ok'] else 'WARN'}, "
            f"soft={'OK' if summary['soft_ok'] else 'WARN'}, "
            f"flush={'OK' if summary['flush_ok'] else 'WARN'}"
        )
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
