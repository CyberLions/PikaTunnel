#!/bin/bash
set -e

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting PikaTunnel (env=$ENVIRONMENT)"

# Fix permissions — devcontainer bind mounts can leave dirs owned by the host uid.
# The backend (uvicorn) runs as a non-root user and must be able to:
#   1. Write /etc/nginx/nginx.conf (regenerated on every route change)
#   2. Write /var/log/nginx/error.log
#   3. Read /etc/nginx/ssl/default.key for the catch-all SSL server block
mkdir -p /etc/nginx/ssl /var/log/nginx /run/pikatunnel
chmod 755 /etc/nginx /etc/nginx/ssl
chmod 755 /var/log/nginx
chmod 644 /etc/nginx/nginx.conf
chmod 644 /etc/nginx/nginx.stream.conf
chmod 644 /etc/nginx/ssl/default.crt
chmod 644 /etc/nginx/ssl/default.key

# Generate default SSL certs for the catch-all server block if missing
if [ ! -f /etc/nginx/ssl/default.key ] || [ ! -f /etc/nginx/ssl/default.crt ]; then
    log "Generating default self-signed SSL certificate..."
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/default.key \
        -out /etc/nginx/ssl/default.crt \
        -subj "/CN=pikatunnel" 2>/dev/null
    chmod 644 /etc/nginx/ssl/default.crt
    chmod 644 /etc/nginx/ssl/default.key
fi

# Touch the stream config so nginx -t passes when no streams are configured
touch /etc/nginx/nginx.stream.conf

log "Starting apache..."
apachectl start

# Start nginx in background
log "Starting nginx..."
nginx

mkdir -p /var/run/pikatunnel

# Run DB migrations before starting the app
log "Running database migrations..."
cd /app && alembic upgrade head

# Start FastAPI backend
log "Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-2}" \
    --log-level info
