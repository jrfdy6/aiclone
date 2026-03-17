#!/usr/bin/env python3
"""Print OpenClaw compaction guardrail settings in a machine-friendly format."""
import json
import pathlib
import sys
from typing import Any

CONFIG_PATH = pathlib.Path.home() / ".openclaw" / "openclaw.json"
MIN_RESERVE = 40000
MIN_SOFT = 4000

def read_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except FileNotFoundError:
        sys.stderr.write(f"Config not found: {CONFIG_PATH}\n")
        sys.exit(2)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Invalid JSON in {CONFIG_PATH}: {exc}\n")
        sys.exit(3)
    return data

def main() -> None:
    data = read_config()
    compaction = (
        data.get("agents", {})
        .get("defaults", {})
        .get("compaction", {})
    )
    reserve = compaction.get("reserveTokensFloor")
    flush = compaction.get("memoryFlush", {})
    soft = flush.get("softThresholdTokens")
    enabled = flush.get("enabled")

    status = []
    if isinstance(reserve, (int, float)) and reserve >= MIN_RESERVE:
        status.append("reserveTokensFloor=OK")
    else:
        status.append("reserveTokensFloor=OUT_OF_RANGE")
    if isinstance(soft, (int, float)) and soft >= MIN_SOFT:
        status.append("softThresholdTokens=OK")
    else:
        status.append("softThresholdTokens=OUT_OF_RANGE")
    status.append(f"flush={'ON' if enabled else 'OFF'}")

    print("Compaction Guardrail Summary")
    print(f"  reserveTokensFloor: {reserve}")
    print(f"  softThresholdTokens: {soft}")
    print(f"  flush.enabled: {enabled}")
    print(f"  status: {', '.join(status)}")

if __name__ == "__main__":
    main()
