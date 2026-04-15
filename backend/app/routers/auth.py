import uuid
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models import OIDCProvider
from app.schemas import OIDCProviderCreate, OIDCProviderUpdate, OIDCProviderResponse, UserInfo
from app.services.oidc import (
    get_authorization_url,
    exchange_code,
    extract_groups,
    create_access_token,
    get_current_user,
    get_auth_provider,
    list_auth_providers,
    require_admin,
    resolve_db_provider,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/providers", response_model=list[OIDCProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    return await list_auth_providers(db)


@router.post("/providers", response_model=OIDCProviderResponse, status_code=201)
async def create_provider(data: OIDCProviderCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    provider = OIDCProvider(**data.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return resolve_db_provider(provider)


@router.put("/providers/{provider_id}", response_model=OIDCProviderResponse)
async def update_provider(provider_id: uuid.UUID, data: OIDCProviderUpdate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    provider = await db.get(OIDCProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, key, value)
    await db.commit()
    await db.refresh(provider)
    return resolve_db_provider(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: uuid.UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    provider = await db.get(OIDCProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
    await db.commit()


@router.get("/login/{provider_id}")
async def login(provider_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    provider = await get_auth_provider(provider_id, db)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="Provider not found or disabled")
    redirect_uri = str(request.url_for("callback").include_query_params(provider_id=provider.id))
    url = await get_authorization_url(provider, redirect_uri)
    return RedirectResponse(url)


@router.get("/callback", name="callback")
async def callback(code: str, provider_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    provider = await get_auth_provider(provider_id, db)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=400, detail="No active OIDC provider")

    redirect_uri = str(request.url_for("callback").include_query_params(provider_id=provider.id))
    userinfo = await exchange_code(provider, code, redirect_uri)

    groups = extract_groups(userinfo, provider.groups_claim)

    token = create_access_token({
        "sub": userinfo.get("sub", ""),
        "email": userinfo.get("email"),
        "name": userinfo.get("name"),
        "groups": groups,
        "admin_group": provider.admin_group or settings.ADMIN_GROUP,
    })

    # Redirect to frontend with token as query param
    frontend_url = f"/?{urlencode({'token': token})}"
    return RedirectResponse(frontend_url)


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_current_user)):
    return UserInfo(
        sub=user.get("sub", ""),
        email=user.get("email"),
        name=user.get("name"),
        groups=user.get("groups", []),
        admin_group=user.get("admin_group") or settings.ADMIN_GROUP,
    )


@router.post("/logout")
async def logout():
    return {"message": "Logged out. Discard your token client-side."}
