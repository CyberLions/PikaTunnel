from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import HealthResponse, NginxHealthInfo, VPNHealthInfo
from app.services import nginx_config, vpn_manager
from app.models import VPNConfig
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    nginx_status_info = await nginx_config.get_nginx_status()
    nginx_info = NginxHealthInfo(
        running=nginx_status_info.get("running", False),
        config_valid=nginx_status_info.get("config_valid", False),
    )

    vpn_enabled = False
    vpn_status = "disabled"
    result = await db.execute(select(VPNConfig).where(VPNConfig.enabled == True).limit(1))
    vpn_config = result.scalar_one_or_none()
    if vpn_config:
        vpn_enabled = True
        vpn_status = await vpn_manager.get_status(vpn_config)

    overall = "healthy" if db_ok else "unhealthy"
    return HealthResponse(
        status=overall,
        database=db_ok,
        nginx=nginx_info,
        vpn=VPNHealthInfo(enabled=vpn_enabled, status=vpn_status),
    )
