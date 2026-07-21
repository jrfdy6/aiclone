#!/usr/bin/env python3
"""Verify repo-surface truth against the frozen baseline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.repo_surface_registry_service import (  # noqa: E402
    STATUS_LIVE,
    STATUS_REFERENCE,
    STATUS_SCAFFOLD,
    build_repo_surface_registry,
)


DEFAULT_BASELINE_PATH = WORKSPACE_ROOT / "docs" / "repo_surface_truth_baseline_2026-04-25.json"


def load_baseline(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Baseline file must contain a JSON object: {path}")
    return payload


def build_verification_report(
    registry_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    current_surface_mismatches = _surface_mismatch_map(registry_payload)
    baseline_surface_mismatches = _baseline_surface_mismatch_map(baseline_payload)

    current_surface_ids = set(current_surface_mismatches)
    baseline_surface_ids = set(baseline_surface_mismatches)

    new_surface_mismatches: list[dict[str, Any]] = []
    changed_surface_mismatches: list[dict[str, Any]] = []
    reduced_surface_mismatches: list[dict[str, Any]] = []
    preserved_baseline_surface_mismatches: list[dict[str, Any]] = []
    resolved_baseline_surfaces = sorted(baseline_surface_ids - current_surface_ids)

    for surface_id in sorted(current_surface_ids):
        current_flags = current_surface_mismatches[surface_id]
        baseline_flags = baseline_surface_mismatches.get(surface_id, set())
        if surface_id not in baseline_surface_mismatches:
            new_surface_mismatches.append({"surface_id": surface_id, "mismatch_flags": sorted(current_flags)})
            continue
        added_flags = sorted(current_flags - baseline_flags)
        removed_flags = sorted(baseline_flags - current_flags)
        if added_flags or removed_flags:
            change_payload = {
                "surface_id": surface_id,
                "added_flags": added_flags,
                "removed_flags": removed_flags,
            }
            if added_flags:
                changed_surface_mismatches.append(change_payload)
            else:
                reduced_surface_mismatches.append(change_payload)
            continue
        preserved_baseline_surface_mismatches.append({"surface_id": surface_id, "mismatch_flags": sorted(current_flags)})

    allowed_runtime_hrefs = _string_list(baseline_payload.get("allowed_unclassified_runtime_shell_hrefs"))
    allowed_legacy_hrefs = _string_list(baseline_payload.get("allowed_unclassified_legacy_nav_hrefs"))
    current_unclassified_runtime_hrefs = _string_list(registry_payload.get("unclassified_runtime_shell_hrefs"))
    current_unclassified_legacy_hrefs = _string_list(registry_payload.get("unclassified_legacy_nav_hrefs"))

    new_unclassified_runtime_hrefs = sorted(set(current_unclassified_runtime_hrefs) - set(allowed_runtime_hrefs))
    new_unclassified_legacy_hrefs = sorted(set(current_unclassified_legacy_hrefs) - set(allowed_legacy_hrefs))

    active_surface_mismatches = _active_surface_mismatches(registry_payload)
    reference_surface_mismatches = _reference_surface_mismatches(registry_payload)

    ok = not (
        active_surface_mismatches
        or new_surface_mismatches
        or changed_surface_mismatches
        or new_unclassified_runtime_hrefs
        or new_unclassified_legacy_hrefs
        or reference_surface_mismatches
        or (strict and current_surface_mismatches)
    )

    summary = registry_payload.get("summary") if isinstance(registry_payload.get("summary"), dict) else {}
    return {
        "ok": ok,
        "mode": "strict" if strict else "baseline_guard",
        "baseline_ref": str(DEFAULT_BASELINE_PATH.relative_to(WORKSPACE_ROOT)),
        "summary": {
            "total_surfaces": int(summary.get("total_surfaces") or 0),
            "mismatch_count": int(summary.get("mismatch_count") or 0),
            "runtime_shell_visible_count": int(summary.get("runtime_shell_visible_count") or 0),
            "legacy_nav_visible_count": int(summary.get("legacy_nav_visible_count") or 0),
            "unclassified_runtime_shell_href_count": int(summary.get("unclassified_runtime_shell_href_count") or 0),
            "unclassified_legacy_nav_href_count": int(summary.get("unclassified_legacy_nav_href_count") or 0),
        },
        "active_surface_mismatches": active_surface_mismatches,
        "reference_surface_mismatches": reference_surface_mismatches,
        "new_surface_mismatches": new_surface_mismatches,
        "changed_surface_mismatches": changed_surface_mismatches,
        "reduced_surface_mismatches": reduced_surface_mismatches,
        "preserved_baseline_surface_mismatches": preserved_baseline_surface_mismatches,
        "resolved_baseline_surfaces": resolved_baseline_surfaces,
        "new_unclassified_runtime_shell_hrefs": new_unclassified_runtime_hrefs,
        "new_unclassified_legacy_nav_hrefs": new_unclassified_legacy_hrefs,
    }


def _surface_mismatch_map(payload: dict[str, Any]) -> dict[str, set[str]]:
    surfaces: dict[str, set[str]] = {}
    for item in payload.get("mismatches") or []:
        if not isinstance(item, dict):
            continue
        surface_id = str(item.get("surface_id") or "").strip()
        if not surface_id:
            continue
        surfaces[surface_id] = {flag for flag in _string_list(item.get("mismatch_flags")) if flag}
    return surfaces


def _baseline_surface_mismatch_map(payload: dict[str, Any]) -> dict[str, set[str]]:
    surfaces: dict[str, set[str]] = {}
    for item in payload.get("allowed_surface_mismatches") or []:
        if not isinstance(item, dict):
            continue
        surface_id = str(item.get("surface_id") or "").strip()
        if not surface_id:
            continue
        surfaces[surface_id] = {flag for flag in _string_list(item.get("mismatch_flags")) if flag}
    return surfaces


def _active_surface_mismatches(registry_payload: dict[str, Any]) -> list[dict[str, Any]]:
    active_statuses = {STATUS_LIVE, STATUS_SCAFFOLD}
    return _select_surface_mismatches(registry_payload, include_statuses=active_statuses)


def _reference_surface_mismatches(registry_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _select_surface_mismatches(registry_payload, include_statuses={STATUS_REFERENCE})


def _select_surface_mismatches(registry_payload: dict[str, Any], *, include_statuses: set[str]) -> list[dict[str, Any]]:
    entries = registry_payload.get("entries") or []
    results: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status_class") or "") not in include_statuses:
            continue
        flags = _string_list(entry.get("mismatch_flags"))
        if not flags:
            continue
        results.append(
            {
                "surface_id": str(entry.get("surface_id") or ""),
                "status_class": str(entry.get("status_class") or ""),
                "mismatch_flags": flags,
            }
        )
    return results


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _print_human_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("Repo surface truth verification")
    print(f"Mode: {report.get('mode')}")
    print(f"Baseline: {report.get('baseline_ref')}")
    print(f"Total surfaces: {summary.get('total_surfaces', 0)}")
    print(f"Current mismatches: {summary.get('mismatch_count', 0)}")
    print(f"Baseline-preserved mismatch surfaces: {len(report.get('preserved_baseline_surface_mismatches') or [])}")

    _print_section("Active surface mismatches", report.get("active_surface_mismatches") or [])
    _print_section("Reference surface mismatches", report.get("reference_surface_mismatches") or [])
    _print_section("New mismatch surfaces", report.get("new_surface_mismatches") or [])
    _print_section("Changed mismatch surfaces", report.get("changed_surface_mismatches") or [])
    _print_section("Reduced mismatch surfaces", report.get("reduced_surface_mismatches") or [])
    _print_section("New unclassified runtime-shell hrefs", report.get("new_unclassified_runtime_shell_hrefs") or [])
    _print_section("New unclassified legacy-nav hrefs", report.get("new_unclassified_legacy_nav_hrefs") or [])

    result = "PASS" if report.get("ok") else "FAIL"
    print(f"Result: {result}")


def _print_section(label: str, items: list[Any]) -> None:
    if not items:
        print(f"{label}: none")
        return
    print(f"{label}:")
    for item in items:
        print(f"- {json.dumps(item, sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify repo-surface truth against the frozen baseline.")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH), help="Path to the baseline JSON file.")
    parser.add_argument("--strict", action="store_true", help="Fail on any mismatch, including known baseline debt.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable report.")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline).expanduser().resolve()
    baseline_payload = load_baseline(baseline_path)
    registry_payload = build_repo_surface_registry(include_entries=True)
    report = build_verification_report(registry_payload, baseline_payload, strict=bool(args.strict))
    report["baseline_ref"] = str(baseline_path.relative_to(WORKSPACE_ROOT)) if baseline_path.is_relative_to(WORKSPACE_ROOT) else str(baseline_path)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human_report(report)

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
