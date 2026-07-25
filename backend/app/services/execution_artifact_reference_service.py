"""Safe logical references for execution-result artifacts.

Execution workers need real filesystem paths while materializing results on the
local host.  The control plane does not: it only needs stable, non-sensitive
references that can be shown in PM state and resolved again by an authorized
local worker.
"""
from __future__ import annotations

import hashlib
import re
import urllib.parse
from pathlib import Path


LOGICAL_ARTIFACT_SCHEMES = frozenset({"state", "repo", "workspace", "local-artifact"})
SAFE_RELATIVE_ROOTS = frozenset(
    {
        "automations",
        "backend",
        "dispatch",
        "docs",
        "knowledge",
        "launchd",
        "memory",
        "scripts",
        "workspaces",
    }
)
PRIVATE_PATH_COMPONENTS = frozenset(
    {
        ".codex",
        ".openclaw",
        ".ssh",
        ".config",
    }
)
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_LOCAL_ARTIFACT_PATH_RE = re.compile(r"^/[0-9a-f]{64}$")
_PRIVATE_TEXT_PATH_RE = re.compile(
    r"(?i)(?:"
    r"(?<![A-Za-z0-9])~(?:[A-Za-z0-9._-]+)?[\\/]"
    r"|(?<![A-Za-z0-9])(?:"
    r"/Users/|/home/|/private/|/tmp/|/var/|/Volumes/|/opt/|/etc/|/usr/|"
    r"/Library/|/Applications/|/workspace/|/root/|/mnt/"
    r")"
    r"|(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    r"|(?:^|[\\/])(?:\\.codex|\\.openclaw|\\.ssh)(?:[\\/]|$)"
    r")"
)


def _decoded(value: str) -> str:
    decoded = value
    for _ in range(3):
        next_value = urllib.parse.unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return decoded


def _safe_components(value: str) -> list[str]:
    normalized = _decoded(value).replace("\\", "/")
    return [component for component in normalized.split("/") if component]


def _validate_components(components: list[str]) -> None:
    if not components:
        raise ValueError("Artifact reference must identify an artifact.")
    lowered = [component.casefold() for component in components]
    if any(component in {".", ".."} for component in lowered):
        raise ValueError("Artifact reference must not contain traversal components.")
    if any(component in PRIVATE_PATH_COMPONENTS for component in lowered):
        raise ValueError("Artifact reference must not expose a private runtime directory.")
    if any("\x00" in component or any(ord(char) < 32 for char in component) for component in components):
        raise ValueError("Artifact reference contains control characters.")


def validate_remote_execution_artifact_reference(
    value: str,
    *,
    allow_web_url: bool = False,
) -> str:
    """Validate one reference that is safe to persist in the remote control plane.

    Safe legacy repo-relative paths remain accepted. New local writers should
    prefer ``state://``, ``repo://``, or ``workspace://`` references.
    """

    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Artifact reference must not be empty.")
    decoded = _decoded(raw)
    if decoded.startswith(("/", "\\", "~")):
        raise ValueError("Artifact reference must not be an absolute or home-relative path.")
    if _WINDOWS_ABSOLUTE_RE.match(decoded) or decoded.startswith("\\\\"):
        raise ValueError("Artifact reference must not be an absolute path.")

    parsed = urllib.parse.urlsplit(raw)
    scheme = parsed.scheme.casefold()
    if scheme:
        if scheme == "https" and allow_web_url:
            if not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Web artifact reference is malformed.")
            return raw
        if scheme not in LOGICAL_ARTIFACT_SCHEMES:
            raise ValueError("Artifact reference uses an unsupported scheme.")
        if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port is not None:
            raise ValueError("Logical artifact reference contains unsupported URI metadata.")
        if scheme == "local-artifact":
            if parsed.netloc != "sha256" or not _LOCAL_ARTIFACT_PATH_RE.fullmatch(parsed.path):
                raise ValueError("Opaque local artifact reference is malformed.")
            return raw
        components = _safe_components("/".join((parsed.netloc, parsed.path)))
        _validate_components(components)
        return raw

    if "\\" in decoded:
        raise ValueError("Artifact reference must use portable separators.")
    components = _safe_components(decoded)
    _validate_components(components)
    if components[0].casefold() not in SAFE_RELATIVE_ROOTS:
        raise ValueError("Legacy artifact reference must be rooted in an approved project directory.")
    return raw


def contains_private_filesystem_reference(value: str) -> bool:
    """Return whether free text contains an obvious host-private path."""

    return bool(_PRIVATE_TEXT_PATH_RE.search(_decoded(str(value or ""))))


def _logical_uri(scheme: str, relative_path: Path) -> str:
    encoded = urllib.parse.quote(relative_path.as_posix(), safe="/-._~")
    return f"{scheme}://{encoded}"


def encode_local_execution_artifact_reference(
    value: str,
    *,
    state_root: Path,
    project_root: Path,
    allow_web_url: bool = True,
) -> str:
    """Convert a local artifact path to a stable, non-sensitive reference."""

    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Artifact reference must not be empty.")

    try:
        return validate_remote_execution_artifact_reference(raw, allow_web_url=allow_web_url)
    except ValueError:
        pass

    try:
        candidate = Path(raw).expanduser()
    except RuntimeError:
        candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
        for scheme, root in (("state", state_root), ("repo", project_root)):
            resolved_root = Path(root).expanduser().resolve(strict=False)
            try:
                relative = resolved.relative_to(resolved_root)
            except ValueError:
                continue
            return _logical_uri(scheme, relative)

    # The control plane can prove that an external local artifact existed
    # without learning its directory or filename.
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"local-artifact://sha256/{digest}"


def resolve_local_execution_artifact_reference(
    value: str,
    *,
    state_root: Path,
    project_root: Path,
) -> Path | None:
    """Resolve a safe logical reference for an authorized local reader."""

    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urllib.parse.urlsplit(raw)
    scheme = parsed.scheme.casefold()
    if scheme in {"state", "repo", "workspace"}:
        validate_remote_execution_artifact_reference(raw)
        components = _safe_components("/".join((parsed.netloc, parsed.path)))
        if scheme == "state":
            root = Path(state_root)
            relative = Path(*components)
        elif scheme == "repo":
            root = Path(project_root)
            relative = Path(*components)
        else:
            root = Path(state_root) / "workspaces"
            relative = Path(*components)
        resolved_root = root.expanduser().resolve(strict=False)
        candidate = root / relative
        resolved_candidate = candidate.expanduser().resolve(strict=False)
        if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
            return None
        return candidate
    if scheme:
        return None
    try:
        validate_remote_execution_artifact_reference(raw)
    except ValueError:
        return None
    root = Path(project_root)
    candidate = root / Path(raw)
    resolved_root = root.expanduser().resolve(strict=False)
    resolved_candidate = candidate.expanduser().resolve(strict=False)
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        return None
    return candidate
