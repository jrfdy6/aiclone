from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_public_release.py"
SPEC = importlib.util.spec_from_file_location("build_public_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
public_release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = public_release
SPEC.loader.exec_module(public_release)
PUBLIC_TEST_NOREPLY_EMAIL = "public-test" + "@" + "users.noreply.github.com"
APPROVED_PUBLIC_WORKSPACE_REFERENCE_LITERALS = {
    "SOURCE_OF_TRUTH.md",
    "backend/app/services/workspace_registry_service.py",
    "workspaces/linkedin-content-os/README.md",
    "workspaces/linkedin-content-os/docs/editorial_mix.md",
    "workspaces/linkedin-content-os/docs/positioning_contract.md",
}


def _write_manifest(
    source_root: Path,
    *,
    includes: list[str],
    required_paths: list[str] | None = None,
    email_metadata_paths: list[str] | None = None,
    require_private_denylist: bool = False,
    file_mappings: dict[str, str] | None = None,
) -> tuple[Path, str]:
    if required_paths is None:
        discovered_required: list[str] = []
        for include in includes:
            include_path = source_root / include
            if include_path.is_file():
                discovered_required.append(include)
                break
            if include_path.is_dir():
                first_file = next(
                    (path for path in sorted(include_path.rglob("*")) if path.is_file()),
                    None,
                )
                if first_file is not None:
                    discovered_required.append(
                        first_file.relative_to(source_root).as_posix()
                    )
                    break
        required_paths = discovered_required
    mappings = file_mappings or {}
    inventory_paths: list[str] = []
    for include in includes:
        include_path = source_root / include
        if include_path.is_dir():
            inventory_paths.extend(
                path.relative_to(source_root).as_posix()
                for path in sorted(include_path.rglob("*"))
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            )
        else:
            inventory_paths.append(mappings.get(include, include))
    manifest_path = source_root / "public-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": public_release.MANIFEST_SCHEMA,
                "name": "public-test",
                "includes": includes,
                "file_mappings": mappings,
                "inventory_sha256": public_release._path_inventory_hash(inventory_paths),
                "excludes": [
                    "**/__pycache__",
                    "**/__pycache__/**",
                    "**/*.pyc",
                ],
                "required_paths": required_paths,
                "third_party_email_metadata_paths": email_metadata_paths or [],
                "require_private_denylist": require_private_denylist,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _, digest, _ = public_release.load_manifest(manifest_path)
    return manifest_path, digest


def _build(
    source_root: Path,
    candidate_root: Path,
    manifest_path: Path,
    digest: str,
    *,
    private_denylist_path: Path | None = None,
):
    return public_release.build_candidate(
        source_root=source_root,
        candidate_root=candidate_root,
        manifest_path=manifest_path,
        expected_manifest_sha256=digest,
        private_denylist_path=private_denylist_path,
    )


def _safe_source_tree(root: Path) -> None:
    app_root = root / "app"
    app_root.mkdir(parents=True)
    (app_root / "main.py").write_text(
        "CONTACT = 'operator@example.com'\nVALUE = 'public source'\n",
        encoding="utf-8",
    )
    lock_path = root / "frontend" / "package-lock.json"
    lock_path.parent.mkdir(parents=True)
    upstream_email = "maintainer" + "@" + "upstream" + ".dev"
    lock_path.write_text(
        json.dumps({"name": "fixture", "third_party_notice": upstream_email}) + "\n",
        encoding="utf-8",
    )


def _policy_payload(kind: str) -> str:
    if kind == "non_reserved_email":
        return "owner" + "@" + "company" + ".com"
    if kind == "mac_user_path":
        return "/" + "Users" + "/operator/project"
    if kind == "linux_user_path":
        return "/" + "home" + "/operator/project"
    if kind == "windows_user_path":
        return "C:" + "\\" + "Users" + "\\operator\\project"
    if kind == "private_key":
        return "-----BEGIN " + "PRIVATE KEY-----"
    if kind == "github_token":
        return "gh" + "p_" + ("A" * 32)
    if kind == "credential_assignment":
        return "password" + " = \"" + ("A" * 24) + "\""
    if kind == "unquoted_password":
        return "CONTROL_PLANE_" + "PASSWORD=" + ("A" * 24)
    if kind == "yaml_api_key":
        return "api_" + "key: " + ("A" * 24)
    if kind == "database_url":
        return "postgres" + "ql://operator:" + ("A" * 24) + "@database:5432/app"
    raise AssertionError(f"unknown fixture kind: {kind}")


def test_canonical_public_source_excludes_private_workspace_goal_authority() -> None:
    manifest_path = REPO_ROOT / "release" / "public_source_manifest.json"
    manifest, _manifest_sha, _raw = public_release.load_manifest(manifest_path)
    private_authority_path = REPO_ROOT / "workspaces" / "shared-ops" / "workspace_goal_contracts.json"
    assert all(not include.startswith("workspaces/") for include in manifest["includes"])
    if not private_authority_path.is_file():
        # Sanitized public checkout: absence is the expected source boundary.
        return

    authority = json.loads(private_authority_path.read_text(encoding="utf-8"))
    collected = public_release.collect_source_files(
        REPO_ROOT,
        manifest,
        private_literals=("f00d" * 8,),
    )
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path, _record in collected.values()
    )
    for contract in authority["contracts"].values():
        private_values = [
            contract["goal"],
            contract["phase_gate"],
            contract["no_action_trigger"],
            *contract["progress_signals"],
            *contract["safe_internal_boundary"],
            *contract["owner_required_boundary"],
            *[
                ref
                for ref in contract["authority_refs"]
                if ref not in APPROVED_PUBLIC_WORKSPACE_REFERENCE_LITERALS
            ],
        ]
        for private_value in private_values:
            assert private_value not in public_text


