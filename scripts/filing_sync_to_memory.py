#!/usr/bin/env python3
"""Ingest filing-system files into today's OpenClaw memory log."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


VALID_SUFFIXES = {".md", ".txt", ".py", ".json", ".sh", ".log"}
DEFAULT_WINDOW_DAYS = 7


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"last_run": None, "files": {}}
    return json.loads(state_path.read_text())


def save_state(state_path: Path, state: dict) -> None:
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def summarize(path: Path, max_lines: int = 2, max_chars: int = 200) -> str:
    try:
        lines = []
        with path.open("r", errors="ignore") as reader:
            for raw in reader:
                text = raw.strip()
                if text:
                    lines.append(text)
                if len(lines) >= max_lines:
                    break
        preview = " — ".join(lines)
        return preview[:max_chars] if preview else "(no preview)"
    except Exception:
        return "(unreadable preview)"


def resolve_sources(workspace: Path) -> list[Path]:
    env_paths = os.getenv("FILING_SYNC_PATHS")
    if env_paths:
        sources = []
        for fragment in env_paths.split(os.pathsep):
            candidate = Path(fragment)
            if not candidate.is_absolute():
                candidate = workspace / fragment
            sources.append(candidate)
        return sources
    return [workspace / "downloads" / "aiclone"]


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    mem_dir = workspace / "memory"
    mem_dir.mkdir(exist_ok=True)

    state_path = mem_dir / "filing_sync_state.json"
    state = load_state(state_path)
    last_run_iso = state.get("last_run")
    now = datetime.now()
    window_days = int(os.getenv("FILING_SYNC_DAYS", DEFAULT_WINDOW_DAYS))

    since = datetime.fromisoformat(last_run_iso) if last_run_iso else now - timedelta(days=window_days)

    sources = resolve_sources(workspace)
    recorded = state.setdefault("files", {})
    entries = []

    for source in sources:
        if not source.exists():
            continue
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in VALID_SUFFIXES:
                continue
            mod_time = datetime.fromtimestamp(path.stat().st_mtime)
            if mod_time <= since:
                continue
            key = str(path.resolve())
            prev_ts = recorded.get(key)
            if prev_ts and mod_time <= datetime.fromtimestamp(prev_ts):
                continue
            entries.append((mod_time, path.relative_to(workspace), summarize(path)))
            recorded[key] = mod_time.timestamp()

    today_file = mem_dir / f"{now.date().isoformat()}.md"
    if not today_file.exists():
        today_file.write_text(f"# Daily memory log — {now.date().isoformat()}\n")

    if entries:
        with today_file.open("a") as fout:
            fout.write(f"\n## Filing sync — {now.isoformat()}\n")
            for mod_time, rel_path, summary_text in entries:
                fout.write(f"- {mod_time.isoformat()} | {rel_path.as_posix()} — {summary_text}\n")
        print(f"Appended {len(entries)} filing entries to {today_file.name}.")
    else:
        print("No new filing entries since the last sync.")

    state["last_run"] = now.isoformat()
    save_state(state_path, state)


if __name__ == "__main__":
    main()
