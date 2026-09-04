#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${ARIA_MODEL_PATH:-/app/models/aria_stage1.pt}"
DB_PATH="${ARIA_DB_PATH:-/app/runtime/db/aria.db}"

# Ensure runtime directories exist
mkdir -p "$(dirname "${DB_PATH}")" "${ARIA_UPLOAD_DIR:-/app/runtime/uploads}" "${YOLO_CONFIG_DIR:-/app/runtime/ultralytics}" "$(dirname "${MODEL_PATH}")"

# Download YOLO model if missing
uv run --locked --no-sync python -m scripts.download_model

# Initialize and seed database if missing
if [ ! -f "${DB_PATH}" ]; then
    echo "Initializing and seeding database at ${DB_PATH}..."
    uv run --locked --no-sync python -m aria.db.seed "${DB_PATH}"
fi

# Dev / custom command passthrough
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# Default production entrypoint: exactly 1 Uvicorn worker
exec uv run --locked --no-sync uvicorn \
    aria.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
