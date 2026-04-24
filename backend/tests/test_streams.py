import pytest


STREAM_PAYLOAD = {
    "name": "test-stream",
    "destination": "10.0.0.1",
    "port": 25577,
    "listen_port": 25565,
    "protocol": "tcp",
    "proxy_protocol": False,
    "enabled": True,
}


class TestStreamCRUD:
    async def test_create_stream(self, client, admin_headers):
        resp = await client.post("/api/v1/streams", json=STREAM_PAYLOAD, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-stream"
        assert data["listen_port"] == 25565
        assert data["groups"] == ""

    async def test_list_streams(self, client, admin_headers):
        await client.post("/api/v1/streams", json=STREAM_PAYLOAD, headers=admin_headers)
        resp = await client.get("/api/v1/streams", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_update_stream(self, client, admin_headers):
        create = await client.post("/api/v1/streams", json=STREAM_PAYLOAD, headers=admin_headers)
        stream_id = create.json()["id"]
        resp = await client.put(
            f"/api/v1/streams/{stream_id}",
            json={"port": 9999},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["port"] == 9999

    async def test_delete_stream(self, client, admin_headers):
        create = await client.post("/api/v1/streams", json=STREAM_PAYLOAD, headers=admin_headers)
        stream_id = create.json()["id"]
        resp = await client.delete(f"/api/v1/streams/{stream_id}", headers=admin_headers)
        assert resp.status_code == 204

    async def test_create_udp_stream(self, client, admin_headers):
        payload = {**STREAM_PAYLOAD, "name": "udp-stream", "protocol": "udp"}
        resp = await client.post("/api/v1/streams", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        assert resp.json()["protocol"] == "udp"

    async def test_export_streams_csv(self, client, admin_headers):
        await client.post("/api/v1/streams", json=STREAM_PAYLOAD, headers=admin_headers)

        resp = await client.get("/api/v1/streams/export.csv", headers=admin_headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "test-stream" in resp.text


class TestStreamGroupFiltering:
    async def test_user_sees_own_group_streams(self, client, admin_headers, user_headers):
        await client.post("/api/v1/streams", json={**STREAM_PAYLOAD, "name": "s1", "groups": "network-team"}, headers=admin_headers)
        await client.post("/api/v1/streams", json={**STREAM_PAYLOAD, "name": "s2", "listen_port": 25566, "groups": "other"}, headers=admin_headers)
        await client.post("/api/v1/streams", json={**STREAM_PAYLOAD, "name": "s3", "listen_port": 25567, "groups": ""}, headers=admin_headers)

        resp = await client.get("/api/v1/streams", headers=user_headers)
        data = resp.json()
        assert data["total"] == 2
        names = {s["name"] for s in data["items"]}
        assert names == {"s1", "s3"}
