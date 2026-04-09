#!/usr/bin/env python3
"""Archive excess Fusion OS dispatch packets once a card has fresh packets."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


@dataclass
class Packet:
    path: Path
    timestamp: datetime
    kind: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Move old dispatch packets into an archive folder so the active "
            "workspace lane keeps only the latest artifacts per card."
        )
    )
    parser.add_argument(
        "--dispatch-dir",
        type=Path,
        default=Path("workspaces/fusion-os/dispatch"),
        help="Path to the dispatch directory (default: workspaces/fusion-os/dispatch)",
    )
    parser.add_argument(
        "--card-id",
        help="If provided, archive packets only for this PM card ID.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=2,
        help="Number of newest packets per card/kind combination to keep active (default: 2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be moved without touching the filesystem.",
    )
    return parser.parse_args()


def iter_packets(dispatch_dir: Path, card_filter: str | None) -> Dict[Tuple[str, str], List[Packet]]:
    groups: Dict[Tuple[str, str], List[Packet]] = defaultdict(list)
    for path in sorted(dispatch_dir.glob("*.json")):
        if not path.is_file():
            continue
        name = path.name
        if "_" not in name:
            continue
        timestamp_str, suffix = name.split("_", 1)
        try:
            timestamp = datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
        except ValueError:
            # Skip files that do not use the timestamped dispatch naming pattern.
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError:
            continue
        card_id = payload.get("card_id") or payload.get("pm_card_id")
        if not card_id:
            continue
        if card_filter and card_id != card_filter:
            continue
        groups[(card_id, suffix)].append(Packet(path=path, timestamp=timestamp, kind=suffix))
    return groups


def archive_packets(groups: Dict[Tuple[str, str], List[Packet]], keep: int, dispatch_dir: Path, dry_run: bool) -> int:
    archive_root = dispatch_dir / "archive"
    moved = 0
    for (card_id, kind), packets in sorted(groups.items()):
        packets.sort(key=lambda pkt: pkt.timestamp)
        if len(packets) <= keep:
            continue
        to_archive = packets[:-keep]
        safe_kind = Path(kind).stem or "misc"
        dest_dir = archive_root / card_id / safe_kind
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
        for pkt in to_archive:
            dest_path = dest_dir / pkt.path.name
            action = f"mv {pkt.path} -> {dest_path}"
            print(action)
            if not dry_run:
                shutil.move(str(pkt.path), dest_path)
            moved += 1
    return moved


def main() -> None:
    args = parse_args()
    dispatch_dir = args.dispatch_dir.expanduser().resolve()
    if not dispatch_dir.exists():
        raise SystemExit(f"Dispatch directory not found: {dispatch_dir}")
    groups = iter_packets(dispatch_dir, args.card_id)
    if not groups:
        print("No matching packets found.")
        return
    moved = archive_packets(groups, max(args.keep, 0), dispatch_dir, args.dry_run)
    if moved == 0:
        print("Nothing to archive; existing packets already within retention window.")
    else:
        verb = "would move" if args.dry_run else "moved"
        print(f"{verb} {moved} packet(s).")


if __name__ == "__main__":
    main()
