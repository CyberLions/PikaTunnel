import pytest


ROUTE_PAYLOAD = {
    "name": "test-route",
    "host": "test.example.com",
    "path": "/",
    "destination": "10.0.0.1",
    "port": 80,
    "ssl_enabled": False,
    "enabled": True,
}


class TestRouteCRUD:
    async def test_create_route(self, client, admin_headers):
        resp = await client.post("/api/v1/routes", json=ROUTE_PAYLOAD, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-route"
        assert data["host"] == "test.example.com"
        assert data["groups"] == ""
        assert data["k8s_ingress_enabled"] is False

    async def test_list_routes(self, client, admin_headers):
        await client.post("/api/v1/routes", json=ROUTE_PAYLOAD, headers=admin_headers)
        resp = await client.get("/api/v1/routes", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    async def test_get_route(self, client, admin_headers):
        create = await client.post("/api/v1/routes", json=ROUTE_PAYLOAD, headers=admin_headers)
        route_id = create.json()["id"]
        resp = await client.get(f"/api/v1/routes/{route_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-route"

    async def test_update_route(self, client, admin_headers):
        create = await client.post("/api/v1/routes", json=ROUTE_PAYLOAD, headers=admin_headers)
        route_id = create.json()["id"]
        resp = await client.put(
            f"/api/v1/routes/{route_id}",
            json={"port": 8080},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["port"] == 8080

    async def test_delete_route(self, client, admin_headers):
        create = await client.post("/api/v1/routes", json=ROUTE_PAYLOAD, headers=admin_headers)
        route_id = create.json()["id"]
        resp = await client.delete(f"/api/v1/routes/{route_id}", headers=admin_headers)
        assert resp.status_code == 204

        resp = await client.get(f"/api/v1/routes/{route_id}", headers=admin_headers)
        assert resp.status_code == 404

    async def test_create_route_with_groups(self, client, admin_headers):
        payload = {**ROUTE_PAYLOAD, "groups": "network-team,devops"}
        resp = await client.post("/api/v1/routes", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        assert resp.json()["groups"] == "network-team,devops"

    async def test_create_route_with_k8s(self, client, admin_headers):
        payload = {
            **ROUTE_PAYLOAD,
            "k8s_ingress_enabled": True,
            "k8s_cert_manager_enabled": True,
            "k8s_authentik_enabled": False,
            "k8s_proxy_body_size": "50m",
        }
        resp = await client.post("/api/v1/routes", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["k8s_ingress_enabled"] is True
        assert data["k8s_cert_manager_enabled"] is True
        assert data["k8s_proxy_body_size"] == "50m"


class TestRouteGroupFiltering:
    async def test_admin_sees_all_routes(self, client, admin_headers):
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "r1", "groups": "team-a"}, headers=admin_headers)
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "r2", "groups": "team-b"}, headers=admin_headers)
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "r3", "groups": ""}, headers=admin_headers)

        resp = await client.get("/api/v1/routes", headers=admin_headers)
        assert resp.json()["total"] == 3

    async def test_user_sees_own_group_routes(self, client, admin_headers, user_headers):
        # user has group "network-team"
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "r1", "groups": "network-team"}, headers=admin_headers)
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "r2", "groups": "other-team"}, headers=admin_headers)
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "r3", "groups": ""}, headers=admin_headers)

        resp = await client.get("/api/v1/routes", headers=user_headers)
        data = resp.json()
        assert data["total"] == 2  # r1 (matching group) + r3 (no groups = visible to all)
        names = {r["name"] for r in data["items"]}
        assert names == {"r1", "r3"}

    async def test_user_cannot_access_other_group_route(self, client, admin_headers, user_headers):
        create = await client.post(
            "/api/v1/routes",
            json={**ROUTE_PAYLOAD, "groups": "other-team"},
            headers=admin_headers,
        )
        route_id = create.json()["id"]

        resp = await client.get(f"/api/v1/routes/{route_id}", headers=user_headers)
        assert resp.status_code == 404

    async def test_user_cannot_update_other_group_route(self, client, admin_headers, user_headers):
        create = await client.post(
            "/api/v1/routes",
            json={**ROUTE_PAYLOAD, "groups": "other-team"},
            headers=admin_headers,
        )
        route_id = create.json()["id"]

        resp = await client.put(
            f"/api/v1/routes/{route_id}",
            json={"port": 9999},
            headers=user_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_delete_other_group_route(self, client, admin_headers, user_headers):
        create = await client.post(
            "/api/v1/routes",
            json={**ROUTE_PAYLOAD, "groups": "other-team"},
            headers=admin_headers,
        )
        route_id = create.json()["id"]

        resp = await client.delete(f"/api/v1/routes/{route_id}", headers=user_headers)
        assert resp.status_code == 404

    async def test_no_group_user_only_sees_ungrouped(self, client, admin_headers, no_group_headers):
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "grouped", "groups": "team-a"}, headers=admin_headers)
        await client.post("/api/v1/routes", json={**ROUTE_PAYLOAD, "name": "ungrouped", "groups": ""}, headers=admin_headers)

        resp = await client.get("/api/v1/routes", headers=no_group_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "ungrouped"


class TestRoutePagination:
    async def test_pagination(self, client, admin_headers):
        for i in range(5):
            await client.post(
                "/api/v1/routes",
                json={**ROUTE_PAYLOAD, "name": f"route-{i}"},
                headers=admin_headers,
            )

        resp = await client.get("/api/v1/routes?page=1&per_page=2", headers=admin_headers)
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1

        resp = await client.get("/api/v1/routes?page=3&per_page=2", headers=admin_headers)
        data = resp.json()
        assert len(data["items"]) == 1
