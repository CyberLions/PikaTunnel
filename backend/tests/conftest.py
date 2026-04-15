import asyncio
import pytest
import os
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://pikatunnel:pikatunnel@db:5432/pikatunnel_test",
)
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["NGINX_CONFIG_PATH"] = "/tmp/test-nginx.conf"
os.environ["NGINX_STREAM_CONFIG_PATH"] = "/tmp/test-nginx-stream.conf"

from app.models import Base
from app.database import get_db
from app.services.oidc import create_access_token

# Build a test-only FastAPI app with no lifespan (avoid startup DB conflicts)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import routes, streams, vpn, auth, health, nginx, cluster

test_app = FastAPI(title="PikaTunnel Test")
test_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
test_app.include_router(routes.router)
test_app.include_router(streams.router)
test_app.include_router(vpn.router)
test_app.include_router(auth.router)
test_app.include_router(health.router)
test_app.include_router(nginx.router)
test_app.include_router(cluster.router)

TEST_DB_URL = os.environ["DATABASE_URL"]
test_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    async with TestSession() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture
async def client():
    async def override_get_db():
        async with TestSession() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    test_app.dependency_overrides.clear()


@pytest.fixture
def admin_token():
    return create_access_token({
        "sub": "test-admin",
        "email": "admin@test.com",
        "name": "Test Admin",
        "groups": ["admin"],
    })


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_token():
    return create_access_token({
        "sub": "test-user",
        "email": "user@test.com",
        "name": "Test User",
        "groups": ["network-team"],
    })


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def no_group_token():
    return create_access_token({
        "sub": "test-nobody",
        "email": "nobody@test.com",
        "name": "Nobody",
        "groups": [],
    })


@pytest.fixture
def no_group_headers(no_group_token):
    return {"Authorization": f"Bearer {no_group_token}"}
