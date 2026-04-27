from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.workspace_registry_service import REPO_ROOT


ROOT = REPO_ROOT
RUNTIME_CHROME_PATH = ROOT / "frontend" / "components" / "runtime" / "RuntimeChrome.tsx"
NAV_HEADER_PATH = ROOT / "frontend" / "components" / "NavHeader.tsx"

STATUS_LIVE = "live_and_production_relevant"
STATUS_SCAFFOLD = "live_but_scaffold_fallback"
STATUS_LEGACY = "present_but_dormant_legacy"
STATUS_REFERENCE = "reference_only"

STATUS_CLASSES = (STATUS_LIVE, STATUS_SCAFFOLD, STATUS_LEGACY, STATUS_REFERENCE)

_HREF_OBJECT_RE = re.compile(r"href:\s*'([^']+)'")
_HREF_ATTR_RE = re.compile(r'href="([^"]+)"')
_API_CALL_RE = re.compile(r"/api/[A-Za-z0-9._~!$&()*+,;=:@%/?-]+")
_IGNORED_NAV_HREFS = frozenset({"/"})
_SCAFFOLD_MARKERS = (
    ("todo_marker", re.compile(r"\bTODO\b", re.IGNORECASE)),
    ("mock_data", re.compile(r"\bmock\b", re.IGNORECASE)),
    ("hardcoded_data", re.compile(r"\bhardcoded\b", re.IGNORECASE)),
    ("stub_language", re.compile(r"\bstub\b", re.IGNORECASE)),
)

_MOUNTED_API_PREFIXES = frozenset(
    {
        "/api/analytics",
        "/api/automations",
        "/api/brain",
        "/api/brain-docs",
        "/api/briefs",
        "/api/calendar",
        "/api/capture",
        "/api/client-errors",
        "/api/content-generation",
        "/api/email",
        "/api/knowledge",
        "/api/lab",
        "/api/notifications",
        "/api/open-brain",
        "/api/persona",
        "/api/playbooks",
        "/api/pm",
        "/api/prospects",
        "/api/standups",
        "/api/system/logs",
        "/api/timeline",
        "/api/topic-intelligence",
        "/api/workspace",
    }
)

