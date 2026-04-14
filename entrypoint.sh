#!/bin/bash
set -e

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting Proxy Manager (env=$ENVIRONMENT)"

# Start nginx in background
log "Starting nginx..."
nginx

# Start FastAPI backend
log "Starting uvicorn..."
exec uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-2}" \
    --log-level info
