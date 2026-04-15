import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import routes, streams, vpn, auth, health, nginx, cluster

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting pikatunnel (env=%s)", settings.ENVIRONMENT)
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured")
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