_SURFACE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "surface_id": "ops",
        "label": "Ops",
        "surface_kind": "page",
        "status_class": STATUS_LIVE,
        "owner": "control_plane",
        "route": "/ops",
        "shell_hrefs": ["/ops"],
        "legacy_nav_hrefs": ["/ops"],
        "frontend_files": [
            "frontend/app/ops/page.tsx",
            "frontend/app/ops/OpsClient.tsx",
        ],
        "backend_contract_prefixes": [
            "/api/analytics",
            "/api/automations",
            "/api/open-brain",
            "/api/pm",
            "/api/standups",
            "/api/system/logs",
            "/api/workspace",
        ],
        "fallback_policy": "primary_runtime",
        "source_of_truth": "runtime_shell+mounted_backend",
        "notes": "Mission Control umbrella and the current runtime homepage.",
    },
    {
        "surface_id": "brain",
        "label": "Brain",
        "surface_kind": "page",
        "status_class": STATUS_LIVE,
        "owner": "brain_control_plane",
        "route": "/brain",
        "shell_hrefs": ["/brain"],
        "legacy_nav_hrefs": ["/brain"],
        "frontend_files": [
            "frontend/app/brain/page.tsx",
            "frontend/app/brain/BrainClient.tsx",
        ],
        "backend_contract_prefixes": [
            "/api/brain",
            "/api/briefs",
            "/api/capture",
            "/api/persona",
        ],
        "fallback_policy": "primary_runtime",
        "source_of_truth": "runtime_shell+mounted_backend",
        "notes": "Global review, docs, persona, and control-plane surface.",
    },
    {
        "surface_id": "workspace",
        "label": "Workspace",
        "surface_kind": "page",
        "status_class": STATUS_LIVE,
        "owner": "workspace_execution",
        "route": "/workspace",
        "shell_hrefs": ["/ops#workspace"],
        "legacy_nav_hrefs": ["/ops#workspace"],
        "frontend_files": [
            "frontend/app/workspace/page.tsx",
            "frontend/app/workspace/WorkspaceClient.tsx",
            "frontend/app/workspace/posting/page.tsx",
        ],
        "backend_contract_prefixes": [
            "/api/content-generation",
            "/api/persona",
            "/api/workspace",
        ],
        "fallback_policy": "primary_runtime",
        "source_of_truth": "runtime_shell+mounted_backend",
        "notes": "Current live FEEZIE execution surface.",
    },
    {
        "surface_id": "inbox",
        "label": "Inbox",
        "surface_kind": "page",
        "status_class": STATUS_LIVE,
        "owner": "email_ops_ui",
        "route": "/inbox",
        "shell_hrefs": ["/inbox"],
        "legacy_nav_hrefs": ["/inbox"],
        "frontend_files": [
            "frontend/app/inbox/page.tsx",
            "frontend/app/inbox/[threadId]/page.tsx",
            "frontend/app/agc-inbox/page.tsx",
        ],
        "backend_contract_prefixes": ["/api/email"],
        "fallback_policy": "primary_runtime",
        "source_of_truth": "runtime_shell+mounted_backend",
        "notes": "Live inbox surface over the mounted email-ops API.",
    },
    {
        "surface_id": "lab",
        "label": "Lab",
        "surface_kind": "page",
        "status_class": STATUS_SCAFFOLD,
        "owner": "lab_observability",
        "route": "/lab",
        "shell_hrefs": ["/lab"],
        "legacy_nav_hrefs": ["/lab"],
        "frontend_files": ["frontend/app/lab/page.tsx"],
        "backend_contract_prefixes": ["/api/automations", "/api/lab"],
        "fallback_policy": "allowed_in_production",
        "source_of_truth": "runtime_shell+mounted_backend",
        "notes": "Live observability surface with explicit fallback and evaluation focus.",
    },
    {
        "surface_id": "content_generation",
        "label": "Content Generation",
        "surface_kind": "route_family",
        "status_class": STATUS_SCAFFOLD,
        "owner": "content_pipeline",
        "route": None,
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": [
            "frontend/app/workspace/WorkspaceClient.tsx",
            "frontend/app/workspace/posting/page.tsx",
        ],
        "backend_contract_prefixes": ["/api/content-generation"],
        "fallback_policy": "allowed_in_production",
        "source_of_truth": "mounted_backend",
        "notes": "Mounted and actively used, but still contains provider and legacy fallback paths.",
    },
    {
        "surface_id": "email_ops",
        "label": "Email Ops",
        "surface_kind": "route_family",
        "status_class": STATUS_SCAFFOLD,
        "owner": "email_ops_backend",
        "route": None,
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": [
            "frontend/app/inbox/page.tsx",
            "frontend/app/inbox/[threadId]/page.tsx",
        ],
        "backend_contract_prefixes": ["/api/email"],
        "fallback_policy": "allowed_in_production",
        "source_of_truth": "mounted_backend",
        "notes": "Mounted and used, but still allows sample-thread fallback and lacks a full approve/send loop.",
    },
    {
        "surface_id": "prospects",
        "label": "Prospects",
        "surface_kind": "route_family",
        "status_class": STATUS_SCAFFOLD,
        "owner": "prospects_backend",
        "route": None,
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": ["frontend/app/prospect-discovery/page.tsx"],
        "backend_contract_prefixes": ["/api/prospects"],
        "fallback_policy": "allowed_in_production",
        "source_of_truth": "mounted_backend",
        "notes": "Mounted, but still relies on Firestore/local fallback behavior.",
    },
    {
        "surface_id": "prospects_manual",
        "label": "Prospects Manual",
        "surface_kind": "route_family",
        "status_class": STATUS_SCAFFOLD,
        "owner": "prospects_backend",
        "route": None,
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": [],
        "backend_contract_prefixes": ["/api/prospects/manual"],
        "fallback_policy": "allowed_in_production",
        "source_of_truth": "mounted_backend",
        "notes": "Mounted and used as a manual/local save path with fallback-tolerant storage.",
    },
    {
        "surface_id": "prospect_discovery",
        "label": "Prospect Discovery",
        "surface_kind": "page",
        "status_class": STATUS_LEGACY,
        "owner": "legacy_product_page",
        "route": "/prospect-discovery",
        "shell_hrefs": [],
        "legacy_nav_hrefs": ["/prospect-discovery"],
        "frontend_files": ["frontend/app/prospect-discovery/page.tsx"],
        "backend_contract_prefixes": ["/api/prospect-discovery", "/api/prospects"],
        "fallback_policy": "legacy_only",
        "source_of_truth": "legacy_nav+page_file",
        "notes": "Visible page that still targets unmounted discovery endpoints.",
    },
    {
        "surface_id": "outreach",
        "label": "Outreach",
        "surface_kind": "page",
        "status_class": STATUS_LEGACY,
        "owner": "legacy_product_page",
        "route": "/outreach",
        "shell_hrefs": [],
        "legacy_nav_hrefs": ["/outreach"],
        "frontend_files": [
            "frontend/app/outreach/page.tsx",
            "frontend/app/outreach/[prospectId]/page.tsx",
        ],
        "backend_contract_prefixes": [],
        "fallback_policy": "legacy_only",
        "source_of_truth": "legacy_nav+page_file",
        "notes": "Mock/TODO product page family that is not part of the trusted runtime shell.",
    },
    {
        "surface_id": "templates",
        "label": "Templates",
        "surface_kind": "page",
        "status_class": STATUS_LEGACY,
        "owner": "legacy_product_page",
        "route": "/templates",
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": ["frontend/app/templates/page.tsx"],
        "backend_contract_prefixes": [],
        "fallback_policy": "legacy_only",
        "source_of_truth": "page_file",
        "notes": "Hardcoded template page retained from the old product surface.",
    },
    {
        "surface_id": "dashboard",
        "label": "Dashboard",
        "surface_kind": "page",
        "status_class": STATUS_LEGACY,
        "owner": "legacy_product_page",
        "route": "/dashboard",
        "shell_hrefs": [],
        "legacy_nav_hrefs": ["/dashboard"],
        "frontend_files": ["frontend/app/dashboard/page.tsx"],
        "backend_contract_prefixes": ["/api/dashboard"],
        "fallback_policy": "legacy_only",
        "source_of_truth": "legacy_nav+page_file",
        "notes": "Old dashboard entry point that still calls an unmounted API contract.",
    },
    {
        "surface_id": "vault",
        "label": "Vault",
        "surface_kind": "page",
        "status_class": STATUS_LEGACY,
        "owner": "legacy_product_page",
        "route": "/vault",
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": ["frontend/app/vault/page.tsx"],
        "backend_contract_prefixes": [],
        "fallback_policy": "legacy_only",
        "source_of_truth": "page_file",
        "notes": "Residual page outside the primary runtime shell.",
    },
    {
        "surface_id": "research_tasks",
        "label": "Research Tasks",
        "surface_kind": "page",
        "status_class": STATUS_LEGACY,
        "owner": "legacy_product_page",
        "route": "/research-tasks",
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": ["frontend/app/research-tasks/page.tsx"],
        "backend_contract_prefixes": [],
        "fallback_policy": "legacy_only",
        "source_of_truth": "page_file",
        "notes": "Residual page outside the primary runtime shell.",
    },
    {
        "surface_id": "downloads_aiclone",
        "label": "downloads/aiclone",
        "surface_kind": "subtree",
        "status_class": STATUS_REFERENCE,
        "owner": "archive_reference",
        "route": None,
        "shell_hrefs": [],
        "legacy_nav_hrefs": [],
        "frontend_files": [],
        "backend_contract_prefixes": [],
        "subtree_paths": ["downloads/aiclone"],
        "fallback_policy": "reference_only",
        "source_of_truth": "archive_reference",
        "notes": "Old donor/archive repo for comparison and selective salvage, not active runtime truth.",
    },
)


