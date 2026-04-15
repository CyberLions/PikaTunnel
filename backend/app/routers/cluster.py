from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ClusterSettings, ProxyRoute
from app.schemas import ClusterSettingsUpdate, ClusterSettingsResponse
from app.services.oidc import require_admin

router = APIRouter(prefix="/api/v1/cluster", tags=["cluster"])


async def _get_or_create(db: AsyncSession) -> ClusterSettings:
    result = await db.execute(select(ClusterSettings).limit(1))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ClusterSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


def _to_response(settings: ClusterSettings) -> dict:
    resp = ClusterSettingsResponse.model_validate(settings)
    resp.has_token = bool(settings.k8s_token)
    resp.has_ca_cert = bool(settings.k8s_ca_cert)
    return resp


@router.get("/settings", response_model=ClusterSettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    settings = await _get_or_create(db)
    return _to_response(settings)


@router.put("/settings", response_model=ClusterSettingsResponse)
async def update_settings(data: ClusterSettingsUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    settings = await _get_or_create(db)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    return _to_response(settings)


@router.post("/settings/test-connection")
async def test_connection(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    settings = await _get_or_create(db)
    if not settings.k8s_api_url and not settings.k8s_in_cluster:
        return {"connected": False, "error": "No Kubernetes API URL configured"}

    try:
        from app.services.k8s_ingress import test_connection as k8s_test
        return await k8s_test(db)
    except ImportError:
        return {"connected": False, "error": "kubernetes package not installed"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/sync-all-ingresses")
async def sync_all_ingresses(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    from app.services.k8s_ingress import sync_ingress
    result = await db.execute(select(ProxyRoute).where(ProxyRoute.k8s_ingress_enabled == True))
    routes = result.scalars().all()
    synced = 0
    errors = 0
    for route in routes:
        try:
            await sync_ingress(route, db)
            synced += 1
        except Exception:
            errors += 1
    return {"synced": synced, "errors": errors, "total": len(routes)}


@router.delete("/settings/credentials")
async def clear_credentials(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    settings = await _get_or_create(db)
    settings.k8s_token = None
    settings.k8s_ca_cert = None
    await db.commit()
    return {"message": "Credentials cleared"}
