import pytest
from app.services.oidc import (
    create_access_token,
    decode_access_token,
    extract_groups,
    user_has_group,
)


class TestJWT:
    def test_create_and_decode_token(self):
        data = {"sub": "user1", "email": "u@test.com", "groups": ["admin"]}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user1"
        assert decoded["groups"] == ["admin"]

    def test_decode_invalid_token(self):
        assert decode_access_token("garbage.token.here") is None

    def test_decode_empty_token(self):
        assert decode_access_token("") is None


class TestExtractGroups:
    def test_simple_list(self):
        userinfo = {"groups": ["admin", "devops"]}
        assert extract_groups(userinfo, "groups") == ["admin", "devops"]

    def test_nested_claim(self):
        userinfo = {"realm_access": {"roles": ["editor", "viewer"]}}
        assert extract_groups(userinfo, "realm_access.roles") == ["editor", "viewer"]

    def test_comma_separated_string(self):
        userinfo = {"groups": "admin, devops, network"}
        assert extract_groups(userinfo, "groups") == ["admin", "devops", "network"]

    def test_missing_claim(self):
        assert extract_groups({}, "groups") == []

    def test_missing_nested_claim(self):
        assert extract_groups({"realm_access": {}}, "realm_access.roles") == []

    def test_non_dict_intermediate(self):
        assert extract_groups({"a": "string"}, "a.b") == []


class TestUserHasGroup:
    def test_admin_sees_everything(self):
        user = {"groups": ["admin"]}
        assert user_has_group(user, "network-team") is True
        assert user_has_group(user, "anything") is True
        assert user_has_group(user, "") is True

    def test_empty_groups_visible_to_all(self):
        user = {"groups": ["viewer"]}
        assert user_has_group(user, "") is True

    def test_matching_group(self):
        user = {"groups": ["network-team", "devops"]}
        assert user_has_group(user, "network-team") is True
        assert user_has_group(user, "devops,network-team") is True

    def test_no_matching_group(self):
        user = {"groups": ["network-team"]}
        assert user_has_group(user, "devops") is False

    def test_multiple_route_groups(self):
        user = {"groups": ["frontend"]}
        assert user_has_group(user, "frontend, backend") is True

    def test_no_user_groups(self):
        user = {"groups": []}
        assert user_has_group(user, "devops") is False
        assert user_has_group(user, "") is True


class TestAuthEndpoints:
    async def test_me_with_token(self, client, admin_headers):
        resp = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "test-admin"
        assert data["groups"] == ["admin"]

    async def test_me_without_token_returns_401(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_with_bad_token(self, client):
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad"})
        assert resp.status_code == 401

    async def test_providers_list_no_auth(self, client):
        """Listing providers is public (login page needs it)."""
        resp = await client.get("/api/v1/auth/providers")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_provider_requires_admin(self, client, user_headers):
        resp = await client.post(
            "/api/v1/auth/providers",
            json={"name": "test", "issuer_url": "https://example.com", "client_id": "id", "client_secret": "secret"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    async def test_create_provider_as_admin(self, client, admin_headers):
        resp = await client.post(
            "/api/v1/auth/providers",
            json={"name": "test", "issuer_url": "https://example.com", "client_id": "id", "client_secret": "secret"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test"
        assert data["groups_claim"] == "groups"