def build_repo_surface_registry(*, include_entries: bool = True) -> dict[str, Any]:
    runtime_shell_hrefs = _extract_hrefs(RUNTIME_CHROME_PATH)
    legacy_nav_hrefs = _extract_hrefs(NAV_HEADER_PATH)
    declared_runtime_shell_hrefs = {
        href
        for spec in _SURFACE_SPECS
        for href in (spec.get("shell_hrefs") or [])
        if isinstance(href, str) and href.strip()
    }
    declared_legacy_nav_hrefs = {
        href
        for spec in _SURFACE_SPECS
        for href in (spec.get("legacy_nav_hrefs") or [])
        if isinstance(href, str) and href.strip()
    }
    unclassified_runtime_shell_hrefs = sorted(
        href for href in runtime_shell_hrefs if href not in declared_runtime_shell_hrefs and href not in _IGNORED_NAV_HREFS
    )
    unclassified_legacy_nav_hrefs = sorted(
        href for href in legacy_nav_hrefs if href not in declared_legacy_nav_hrefs and href not in _IGNORED_NAV_HREFS
    )
    entries = [_build_surface_entry(spec, runtime_shell_hrefs=runtime_shell_hrefs, legacy_nav_hrefs=legacy_nav_hrefs) for spec in _SURFACE_SPECS]
    mismatches = [
        {
            "surface_id": entry["surface_id"],
            "label": entry["label"],
            "status_class": entry["status_class"],
            "route": entry.get("route"),
            "mismatch_flags": entry["mismatch_flags"],
            "frontend_unmounted_api_calls": entry.get("frontend_unmounted_api_calls") or [],
        }
        for entry in entries
        if entry["mismatch_flags"]
    ]
    status_counts = {status: sum(1 for entry in entries if entry["status_class"] == status) for status in STATUS_CLASSES}
    summary = {
        "total_surfaces": len(entries),
        "status_counts": status_counts,
        "runtime_shell_visible_count": sum(1 for entry in entries if entry.get("runtime_shell_visible")),
        "legacy_nav_visible_count": sum(1 for entry in entries if entry.get("legacy_nav_visible")),
        "mismatch_count": len(mismatches),
        "mounted_api_prefix_count": len(_MOUNTED_API_PREFIXES),
        "unclassified_runtime_shell_href_count": len(unclassified_runtime_shell_hrefs),
        "unclassified_legacy_nav_href_count": len(unclassified_legacy_nav_hrefs),
    }
    payload: dict[str, Any] = {
        "schema_version": "repo_surface_registry/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_shell_source": _relative_path(RUNTIME_CHROME_PATH),
        "legacy_nav_source": _relative_path(NAV_HEADER_PATH),
        "observed_runtime_shell_hrefs": sorted(runtime_shell_hrefs),
        "observed_legacy_nav_hrefs": sorted(legacy_nav_hrefs),
        "declared_runtime_shell_hrefs": sorted(declared_runtime_shell_hrefs),
        "declared_legacy_nav_hrefs": sorted(declared_legacy_nav_hrefs),
        "unclassified_runtime_shell_hrefs": unclassified_runtime_shell_hrefs,
        "unclassified_legacy_nav_hrefs": unclassified_legacy_nav_hrefs,
        "mounted_api_prefixes": sorted(_MOUNTED_API_PREFIXES),
        "summary": summary,
        "mismatches": mismatches,
    }
    if include_entries:
        payload["entries"] = entries
    return payload


