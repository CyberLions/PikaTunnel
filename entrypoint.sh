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

# If tables already exist but alembic has no version record (pre-alembic deployment),
# detect which revision the DB is actually at and stamp to that so upgrade head
# only runs genuinely new migrations.
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

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        has_version = await table_exists(conn, "alembic_version")
        if has_version:
            return  # alembic already tracking — no stamp needed
        if not await table_exists(conn, "proxy_routes"):
            return  # fresh DB — let alembic run from scratch

        # Walk migrations newest-first; stamp at the highest one whose changes are present
        if await col_exists(conn, "proxy_routes", "proxy_host_header"):
            print("006")
        elif await col_exists(conn, "proxy_routes", "ssl_cert_name"):
            print("005")
        elif await col_exists(conn, "proxy_routes", "k8s_ingress_enabled"):
            print("004")
        elif await table_exists(conn, "cluster_settings"):
            print("003")
        elif await col_exists(conn, "proxy_routes", "groups"):
            print("002")
        else:
            print("001")
    await engine.dispose()

asyncio.run(main())
EOF
)
if [ -n "$STAMP_REV" ]; then
    log "Existing DB detected at revision $STAMP_REV — stamping before upgrade"
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
