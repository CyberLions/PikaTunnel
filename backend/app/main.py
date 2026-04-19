import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import routes, streams, vpn, auth, health, nginx, cluster, certs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
SCHEMA_BOOTSTRAP_LOCK = "pikatunnel_schema_bootstrap"


# Additive column migrations applied at startup when alembic isn't run out-of-band.
# Each entry is idempotent: IF NOT EXISTS so re-running is a no-op.
_ADDITIVE_COLUMNS: list[str] = [
    "ALTER TABLE IF EXISTS proxy_routes ADD COLUMN IF NOT EXISTS ssl_cert_name VARCHAR(255)",
    "ALTER TABLE IF EXISTS cluster_settings ADD COLUMN IF NOT EXISTS k8s_loadbalancer_service_name VARCHAR(255)",
    "ALTER TABLE IF EXISTS vpn_configs ADD COLUMN IF NOT EXISTS autostart BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE IF EXISTS vpn_configs ADD COLUMN IF NOT EXISTS reconnect_suspended_until TIMESTAMPTZ",
    "ALTER TABLE IF EXISTS tls_certificates ALTER COLUMN cert_pem DROP NOT NULL",
    "ALTER TABLE IF EXISTS tls_certificates ALTER COLUMN key_pem DROP NOT NULL",
    "ALTER TABLE IF EXISTS tls_certificates ADD COLUMN IF NOT EXISTS cert_path VARCHAR(1024)",
    "ALTER TABLE IF EXISTS tls_certificates ADD COLUMN IF NOT EXISTS key_path VARCHAR(1024)",
]


# Arbitrary keys; chosen so they won't collide with other advisory locks.
_AUTOSTART_LOCK_ID = 918_293_841  # xact lock for reservation inside one check
_WATCHER_TICK_SECS = 30


async def _supervise_autostart_once() -> None:
    """One iteration of the VPN watcher: start or reconnect if needed.

    Uses a transactional advisory lock to ensure only one uvicorn worker runs
    the check at a time, and atomically reserves the target (flipping status
    to 'connecting') before releasing the lock so a parallel iteration on
    another worker can't double-reconnect.
    """
    from sqlalchemy import select
    from app.database import async_session
    from app.models import VPNConfig
    from app.services import vpn_manager

    target_id = None
    target_name = ""
    reason = ""

    async with async_session() as db:
        async with db.begin():
            got_lock = (await db.execute(
                text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": _AUTOSTART_LOCK_ID},
            )).scalar()
            if not got_lock:
                return  # another worker is checking right now

            result = await db.execute(
                select(VPNConfig).where(VPNConfig.enabled == True, VPNConfig.autostart == True)  # noqa: E712
            )
            configs = list(result.scalars().all())
            if not configs:
                return
            if len(configs) > 1:
                names = ", ".join(c.name for c in configs)
                logger.warning("Multiple VPN configs marked autostart (%s); supervising only %s",
                               names, configs[0].name)
            target = configs[0]

            live = await vpn_manager.get_status(target)
            if live == "connected":
                if target.status != "connected":
                    target.status = "connected"
                    db.add(target)
                return

            # Honor manual disconnect: don't fight the user for the suspension window.
            suspended_until = target.reconnect_suspended_until
            if suspended_until is not None:
                now = datetime.now(timezone.utc)
                # Database timestamps come back timezone-aware with our schema,
                # but guard against a naive value just in case.
                if suspended_until.tzinfo is None:
                    suspended_until = suspended_until.replace(tzinfo=timezone.utc)
                if now < suspended_until:
                    return
                # Suspension expired — clear it so we stop checking the clock.
                target.reconnect_suspended_until = None
                db.add(target)

            # live is not 'connected' — decide whether to (re)connect.
            if target.status == "connecting":
                # Another reconnect is already in flight; let it finish.
                return

            reason = "initial start" if target.status == "disconnected" and live == "disconnected" else \
                     f"live={live}, db={target.status}"
            target.status = "connecting"
            db.add(target)
            target_id = target.id
            target_name = target.name
        # xact lock released here on commit

    if target_id is None:
        return

    async with async_session() as db:
        attached = await db.get(VPNConfig, target_id)
        if not attached:
            return
        logger.info("VPN watcher: (re)connecting '%s' (%s)", target_name, reason)
        try:
            status = await vpn_manager.connect(attached, db)
            logger.info("VPN watcher: '%s' -> %s", target_name, status)
        except Exception as e:
            logger.exception("VPN watcher: reconnect failed for '%s': %s", target_name, e)


async def vpn_watcher() -> None:
    """Long-running task: supervise autostart VPNs, reconnect on drop."""
    # First pass runs immediately so boot-time autostart still kicks in right away.
    while True:
        try:
            await _supervise_autostart_once()
        except Exception as e:
            logger.exception("VPN watcher iteration failed: %s", e)
        await asyncio.sleep(_WATCHER_TICK_SECS)


async def _bootstrap_nginx() -> None:
    """Regenerate nginx configs from DB on startup and reload.

    Run once per container boot so proxy/stream routes and mounted TLS certs
    are reflected immediately, without waiting for a user-triggered change.
    One uvicorn worker wins an advisory try-lock and does the work; the rest
    skip to avoid duplicate reloads.
    """
    from app.database import async_session
    from app.services import nginx_config

    async with async_session() as db:
        got_lock = (await db.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:name))"),
            {"name": "pikatunnel_nginx_bootstrap"},
        )).scalar()
        if not got_lock:
            return
        try:
            await nginx_config.generate_and_reload(db)
        except Exception as e:
            logger.exception("nginx bootstrap reload failed: %s", e)
        finally:
            await db.execute(
                text("SELECT pg_advisory_unlock(hashtext(:name))"),
                {"name": "pikatunnel_nginx_bootstrap"},
            )


async def ensure_database_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        # Multiple uvicorn workers run startup concurrently in production.
        # Serialize metadata DDL so PostgreSQL enum/table creation cannot race.
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"), {"lock_name": SCHEMA_BOOTSTRAP_LOCK})
        logger.info("Database schema lock acquired")
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _ADDITIVE_COLUMNS:
            await conn.execute(text(stmt))
        logger.info("Database tables ensured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting pikatunnel (env=%s)", settings.ENVIRONMENT)
    await ensure_database_schema()
    await _bootstrap_nginx()
    # Fire-and-forget: the watcher does the initial autostart on its first
    # iteration, then polls every 30s to reconnect on unintentional drops.
    # Multiple uvicorn workers can all run this safely — a PG advisory lock
    # inside _supervise_autostart_once elects a single active checker.
    task = asyncio.create_task(vpn_watcher())
    app.state.vpn_watcher_task = task
    yield
    task.cancel()
    await engine.dispose()


app = FastAPI(title="PikaTunnel", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(streams.router)
app.include_router(vpn.router)
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(nginx.router)
app.include_router(cluster.router)
app.include_router(certs.router)
