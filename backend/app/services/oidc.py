import logging
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models import OIDCProvider

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


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
            return {"sub": "dev-user", "email": "dev@localhost", "name": "Development User"}

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return payload


def require_auth(user: dict | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
