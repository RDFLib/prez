#!/bin/bash
set -e

# Define paths
REFERENCE_DATA_DIR="/app/reference_data"
REFERENCE_DATA_DEFAULTS="${VIRTUAL_ENV}/lib/python*/site-packages/prez/reference_data"
REFERENCE_DATA_CUSTOM="/app/reference_data-custom"

echo "Prez config merge entrypoint"

# Create the working reference_data directory
mkdir -p "${REFERENCE_DATA_DIR}"

# Find the actual path to the installed prez package reference_data
INSTALLED_REF_DATA=$(find ${VIRTUAL_ENV}/lib -path "*/prez/reference_data" -type d 2>/dev/null | head -1)

if [ -n "${INSTALLED_REF_DATA}" ] && [ -d "${INSTALLED_REF_DATA}" ]; then
    echo "Copying default reference_data from ${INSTALLED_REF_DATA}..."
    cp -r "${INSTALLED_REF_DATA}"/* "${REFERENCE_DATA_DIR}/"
    echo "Default reference_data loaded"
else
    echo "Warning: Could not find installed prez reference_data"
fi

# Overlay custom config if mounted
if [ -d "${REFERENCE_DATA_CUSTOM}" ] && [ "$(ls -A ${REFERENCE_DATA_CUSTOM})" ]; then
    echo "Applying custom reference_data configuration..."
    # Use cp with no-clobber flag removed, so files with same names override
    cp -rf "${REFERENCE_DATA_CUSTOM}"/* "${REFERENCE_DATA_DIR}/"
    echo "Custom reference_data applied"
else
    echo "No custom reference_data mounted at ${REFERENCE_DATA_CUSTOM}"
fi

echo "Reference data configuration complete"
echo "Starting Prez..."

# Execute the actual application command
exec "$@"
