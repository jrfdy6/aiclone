#!/usr/bin/env python3
"""Build and verify a reproducible, privacy-bounded public source release."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "release" / "public_source_manifest.json"
MANIFEST_SCHEMA = "aiclone_public_source_manifest/v2"
RECEIPT_SCHEMA = "aiclone_public_release/v2"
BUILDER_VERSION = "2.0.2"
METADATA_DIR = ".public-release"
RECEIPT_NAME = "receipt.json"
MANIFEST_COPY_NAME = "manifest.json"

_MANIFEST_KEYS = {
    "schema_version",
    "name",
    "includes",
    "file_mappings",
    "inventory_sha256",
    "excludes",
    "required_paths",
    "third_party_email_metadata_paths",
    "require_private_denylist",
}

_GENERATED_COMPONENTS = {
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}
_FORBIDDEN_COMPONENTS = {
    ".codex",
    ".git",
    ".hg",
    ".railway",
    ".svn",
    ".vercel",
    "artifacts",
    "backups",
    "downloads",
    "interview-prep",
    "keys",
    "logs",
    "media",
    "secrets",
}
_FORBIDDEN_ROOTS = {
    "SOPs",
    "agents",
    "automations",
    "knowledge",
    "memory",
    "workspaces",
}
_FORBIDDEN_PREFIXES = (
    "backend/data",
    "frontend/legacy",
)
_FORBIDDEN_FILE_PATTERNS = (
    "*.db",
    "*.dump",
    "*.key",
    "*.log",
    "*.p12",
    "*.pem",
    "*.pfx",
    "*.sqlite",
    "*.sqlite3",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.zip",
    ".env",
    ".env.*",
    "id_rsa*",
    "*oauth*token*.json",
    "*service-account*.json",
)
_GENERATED_FILE_PATTERNS = (
    "*.pyc",
    "*.pyo",
    "*.tsbuildinfo",
    ".DS_Store",
)
_PUBLIC_BINARY_SUFFIXES = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
    ".woff",
    ".woff2",
}

_EMAIL_RE = re.compile(
    r"\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Z0-9-]+\.)+[A-Z]{2,}\b",
    re.IGNORECASE,
)
_POSIX_USER_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])/(?:Users|home)/[A-Za-z0-9._-]+(?:/[^\s\"'`<>]*)?",
    re.IGNORECASE,
)
_WINDOWS_USER_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])[A-Z]:(?:\\+|/+)(?:Users)(?:\\+|/+)[A-Za-z0-9._-]+",
    re.IGNORECASE,
)
_CREDENTIAL_LITERAL_RE = re.compile(
    r"\b(?:api[_-]?key|access[_-]?key|client[_-]?secret|password|passwd|private[_-]?key|secret|token)\b"
    r"\s*(?:=|:)\s*(?P<quote>['\"])(?P<value>[^'\"\r\n]{8,})(?P=quote)",
    re.IGNORECASE,
)
_UNQUOTED_ENV_CREDENTIAL_RE = re.compile(
    r"(?m)^\s*(?:export\s+)?"
    r"(?P<key>(?:[A-Z][A-Z0-9_]*_)?(?:API_KEY|PASSWORD|PASSWD|TOKEN|SECRET|PRIVATE_KEY|DATABASE_URL|REDIS_URL))"
    r"\s*(?:=|:)\s*(?P<value>[^\s#]+)"
)
_UNQUOTED_YAML_CREDENTIAL_RE = re.compile(
    r"(?im)^\s*(?:api[_-]?key|access[_-]?key|client[_-]?secret|password|passwd|private[_-]?key|secret|token|database[_-]?url|redis[_-]?url)"
    r"\s*:\s*(?P<value>[^\s#]+)"
)
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key_material",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    (
        "openai_token",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{25,}\b"),
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    ),
    (
        "stripe_live_key",
        re.compile(r"\b(?:rk|sk)_live_[0-9A-Za-z]{16,}\b"),
    ),
    (
        "bearer_token_literal",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{24,}\b", re.IGNORECASE),
    ),
    (
        "credentialed_url",
        re.compile(
            r"\b(?:https?|postgres(?:ql)?|mysql|mariadb|redis|rediss|mongodb(?:\+srv)?|amqp|amqps)://"
            r"[^/@\s:]+:[^/@\s]+@",
            re.IGNORECASE,
        ),
    ),
)
_SAFE_CREDENTIAL_PLACEHOLDERS = {
    "<redacted>",
    "<replace-me>",
    "changeme",
    "dummy-value",
    "example-only",
    "not-a-secret",
    "placeholder",
    "replace-me",
    "test-only",
}
_RESERVED_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
}
_RESERVED_EMAIL_SUFFIXES = (
    ".example",
    ".invalid",
    ".localhost",
    ".test",
)
_REGEX_STRUCTURAL_ESCAPE_RE = re.compile(
    r"\\(?:[AbBdDsSwWZ]|[fnrtv]|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})"
)


class PublicReleaseError(RuntimeError):
    """Raised when a public candidate cannot be built or verified safely."""


@dataclass(frozen=True, order=True)
class PolicyViolation:
    path: str
    code: str


class PublicReleasePolicyError(PublicReleaseError):
    """A privacy policy failure that never carries matched source content."""

    def __init__(self, violations: Iterable[PolicyViolation]):
        self.violations = tuple(sorted(set(violations)))
        summary = "; ".join(f"{item.path} [{item.code}]" for item in self.violations)
        super().__init__(
            f"public release rejected {len(self.violations)} policy issue(s)"
            + (f": {summary}" if summary else "")
        )


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _path_chain_contains_symlink(path: Path) -> bool:
    current = _lexical_absolute(path)
    return current.is_symlink() or current.parent.is_symlink()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: Any, *, field: str, allow_glob: bool = False) -> str:
    if not isinstance(value, str):
        raise PublicReleaseError(f"manifest field {field!r} must contain strings")
    raw = value.strip().replace("\\", "/")
    parsed = PurePosixPath(raw)
    if not raw or raw == "." or parsed.is_absolute() or ".." in parsed.parts:
        raise PublicReleaseError(f"manifest field {field!r} contains an unsafe path")
    if not allow_glob and any(character in raw for character in "*?["):
        raise PublicReleaseError(f"manifest field {field!r} must use exact paths")
    return parsed.as_posix()


def load_manifest(path: Path) -> tuple[dict[str, Any], str, bytes]:
    if _path_chain_contains_symlink(path):
        raise PublicReleaseError("public release manifest path must not traverse a symlink")
    manifest_path = path.expanduser().resolve(strict=True)
    if not manifest_path.is_file():
        raise PublicReleaseError("public release manifest must be a regular file")
    raw = manifest_path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicReleaseError("public release manifest must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != MANIFEST_SCHEMA:
        raise PublicReleaseError(f"public release manifest must use {MANIFEST_SCHEMA}")
    unexpected = set(payload) - _MANIFEST_KEYS
    if unexpected:
        raise PublicReleaseError("public release manifest contains unsupported fields")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise PublicReleaseError("public release manifest requires a non-empty name")
    for field in ("includes", "required_paths"):
        values = payload.get(field)
        if not isinstance(values, list) or not values:
            raise PublicReleaseError(f"public release manifest field {field!r} must be non-empty")
        payload[field] = [_safe_relative_path(value, field=field) for value in values]
    excludes = payload.get("excludes", [])
    if not isinstance(excludes, list):
        raise PublicReleaseError("public release manifest field 'excludes' must be a list")
    payload["excludes"] = [
        _safe_relative_path(value, field="excludes", allow_glob=True)
        for value in excludes
    ]
    mappings = payload.get("file_mappings", {})
    if not isinstance(mappings, dict):
        raise PublicReleaseError("manifest field 'file_mappings' must be an object")
    normalized_mappings: dict[str, str] = {}
    for source, target in mappings.items():
        safe_source = _safe_relative_path(source, field="file_mappings")
        safe_target = _safe_relative_path(target, field="file_mappings")
        if safe_source == safe_target:
            raise PublicReleaseError("file_mappings must rename the source path")
        normalized_mappings[safe_source] = safe_target
    if not set(normalized_mappings).issubset(set(payload["includes"])):
        raise PublicReleaseError("file_mappings sources must be exact manifest includes")
    if len(set(normalized_mappings.values())) != len(normalized_mappings):
        raise PublicReleaseError("file_mappings destinations must be unique")
    payload["file_mappings"] = normalized_mappings
    inventory_sha256 = payload.get("inventory_sha256")
    if not isinstance(inventory_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", inventory_sha256.strip().lower()
    ):
        raise PublicReleaseError("inventory_sha256 must be a SHA-256 digest")
    payload["inventory_sha256"] = inventory_sha256.strip().lower()
    email_paths = payload.get("third_party_email_metadata_paths", [])
    if not isinstance(email_paths, list):
        raise PublicReleaseError(
            "public release manifest field 'third_party_email_metadata_paths' must be a list"
        )
    payload["third_party_email_metadata_paths"] = [
        _safe_relative_path(value, field="third_party_email_metadata_paths")
        for value in email_paths
    ]
    require_denylist = payload.get("require_private_denylist", False)
    if not isinstance(require_denylist, bool):
        raise PublicReleaseError("require_private_denylist must be true or false")
    payload["require_private_denylist"] = require_denylist
    return payload, _sha256_bytes(raw), raw


def _matches_exclude(relative_path: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if relative_path == prefix or relative_path.startswith(f"{prefix}/"):
                return True
        if fnmatch.fnmatchcase(relative_path, pattern):
            return True
    return False


def _generated_reason(relative_path: str) -> str | None:
    parts = PurePosixPath(relative_path).parts
    if any(
        part in _GENERATED_COMPONENTS
        or part == "venv"
        or part.startswith(".venv")
        for part in parts
    ):
        return "generated_dependency_or_cache"
    name = parts[-1]
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in _GENERATED_FILE_PATTERNS):
        return "generated_file"
    return None


def _forbidden_path_reason(relative_path: str) -> str | None:
    parts = PurePosixPath(relative_path).parts
    if not parts:
        return "invalid_path"
    if parts[0] in _FORBIDDEN_ROOTS:
        return "private_root"
    if any(part in _FORBIDDEN_COMPONENTS for part in parts):
        return "private_or_platform_metadata"
    if any(
        relative_path == prefix or relative_path.startswith(f"{prefix}/")
        for prefix in _FORBIDDEN_PREFIXES
    ):
        return "private_or_legacy_path"
    name = parts[-1]
    if name == ".env.example":
        return None
    if any(fnmatch.fnmatchcase(name.lower(), pattern.lower()) for pattern in _FORBIDDEN_FILE_PATTERNS):
        return "credential_or_private_artifact"
    return None


def _git_portable_mode(mode: int) -> int:
    """Return the only file-mode distinction represented by a Git tree."""

    return 0o755 if mode & 0o111 else 0o644


def _record(path: Path, relative_path: str) -> dict[str, Any]:
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise PublicReleasePolicyError(
            [PolicyViolation(relative_path, "non_regular_file")]
        )
    return {
        "path": relative_path,
        "sha256": _sha256_file(path),
        "size": info.st_size,
        "mode": _git_portable_mode(info.st_mode),
    }


def load_private_literals(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    try:
        if _path_chain_contains_symlink(path):
            raise PublicReleaseError("private literal denylist path must not traverse a symlink")
        denylist_path = path.expanduser().resolve(strict=True)
        if not denylist_path.is_file():
            raise PublicReleaseError("private literal denylist must be a regular file")
        raw = denylist_path.read_text(encoding="utf-8")
    except PublicReleaseError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        raise PublicReleaseError("private literal denylist could not be read as UTF-8") from exc
    values: list[str] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        normalized = _normalize_private_text(value)
        if len(normalized.replace(" ", "")) < 2:
            raise PublicReleaseError(
                f"private literal denylist entry on line {line_number} is too short to match safely"
            )
        values.append(value)
    if not values:
        raise PublicReleaseError("private literal denylist contains no usable entries")
    return tuple(dict.fromkeys(values))


def _email_domain_is_reserved(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in _RESERVED_EMAIL_DOMAINS or domain.endswith(_RESERVED_EMAIL_SUFFIXES)


def _normalize_private_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()


def _normalize_regex_obfuscated_private_text(value: str) -> str:
    """Remove regex-only structure that could split a denylisted literal."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = _REGEX_STRUCTURAL_ESCAPE_RE.sub(" ", normalized)
    normalized = normalized.replace("_", " ")
    return re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()


