#!/bin/bash
set -e

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting PikaTunnel (env=$ENVIRONMENT)"

log "Starting apache..."
apachectl start

# Start nginx in background
log "Starting nginx..."
nginx

# Start pritunl-client-service daemon (needed for VPN profile commands)
if command -v pritunl-client-service >/dev/null 2>&1; then
    log "Starting pritunl-client-service..."
    pritunl-client-service &
    # Wait up to 10s for the auth key file to appear
    for _ in $(seq 1 20); do
        [ -f /var/run/pritunl.auth ] && break
        sleep 0.5
    done
fi

# Start FastAPI backend
log "Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-2}" \
    --log-level info
