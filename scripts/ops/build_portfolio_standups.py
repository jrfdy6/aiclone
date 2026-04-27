#!/usr/bin/env python3
"""Create and promote stale or missing portfolio standups."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from automation_run_mirror import build_run_payload, mirror_runs  # noqa: E402
from promote_standup_packet import _build_payload as build_promoted_standup_payload  # noqa: E402

DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
REPORT_PATH = WORKSPACE_ROOT / "memory/reports/portfolio_standup_prep_latest.json"
AUTOMATION_ID = "portfolio_standup_prep"
AUTOMATION_NAME = "Portfolio Standup Prep"


@dataclass(frozen=True)
class StandupTarget:
    workspace_key: str
    standup_kind: str
    max_age_hours: int
    owner_agent: str = "jean-claude"


TARGETS: tuple[StandupTarget, ...] = (
    StandupTarget("shared_ops", "executive_ops", 12),
    StandupTarget("shared_ops", "operations", 36),
    StandupTarget("shared_ops", "weekly_review", 8 * 24),
    StandupTarget("shared_ops", "saturday_vision", 8 * 24),
    StandupTarget("feezie-os", "workspace_sync", 36),
    StandupTarget("fusion-os", "workspace_sync", 72),
    StandupTarget("easyoutfitapp", "workspace_sync", 72),
    StandupTarget("ai-swag-store", "workspace_sync", 72),
    StandupTarget("agc", "workspace_sync", 72),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _standup_kind(entry: dict[str, Any]) -> str:
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    value = payload.get("standup_kind")
    if isinstance(value, str) and value.strip():
        return value.strip()
    workspace_key = entry.get("workspace_key")
    return workspace_key.strip() if isinstance(workspace_key, str) and workspace_key.strip() else "shared_ops"


def _latest_for(rows: list[dict[str, Any]], target: StandupTarget) -> dict[str, Any] | None:
    for entry in rows:
        if str(entry.get("workspace_key") or "shared_ops") == target.workspace_key and _standup_kind(entry) == target.standup_kind:
            return entry
    return None


def _needs_refresh(entry: dict[str, Any] | None, target: StandupTarget, now: datetime, *, force: bool) -> tuple[bool, str]:
    if force:
        return True, "force"
    if entry is None:
        return True, "missing"
    status = str(entry.get("status") or "").strip().lower()
    if status == "prepared":
        return True, "prepared_needs_promotion"
    if status != "completed":
        return True, "not_completed"
    created_at = _parse_datetime(entry.get("created_at"))
    if created_at is None:
        return True, "timestamp_missing"
    age = now - created_at
    if age > timedelta(hours=target.max_age_hours):
        return True, "stale"
    return False, "fresh"


def _load_recent_standups(api_url: str, limit: int) -> list[dict[str, Any]]:
    payload = _fetch_json(f"{api_url.rstrip('/')}/api/standups/?limit={limit}")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _prep_path_from_standup(entry: dict[str, Any] | None) -> Path | None:
    if not isinstance(entry, dict):
        return None
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    for key in ("prep_json_path", "json_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
    return None


def _promotion_payload_from_prep(prep: dict[str, Any]) -> dict[str, Any]:
    chronicle_entries = prep.get("chronicle_entries") or []
    chronicle_entry = chronicle_entries[-1] if chronicle_entries else None
    return build_promoted_standup_payload(
        prep,
        None,
        chronicle_entry if isinstance(chronicle_entry, dict) else None,
    )


def _summarize_promotion(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "created_standup_id": None,
            "created_card_count": 0,
            "existing_card_count": 0,
            "created_card_ids": [],
            "existing_card_ids": [],
        }
    standup = result.get("standup") if isinstance(result.get("standup"), dict) else {}
    created_cards = [item for item in (result.get("created_cards") or []) if isinstance(item, dict)]
    existing_cards = [item for item in (result.get("existing_cards") or []) if isinstance(item, dict)]
    return {
        "created_standup_id": standup.get("id"),
        "created_card_count": len(created_cards),
        "existing_card_count": len(existing_cards),
        "created_card_ids": [item.get("id") for item in created_cards if item.get("id")],
        "existing_card_ids": [item.get("id") for item in existing_cards if item.get("id")],
    }


def _promote_prep_path(api_url: str, prep_path: Path) -> dict[str, Any]:
    prep = _read_json(prep_path)
    payload = _promotion_payload_from_prep(prep)
    result = _post_json(f"{api_url.rstrip('/')}/api/standups/promote", payload)
    return _summarize_promotion(result)


def _promote_existing_prepared(
    target: StandupTarget,
    *,
    api_url: str,
    entry: dict[str, Any],
    prep_path: Path,
) -> dict[str, Any]:
    try:
        promotion = _promote_prep_path(api_url, prep_path)
        return {
            "workspace_key": target.workspace_key,
            "standup_kind": target.standup_kind,
            "status": "promoted",
            "returncode": 0,
            "prep_json_path": str(prep_path),
            "promoted_from_standup_id": entry.get("id"),
            "promotion_error": None,
            "create_error": None,
            "stdout_tail": "",
            "stderr_tail": "",
            **promotion,
        }
    except Exception as exc:
        return {
            "workspace_key": target.workspace_key,
            "standup_kind": target.standup_kind,
            "status": "failed",
            "returncode": 0,
            "prep_json_path": str(prep_path),
            "promoted_from_standup_id": entry.get("id"),
            "created_standup_id": None,
            "created_card_count": 0,
            "existing_card_count": 0,
            "created_card_ids": [],
            "existing_card_ids": [],
            "promotion_error": str(exc),
            "create_error": str(exc),
            "stdout_tail": "",
            "stderr_tail": "",
        }


def _run_builder(
    target: StandupTarget,
    *,
    api_url: str,
    chronicle_limit: int,
    create_entry: bool,
    promote_entry: bool,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(WORKSPACE_ROOT / "scripts/build_standup_prep.py"),
        "--workspace-key",
        target.workspace_key,
        "--standup-kind",
        target.standup_kind,
        "--owner-agent",
        target.owner_agent,
        "--chronicle-limit",
        str(chronicle_limit),
        "--api-url",
        api_url,
    ]
    result = subprocess.run(
        command,
        cwd=str(WORKSPACE_ROOT),
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    stdout = result.stdout or ""
    json_path = _json_path_from_stdout(stdout)
    created_entry: Any = None
    create_error: str | None = None
    promotion_error: str | None = None
    promotion: dict[str, Any] = {
        "created_standup_id": None,
        "created_card_count": 0,
        "existing_card_count": 0,
        "created_card_ids": [],
        "existing_card_ids": [],
    }
    if result.returncode == 0 and create_entry:
        if json_path is None:
            create_error = "standup prep JSON path was not found in builder stdout"
        else:
            try:
                if promote_entry:
                    promotion = _promote_prep_path(api_url, json_path)
                else:
                    prep = _read_json(json_path)
                    standup_payload = prep.get("standup_payload")
                    if not isinstance(standup_payload, dict):
                        raise ValueError("standup_payload missing from generated prep JSON")
                    created_entry = _post_json(f"{api_url.rstrip('/')}/api/standups/", standup_payload)
                    promotion["created_standup_id"] = created_entry.get("id") if isinstance(created_entry, dict) else None
            except Exception as exc:
                create_error = str(exc)
                if promote_entry:
                    promotion_error = str(exc)
    status = "failed" if result.returncode != 0 or create_error else ("promoted" if create_entry and promote_entry else ("created" if create_entry else "prepared"))
    return {
        "workspace_key": target.workspace_key,
        "standup_kind": target.standup_kind,
        "status": status,
        "returncode": result.returncode,
        "prep_json_path": str(json_path) if json_path else None,
        "promotion_error": promotion_error,
        "create_error": create_error,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": (result.stderr or "")[-1200:],
        **promotion,
    }


def _json_path_from_stdout(stdout: str) -> Path | None:
    for line in stdout.splitlines():
        if line.startswith("JSON: "):
            value = line.removeprefix("JSON: ").strip()
            return Path(value) if value else None
    return None


def build_portfolio_standups(
    *,
    api_url: str,
    limit: int,
    chronicle_limit: int,
    force: bool,
    create_entry: bool,
    promote_entry: bool = True,
    targets: tuple[StandupTarget, ...] = TARGETS,
) -> dict[str, Any]:
    now = _now()
    rows = _load_recent_standups(api_url, limit)
    results: list[dict[str, Any]] = []
    for target in targets:
        latest = _latest_for(rows, target)
        prep_path = _prep_path_from_standup(latest)
        if (
            create_entry
            and promote_entry
            and str((latest or {}).get("status") or "").strip().lower() == "prepared"
            and prep_path is not None
            and prep_path.exists()
        ):
            promoted = _promote_existing_prepared(target, api_url=api_url, entry=latest or {}, prep_path=prep_path)
            promoted["reason"] = "prepared_needs_promotion"
            results.append(promoted)
            continue

        should_run, reason = _needs_refresh(latest, target, now, force=force)
        if not should_run:
            results.append(
                {
                    "workspace_key": target.workspace_key,
                    "standup_kind": target.standup_kind,
                    "status": "skipped",
                    "reason": reason,
                    "latest_standup_id": latest.get("id") if latest else None,
                    "latest_created_at": latest.get("created_at") if latest else None,
                }
            )
            continue
        created = _run_builder(
            target,
            api_url=api_url,
            chronicle_limit=chronicle_limit,
            create_entry=create_entry,
            promote_entry=promote_entry,
        )
        created["reason"] = reason
        results.append(created)

    return {
        "schema_version": "portfolio_standup_prep/v1",
        "generated_at": _iso(now),
        "source": AUTOMATION_ID,
        "create_entry": create_entry,
        "promote_entry": promote_entry,
        "force": force,
        "counts": {
            "targets": len(results),
            "created": sum(1 for item in results if item.get("status") == "created"),
            "promoted": sum(1 for item in results if item.get("status") == "promoted"),
            "prepared": sum(1 for item in results if item.get("status") == "prepared"),
            "skipped": sum(1 for item in results if item.get("status") == "skipped"),
            "failed": sum(1 for item in results if item.get("status") == "failed"),
            "pm_cards_created": sum(int(item.get("created_card_count") or 0) for item in results),
        },
        "results": results,
    }


def _write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mirror(report: dict[str, Any], *, api_url: str, started_at: datetime, finished_at: datetime) -> bool:
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    failed = int(counts.get("failed") or 0)
    created = int(counts.get("created") or 0)
    promoted = int(counts.get("promoted") or 0)
    prepared = int(counts.get("prepared") or 0)
    skipped = int(counts.get("skipped") or 0)
    pm_cards_created = int(counts.get("pm_cards_created") or 0)
    status = "error" if failed else "ok"
    run = build_run_payload(
        run_id=f"{AUTOMATION_ID}::{finished_at.isoformat()}",
        automation_id=AUTOMATION_ID,
        automation_name=AUTOMATION_NAME,
        status=status,
        source="local_launchd_registry",
        runtime="launchd",
        run_at=started_at,
        finished_at=finished_at,
        duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        error=f"{failed} portfolio standup target(s) failed." if failed else None,
        scope="shared_ops",
        action_required=bool(failed),
        metadata={
            "has_observed_run": True,
            "summary": (
                f"Promoted {promoted} standup(s); created {created} prepared entry/entries; "
                f"prepared-only {prepared}; created {pm_cards_created} PM card(s); skipped {skipped}; failed {failed}."
            ),
            "portfolio_standup_counts": counts,
            "portfolio_standup_results": report.get("results") or [],
        },
    )
    return mirror_runs(api_url, [run])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("AICLONE_API_URL", DEFAULT_API_URL))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--chronicle-limit", type=int, default=8)
    parser.add_argument("--report-path", default=str(REPORT_PATH))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-create-standup-entry", action="store_true")
    parser.add_argument(
        "--prepared-only",
        action="store_true",
        help="Keep the legacy behavior: write prep and create a prepared standup entry without promotion.",
    )
    parser.add_argument("--no-mirror", action="store_true")
    args = parser.parse_args()

    started_at = _now()
    report = build_portfolio_standups(
        api_url=args.api_url,
        limit=args.limit,
        chronicle_limit=args.chronicle_limit,
        force=args.force,
        create_entry=not args.no_create_standup_entry,
        promote_entry=not args.prepared_only,
    )
    report_path = Path(args.report_path)
    _write_report(report, report_path)
    finished_at = _now()
    mirrored = True if args.no_mirror else _mirror(report, api_url=args.api_url, started_at=started_at, finished_at=finished_at)
    report["mirrored"] = mirrored
    _write_report(report, report_path)
    print(json.dumps({"status": "ok" if not report["counts"]["failed"] else "error", "mirrored": mirrored, **report["counts"]}))
    return 1 if report["counts"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
