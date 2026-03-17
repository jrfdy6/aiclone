#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="${1:-/Users/neo/.openclaw/workspace}"
BACKUP_DIR="${2:-/Users/neo/.openclaw/workspace/backups}"
TS=$(date -u +%Y%m%d-%H%M%S)
ARCHIVE_NAME="neo-core-backup-${TS}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"

mkdir -p "${BACKUP_DIR}"

if [ ! -d "${SRC_DIR}" ]; then
  echo "Source directory not found: ${SRC_DIR}" >&2
  exit 1
fi

EXCLUDE_ARGS=()
case "${BACKUP_DIR}" in
  "${SRC_DIR}"*)
    REL_PATH="${BACKUP_DIR#${SRC_DIR}/}"
    if [ -n "${REL_PATH}" ] && [ "${REL_PATH}" != "${BACKUP_DIR}" ]; then
      EXCLUDE_ARGS+=("--exclude=${REL_PATH}")
    fi
    ;;
  *)
    ;;
esac

if [ ${#EXCLUDE_ARGS[@]} -gt 0 ]; then
  tar "${EXCLUDE_ARGS[@]}" -czf "${ARCHIVE_PATH}" -C "${SRC_DIR}" .
else
  tar -czf "${ARCHIVE_PATH}" -C "${SRC_DIR}" .
fi

SHA=$(shasum -a 256 "${ARCHIVE_PATH}" | awk '{print $1}')

cat <<JSON
{
  "archive": "${ARCHIVE_PATH}",
  "checksum": "${SHA}",
  "size_bytes": $(stat -f %z "${ARCHIVE_PATH}"),
  "created_at": "${TS}Z"
}
JSON
