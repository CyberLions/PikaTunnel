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
cd /app

# Reconcile alembic_version with the actual DB schema. Probes for each migration's
# sentinel column/table and re-stamps if the recorded revision is wrong (or missing).
# This handles both pre-alembic deployments AND DBs that were previously stamped
# incorrectly (e.g. stamped to head before all migrations were applied).
STAMP_REV=$(python3 - <<'EOF'
import asyncio, sys
sys.path.insert(0, '/app')

async def col_exists(conn, table, col):
    from sqlalchemy import text
    return await conn.scalar(text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_name=:t AND column_name=:c)"
    ), {"t": table, "c": col})

async def table_exists(conn, table):
    from sqlalchemy import text
    return await conn.scalar(text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=:t)"
    ), {"t": table})

async def detect_actual_rev(conn):
    if not await table_exists(conn, "proxy_routes"):
        return None  # fresh DB
    if await col_exists(conn, "proxy_routes", "proxy_host_header"):
        return "006"
    if await col_exists(conn, "proxy_routes", "ssl_cert_name"):
        return "005"
    if await col_exists(conn, "proxy_routes", "k8s_ingress_enabled"):
        return "004"
    if await table_exists(conn, "cluster_settings"):
        return "003"
    if await col_exists(conn, "proxy_routes", "groups"):
        return "002"
    return "001"

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        actual = await detect_actual_rev(conn)
        if actual is None:
            return  # fresh DB — let alembic run from scratch

        recorded = None
        if await table_exists(conn, "alembic_version"):
            recorded = await conn.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))

        if recorded != actual:
            print(actual)
    await engine.dispose()

asyncio.run(main())
EOF
)
if [ -n "$STAMP_REV" ]; then
    log "Reconciling alembic_version to actual DB revision $STAMP_REV"
    alembic stamp "$STAMP_REV"
fi

alembic upgrade head

# Start FastAPI backend
log "Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-2}" \
    --log-level info
