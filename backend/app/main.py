import asyncio
import logging
from contextlib import asynccontextmanager
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
]


# Arbitrary key; chosen so it won't collide with other advisory locks in the app.
_AUTOSTART_LOCK_ID = 918_293_841


async def _reserve_autostart_target() -> "uuid.UUID | None":  # type: ignore[name-defined]
    """Atomically pick (and mark 'connecting') exactly one VPN to autostart.

    Returns the target's id, or None if there's nothing to start or another
    worker already reserved it. Uses a transactional advisory lock so multiple
    uvicorn workers can't race into autostart() in parallel.
    """
    from sqlalchemy import select
    from app.database import async_session
    from app.models import VPNConfig

    async with async_session() as db:
        async with db.begin():
            # Blocking lock; released automatically at transaction end.
            await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _AUTOSTART_LOCK_ID})

            result = await db.execute(
                select(VPNConfig).where(VPNConfig.enabled == True, VPNConfig.autostart == True)  # noqa: E712
            )
            configs = list(result.scalars().all())
            if not configs:
                return None

            target = configs[0]
            if len(configs) > 1:
                names = ", ".join(c.name for c in configs)
                logger.warning("Multiple VPN configs marked autostart (%s); only starting %s", names, target.name)

            # If another worker in a previous run already flipped status,
            # don't start a second one that would _stop_all() the first.
            if target.status in ("connecting", "connected"):
                logger.info("Autostart skipped — '%s' already in state %s", target.name, target.status)
                return None

            target.status = "connecting"
            db.add(target)
            # commit happens at end of db.begin() — lock released, flag persisted
            return target.id


async def autostart_vpns() -> None:
    """Pick one autostart target and connect it. Safe to run from multiple workers."""
    from app.database import async_session
    from app.models import VPNConfig
    from app.services import vpn_manager

    try:
        target_id = await _reserve_autostart_target()
    except Exception as e:
        logger.exception("Autostart reservation failed: %s", e)
        return
    if target_id is None:
        return

    async with async_session() as db:
        attached = await db.get(VPNConfig, target_id)
        if not attached:
            return
        logger.info("Autostarting VPN '%s'", attached.name)
        try:
            status = await vpn_manager.connect(attached, db)
            logger.info("Autostart result for '%s': %s", attached.name, status)
        except Exception as e:
            logger.exception("Autostart failed for '%s': %s", attached.name, e)


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
    # Fire-and-forget: openvpn's --daemon init can block for seconds on slow
    # upstreams; running it inside lifespan would stall the HTTP server.
    task = asyncio.create_task(autostart_vpns())
    app.state.autostart_task = task  # keep a ref so it doesn't get GC'd
    yield
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
