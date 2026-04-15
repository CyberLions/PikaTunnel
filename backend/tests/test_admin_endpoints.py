import pytest


class TestVPNRequiresAdmin:
    async def test_list_vpns_requires_admin(self, client, user_headers):
        resp = await client.get("/api/v1/vpn/config", headers=user_headers)
        assert resp.status_code == 403

    async def test_list_vpns_as_admin(self, client, admin_headers):
        resp = await client.get("/api/v1/vpn/config", headers=admin_headers)
        assert resp.status_code == 200

    async def test_vpn_no_auth(self, client):
        resp = await client.get("/api/v1/vpn/config")
        assert resp.status_code == 401


class TestNginxRequiresAdmin:
    async def test_nginx_status_requires_admin(self, client, user_headers):
        resp = await client.get("/api/v1/nginx/status", headers=user_headers)
        assert resp.status_code == 403

    async def test_nginx_status_as_admin(self, client, admin_headers):
        resp = await client.get("/api/v1/nginx/status", headers=admin_headers)
        assert resp.status_code == 200

    async def test_nginx_config_requires_admin(self, client, user_headers):
        resp = await client.get("/api/v1/nginx/config", headers=user_headers)
        assert resp.status_code == 403


class TestClusterSettingsRequiresAdmin:
    async def test_settings_requires_admin(self, client, user_headers):
        resp = await client.get("/api/v1/cluster/settings", headers=user_headers)
        assert resp.status_code == 403

    async def test_settings_as_admin(self, client, admin_headers):
        resp = await client.get("/api/v1/cluster/settings", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_ingress_class"] == "nginx"
        assert data["has_token"] is False

    async def test_update_settings(self, client, admin_headers):
        resp = await client.put(
            "/api/v1/cluster/settings",
            json={"k8s_namespace": "production", "default_cluster_issuer": "letsencrypt-prod"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["k8s_namespace"] == "production"
        assert data["default_cluster_issuer"] == "letsencrypt-prod"

    async def test_update_token_shows_has_token(self, client, admin_headers):
        resp = await client.put(
            "/api/v1/cluster/settings",
            json={"k8s_token": "eyJhbGciOiJSUzI1NiJ9.test"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["has_token"] is True

    async def test_clear_credentials(self, client, admin_headers):
        await client.put(
            "/api/v1/cluster/settings",
            json={"k8s_token": "some-token", "k8s_ca_cert": "some-cert"},
            headers=admin_headers,
        )
        resp = await client.delete("/api/v1/cluster/settings/credentials", headers=admin_headers)
        assert resp.status_code == 200

        resp = await client.get("/api/v1/cluster/settings", headers=admin_headers)
        assert resp.json()["has_token"] is False
        assert resp.json()["has_ca_cert"] is False