def _contains_private_literal(value: str, private_literals: Sequence[str]) -> bool:
    normalized_lines: list[str] = []
    seen_normalized_lines: set[str] = set()
    for line in value.splitlines() or [value]:
        for normalized in (
            _normalize_private_text(line),
            _normalize_regex_obfuscated_private_text(line),
        ):
            if normalized and normalized not in seen_normalized_lines:
                seen_normalized_lines.add(normalized)
                normalized_lines.append(normalized)
    for normalized_value in normalized_lines:
        padded_value = f" {normalized_value} "
        for literal in private_literals:
            normalized_literal = _normalize_private_text(literal)
            if not normalized_literal:
                continue
            compact_length = len(normalized_literal.replace(" ", ""))
            if compact_length < 4:
                if f" {normalized_literal} " in padded_value:
                    return True
                continue
            if normalized_literal in normalized_value:
                return True
    return False


def _credential_literal_is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'\"[],").lower()
    if normalized in _SAFE_CREDENTIAL_PLACEHOLDERS:
        return True
    return (
        (normalized.startswith("<") and normalized.endswith(">"))
        or (normalized.startswith("${") and normalized.endswith("}"))
        or normalized.startswith("${{")
        or bool(re.fullmatch(r"\$[A-Z_][A-Z0-9_]*", normalized, re.IGNORECASE))
        or normalized in {"", "disabled", "false", "none", "null", "true"}
    )


