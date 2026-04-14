import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import OIDCProvider
from app.schemas import OIDCProviderCreate, OIDCProviderUpdate, OIDCProviderResponse, UserInfo
from app.services.oidc import (
    get_authorization_url,
    exchange_code,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/providers", response_model=list[OIDCProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OIDCProvider))
    return result.scalars().all()


@router.post("/providers", response_model=OIDCProviderResponse, status_code=201)
async def create_provider(data: OIDCProviderCreate, db: AsyncSession = Depends(get_db)):
    provider = OIDCProvider(**data.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.put("/providers/{provider_id}", response_model=OIDCProviderResponse)
async def update_provider(provider_id: uuid.UUID, data: OIDCProviderUpdate, db: AsyncSession = Depends(get_db)):
    provider = await db.get(OIDCProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(provider, key, value)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await db.get(OIDCProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
    await db.commit()


@router.get("/login/{provider_id}")
async def login(provider_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    provider = await db.get(OIDCProvider, provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="Provider not found or disabled")
    redirect_uri = str(request.url_for("callback"))
    url = await get_authorization_url(provider, redirect_uri)
    return RedirectResponse(url)


@router.get("/callback", name="callback")
async def callback(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OIDCProvider).where(OIDCProvider.enabled == True).limit(1))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=400, detail="No active OIDC provider")

    redirect_uri = str(request.url_for("callback"))
    userinfo = await exchange_code(provider, code, redirect_uri)

    token = create_access_token({
        "sub": userinfo.get("sub", ""),
        "email": userinfo.get("email"),
        "name": userinfo.get("name"),
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_current_user)):
    return UserInfo(
        sub=user.get("sub", ""),
        email=user.get("email"),
        name=user.get("name"),
    )


@router.post("/logout")
async def logout():
    return {"message": "Logged out. Discard your token client-side."}