def _build_surface_entry(
    spec: dict[str, Any],
    *,
    runtime_shell_hrefs: set[str],
    legacy_nav_hrefs: set[str],
) -> dict[str, Any]:
    frontend_files = [_relative_path(path) for path in _resolve_paths(spec.get("frontend_files"))]
    frontend_paths = _resolve_paths(spec.get("frontend_files"))
    api_calls = _extract_api_calls(frontend_paths)
    unmounted_api_calls = [call for call in api_calls if not _api_call_is_mounted(call)]
    scaffold_markers = _extract_scaffold_markers(frontend_paths)
    subtree_paths = _resolve_paths(spec.get("subtree_paths"))
    subtree_exists = all(path.exists() for path in subtree_paths) if subtree_paths else None
    declared_prefixes = list(spec.get("backend_contract_prefixes") or [])
    backend_contract_mounted = all(_api_call_is_mounted(prefix) for prefix in declared_prefixes)
    runtime_shell_visible = any(href in runtime_shell_hrefs for href in spec.get("shell_hrefs") or [])
    legacy_nav_visible = any(href in legacy_nav_hrefs for href in spec.get("legacy_nav_hrefs") or [])
    mismatch_flags = _mismatch_flags(
        status_class=str(spec.get("status_class") or ""),
        runtime_shell_visible=runtime_shell_visible,
        legacy_nav_visible=legacy_nav_visible,
        backend_contract_prefixes=declared_prefixes,
        backend_contract_mounted=backend_contract_mounted,
        unmounted_api_calls=unmounted_api_calls,
        subtree_exists=subtree_exists,
    )
    return {
        "surface_id": spec["surface_id"],
        "label": spec["label"],
        "surface_kind": spec["surface_kind"],
        "status_class": spec["status_class"],
        "owner": spec["owner"],
        "route": spec.get("route"),
        "nav_visibility": _nav_visibility(runtime_shell_visible=runtime_shell_visible, legacy_nav_visible=legacy_nav_visible),
        "runtime_shell_visible": runtime_shell_visible,
        "legacy_nav_visible": legacy_nav_visible,
        "backend_contract_prefixes": declared_prefixes,
        "backend_contract_mounted": backend_contract_mounted,
        "frontend_files": frontend_files,
        "frontend_file_count": len(frontend_files),
        "frontend_api_calls": api_calls,
        "frontend_unmounted_api_calls": unmounted_api_calls,
        "scaffold_markers": scaffold_markers,
        "subtree_paths": [_relative_path(path) for path in subtree_paths],
        "subtree_exists": subtree_exists,
        "fallback_policy": spec.get("fallback_policy"),
        "source_of_truth": spec.get("source_of_truth"),
        "notes": spec.get("notes"),
        "mismatch_flags": mismatch_flags,
    }


