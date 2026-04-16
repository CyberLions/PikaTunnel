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


async def autostart_vpns() -> None:
    """Start any VPN config flagged enabled + autostart after boot."""
    from sqlalchemy import select
    from app.database import async_session
    from app.models import VPNConfig
    from app.services import vpn_manager

    async with async_session() as db:
        result = await db.execute(
            select(VPNConfig).where(VPNConfig.enabled == True, VPNConfig.autostart == True)  # noqa: E712
        )
        configs = list(result.scalars().all())

    if not configs:
        return

    # Only one VPN can run per container; if multiple are flagged, warn and use the first.
    if len(configs) > 1:
        names = ", ".join(c.name for c in configs)
        logger.warning("Multiple VPN configs marked autostart (%s); only starting %s", names, configs[0].name)

    target = configs[0]
    logger.info("Autostarting VPN '%s'", target.name)
    async with async_session() as db:
        attached = await db.get(VPNConfig, target.id)
        if not attached:
            return
        try:
            status = await vpn_manager.connect(attached, db)
            logger.info("Autostart result for '%s': %s", target.name, status)
        except Exception as e:
            logger.exception("Autostart failed for '%s': %s", target.name, e)


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
    try:
        await autostart_vpns()
    except Exception as e:
        logger.exception("VPN autostart raised: %s", e)
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
