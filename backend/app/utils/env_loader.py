from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

parents = Path(__file__).resolve().parents
workspace_hint = parents[5] if len(parents) > 5 else parents[-1]

ENV_CANDIDATES = [
    workspace_hint / "secrets" / "railway.env",
]


def parse_env_file(path: Path) -> Iterable[tuple[str, str]]:
    for line in path.read_text().splitlines():
        if not line or line.strip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        raw = value.strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        decoded = bytes(raw, "utf-8").decode("unicode_escape") if raw else ""
        yield key.strip(), decoded


def load_env():
    for candidate in ENV_CANDIDATES:
        if candidate.exists():
            for key, value in parse_env_file(candidate):
                os.environ.setdefault(key, value)


load_env()
