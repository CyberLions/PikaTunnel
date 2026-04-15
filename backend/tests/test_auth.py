import pytest
from app.config import AuthProviderSettings, settings
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

    def test_custom_admin_group_sees_everything(self):
        user = {"groups": ["platform-admins"], "admin_group": "platform-admins"}
        assert user_has_group(user, "network-team") is True


class TestAuthEndpoints:
    async def test_me_with_token(self, client, admin_headers):
        resp = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "test-admin"
        assert data["groups"] == ["admin"]
        assert data["admin_group"] == "admin"

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

    async def test_providers_list_includes_env_config(self, client):
        original = settings.AUTH_PROVIDERS
        settings.AUTH_PROVIDERS = [
            AuthProviderSettings(
                id="authentik",
                name="Authentik",
                issuer_url="https://auth.example.com/application/o/pikatunnel/",
                client_id="env-client",
                client_secret="env-secret",
                groups_claim="groups",
                admin_group="platform-admins",
            )
        ]
        try:
            resp = await client.get("/api/v1/auth/providers")
        finally:
            settings.AUTH_PROVIDERS = original

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "env:authentik"
        assert data[0]["source"] == "environment"
        assert data[0]["read_only"] is True
        assert data[0]["admin_group"] == "platform-admins"

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
        assert data["admin_group"] == "admin"
        assert data["read_only"] is False