def _safe_violation_path(relative_path: str, private_literals: Sequence[str]) -> str:
    if _contains_private_literal(relative_path, private_literals):
        return "[redacted-private-path]"
    if any(not _email_domain_is_reserved(match.group(0)) for match in _EMAIL_RE.finditer(relative_path)):
        return "[redacted-sensitive-path]"
    if any(pattern.search(relative_path) for _, pattern in _SECRET_PATTERNS):
        return "[redacted-sensitive-path]"
    return relative_path


def scan_bytes_content(
    data: bytes,
    relative_path: str,
    *,
    third_party_email_metadata_paths: set[str],
    private_literals: Sequence[str],
) -> tuple[PolicyViolation, ...]:
    violations: set[PolicyViolation] = set()

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if PurePosixPath(relative_path).suffix.lower() not in _PUBLIC_BINARY_SUFFIXES:
            violations.add(PolicyViolation(relative_path, "unreviewed_binary_file"))
        return tuple(sorted(violations))

    if _contains_private_literal(text, private_literals):
        violations.add(PolicyViolation(relative_path, "private_literal"))

    if _POSIX_USER_PATH_RE.search(text):
        violations.add(PolicyViolation(relative_path, "absolute_user_path"))
    if _WINDOWS_USER_PATH_RE.search(text):
        violations.add(PolicyViolation(relative_path, "absolute_windows_user_path"))

    if relative_path not in third_party_email_metadata_paths:
        if any(not _email_domain_is_reserved(match.group(0)) for match in _EMAIL_RE.finditer(text)):
            violations.add(PolicyViolation(relative_path, "non_reserved_email"))

    for code, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            violations.add(PolicyViolation(relative_path, code))

    if any(
        not _credential_literal_is_placeholder(match.group("value"))
        for match in _CREDENTIAL_LITERAL_RE.finditer(text)
    ):
        violations.add(PolicyViolation(relative_path, "credential_literal_assignment"))
    unquoted_matches = list(_UNQUOTED_ENV_CREDENTIAL_RE.finditer(text))
    if relative_path.lower().endswith((".yaml", ".yml")):
        unquoted_matches.extend(_UNQUOTED_YAML_CREDENTIAL_RE.finditer(text))
    if any(
        not _credential_literal_is_placeholder(match.group("value"))
        for match in unquoted_matches
    ):
        violations.add(PolicyViolation(relative_path, "unquoted_credential_assignment"))

    return tuple(sorted(violations))


def scan_file_content(
    path: Path,
    relative_path: str,
    *,
    third_party_email_metadata_paths: set[str],
    private_literals: Sequence[str],
) -> tuple[PolicyViolation, ...]:
    return scan_bytes_content(
        path.read_bytes(),
        relative_path,
        third_party_email_metadata_paths=third_party_email_metadata_paths,
        private_literals=private_literals,
    )


