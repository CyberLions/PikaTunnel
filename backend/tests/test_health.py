import pytest


async def test_health_returns_200(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] is True


async def test_health_no_auth_required(client):
    """Health endpoint should work without authentication."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
