#!/usr/bin/env python3
"""Update the OpenClaw heartbeat model to a reachable provider."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CONFIG = Path("~/.openclaw/openclaw.json").expanduser()
DEFAULT_MODEL = "openai/gpt-4o-mini"


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return json.loads(path.read_text())


def _ensure_model_entry(models: dict, model: str) -> None:
    if model in models:
        return
    alias = model.split("/")[-1]
    models[model] = {"alias": alias}


def _update_model(data: dict, model: str) -> str | None:
    agents = data.setdefault("agents", {})
    defaults = agents.setdefault("defaults", {})
    heartbeat = defaults.setdefault("heartbeat", {})
    previous = heartbeat.get("model")
    heartbeat["model"] = model

    # Keep the friendly alias map populated so UI prompts render cleanly.
    model_map = defaults.setdefault("models", {})
    _ensure_model_entry(model_map, model)
    return previous


def _touch_meta(data: dict) -> None:
    meta = data.setdefault("meta", {})
    meta["lastTouchedAt"] = datetime.now(tz=timezone.utc).isoformat()


def update_heartbeat_model(config_path: Path, model: str, *, keep_backup: bool = True) -> tuple[str | None, Path | None]:
    data = _load_config(config_path)
    previous = _update_model(data, model)
    _touch_meta(data)

    backup_path: Path | None = None
    if keep_backup:
        backup_suffix = ".bak"
        backup_path = config_path.with_suffix(config_path.suffix + backup_suffix)
        shutil.copy2(config_path, backup_path)

    config_path.write_text(json.dumps(data, indent=2) + "\n")
    return previous, backup_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to openclaw.json (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Heartbeat model identifier (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip writing a .bak copy of the original config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    previous, backup_path = update_heartbeat_model(
        config_path, args.model, keep_backup=not args.no_backup
    )

    print(f"Updated heartbeat model in {config_path}")
    if previous:
        print(f"- Previous model: {previous}")
    print(f"- New model: {args.model}")
    if backup_path:
        print(f"- Backup written to {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