def collect_source_files(
    source_root: Path,
    manifest: dict[str, Any],
    *,
    private_literals: Sequence[str] = (),
    enforce_inventory: bool = True,
    source_is_projection: bool = False,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    if _path_chain_contains_symlink(source_root):
        raise PublicReleaseError("source root path must not traverse a symlink")
    root = source_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise PublicReleaseError("source root must be a regular directory")
    collected: dict[str, tuple[Path, dict[str, Any]]] = {}
    violations: set[PolicyViolation] = set()
    excludes = tuple(manifest["excludes"])
    email_metadata_paths = set(manifest["third_party_email_metadata_paths"])
    file_mappings = dict(manifest["file_mappings"])
    used_mappings: set[str] = set()

    if manifest["require_private_denylist"] and not private_literals:
        raise PublicReleaseError("this public manifest requires an external private literal denylist")

    def add_file(path: Path, relative_path: str) -> None:
        violation_path = _safe_violation_path(relative_path, private_literals)
        if violation_path != relative_path:
            code = (
                "private_literal_in_path"
                if violation_path == "[redacted-private-path]"
                else "sensitive_literal_in_path"
            )
            violations.add(PolicyViolation(violation_path, code))
            return
        forbidden = _forbidden_path_reason(relative_path)
        if forbidden:
            violations.add(PolicyViolation(violation_path, forbidden))
            return
        generated = _generated_reason(relative_path)
        if generated:
            if not _matches_exclude(relative_path, excludes):
                violations.add(PolicyViolation(relative_path, generated))
            return
        if _matches_exclude(relative_path, excludes):
            return
        if path.is_symlink():
            violations.add(PolicyViolation(relative_path, "symlink"))
            return
        if not path.is_file():
            violations.add(PolicyViolation(relative_path, "non_regular_file"))
            return
        if relative_path in collected:
            violations.add(PolicyViolation(relative_path, "duplicate_output_path"))
            return
        violations.update(
            scan_file_content(
                path,
                relative_path,
                third_party_email_metadata_paths=email_metadata_paths,
                private_literals=private_literals,
            )
        )
        collected[relative_path] = (path, _record(path, relative_path))

    for include in manifest["includes"]:
        violation_path = _safe_violation_path(include, private_literals)
        if violation_path != include:
            code = (
                "private_literal_in_path"
                if violation_path == "[redacted-private-path]"
                else "sensitive_literal_in_path"
            )
            violations.add(PolicyViolation(violation_path, code))
            continue
        include_reason = _forbidden_path_reason(include)
        if include_reason:
            violations.add(PolicyViolation(violation_path, include_reason))
            continue
        source_relative_path = (
            file_mappings[include]
            if source_is_projection and include in file_mappings
            else include
        )
        source = root / source_relative_path
        if source.is_symlink():
            violations.add(PolicyViolation(include, "symlink"))
            continue
        if not source.exists():
            violations.add(PolicyViolation(include, "missing_allowlisted_path"))
            continue
        if source.is_file():
            mapped_path = file_mappings.get(include, include)
            mapped_violation_path = _safe_violation_path(mapped_path, private_literals)
            mapped_reason = _forbidden_path_reason(mapped_path)
            if mapped_violation_path != mapped_path:
                violations.add(PolicyViolation(mapped_violation_path, "private_literal_in_path"))
                continue
            if mapped_reason:
                violations.add(PolicyViolation(mapped_violation_path, mapped_reason))
                continue
            if include in file_mappings:
                used_mappings.add(include)
            add_file(source, mapped_path)
            continue
        if not source.is_dir():
            violations.add(PolicyViolation(include, "non_regular_file"))
            continue
        if include in file_mappings:
            violations.add(PolicyViolation(include, "mapped_source_must_be_file"))
            continue
        for current, dirnames, filenames in os.walk(source, followlinks=False):
            current_path = Path(current)
            kept_dirs: list[str] = []
            for dirname in sorted(dirnames):
                child = current_path / dirname
                relative = child.relative_to(root).as_posix()
                child_violation_path = _safe_violation_path(relative, private_literals)
                if child_violation_path != relative:
                    code = (
                        "private_literal_in_path"
                        if child_violation_path == "[redacted-private-path]"
                        else "sensitive_literal_in_path"
                    )
                    violations.add(PolicyViolation(child_violation_path, code))
                    continue
                forbidden = _forbidden_path_reason(relative)
                if forbidden:
                    violations.add(PolicyViolation(child_violation_path, forbidden))
                    continue
                generated = _generated_reason(relative)
                if generated:
                    if not _matches_exclude(relative, excludes):
                        violations.add(PolicyViolation(relative, generated))
                    continue
                if _matches_exclude(relative, excludes):
                    continue
                if child.is_symlink():
                    violations.add(PolicyViolation(relative, "symlink"))
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs
            for filename in sorted(filenames):
                child = current_path / filename
                add_file(child, child.relative_to(root).as_posix())

    if violations:
        raise PublicReleasePolicyError(violations)
    if used_mappings != set(file_mappings):
        raise PublicReleaseError("one or more public file mappings were not applied")
    missing_required = sorted(set(manifest["required_paths"]) - set(collected))
    if missing_required:
        raise PublicReleasePolicyError(
            PolicyViolation(path, "missing_required_path") for path in missing_required
        )
    metadata_email_paths = email_metadata_paths - set(collected)
    if metadata_email_paths:
        raise PublicReleasePolicyError(
            PolicyViolation(path, "unused_email_metadata_exception")
            for path in metadata_email_paths
        )
    inventory_sha256 = _path_inventory_hash(collected)
    if enforce_inventory and inventory_sha256 != manifest["inventory_sha256"]:
        raise PublicReleasePolicyError(
            [PolicyViolation("[public-inventory]", "inventory_sha256_mismatch")]
        )
    return dict(sorted(collected.items()))


def _path_inventory_hash(paths: Iterable[str]) -> str:
    canonical = json.dumps(
        sorted(paths),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _tree_hash(records: Sequence[dict[str, Any]]) -> str:
    canonical = json.dumps(
        list(records),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _validate_candidate_target(source_root: Path, candidate_root: Path) -> Path:
    source = source_root.expanduser().resolve(strict=True)
    target = candidate_root.expanduser()
    if _path_chain_contains_symlink(target.parent):
        raise PublicReleaseError("candidate parent chain must not traverse a symlink")
    if target.exists() or target.is_symlink():
        raise PublicReleaseError("candidate root must not already exist")
    resolved = target.resolve(strict=False)
    broad_roots = {Path("/"), Path.home().resolve(), source}
    if resolved in broad_roots or source in resolved.parents or resolved in source.parents:
        raise PublicReleaseError("candidate root must be isolated from source and broad system roots")
    ancestor = resolved.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if ancestor.is_symlink():
        raise PublicReleaseError("candidate parent chain must not traverse a symlink")
    return resolved


def build_candidate(
    *,
    source_root: Path,
    candidate_root: Path,
    manifest_path: Path,
    expected_manifest_sha256: str,
    private_denylist_path: Path | None = None,
) -> dict[str, Any]:
    source = source_root.expanduser().resolve(strict=True)
    target = _validate_candidate_target(source, candidate_root)
    manifest, manifest_sha256, manifest_raw = load_manifest(manifest_path)
    expected = expected_manifest_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != manifest_sha256:
        raise PublicReleaseError("expected manifest hash does not match the exact manifest bytes")
    private_literals = load_private_literals(private_denylist_path)
    manifest_violations = scan_file_content(
        manifest_path.expanduser().resolve(strict=True),
        "public_source_manifest.json",
        third_party_email_metadata_paths=set(),
        private_literals=private_literals,
    )
    if manifest_violations:
        raise PublicReleasePolicyError(manifest_violations)
    source_files = collect_source_files(
        source,
        manifest,
        private_literals=private_literals,
    )
    records = [record for _, record in source_files.values()]
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "builder_version": BUILDER_VERSION,
        "manifest": {
            "name": manifest["name"],
            "sha256": manifest_sha256,
        },
        "policy": {
            "content_scan": "high_confidence_public_boundary/v1",
            "inventory_sha256": manifest["inventory_sha256"],
            "private_denylist_applied": bool(private_literals),
            "private_denylist_required": bool(manifest["require_private_denylist"]),
        },
        "candidate": {
            "file_count": len(records),
            "tree_sha256": _tree_hash(records),
            "files": records,
        },
    }
    receipt_raw = (
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    receipt_sha256 = _sha256_bytes(receipt_raw)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.building-", dir=target.parent)
    )
    try:
        for relative_path, (source_path, expected_record) in source_files.items():
            destination = temporary / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination, follow_symlinks=False)
            destination.chmod(expected_record["mode"])
            if _record(destination, relative_path) != expected_record:
                raise PublicReleaseError("source changed while the public candidate was copied")
        metadata_root = temporary / METADATA_DIR
        metadata_root.mkdir(mode=0o755)
        (metadata_root / MANIFEST_COPY_NAME).write_bytes(manifest_raw)
        (metadata_root / RECEIPT_NAME).write_bytes(receipt_raw)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return {
        "ok": True,
        "file_count": len(records),
        "tree_sha256": receipt["candidate"]["tree_sha256"],
        "receipt_sha256": receipt_sha256,
        "manifest_sha256": manifest_sha256,
        "private_denylist_applied": bool(private_literals),
    }


def _candidate_file_paths(candidate_root: Path) -> set[str]:
    paths: set[str] = set()
    for current, dirnames, filenames in os.walk(candidate_root, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(candidate_root)
        if relative_dir == Path(METADATA_DIR):
            dirnames[:] = []
            continue
        if METADATA_DIR in relative_dir.parts:
            dirnames[:] = []
            continue
        for dirname in list(dirnames):
            child = current_path / dirname
            relative = child.relative_to(candidate_root).as_posix()
            if child.is_symlink():
                raise PublicReleasePolicyError([PolicyViolation(relative, "symlink")])
        for filename in filenames:
            child = current_path / filename
            relative = child.relative_to(candidate_root).as_posix()
            if child.is_symlink() or not child.is_file():
                raise PublicReleasePolicyError(
                    [PolicyViolation(relative, "non_regular_file")]
                )
            paths.add(relative)
    return paths


def verify_candidate(
    *,
    candidate_root: Path,
    expected_receipt_sha256: str,
    private_denylist_path: Path | None = None,
) -> dict[str, Any]:
    if _path_chain_contains_symlink(candidate_root):
        raise PublicReleaseError("candidate root path must not traverse a symlink")
    root = candidate_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise PublicReleaseError("candidate root must be a regular directory")
    metadata_root = root / METADATA_DIR
    receipt_path = metadata_root / RECEIPT_NAME
    manifest_path = metadata_root / MANIFEST_COPY_NAME
    expected_metadata = {RECEIPT_NAME, MANIFEST_COPY_NAME}
    if not metadata_root.is_dir() or metadata_root.is_symlink():
        raise PublicReleaseError("candidate receipt metadata is unavailable")
    metadata_files = {
        path.name
        for path in metadata_root.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    if metadata_files != expected_metadata or any(path.is_dir() for path in metadata_root.iterdir()):
        raise PublicReleaseError("candidate receipt metadata contains unexpected entries")
    receipt_raw = receipt_path.read_bytes()
    expected_receipt = expected_receipt_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_receipt):
        raise PublicReleaseError("expected receipt hash must be a SHA-256 digest")
    if _sha256_bytes(receipt_raw) != expected_receipt:
        raise PublicReleaseError("candidate receipt hash does not match")
    try:
        receipt = json.loads(receipt_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicReleaseError("candidate receipt is invalid") from exc
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise PublicReleaseError("candidate receipt schema is invalid")
    if receipt.get("builder_version") != BUILDER_VERSION:
        raise PublicReleaseError("candidate builder version is unsupported")

    manifest, manifest_sha256, _ = load_manifest(manifest_path)
    if manifest_sha256 != receipt.get("manifest", {}).get("sha256"):
        raise PublicReleaseError("candidate manifest does not match its receipt")
    private_literals = load_private_literals(private_denylist_path)
    manifest_violations = scan_file_content(
        manifest_path,
        "public_source_manifest.json",
        third_party_email_metadata_paths=set(),
        private_literals=private_literals,
    )
    if manifest_violations:
        raise PublicReleasePolicyError(manifest_violations)
    policy = receipt.get("policy") if isinstance(receipt.get("policy"), dict) else {}
    if (policy.get("private_denylist_required") or policy.get("private_denylist_applied")) and not private_literals:
        raise PublicReleaseError("candidate verification requires the external private literal denylist")

    source_files = collect_source_files(
        root,
        manifest,
        private_literals=private_literals,
        source_is_projection=True,
    )
    records = [record for _, record in source_files.values()]
    actual_paths = _candidate_file_paths(root)
    expected_paths = set(source_files)
    if actual_paths != expected_paths:
        raise PublicReleaseError("candidate contains missing or unexpected public files")
    candidate_receipt = receipt.get("candidate")
    if not isinstance(candidate_receipt, dict):
        raise PublicReleaseError("candidate receipt is incomplete")
    if records != candidate_receipt.get("files"):
        raise PublicReleaseError("candidate files no longer match the receipt")
    tree_sha256 = _tree_hash(records)
    if tree_sha256 != candidate_receipt.get("tree_sha256"):
        raise PublicReleaseError("candidate tree hash no longer matches the receipt")
    if len(records) != candidate_receipt.get("file_count"):
        raise PublicReleaseError("candidate file count no longer matches the receipt")
    return {
        "ok": True,
        "file_count": len(records),
        "tree_sha256": tree_sha256,
        "receipt_sha256": expected_receipt,
        "manifest_sha256": manifest_sha256,
        "private_denylist_applied": bool(private_literals),
    }


def _run_git(root: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", os.fspath(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PublicReleaseError("public source tree Git verification failed") from exc
    return completed.stdout


def _git_identity_is_noreply(email: str) -> bool:
    normalized = email.strip().casefold()
    return normalized.endswith("@users.noreply.github.com")


def _verify_git_identity(
    *,
    name: str,
    email: str,
    expected_name: str | None,
    require_noreply_email: bool,
    role: str,
) -> None:
    if expected_name is not None and name.strip() != expected_name:
        raise PublicReleaseError(f"public Git {role} name is not the approved release identity")
    if require_noreply_email and not _git_identity_is_noreply(email):
        raise PublicReleaseError(f"public Git {role} email must use GitHub no-reply")


def _scan_reachable_git_history(
    *,
    root: Path,
    private_literals: Sequence[str],
    third_party_email_metadata_paths: set[str],
    expected_git_name: str | None,
    require_noreply_email: bool,
) -> int:
    commits = [
        line
        for line in _run_git(root, "rev-list", "--reverse", "HEAD")
        .decode("ascii")
        .splitlines()
        if line
    ]
    if not commits:
        raise PublicReleaseError("public Git lineage contains no commits")

    seen_blobs: set[str] = set()
    violations: set[PolicyViolation] = set()
    for commit in commits:
        identity_fields = _run_git(
            root,
            "show",
            "-s",
            "--format=%an%n%ae%n%cn%n%ce",
            commit,
        ).decode("utf-8", errors="strict").splitlines()
        if len(identity_fields) != 4:
            raise PublicReleaseError("public Git commit identity metadata is malformed")
        _verify_git_identity(
            name=identity_fields[0],
            email=identity_fields[1],
            expected_name=expected_git_name,
            require_noreply_email=require_noreply_email,
            role="author",
        )
        _verify_git_identity(
            name=identity_fields[2],
            email=identity_fields[3],
            expected_name=expected_git_name,
            require_noreply_email=require_noreply_email,
            role="committer",
        )
        violations.update(
            scan_bytes_content(
                _run_git(root, "show", "-s", "--format=%B", commit),
                ".git-metadata/commit-message.txt",
                third_party_email_metadata_paths=set(),
                private_literals=private_literals,
            )
        )

        tree = _run_git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            try:
                metadata, raw_path = entry.split(b"\t", 1)
                _, object_type, object_id = metadata.decode("ascii").split(" ", 2)
                relative_path = raw_path.decode("utf-8")
            except (UnicodeDecodeError, ValueError) as exc:
                raise PublicReleaseError("public Git tree metadata is malformed") from exc
            violation_path = _safe_violation_path(relative_path, private_literals)
            if violation_path != relative_path:
                violations.add(PolicyViolation(violation_path, "sensitive_literal_in_history_path"))
                continue
            forbidden = _forbidden_path_reason(relative_path)
            generated = _generated_reason(relative_path)
            if forbidden:
                violations.add(PolicyViolation(relative_path, forbidden))
                continue
            if generated:
                violations.add(PolicyViolation(relative_path, generated))
                continue
            if object_type != "blob":
                violations.add(PolicyViolation(relative_path, "non_blob_history_entry"))
                continue
            if object_id in seen_blobs:
                continue
            seen_blobs.add(object_id)
            violations.update(
                scan_bytes_content(
                    _run_git(root, "cat-file", "blob", object_id),
                    relative_path,
                    third_party_email_metadata_paths=third_party_email_metadata_paths,
                    private_literals=private_literals,
                )
            )

    if violations:
        raise PublicReleasePolicyError(violations)
    return len(commits)


def verify_release_tag(
    *,
    source_root: Path,
    tag: str,
    private_denylist_path: Path | None = None,
    expected_git_name: str | None = None,
    require_noreply_email: bool = False,
) -> dict[str, Any]:
    root = source_root.expanduser().resolve(strict=True)
    if not re.fullmatch(r"public-v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise PublicReleaseError("public release tag name is invalid")
    if _run_git(root, "cat-file", "-t", f"refs/tags/{tag}").strip() != b"tag":
        raise PublicReleaseError("public release tag must be annotated")
    target = _run_git(root, "rev-parse", f"refs/tags/{tag}^{{}}").strip()
    head = _run_git(root, "rev-parse", "HEAD").strip()
    if target != head:
        raise PublicReleaseError("public release tag target does not match the verified checkout")

    raw_tag = _run_git(root, "cat-file", "tag", f"refs/tags/{tag}")
    header, separator, message = raw_tag.partition(b"\n\n")
    if not separator:
        raise PublicReleaseError("annotated public release tag metadata is malformed")
    tagger_lines = [line for line in header.splitlines() if line.startswith(b"tagger ")]
    if len(tagger_lines) != 1:
        raise PublicReleaseError("annotated public release tagger metadata is malformed")
    match = re.fullmatch(rb"tagger (.+) <([^<>]+)> [0-9]+ [+-][0-9]{4}", tagger_lines[0])
    if not match:
        raise PublicReleaseError("annotated public release tagger identity is malformed")
    try:
        tagger_name = match.group(1).decode("utf-8")
        tagger_email = match.group(2).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicReleaseError("annotated public release tagger identity is malformed") from exc
    _verify_git_identity(
        name=tagger_name,
        email=tagger_email,
        expected_name=expected_git_name,
        require_noreply_email=require_noreply_email,
        role="tagger",
    )
    private_literals = load_private_literals(private_denylist_path)
    violations = scan_bytes_content(
        message,
        ".git-metadata/tag-message.txt",
        third_party_email_metadata_paths=set(),
        private_literals=private_literals,
    )
    if violations:
        raise PublicReleasePolicyError(violations)
    return {"ok": True, "tag": tag, "target_matches_head": True}


def verify_source_tree(
    *,
    source_root: Path,
    manifest_path: Path,
    private_denylist_path: Path | None = None,
    expected_lineage_root: str | None = None,
    expected_git_name: str | None = None,
    require_noreply_email: bool = False,
) -> dict[str, Any]:
    """Verify that a Git checkout is exactly one receipt-bound public projection."""

    if _path_chain_contains_symlink(source_root):
        raise PublicReleaseError("source root path must not traverse a symlink")
    root = source_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise PublicReleaseError("source root must be a regular directory")

    git_root = Path(os.fsdecode(_run_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    if git_root != root:
        raise PublicReleaseError("public source verification must run at the Git root")
    if _run_git(root, "status", "--porcelain=v1", "--untracked-files=no").strip():
        raise PublicReleaseError("Git contains uncommitted tracked-file changes")

    manifest, manifest_sha256, source_manifest_raw = load_manifest(manifest_path)
    private_literals = load_private_literals(private_denylist_path)
    manifest_violations = scan_file_content(
        manifest_path.expanduser().resolve(strict=True),
        "public_source_manifest.json",
        third_party_email_metadata_paths=set(),
        private_literals=private_literals,
    )
    if manifest_violations:
        raise PublicReleasePolicyError(manifest_violations)
    source_files = collect_source_files(
        root,
        manifest,
        private_literals=private_literals,
        source_is_projection=True,
    )
    records = [record for _, record in source_files.values()]

    metadata_root = root / METADATA_DIR
    receipt_path = metadata_root / RECEIPT_NAME
    manifest_copy_path = metadata_root / MANIFEST_COPY_NAME
    if (
        not metadata_root.is_dir()
        or metadata_root.is_symlink()
        or receipt_path.is_symlink()
        or manifest_copy_path.is_symlink()
        or not receipt_path.is_file()
        or not manifest_copy_path.is_file()
    ):
        raise PublicReleaseError("committed public receipt metadata is unavailable")
    metadata_entries = {entry.name for entry in metadata_root.iterdir()}
    if metadata_entries != {RECEIPT_NAME, MANIFEST_COPY_NAME}:
        raise PublicReleaseError("committed public receipt metadata contains unexpected entries")
    if manifest_copy_path.read_bytes() != source_manifest_raw:
        raise PublicReleaseError("committed public manifest copy does not match source")
    for path, relative in (
        (manifest_copy_path, f"{METADATA_DIR}/{MANIFEST_COPY_NAME}"),
        (receipt_path, f"{METADATA_DIR}/{RECEIPT_NAME}"),
    ):
        violations = scan_file_content(
            path,
            relative,
            third_party_email_metadata_paths=set(),
            private_literals=private_literals,
        )
        if violations:
            raise PublicReleasePolicyError(violations)

    receipt_raw = receipt_path.read_bytes()
    try:
        receipt = json.loads(receipt_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicReleaseError("committed public receipt is invalid") from exc
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise PublicReleaseError("committed public receipt schema is invalid")
    if receipt.get("builder_version") != BUILDER_VERSION:
        raise PublicReleaseError("committed public receipt builder version is stale")
    if receipt.get("manifest", {}).get("sha256") != manifest_sha256:
        raise PublicReleaseError("committed public receipt has a different manifest")
    candidate_receipt = receipt.get("candidate")
    if not isinstance(candidate_receipt, dict):
        raise PublicReleaseError("committed public receipt is incomplete")
    if candidate_receipt.get("files") != records:
        raise PublicReleaseError("committed public files do not match their receipt")
    if candidate_receipt.get("file_count") != len(records):
        raise PublicReleaseError("committed public receipt file count is stale")
    tree_sha256 = _tree_hash(records)
    if candidate_receipt.get("tree_sha256") != tree_sha256:
        raise PublicReleaseError("committed public receipt tree hash is stale")

    tracked = {
        os.fsdecode(item)
        for item in _run_git(root, "ls-files", "-z").split(b"\0")
        if item
    }
    expected_tracked = set(source_files) | {
        f"{METADATA_DIR}/{MANIFEST_COPY_NAME}",
        f"{METADATA_DIR}/{RECEIPT_NAME}",
    }
    if tracked != expected_tracked:
        raise PublicReleaseError("Git contains missing or unexpected public files")

    roots = [line for line in _run_git(root, "rev-list", "--max-parents=0", "HEAD").decode("ascii").splitlines() if line]
    if len(roots) != 1:
        raise PublicReleaseError("public Git lineage must have exactly one root")
    if expected_lineage_root is not None:
        normalized_expected_root = expected_lineage_root.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", normalized_expected_root):
            raise PublicReleaseError("expected public lineage root is not a Git object id")
        if roots[0].lower() != normalized_expected_root:
            raise PublicReleaseError("public Git lineage does not descend from the approved root")
    try:
        _run_git(root, "cat-file", "-e", f"{roots[0]}:.public-lineage-root")
    except PublicReleaseError as exc:
        raise PublicReleaseError("public Git root is missing its lineage marker") from exc

    commit_count = _scan_reachable_git_history(
        root=root,
        private_literals=private_literals,
        third_party_email_metadata_paths=set(manifest["third_party_email_metadata_paths"]),
        expected_git_name=expected_git_name,
        require_noreply_email=require_noreply_email,
    )

    return {
        "ok": True,
        "file_count": len(records),
        "tree_sha256": tree_sha256,
        "receipt_sha256": _sha256_bytes(receipt_raw),
        "manifest_sha256": manifest_sha256,
        "private_denylist_applied": bool(private_literals),
        "single_root_public_lineage": True,
        "reachable_commit_count": commit_count,
        "history_content_scanned": True,
    }


def _json_report(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    digest_parser = subparsers.add_parser(
        "manifest-sha256",
        help="Print the reviewed manifest digest without reading source files.",
    )
    digest_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)

    inventory_parser = subparsers.add_parser(
        "inventory-sha256",
        help="Print the exact projected path-inventory digest for manifest review.",
    )
    inventory_parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    inventory_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    inventory_parser.add_argument("--private-denylist", type=Path)

    build_parser = subparsers.add_parser("build", help="Build an isolated public candidate.")
    build_parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    build_parser.add_argument("--candidate-root", type=Path, required=True)
    build_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    build_parser.add_argument("--expected-manifest-sha256", required=True)
    build_parser.add_argument("--private-denylist", type=Path)

    verify_parser = subparsers.add_parser("verify", help="Verify an immutable public candidate.")
    verify_parser.add_argument("--candidate-root", type=Path, required=True)
    verify_parser.add_argument("--expected-receipt-sha256", required=True)
    verify_parser.add_argument("--private-denylist", type=Path)

    source_tree_parser = subparsers.add_parser(
        "verify-source-tree",
        help="Verify an exact receipt-bound public Git checkout.",
    )
    source_tree_parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    source_tree_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    source_tree_parser.add_argument("--private-denylist", type=Path)
    source_tree_parser.add_argument("--expected-lineage-root")
    source_tree_parser.add_argument("--expected-git-name")
    source_tree_parser.add_argument("--require-noreply-email", action="store_true")

    tag_parser = subparsers.add_parser(
        "verify-release-tag",
        help="Verify annotated public release tag target, identity, and message metadata.",
    )
    tag_parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    tag_parser.add_argument("--tag", required=True)
    tag_parser.add_argument("--private-denylist", type=Path)
    tag_parser.add_argument("--expected-git-name")
    tag_parser.add_argument("--require-noreply-email", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "manifest-sha256":
            _, digest, _ = load_manifest(args.manifest)
            print(digest)
            return 0
        if args.command == "inventory-sha256":
            manifest, _, _ = load_manifest(args.manifest)
            private_literals = load_private_literals(args.private_denylist)
            source_files = collect_source_files(
                args.source_root,
                manifest,
                private_literals=private_literals,
                enforce_inventory=False,
            )
            print(_path_inventory_hash(source_files))
            return 0
        if args.command == "build":
            _json_report(
                build_candidate(
                    source_root=args.source_root,
                    candidate_root=args.candidate_root,
                    manifest_path=args.manifest,
                    expected_manifest_sha256=args.expected_manifest_sha256,
                    private_denylist_path=args.private_denylist,
                )
            )
            return 0
        if args.command == "verify":
            _json_report(
                verify_candidate(
                    candidate_root=args.candidate_root,
                    expected_receipt_sha256=args.expected_receipt_sha256,
                    private_denylist_path=args.private_denylist,
                )
            )
            return 0
        if args.command == "verify-source-tree":
            _json_report(
                verify_source_tree(
                    source_root=args.source_root,
                    manifest_path=args.manifest,
                    private_denylist_path=args.private_denylist,
                    expected_lineage_root=args.expected_lineage_root,
                    expected_git_name=args.expected_git_name,
                    require_noreply_email=args.require_noreply_email,
                )
            )
            return 0
        if args.command == "verify-release-tag":
            _json_report(
                verify_release_tag(
                    source_root=args.source_root,
                    tag=args.tag,
                    private_denylist_path=args.private_denylist,
                    expected_git_name=args.expected_git_name,
                    require_noreply_email=args.require_noreply_email,
                )
            )
            return 0
    except PublicReleaseError as exc:
        parser.exit(1, f"error: {exc}\n")
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
