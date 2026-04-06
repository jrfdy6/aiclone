#!/usr/bin/env python3
"""End-to-end OpenClaw workspace-alignment audit.

This script derives the canonical workspace contract from the codebase, asks
OpenClaw to answer the same contract using an isolated GPT-5 nano run, then
scores the reply deterministically and writes a report.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workspace_registry_service import workspace_registry_entries  # noqa: E402


OPENCLAW_ROOT = Path("/Users/neo/.openclaw")
RUNS_ROOT = OPENCLAW_ROOT / "cron" / "runs"
REPORT_ROOT = ROOT / "memory" / "reports"

LATEST_JSON_PATH = REPORT_ROOT / "openclaw_workspace_alignment_latest.json"
LATEST_MD_PATH = REPORT_ROOT / "openclaw_workspace_alignment_latest.md"

MINIMUM_LANE_DIRECTORIES = [
    "dispatch/",
    "briefings/",
    "docs/",
    "memory/",
    "agent-ledgers/",
]

STARTUP_ANCHORS = {
    "pack": "local pack",
    "docs_readme": "docs/README.md",
    "dispatch_glob": "dispatch/*.json",
    "briefings_glob": "briefings/*.md",
    "memory_log": "memory/execution_log.md",
}

CANONICAL_READ_FILES = [
    str(ROOT / "CODEX_STARTUP.md"),
    str(ROOT / "SOURCE_OF_TRUTH.md"),
    str(ROOT / "SOPs" / "workspace_portfolio_registry_sop.md"),
    str(ROOT / "docs" / "workspace_agent_contract.md"),
    str(ROOT / "docs" / "workspace_identity_pack_standard.md"),
]


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    expected: dict[str, Any]
    prompt: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug_date(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_pathish(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    return text.rstrip().lower()


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("OpenClaw returned empty output.")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("OpenClaw output did not contain a JSON object.") from None
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Expected top-level JSON object.")
    return payload


def build_alignment_spec() -> dict[str, Any]:
    portfolio: dict[str, Any] = {}
    for entry in workspace_registry_entries():
        key = str(entry["key"])
        root_slug = str(entry.get("workspace_root") or key)
        portfolio[key] = {
            "kind": str(entry.get("kind") or ""),
            "status": str(entry.get("status") or ""),
            "filesystem_root": f"workspaces/{root_slug}",
            "execution_mode": str(entry.get("execution_mode") or ""),
        }

    return {
        "generated_at": _iso(_now()),
        "source": "workspace_alignment_audit",
        "portfolio": portfolio,
        "minimum_lane_directories": list(MINIMUM_LANE_DIRECTORIES),
        "startup_anchors": dict(STARTUP_ANCHORS),
        "feezie_alias_contract": {
            "canonical_workspace_key": "feezie-os",
            "filesystem_root": "workspaces/linkedin-content-os",
            "legacy_aliases": ["linkedin-os", "linkedin-content-os"],
        },
        "shared_ops_is_exempt": True,
        "canonical_read_files": list(CANONICAL_READ_FILES),
        "audit_model": "openai/gpt-5-nano",
    }


def _common_audit_header() -> str:
    file_lines = "\n".join(f"- {path}" for path in CANONICAL_READ_FILES)
    return (
        "You are performing a workspace alignment audit for OpenClaw.\n"
        "Before answering, read these canonical files:\n"
        f"{file_lines}\n"
        "Use the canonical workspace contract only.\n"
        "Do not infer. Do not explain. Return strict JSON only.\n"
    )


def build_audit_cases(spec: dict[str, Any]) -> list[AuditCase]:
    portfolio_expected = spec["portfolio"]
    portfolio_keys = list(portfolio_expected.keys())
    portfolio_schema = {
        "portfolio": {
            key: {
                "kind": "",
                "status": "",
                "filesystem_root": "",
                "execution_mode": "",
            }
            for key in portfolio_keys
        }
    }
    portfolio_prompt = (
        _common_audit_header()
        + "Return this exact JSON shape with values filled in:\n"
        + json.dumps(portfolio_schema, indent=2)
    )

    lane_expected = {
        "minimum_lane_directories": spec["minimum_lane_directories"],
        "startup_anchors": spec["startup_anchors"],
        "shared_ops_is_exempt": spec["shared_ops_is_exempt"],
    }
    lane_schema = {
        "minimum_lane_directories": ["", "", "", "", ""],
        "startup_anchors": {
            "pack": "",
            "docs_readme": "",
            "dispatch_glob": "",
            "briefings_glob": "",
            "memory_log": "",
        },
        "shared_ops_is_exempt": True,
    }
    lane_prompt = (
        _common_audit_header()
        + "Return the minimum non-executive lane contract in this exact JSON shape:\n"
        + json.dumps(lane_schema, indent=2)
    )

    alias_expected = spec["feezie_alias_contract"]
    alias_schema = {
        "canonical_workspace_key": "",
        "filesystem_root": "",
        "legacy_aliases": ["", ""],
    }
    alias_prompt = (
        _common_audit_header()
        + "Return the canonical Feezie naming and filesystem mapping in this exact JSON shape:\n"
        + json.dumps(alias_schema, indent=2)
    )

    return [
        AuditCase("portfolio_registry", {"portfolio": portfolio_expected}, portfolio_prompt),
        AuditCase("lane_contract", lane_expected, lane_prompt),
        AuditCase("feezie_alias", alias_expected, alias_prompt),
    ]


def _compare_portfolio(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    actual_portfolio = actual.get("portfolio")
    if not isinstance(actual_portfolio, dict):
        return False, ["Missing top-level `portfolio` object."]

    for key, expected_item in expected["portfolio"].items():
        actual_item = actual_portfolio.get(key)
        if not isinstance(actual_item, dict):
            mismatches.append(f"{key}: missing object.")
            continue
        for field, expected_value in expected_item.items():
            actual_value = actual_item.get(field)
            if _normalize_pathish(actual_value) != _normalize_pathish(expected_value):
                mismatches.append(f"{key}.{field}: expected `{expected_value}` got `{actual_value}`.")
    return len(mismatches) == 0, mismatches


def _compare_lane_contract(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    actual_dirs = actual.get("minimum_lane_directories")
    if not isinstance(actual_dirs, list):
        mismatches.append("Missing `minimum_lane_directories` list.")
    else:
        normalized_actual_dirs = [_normalize_pathish(item) for item in actual_dirs]
        normalized_expected_dirs = [_normalize_pathish(item) for item in expected["minimum_lane_directories"]]
        if normalized_actual_dirs != normalized_expected_dirs:
            mismatches.append(
                "minimum_lane_directories mismatch: "
                f"expected `{expected['minimum_lane_directories']}` got `{actual_dirs}`."
            )

    actual_anchors = actual.get("startup_anchors")
    if not isinstance(actual_anchors, dict):
        mismatches.append("Missing `startup_anchors` object.")
    else:
        for field, expected_value in expected["startup_anchors"].items():
            actual_value = actual_anchors.get(field)
            if _normalize_pathish(actual_value) != _normalize_pathish(expected_value):
                mismatches.append(f"startup_anchors.{field}: expected `{expected_value}` got `{actual_value}`.")

    if bool(actual.get("shared_ops_is_exempt")) is not bool(expected["shared_ops_is_exempt"]):
        mismatches.append(
            f"shared_ops_is_exempt: expected `{expected['shared_ops_is_exempt']}` got `{actual.get('shared_ops_is_exempt')}`."
        )

    return len(mismatches) == 0, mismatches


def _compare_feezie_alias(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for field in ("canonical_workspace_key", "filesystem_root"):
        if _normalize_pathish(actual.get(field)) != _normalize_pathish(expected[field]):
            mismatches.append(f"{field}: expected `{expected[field]}` got `{actual.get(field)}`.")

    actual_aliases = actual.get("legacy_aliases")
    if not isinstance(actual_aliases, list):
        mismatches.append("Missing `legacy_aliases` list.")
    else:
        normalized_actual = {_normalize_text(item) for item in actual_aliases}
        for alias in expected["legacy_aliases"]:
            if _normalize_text(alias) not in normalized_actual:
                mismatches.append(f"legacy_aliases missing required alias `{alias}`.")

    return len(mismatches) == 0, mismatches


def evaluate_case(case: AuditCase, actual_payload: dict[str, Any]) -> dict[str, Any]:
    if case.case_id == "portfolio_registry":
        passed, mismatches = _compare_portfolio(case.expected, actual_payload)
    elif case.case_id == "lane_contract":
        passed, mismatches = _compare_lane_contract(case.expected, actual_payload)
    elif case.case_id == "feezie_alias":
        passed, mismatches = _compare_feezie_alias(case.expected, actual_payload)
    else:
        passed, mismatches = False, [f"Unknown case `{case.case_id}`."]

    return {
        "case_id": case.case_id,
        "passed": passed,
        "mismatches": mismatches,
        "expected": case.expected,
        "actual": actual_payload,
    }


def _run_command(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)


def _wait_for_run_record(job_id: str, started_at_ms: int, *, timeout_seconds: int) -> dict[str, Any]:
    run_path = RUNS_ROOT / f"{job_id}.jsonl"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if run_path.exists():
            lines = [line for line in run_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
            for raw_line in reversed(lines):
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if str(payload.get("jobId") or "") != job_id:
                    continue
                if str(payload.get("action") or "") != "finished":
                    continue
                ts = int(payload.get("ts") or 0)
                if ts >= started_at_ms - 1000:
                    return payload
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for OpenClaw cron run record for job {job_id}.")


def _safe_rm_job(job_id: str) -> None:
    _run_command(["openclaw", "cron", "rm", job_id, "--json"], timeout=60)


def run_openclaw_case(case: AuditCase, *, model: str, thinking: str, timeout_seconds: int) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job_name = f"Workspace Alignment Audit [{case.case_id}] {stamp}"
    add_cmd = [
        "openclaw",
        "cron",
        "add",
        "--json",
        "--name",
        job_name,
        "--at",
        "20m",
        "--keep-after-run",
        "--session",
        "isolated",
        "--no-deliver",
        "--light-context",
        "--thinking",
        thinking,
        "--timeout-seconds",
        str(timeout_seconds),
        "--model",
        model,
        "--message",
        case.prompt,
    ]
    add_result = _run_command(add_cmd, timeout=120)
    if add_result.returncode != 0:
        raise RuntimeError(f"Failed to create OpenClaw audit job for {case.case_id}: {add_result.stderr or add_result.stdout}")
    add_payload = _extract_json_object(add_result.stdout)
    job_id = str(add_payload.get("id") or "")
    if not job_id:
        raise RuntimeError(f"OpenClaw did not return a job id for {case.case_id}.")

    started_at_ms = int(time.time() * 1000)
    try:
        run_result = _run_command(
            [
                "openclaw",
                "cron",
                "run",
                job_id,
                "--expect-final",
                "--timeout",
                str(timeout_seconds * 1000),
            ],
            timeout=timeout_seconds + 30,
        )
        if run_result.returncode != 0:
            raise RuntimeError(f"Failed to run OpenClaw audit job {job_id}: {run_result.stderr or run_result.stdout}")
        run_record = _wait_for_run_record(job_id, started_at_ms, timeout_seconds=timeout_seconds)
    finally:
        _safe_rm_job(job_id)

    summary_text = str(run_record.get("summary") or "").strip()
    parsed_summary = _extract_json_object(summary_text)
    return {
        "case_id": case.case_id,
        "job_id": job_id,
        "job_name": job_name,
        "model": str(run_record.get("model") or model),
        "provider": str(run_record.get("provider") or ""),
        "status": str(run_record.get("status") or ""),
        "duration_ms": int(run_record.get("durationMs") or 0),
        "raw_summary": summary_text,
        "parsed_summary": parsed_summary,
        "run_stdout": run_result.stdout,
        "run_stderr": run_result.stderr,
    }


def build_report(*, spec: dict[str, Any], mode: str, case_results: list[dict[str, Any]]) -> dict[str, Any]:
    passed_cases = [item for item in case_results if item.get("passed")]
    failed_cases = [item for item in case_results if not item.get("passed")]
    return {
        "generated_at": _iso(_now()),
        "mode": mode,
        "source": "openclaw_workspace_alignment_audit",
        "overall_status": "pass" if not failed_cases else "fail",
        "case_count": len(case_results),
        "passed_case_count": len(passed_cases),
        "failed_case_count": len(failed_cases),
        "spec": spec,
        "cases": case_results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Workspace Alignment Audit",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Overall status: `{report['overall_status']}`",
        f"- Cases: `{report['passed_case_count']}/{report['case_count']}` passed",
        "",
        "## Cases",
    ]
    for case in report["cases"]:
        lines.extend(
            [
                "",
                f"### {case['case_id']}",
                f"- Passed: `{case['passed']}`",
            ]
        )
        if case.get("model"):
            lines.append(f"- Model: `{case['model']}`")
        if case.get("job_id"):
            lines.append(f"- Job id: `{case['job_id']}`")
        if case.get("duration_ms") is not None:
            lines.append(f"- Duration ms: `{case.get('duration_ms', 0)}`")
        mismatches = case.get("mismatches") or []
        if mismatches:
            lines.append("- Mismatches:")
            for item in mismatches:
                lines.append(f"  - {item}")
        else:
            lines.append("- Mismatches: none")
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    dated_json = REPORT_ROOT / f"openclaw_workspace_alignment_{_slug_date(_now())}.json"
    dated_md = REPORT_ROOT / f"openclaw_workspace_alignment_{_slug_date(_now())}.md"
    markdown = render_markdown(report)

    LATEST_JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    dated_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    LATEST_MD_PATH.write_text(markdown, encoding="utf-8")
    dated_md.write_text(markdown, encoding="utf-8")
    return LATEST_JSON_PATH, LATEST_MD_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether OpenClaw and the canonical workspace system are aligned.")
    parser.add_argument("--mode", choices=("spec", "run-openclaw"), default="spec")
    parser.add_argument("--model", default="openai/gpt-5-nano")
    parser.add_argument("--thinking", default="minimal")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--case", action="append", dest="cases", help="Optional case id filter.")
    parser.add_argument("--print-prompts", action="store_true")
    args = parser.parse_args()

    spec = build_alignment_spec()
    cases = build_audit_cases(spec)
    if args.cases:
        requested = {item.strip() for item in args.cases if item and item.strip()}
        cases = [case for case in cases if case.case_id in requested]
        if not cases:
            raise SystemExit("No matching audit cases selected.")

    if args.print_prompts:
        for case in cases:
            print(f"\n--- {case.case_id} ---\n{case.prompt}\n")

    if args.mode == "spec":
        case_results = [
            {
                "case_id": case.case_id,
                "passed": True,
                "mismatches": [],
                "expected": case.expected,
            }
            for case in cases
        ]
        report = build_report(spec=spec, mode="spec", case_results=case_results)
        json_path, md_path = write_report(report)
        print(f"wrote json={json_path}")
        print(f"wrote markdown={md_path}")
        return 0

    case_results: list[dict[str, Any]] = []
    for case in cases:
        run_payload = run_openclaw_case(case, model=args.model, thinking=args.thinking, timeout_seconds=args.timeout_seconds)
        evaluation = evaluate_case(case, run_payload["parsed_summary"])
        case_results.append({**run_payload, **evaluation})

    report = build_report(spec=spec, mode="run-openclaw", case_results=case_results)
    json_path, md_path = write_report(report)
    print(f"wrote json={json_path}")
    print(f"wrote markdown={md_path}")
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
