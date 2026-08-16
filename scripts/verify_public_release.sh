#!/usr/bin/env bash
set -euo pipefail

PUBLIC_RELEASE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIVATE_DENYLIST="${AI_CLONE_PRIVATE_DENYLIST_FILE:-}"
PUBLIC_OUTPUT_ROOT="${AI_CLONE_PUBLIC_OUTPUT_ROOT:-}"
PUBLIC_PYTHON="${AI_CLONE_PUBLIC_PYTHON:-python3}"
PUBLIC_NPM_CACHE="${NPM_CONFIG_CACHE:-$HOME/.npm}"
PUBLIC_GIT_TREE_MODE="${AI_CLONE_PUBLIC_GIT_TREE_MODE:-0}"

case "$PUBLIC_GIT_TREE_MODE" in
  0|1) ;;
  *)
    echo "error: AI_CLONE_PUBLIC_GIT_TREE_MODE must be 0 or 1" >&2
    exit 1
    ;;
esac

if [[ -z "$PRIVATE_DENYLIST" || ! -f "$PRIVATE_DENYLIST" ]]; then
  echo "error: AI_CLONE_PRIVATE_DENYLIST_FILE must name a private file outside the repository" >&2
  exit 1
fi

case "$(cd "$(dirname "$PRIVATE_DENYLIST")" && pwd)/$(basename "$PRIVATE_DENYLIST")" in
  "$PUBLIC_RELEASE_ROOT"/*)
    echo "error: the private denylist must remain outside the repository" >&2
    exit 1
    ;;
esac

PUBLIC_RELEASE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/aiclone-public-release.XXXXXXXX")"
PUBLIC_CANDIDATE="$PUBLIC_RELEASE_TMP/candidate"
PUBLIC_TEST_HOME="$PUBLIC_RELEASE_TMP/empty-home"
PUBLIC_TEST_SECRETS="$PUBLIC_RELEASE_TMP/empty-secrets"
PUBLIC_PRESERVED_STAGING="$PUBLIC_RELEASE_TMP/preserved-candidate"
mkdir -p "$PUBLIC_TEST_HOME" "$PUBLIC_TEST_SECRETS"
: > "$PUBLIC_TEST_HOME/npmrc"
trap 'rm -rf -- "$PUBLIC_RELEASE_TMP"' EXIT

if ! command -v "$PUBLIC_PYTHON" >/dev/null 2>&1; then
  echo "error: AI_CLONE_PUBLIC_PYTHON must name an available Python interpreter" >&2
  exit 1
fi

PUBLIC_SAFE_ENV=(
  env -i
  "HOME=$PUBLIC_TEST_HOME"
  "PATH=$PATH"
  "TMPDIR=${TMPDIR:-/tmp}"
  "AI_CLONE_SECRETS_ROOT=$PUBLIC_TEST_SECRETS"
  "CONTENT_GENERATION_ENABLE_OLLAMA=false"
  "NEO_ENABLE_OLLAMA=false"
  "NEXT_TELEMETRY_DISABLED=1"
  "NPM_CONFIG_AUDIT=false"
  "NPM_CONFIG_CACHE=$PUBLIC_NPM_CACHE"
  "NPM_CONFIG_FUND=false"
  "NPM_CONFIG_USERCONFIG=$PUBLIC_TEST_HOME/npmrc"
  "NO_UPDATE_NOTIFIER=1"
  "PYTHONHASHSEED=0"
)
for PUBLIC_TRUST_ENV_NAME in \
  CODEX_CI \
  CODEX_PERMISSION_PROFILE \
  CODEX_SANDBOX \
  CODEX_SANDBOX_NETWORK_DISABLED \
  NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S \
  NODE_REPL_TRUSTED_CODE_PATHS
do
  if [[ -n "${!PUBLIC_TRUST_ENV_NAME:-}" ]]; then
    PUBLIC_SAFE_ENV+=("$PUBLIC_TRUST_ENV_NAME=${!PUBLIC_TRUST_ENV_NAME}")
  fi
done

run_public_npm() (
  while IFS='=' read -r PUBLIC_ENV_NAME _; do
    case "$PUBLIC_ENV_NAME" in
      *API_KEY*|*ACCESS_KEY*|*AUTH*|*COOKIE*|*CREDENTIAL*|*DATABASE_URL*|*DENYLIST*|*FIREBASE*|*GITHUB*|GH_*|*GMAIL*|*GOOGLE*|*OPENAI*|*ANTHROPIC*|*OLLAMA*|*PASSWORD*|*PASSWD*|*PERPLEXITY*|*FIRECRAWL*|*PRIVATE_KEY*|*RAILWAY*|*REDIS_URL*|*SECRET*|*SESSION*|*SIGNING*|*TOKEN*|*VERCEL*)
        unset "$PUBLIC_ENV_NAME" 2>/dev/null || true
        ;;
    esac
  done < <(env)
  export HOME="$PUBLIC_TEST_HOME"
  export AI_CLONE_SECRETS_ROOT="$PUBLIC_TEST_SECRETS"
  export CONTENT_GENERATION_ENABLE_OLLAMA=false
  export NEO_ENABLE_OLLAMA=false
  export NEXT_TELEMETRY_DISABLED=1
  export NPM_CONFIG_AUDIT=false
  export NPM_CONFIG_CACHE="$PUBLIC_NPM_CACHE"
  export NPM_CONFIG_FUND=false
  export NPM_CONFIG_USERCONFIG="$PUBLIC_TEST_HOME/npmrc"
  export NO_UPDATE_NOTIFIER=1
  export CI=1
  npm "$@"
)

if [[ -n "$PUBLIC_OUTPUT_ROOT" ]]; then
  if [[ "$PUBLIC_GIT_TREE_MODE" == "1" ]]; then
    echo "error: AI_CLONE_PUBLIC_OUTPUT_ROOT cannot be used while verifying a public Git tree" >&2
    exit 1
  fi
  if [[ "$PUBLIC_OUTPUT_ROOT" != /* ]]; then
    echo "error: AI_CLONE_PUBLIC_OUTPUT_ROOT must be an absolute path" >&2
    exit 1
  fi
  if [[ -e "$PUBLIC_OUTPUT_ROOT" || -L "$PUBLIC_OUTPUT_ROOT" ]]; then
    echo "error: AI_CLONE_PUBLIC_OUTPUT_ROOT must not already exist" >&2
    exit 1
  fi
  OUTPUT_PARENT="$(dirname "$PUBLIC_OUTPUT_ROOT")"
  if [[ ! -d "$OUTPUT_PARENT" || -L "$OUTPUT_PARENT" ]]; then
    echo "error: AI_CLONE_PUBLIC_OUTPUT_ROOT parent must be an existing non-symlink directory" >&2
    exit 1
  fi
  OUTPUT_PARENT="$(cd "$OUTPUT_PARENT" && pwd -P)"
  PUBLIC_OUTPUT_ROOT="$OUTPUT_PARENT/$(basename "$PUBLIC_OUTPUT_ROOT")"
  case "$PUBLIC_OUTPUT_ROOT" in
    "$PUBLIC_RELEASE_ROOT"|"$PUBLIC_RELEASE_ROOT"/*)
      echo "error: AI_CLONE_PUBLIC_OUTPUT_ROOT must remain outside the private workspace" >&2
      exit 1
      ;;
  esac
fi

MANIFEST_SHA="$("$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" manifest-sha256)"
if [[ -n "${AI_CLONE_PUBLIC_MANIFEST_SHA256:-}" && "$MANIFEST_SHA" != "$AI_CLONE_PUBLIC_MANIFEST_SHA256" ]]; then
  echo "error: reviewed public manifest digest does not match" >&2
  exit 1
fi

if [[ "$PUBLIC_GIT_TREE_MODE" == "1" ]]; then
  if [[ -z "${AI_CLONE_PUBLIC_MANIFEST_SHA256:-}" || -z "${AI_CLONE_PUBLIC_LINEAGE_ROOT_COMMIT:-}" ]]; then
    echo "error: public Git-tree verification requires the reviewed manifest and lineage root" >&2
    exit 1
  fi
  VERIFY_TREE_ARGS=(
    verify-source-tree
    --source-root "$PUBLIC_RELEASE_ROOT"
    --private-denylist "$PRIVATE_DENYLIST"
    --expected-lineage-root "$AI_CLONE_PUBLIC_LINEAGE_ROOT_COMMIT"
    --expected-git-name "AI Clone Release"
    --require-noreply-email
  )
  "$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" "${VERIFY_TREE_ARGS[@]}"
  PUBLIC_CANDIDATE="$PUBLIC_RELEASE_ROOT"
else
  BUILD_REPORT="$(
    "$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" build \
      --candidate-root "$PUBLIC_CANDIDATE" \
      --expected-manifest-sha256 "$MANIFEST_SHA" \
      --private-denylist "$PRIVATE_DENYLIST"
  )"
  RECEIPT_SHA="$(printf '%s' "$BUILD_REPORT" | "$PUBLIC_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["receipt_sha256"])')"
  printf '%s\n' "$BUILD_REPORT"

  "$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" verify \
    --candidate-root "$PUBLIC_CANDIDATE" \
    --expected-receipt-sha256 "$RECEIPT_SHA" \
    --private-denylist "$PRIVATE_DENYLIST"
fi

"${PUBLIC_SAFE_ENV[@]}" "$PUBLIC_PYTHON" -m compileall -q \
  "$PUBLIC_CANDIDATE/backend/app" \
  "$PUBLIC_CANDIDATE/backend/runtime_paths.py" \
  "$PUBLIC_CANDIDATE/scripts"

"${PUBLIC_SAFE_ENV[@]}" "PYTHONPATH=$PUBLIC_CANDIDATE/backend" "$PUBLIC_PYTHON" -c \
  'from fastapi.testclient import TestClient; from app.main import app; response = TestClient(app).get("/health"); assert response.status_code == 200; assert response.json().get("status") == "healthy"'

"${PUBLIC_SAFE_ENV[@]}" "$PUBLIC_PYTHON" -m pytest -q \
  "$PUBLIC_CANDIDATE/backend/tests/test_public_release_builder.py"

run_public_npm --prefix "$PUBLIC_CANDIDATE/frontend" ci
run_public_npm --prefix "$PUBLIC_CANDIDATE/frontend" test
run_public_npm --prefix "$PUBLIC_CANDIDATE/frontend" run build

if [[ "$PUBLIC_GIT_TREE_MODE" == "1" ]]; then
  "$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" "${VERIFY_TREE_ARGS[@]}" >/dev/null
elif [[ -n "$PUBLIC_OUTPUT_ROOT" ]]; then
  FINAL_BUILD_REPORT="$(
    "$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" build \
      --candidate-root "$PUBLIC_PRESERVED_STAGING" \
      --expected-manifest-sha256 "$MANIFEST_SHA" \
      --private-denylist "$PRIVATE_DENYLIST"
  )"
  FINAL_RECEIPT_SHA="$(printf '%s' "$FINAL_BUILD_REPORT" | "$PUBLIC_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["receipt_sha256"])')"
  if [[ "$FINAL_RECEIPT_SHA" != "$RECEIPT_SHA" ]]; then
    echo "error: source changed while the tested public candidate was being verified" >&2
    exit 1
  fi
  "$PUBLIC_PYTHON" "$PUBLIC_RELEASE_ROOT/scripts/build_public_release.py" verify \
    --candidate-root "$PUBLIC_PRESERVED_STAGING" \
    --expected-receipt-sha256 "$FINAL_RECEIPT_SHA" \
    --private-denylist "$PRIVATE_DENYLIST" >/dev/null
  mv "$PUBLIC_PRESERVED_STAGING" "$PUBLIC_OUTPUT_ROOT"
  "$PUBLIC_PYTHON" "$PUBLIC_OUTPUT_ROOT/scripts/build_public_release.py" verify \
    --candidate-root "$PUBLIC_OUTPUT_ROOT" \
    --expected-receipt-sha256 "$FINAL_RECEIPT_SHA" \
    --private-denylist "$PRIVATE_DENYLIST" >/dev/null
  printf 'Verified public candidate preserved at %s\n' "$PUBLIC_OUTPUT_ROOT"
fi

echo "Public source release gate passed."
