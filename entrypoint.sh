#!/bin/bash
set -e

echo "Prez config merge entrypoint"

DEFAULTS_DIR=$(find "${VIRTUAL_ENV}/lib" -path "*/prez/reference_data" -type d 2>/dev/null | head -1)
CUSTOM_DIR="/app/reference_data"     # read-only, user-supplied
TARGET_DIR="/data/reference_data"    # writable, merged

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

# 1. Copy defaults first
if [ -d "${DEFAULTS_DIR}" ]; then
  echo "Copying defaults from ${DEFAULTS_DIR}"
  cp -a "${DEFAULTS_DIR}/." "${TARGET_DIR}/"
else
  echo "⚠️  No defaults found at ${DEFAULTS_DIR}"
fi

# 2. Overlay user config (override on same filename, keep others)
if [ -d "${CUSTOM_DIR}" ] && [ "$(ls -A "${CUSTOM_DIR}")" ]; then
  echo "Merging custom config from ${CUSTOM_DIR}"
  rsync -a --ignore-times --update --checksum "${CUSTOM_DIR}/" "${TARGET_DIR}/"
else
  echo "No custom config provided at ${CUSTOM_DIR}"
fi

export PREZ_REFERENCE_DATA_DIR="${TARGET_DIR}"
echo "Reference data merged at ${PREZ_REFERENCE_DATA_DIR}"

exec "$@"
