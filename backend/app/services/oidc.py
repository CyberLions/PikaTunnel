import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import AuthProviderSettings, settings
from app.database import get_db
from app.models import OIDCProvider

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60
ENV_PROVIDER_TIMESTAMP = datetime.fromtimestamp(0, tz=timezone.utc)


@dataclass(slots=True)
class ResolvedOIDCProvider:
    id: str
    name: str
    issuer_url: str
    client_id: str
    client_secret: str
    scopes: str
    groups_claim: str
    enabled: bool
    admin_group: str
    source: str
    read_only: bool
    created_at: datetime
    updated_at: datetime


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def resolve_env_provider(provider: AuthProviderSettings, index: int) -> ResolvedOIDCProvider:
    provider_id = provider.id.strip() if provider.id else _slugify(provider.name) or f"provider-{index + 1}"
    return ResolvedOIDCProvider(
        id=f"env:{provider_id}",
        name=provider.name,
        issuer_url=provider.issuer_url,
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        scopes=provider.scopes,
        groups_claim=provider.groups_claim,
        enabled=provider.enabled,
        admin_group=provider.admin_group or settings.ADMIN_GROUP,
        source="environment",
        read_only=True,
        created_at=ENV_PROVIDER_TIMESTAMP,
        updated_at=ENV_PROVIDER_TIMESTAMP,
    )


def resolve_db_provider(provider: OIDCProvider) -> ResolvedOIDCProvider:
    return ResolvedOIDCProvider(
        id=str(provider.id),
        name=provider.name,
        issuer_url=provider.issuer_url,
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        scopes=provider.scopes,
        groups_claim=provider.groups_claim,
        enabled=provider.enabled,
        admin_group=settings.ADMIN_GROUP,
        source="database",
        read_only=False,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def list_env_providers() -> list[ResolvedOIDCProvider]:
    return [resolve_env_provider(provider, index) for index, provider in enumerate(settings.AUTH_PROVIDERS)]


async def list_auth_providers(db: AsyncSession) -> list[ResolvedOIDCProvider]:
    result = await db.execute(select(OIDCProvider))
    db_providers = [resolve_db_provider(provider) for provider in result.scalars().all()]
    return [*list_env_providers(), *db_providers]


async def get_auth_provider(provider_id: str, db: AsyncSession) -> ResolvedOIDCProvider | None:
    if provider_id.startswith("env:"):
        return next((provider for provider in list_env_providers() if provider.id == provider_id), None)

    try:
        db_provider_id = uuid.UUID(provider_id)
    except ValueError:
        return None

    provider = await db.get(OIDCProvider, db_provider_id)
    if not provider:
        return None
    return resolve_db_provider(provider)


def extract_groups(userinfo: dict, groups_claim: str) -> list[str]:
    """Extract groups from userinfo using dot-notation claim path."""
    value = userinfo
    for part in groups_claim.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return []
    if isinstance(value, list):
        return [str(g) for g in value]
    if isinstance(value, str):
        return [g.strip() for g in value.split(",") if g.strip()]
    return []


async def get_oidc_client(provider: OIDCProvider) -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        scope=provider.scopes,
    )


async def get_authorization_url(provider: OIDCProvider, redirect_uri: str) -> str:
    client = await get_oidc_client(provider)
    well_known = f"{provider.issuer_url.rstrip('/')}/.well-known/openid-configuration"

    import httpx
    async with httpx.AsyncClient() as http:
        resp = await http.get(well_known)
        metadata = resp.json()

    authorization_endpoint = metadata["authorization_endpoint"]
    url, _ = client.create_authorization_url(authorization_endpoint, redirect_uri=redirect_uri)
    return url


async def exchange_code(provider: OIDCProvider, code: str, redirect_uri: str) -> dict:
    client = await get_oidc_client(provider)
    well_known = f"{provider.issuer_url.rstrip('/')}/.well-known/openid-configuration"

    import httpx
    async with httpx.AsyncClient() as http:
        resp = await http.get(well_known)
        metadata = resp.json()

    token_endpoint = metadata["token_endpoint"]
    token = await client.fetch_token(
        token_endpoint,
        code=code,
        redirect_uri=redirect_uri,
    )

    userinfo_endpoint = metadata.get("userinfo_endpoint")
    if userinfo_endpoint:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            return resp.json()

    return token


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    if settings.ENVIRONMENT == "development":
        if not credentials:
            return {
                "sub": "dev-user",
                "email": "dev@localhost",
                "name": "Development User",
                "groups": [settings.ADMIN_GROUP],
                "admin_group": settings.ADMIN_GROUP,
            }

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return payload


def get_admin_group(user: dict) -> str:
    return str(user.get("admin_group") or settings.ADMIN_GROUP)


def require_auth(user: dict | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin(user: dict = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    groups = user.get("groups", [])
    if get_admin_group(user) not in groups:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def user_has_group(user: dict, route_groups: str) -> bool:
    """Check if user has access to a route based on its groups."""
    user_groups = set(user.get("groups", []))
    if get_admin_group(user) in user_groups:
        return True
    if not route_groups:
        return True
    route_group_set = {g.strip() for g in route_groups.split(",") if g.strip()}
    return bool(user_groups & route_group_set)