def test_build_and_verify_preserve_relative_paths_and_lockfile_metadata(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _safe_source_tree(source_root)
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app", "frontend/package-lock.json"],
        required_paths=["app/main.py", "frontend/package-lock.json"],
        email_metadata_paths=["frontend/package-lock.json"],
    )
    candidate_root = tmp_path / "candidate"

    report = _build(source_root, candidate_root, manifest_path, digest)

    assert report["ok"] is True
    assert report["file_count"] == 2
    assert (candidate_root / "app" / "main.py").is_file()
    assert (candidate_root / "frontend" / "package-lock.json").is_file()
    assert not (candidate_root / "public-manifest.json").exists()
    verified = public_release.verify_candidate(
        candidate_root=candidate_root,
        expected_receipt_sha256=report["receipt_sha256"],
    )
    assert verified["tree_sha256"] == report["tree_sha256"]


def test_identical_inputs_produce_identical_receipts(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _safe_source_tree(source_root)
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app", "frontend/package-lock.json"],
        email_metadata_paths=["frontend/package-lock.json"],
    )

    first = _build(source_root, tmp_path / "candidate-a", manifest_path, digest)
    second = _build(source_root, tmp_path / "candidate-b", manifest_path, digest)

    assert first["tree_sha256"] == second["tree_sha256"]
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert (
        tmp_path / "candidate-a" / public_release.METADATA_DIR / public_release.RECEIPT_NAME
    ).read_bytes() == (
        tmp_path / "candidate-b" / public_release.METADATA_DIR / public_release.RECEIPT_NAME
    ).read_bytes()


