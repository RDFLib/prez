#!/bin/sh
set -eu

echo "Prez config merge entrypoint"

DEFAULTS_DIR="$(find "${VIRTUAL_ENV}/lib" -path "*/prez/reference_data" -type d 2>/dev/null | head -n1 || true)"
CUSTOM_DIR="/app/reference_data"      # read-only mount from host
TARGET_DIR="/data/reference_data"     # writable merge area

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

# 1. Copy defaults
if [ -n "${DEFAULTS_DIR:-}" ] && [ -d "${DEFAULTS_DIR}" ]; then
  echo "Copying defaults from ${DEFAULTS_DIR}"
  cp -a "${DEFAULTS_DIR}/." "${TARGET_DIR}/"
else
  echo "⚠️  No defaults found at ${DEFAULTS_DIR:-<unset>}"
fi

# 2. Overlay user config (union; same-name files override)
if [ -d "${CUSTOM_DIR}" ] && [ "$(ls -A "${CUSTOM_DIR}")" ]; then
  echo "Merging custom config from ${CUSTOM_DIR}"
  cp -a "${CUSTOM_DIR}/." "${TARGET_DIR}/"
else
  echo "No custom config provided at ${CUSTOM_DIR}"
fi

export PREZ_REFERENCE_DATA_DIR="${TARGET_DIR}"
echo "Reference data merged at ${PREZ_REFERENCE_DATA_DIR}"

exec "$@"
