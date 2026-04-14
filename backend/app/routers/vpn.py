import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import VPNConfig
from app.schemas import VPNConfigCreate, VPNConfigUpdate, VPNConfigResponse, VPNStatusResponse
from app.services import vpn_manager

router = APIRouter(prefix="/api/v1/vpn", tags=["vpn"])


@router.get("/config", response_model=list[VPNConfigResponse])
async def list_vpn_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VPNConfig))
    return result.scalars().all()


@router.post("/config", response_model=VPNConfigResponse, status_code=201)
async def create_vpn_config(data: VPNConfigCreate, db: AsyncSession = Depends(get_db)):
    config = VPNConfig(**data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/config/{config_id}", response_model=VPNConfigResponse)
async def update_vpn_config(config_id: uuid.UUID, data: VPNConfigUpdate, db: AsyncSession = Depends(get_db)):
    config = await db.get(VPNConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VPN config not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/config/{config_id}", status_code=204)
async def delete_vpn_config(config_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    config = await db.get(VPNConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VPN config not found")
    await db.delete(config)
    await db.commit()


@router.post("/config/{config_id}/connect", response_model=VPNStatusResponse)
async def connect_vpn(config_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    config = await db.get(VPNConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VPN config not found")
    status = await vpn_manager.connect(config, db)
    return VPNStatusResponse(id=config.id, name=config.name, vpn_type=config.vpn_type, status=status)


@router.post("/config/{config_id}/disconnect", response_model=VPNStatusResponse)
async def disconnect_vpn(config_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    config = await db.get(VPNConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VPN config not found")
    status = await vpn_manager.disconnect(config, db)
    return VPNStatusResponse(id=config.id, name=config.name, vpn_type=config.vpn_type, status=status)


@router.get("/status", response_model=list[VPNStatusResponse])
async def vpn_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VPNConfig))
    configs = result.scalars().all()
    statuses = []
    for config in configs:
        current = await vpn_manager.get_status(config)
        statuses.append(VPNStatusResponse(id=config.id, name=config.name, vpn_type=config.vpn_type, status=current))
    return statuses