def _mismatch_flags(
    *,
    status_class: str,
    runtime_shell_visible: bool,
    legacy_nav_visible: bool,
    backend_contract_prefixes: list[str],
    backend_contract_mounted: bool,
    unmounted_api_calls: list[str],
    subtree_exists: bool | None,
) -> list[str]:
    flags: list[str] = []
    if status_class == STATUS_LIVE:
        if backend_contract_prefixes and not backend_contract_mounted:
            flags.append("live_surface_missing_mounted_backend")
        if unmounted_api_calls:
            flags.append("live_surface_calls_unmounted_api")
    if status_class == STATUS_SCAFFOLD:
        if backend_contract_prefixes and not backend_contract_mounted:
            flags.append("scaffold_surface_missing_mounted_backend")
    if status_class == STATUS_LEGACY:
        if runtime_shell_visible:
            flags.append("legacy_surface_visible_in_runtime_shell")
        if legacy_nav_visible:
            flags.append("legacy_surface_visible_in_nav")
        if unmounted_api_calls:
            flags.append("legacy_surface_calls_unmounted_api")
    if status_class == STATUS_REFERENCE and subtree_exists is False:
        flags.append("reference_surface_missing_path")
    return flags


def _nav_visibility(*, runtime_shell_visible: bool, legacy_nav_visible: bool) -> str:
    if runtime_shell_visible:
        return "runtime_shell"
    if legacy_nav_visible:
        return "legacy_nav"
    return "hidden"


def _extract_hrefs(path: Path) -> set[str]:
    text = _read_text(path)
    if not text:
        return set()
    matches = {match.strip() for match in _HREF_OBJECT_RE.findall(text)}
    matches.update(match.strip() for match in _HREF_ATTR_RE.findall(text))
    return {match for match in matches if match}


def _extract_api_calls(paths: list[Path]) -> list[str]:
    seen: set[str] = set()
    calls: list[str] = []
    for path in paths:
        text = _read_text(path)
        if not text:
            continue
        for raw in _API_CALL_RE.findall(text):
            call = raw.rstrip("'\"),};")
            if call and call not in seen:
                seen.add(call)
                calls.append(call)
    return calls


def _extract_scaffold_markers(paths: list[Path]) -> list[str]:
    markers: list[str] = []
    seen: set[str] = set()
    for path in paths:
        text = _read_text(path)
        if not text:
            continue
        for marker, pattern in _SCAFFOLD_MARKERS:
            if marker in seen:
                continue
            if pattern.search(text):
                seen.add(marker)
                markers.append(marker)
    return markers


def _api_call_is_mounted(call: str) -> bool:
    return any(call == prefix or call.startswith(prefix + "/") or call.startswith(prefix + "?") for prefix in _MOUNTED_API_PREFIXES)


def _resolve_paths(relative_paths: Any) -> list[Path]:
    paths: list[Path] = []
    for item in relative_paths or []:
        text = str(item or "").strip()
        if not text:
            continue
        path = ROOT / text
        paths.append(path)
    return paths


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")