def test_receipt_uses_git_portable_modes_and_normalizes_candidate(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    plain_path = app_root / "plain.txt"
    executable_path = app_root / "run.sh"
    plain_path.write_text("safe\n", encoding="utf-8")
    executable_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    plain_path.chmod(0o640)
    executable_path.chmod(0o700)
    manifest_path, digest = _write_manifest(source_root, includes=["app"])
    candidate_root = tmp_path / "candidate"

    report = _build(source_root, candidate_root, manifest_path, digest)

    assert (candidate_root / "app" / "plain.txt").stat().st_mode & 0o777 == 0o644
    assert (candidate_root / "app" / "run.sh").stat().st_mode & 0o777 == 0o755
    receipt = json.loads(
        (candidate_root / public_release.METADATA_DIR / public_release.RECEIPT_NAME).read_text(
            encoding="utf-8"
        )
    )
    modes = {record["path"]: record["mode"] for record in receipt["candidate"]["files"]}
    assert modes == {"app/plain.txt": 0o644, "app/run.sh": 0o755}
    verified = public_release.verify_candidate(
        candidate_root=candidate_root,
        expected_receipt_sha256=report["receipt_sha256"],
    )
    assert verified["ok"] is True


@pytest.mark.parametrize(
    "kind,expected_code",
    [
        ("non_reserved_email", "non_reserved_email"),
        ("mac_user_path", "absolute_user_path"),
        ("linux_user_path", "absolute_user_path"),
        ("windows_user_path", "absolute_windows_user_path"),
        ("private_key", "private_key_material"),
        ("github_token", "github_token"),
        ("credential_assignment", "credential_literal_assignment"),
        ("unquoted_password", "unquoted_credential_assignment"),
        ("yaml_api_key", "unquoted_credential_assignment"),
        ("database_url", "credentialed_url"),
    ],
)
def test_content_policy_fails_closed_without_echoing_values(
    tmp_path: Path,
    kind: str,
    expected_code: str,
) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    payload = _policy_payload(kind)
    suffix = ".yaml" if kind == "yaml_api_key" else ".txt"
    (app_root / f"main{suffix}").write_text(payload + "\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(source_root, includes=["app"])

    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(source_root, tmp_path / "candidate", manifest_path, digest)

    message = str(captured.value)
    assert expected_code in message
    assert payload not in message
    assert not (tmp_path / "candidate").exists()


def test_external_private_denylist_is_required_and_never_echoed(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    private_value = "Private" + "OperatorLiteral"
    (app_root / "main.txt").write_text(
        f"This contains {private_value}.\n",
        encoding="utf-8",
    )
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app"],
        require_private_denylist=True,
    )

    with pytest.raises(public_release.PublicReleaseError, match="requires an external"):
        _build(source_root, tmp_path / "candidate-missing", manifest_path, digest)

    denylist_path = tmp_path / "private-denylist.txt"
    denylist_path.write_text(private_value + "\n", encoding="utf-8")
    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(
            source_root,
            tmp_path / "candidate-rejected",
            manifest_path,
            digest,
            private_denylist_path=denylist_path,
        )

    assert "private_literal" in str(captured.value)
    assert private_value not in str(captured.value)


def test_external_private_denylist_normalizes_case_and_separators(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    private_value = "Private" + "-Operator-Literal"
    case_variant = "PRIVATE" + " operator literal"
    (app_root / "main.txt").write_text(case_variant + "\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app"],
        require_private_denylist=True,
    )
    denylist_path = tmp_path / "private-denylist.txt"
    denylist_path.write_text(private_value + "\n", encoding="utf-8")

    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(
            source_root,
            tmp_path / "candidate",
            manifest_path,
            digest,
            private_denylist_path=denylist_path,
        )

    assert "private_literal" in str(captured.value)
    assert case_variant not in str(captured.value)


def test_external_private_denylist_detects_regex_obfuscation_without_echo(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    private_value = "Private" + " Organization Fixture"
    regex_fragment = r"\bPrivate\s+Organization\s+Fixture\b"
    (app_root / "main.py").write_text(
        f"PRIVATE_NAME_RE = re.compile(r'{regex_fragment}')\n",
        encoding="utf-8",
    )
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app"],
        require_private_denylist=True,
    )
    denylist_path = tmp_path / "private-denylist.txt"
    denylist_path.write_text(private_value + "\n", encoding="utf-8")

    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(
            source_root,
            tmp_path / "candidate",
            manifest_path,
            digest,
            private_denylist_path=denylist_path,
        )

    message = str(captured.value)
    assert "private_literal" in message
    assert private_value not in message
    assert regex_fragment not in message


def test_short_private_literal_matches_only_as_a_whole_word(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    (app_root / "main.txt").write_text("accounting remains public safe\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app"],
        require_private_denylist=True,
    )
    denylist_path = tmp_path / "private-denylist.txt"
    denylist_path.write_text("AC\n", encoding="utf-8")
    report = _build(
        source_root,
        tmp_path / "candidate-safe",
        manifest_path,
        digest,
        private_denylist_path=denylist_path,
    )
    assert report["ok"] is True

    (app_root / "main.txt").write_text("AC project\n", encoding="utf-8")
    with pytest.raises(public_release.PublicReleasePolicyError, match="private_literal"):
        _build(
            source_root,
            tmp_path / "candidate-rejected",
            manifest_path,
            digest,
            private_denylist_path=denylist_path,
        )


def test_private_denylist_requirement_is_receipt_bound(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    (app_root / "main.txt").write_text("Safe public content.\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app"],
        require_private_denylist=True,
    )
    denylist_path = tmp_path / "private-denylist.txt"
    denylist_path.write_text("NeverPublishThisLiteral\n", encoding="utf-8")
    report = _build(
        source_root,
        tmp_path / "candidate",
        manifest_path,
        digest,
        private_denylist_path=denylist_path,
    )

    with pytest.raises(public_release.PublicReleaseError, match="requires the external"):
        public_release.verify_candidate(
            candidate_root=tmp_path / "candidate",
            expected_receipt_sha256=report["receipt_sha256"],
        )
    verified = public_release.verify_candidate(
        candidate_root=tmp_path / "candidate",
        expected_receipt_sha256=report["receipt_sha256"],
        private_denylist_path=denylist_path,
    )
    assert verified["ok"] is True


def test_private_literal_in_filename_is_rejected_without_echo(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    private_value = "Private" + "FileMarker"
    (app_root / f"{private_value}.txt").write_text("Safe body.\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["app"],
        require_private_denylist=True,
    )
    denylist_path = tmp_path / "private-denylist.txt"
    denylist_path.write_text(private_value + "\n", encoding="utf-8")

    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(
            source_root,
            tmp_path / "candidate",
            manifest_path,
            digest,
            private_denylist_path=denylist_path,
        )

    assert any(
        code in str(captured.value)
        for code in ("private_literal_in_path", "private_literal")
    )
    assert private_value not in str(captured.value)


def test_forbidden_private_root_cannot_be_allowlisted(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    private_root = source_root / "memory"
    private_root.mkdir(parents=True)
    (private_root / "state.md").write_text("private\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(source_root, includes=["memory"])

    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(source_root, tmp_path / "candidate", manifest_path, digest)

    assert "private_root" in str(captured.value)


def test_verification_rejects_mutation_and_unexpected_files(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    (app_root / "main.txt").write_text("Safe public content.\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(source_root, includes=["app"])
    candidate_root = tmp_path / "candidate"
    report = _build(source_root, candidate_root, manifest_path, digest)

    (candidate_root / "app" / "unexpected.txt").write_text("new\n", encoding="utf-8")
    with pytest.raises(public_release.PublicReleaseError):
        public_release.verify_candidate(
            candidate_root=candidate_root,
            expected_receipt_sha256=report["receipt_sha256"],
        )


def test_repository_manifest_is_a_strict_public_app_allowlist() -> None:
    manifest, _, _ = public_release.load_manifest(
        REPO_ROOT / "release" / "public_source_manifest.json"
    )
    includes = set(manifest["includes"])

    assert manifest["require_private_denylist"] is True
    assert "backend/app" in includes
    assert "frontend/app" in includes
    assert "frontend/components" in includes
    assert "frontend/lib" in includes
    assert "scripts/build_public_release.py" in includes
    assert "backend" not in includes
    assert "frontend" not in includes
    assert "scripts" not in includes
    assert all(
        not (
            path == prefix or path.startswith(f"{prefix}/")
        )
        for path in includes
        for prefix in (
            "SOPs",
            "agents",
            "automations",
            "knowledge",
            "memory",
            "workspaces",
        )
    )
    assert manifest["third_party_email_metadata_paths"] == []
    assert manifest["file_mappings"] == {
        "release/public.gitignore": ".gitignore",
        "release/public.package.json": "package.json",
        "release/public.README.md": "README.md",
        "scripts/runtime_http.py": "backend/scripts/runtime_http.py",
        "scripts/personal-brand/build_social_feed.py": "backend/scripts/personal-brand/build_social_feed.py",
        "scripts/personal-brand/fetch_reddit_signals.py": "backend/scripts/personal-brand/fetch_reddit_signals.py",
        "scripts/personal-brand/fetch_rss_signals.py": "backend/scripts/personal-brand/fetch_rss_signals.py",
        "scripts/personal-brand/generate_linkedin_reaction_queue.py": "backend/scripts/personal-brand/generate_linkedin_reaction_queue.py",
        "scripts/personal-brand/linkedin_idea_qualification.py": "backend/scripts/personal-brand/linkedin_idea_qualification.py",
        "scripts/personal-brand/linkedin_strategy_utils.py": "backend/scripts/personal-brand/linkedin_strategy_utils.py",
        "scripts/personal-brand/refresh_social_feed.py": "backend/scripts/personal-brand/refresh_social_feed.py",
        "scripts/personal-brand/sync_market_signal_archive.py": "backend/scripts/personal-brand/sync_market_signal_archive.py",
    }


def test_inventory_digest_rejects_new_file_under_recursive_include(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    app_root = source_root / "app"
    app_root.mkdir(parents=True)
    (app_root / "main.txt").write_text("safe\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(source_root, includes=["app"])
    (app_root / "new-note.txt").write_text("also safe but unreviewed\n", encoding="utf-8")

    with pytest.raises(public_release.PublicReleasePolicyError, match="inventory_sha256_mismatch"):
        _build(source_root, tmp_path / "candidate", manifest_path, digest)


def test_file_mapping_projects_public_metadata_to_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    release_root = source_root / "release"
    release_root.mkdir(parents=True)
    (release_root / "public.gitignore").write_text("node_modules/\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(
        source_root,
        includes=["release/public.gitignore"],
        required_paths=[".gitignore"],
        file_mappings={"release/public.gitignore": ".gitignore"},
    )
    candidate_root = tmp_path / "candidate"
    _build(source_root, candidate_root, manifest_path, digest)

    assert (candidate_root / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"
    assert not (candidate_root / "release" / "public.gitignore").exists()


def test_manifest_symlink_is_rejected_before_resolution(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _safe_source_tree(source_root)
    manifest_path, _ = _write_manifest(source_root, includes=["app"])
    linked_manifest = tmp_path / "linked-manifest.json"
    linked_manifest.symlink_to(manifest_path)

    with pytest.raises(public_release.PublicReleaseError, match="symlink"):
        public_release.load_manifest(linked_manifest)


def test_manifest_content_is_scanned_even_when_not_allowlisted(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _safe_source_tree(source_root)
    manifest_path, _ = _write_manifest(source_root, includes=["app"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["name"] = "gh" + "p_" + ("A" * 32)
    manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    _, digest, _ = public_release.load_manifest(manifest_path)

    with pytest.raises(public_release.PublicReleasePolicyError) as captured:
        _build(source_root, tmp_path / "candidate", manifest_path, digest)

    assert "github_token" in str(captured.value)
    assert payload["name"] not in str(captured.value)


def test_verify_source_tree_requires_exact_receipt_bound_orphan_checkout(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _safe_source_tree(source_root)
    (source_root / ".public-lineage-root").write_text(
        "public-test-lineage/v1\n",
        encoding="utf-8",
    )
    manifest_path, digest = _write_manifest(
        source_root,
        includes=[
            ".public-lineage-root",
            "app",
            "frontend/package-lock.json",
            "public-manifest.json",
        ],
        required_paths=[
            ".public-lineage-root",
            "app/main.py",
            "frontend/package-lock.json",
            "public-manifest.json",
        ],
        email_metadata_paths=["frontend/package-lock.json"],
    )
    candidate_root = tmp_path / "candidate"
    _build(source_root, candidate_root, manifest_path, digest)

    subprocess.run(["git", "init", "-q", candidate_root], check=True)
    subprocess.run(["git", "-C", candidate_root, "config", "user.name", "Public Test"], check=True)
    subprocess.run(
        ["git", "-C", candidate_root, "config", "user.email", PUBLIC_TEST_NOREPLY_EMAIL],
        check=True,
    )
    subprocess.run(["git", "-C", candidate_root, "add", "-A"], check=True)
    subprocess.run(["git", "-C", candidate_root, "commit", "-qm", "public root"], check=True)

    lineage_root = subprocess.run(
        ["git", "-C", candidate_root, "rev-list", "--max-parents=0", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report = public_release.verify_source_tree(
        source_root=candidate_root,
        manifest_path=candidate_root / "public-manifest.json",
        expected_lineage_root=lineage_root,
        expected_git_name="Public Test",
        require_noreply_email=True,
    )
    assert report["ok"] is True
    assert report["single_root_public_lineage"] is True

    (candidate_root / "app" / "main.py").write_text(
        "CONTACT = 'operator@example.com'\nVALUE = 'changed after commit'\n",
        encoding="utf-8",
    )
    with pytest.raises(public_release.PublicReleaseError, match="uncommitted"):
        public_release.verify_source_tree(
            source_root=candidate_root,
            manifest_path=candidate_root / "public-manifest.json",
            expected_lineage_root=lineage_root,
            expected_git_name="Public Test",
            require_noreply_email=True,
        )
    subprocess.run(
        ["git", "-C", candidate_root, "restore", "app/main.py"],
        check=True,
    )

    (candidate_root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    subprocess.run(["git", "-C", candidate_root, "add", "unexpected.txt"], check=True)
    with pytest.raises(
        public_release.PublicReleaseError,
        match="uncommitted|missing or unexpected",
    ):
        public_release.verify_source_tree(
            source_root=candidate_root,
            manifest_path=candidate_root / "public-manifest.json",
            expected_lineage_root=lineage_root,
            expected_git_name="Public Test",
            require_noreply_email=True,
        )


def test_verify_source_tree_scans_deleted_secret_from_reachable_history(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _safe_source_tree(source_root)
    (source_root / ".public-lineage-root").write_text("public-test-lineage/v1\n", encoding="utf-8")
    manifest_path, digest = _write_manifest(
        source_root,
        includes=[
            ".public-lineage-root",
            "app",
            "frontend/package-lock.json",
            "public-manifest.json",
        ],
        required_paths=[
            ".public-lineage-root",
            "app/main.py",
            "frontend/package-lock.json",
            "public-manifest.json",
        ],
        email_metadata_paths=["frontend/package-lock.json"],
    )
    candidate_root = tmp_path / "candidate-history"
    _build(source_root, candidate_root, manifest_path, digest)
    subprocess.run(["git", "init", "-q", candidate_root], check=True)
    subprocess.run(["git", "-C", candidate_root, "config", "user.name", "Public Test"], check=True)
    subprocess.run(
        ["git", "-C", candidate_root, "config", "user.email", PUBLIC_TEST_NOREPLY_EMAIL],
        check=True,
    )
    subprocess.run(["git", "-C", candidate_root, "add", "-A"], check=True)
    subprocess.run(["git", "-C", candidate_root, "commit", "-qm", "public root"], check=True)

    transient = candidate_root / "app" / "transient.txt"
    transient.write_text("gh" + "p_" + ("A" * 32) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", candidate_root, "add", "app/transient.txt"], check=True)
    subprocess.run(["git", "-C", candidate_root, "commit", "-qm", "temporary file"], check=True)
    transient.unlink()
    subprocess.run(["git", "-C", candidate_root, "add", "-u"], check=True)
    subprocess.run(["git", "-C", candidate_root, "commit", "-qm", "remove temporary file"], check=True)

    with pytest.raises(public_release.PublicReleasePolicyError, match="github_token"):
        public_release.verify_source_tree(
            source_root=candidate_root,
            manifest_path=candidate_root / "public-manifest.json",
            expected_git_name="Public Test",
            require_noreply_email=True,
        )
