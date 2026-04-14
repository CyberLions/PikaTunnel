from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.schemas import NginxConfigResponse, NginxStatusResponse
from app.services import nginx_config

router = APIRouter(prefix="/api/v1/nginx", tags=["nginx"])


@router.post("/reload")
async def reload(db: AsyncSession = Depends(get_db)):
    http_conf, stream_conf = await nginx_config.generate_and_reload(db)
    return {"message": "Nginx configuration regenerated and reload triggered"}


@router.get("/config", response_model=NginxConfigResponse)
async def get_config():
    http_path = Path(settings.NGINX_CONFIG_PATH)
    stream_path = Path(settings.NGINX_STREAM_CONFIG_PATH)
    http_content = http_path.read_text() if http_path.exists() else ""
    stream_content = stream_path.read_text() if stream_path.exists() else ""
    return NginxConfigResponse(http_config=http_content, stream_config=stream_content)


@router.get("/status", response_model=NginxStatusResponse)
async def status():
    info = await nginx_config.get_nginx_status()
    return NginxStatusResponse(running=info.get("running", False), pid=info.get("pid"))
