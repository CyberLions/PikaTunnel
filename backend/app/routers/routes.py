import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ProxyRoute
from app.schemas import ProxyRouteCreate, ProxyRouteUpdate, ProxyRouteResponse
from app.services import nginx_config
from app.services import k8s_ingress
from app.services.oidc import get_current_user, user_has_group

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@router.get("", response_model=dict)
async def list_routes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = select(ProxyRoute)
    if enabled is not None:
        query = query.where(ProxyRoute.enabled == enabled)

    result = await db.execute(query)
    all_routes = result.scalars().all()

    # Filter by user groups
    visible = [r for r in all_routes if user_has_group(user, r.groups)]
    total = len(visible)

    # Paginate
    start = (page - 1) * per_page
    items = [ProxyRouteResponse.model_validate(r) for r in visible[start:start + per_page]]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("", response_model=ProxyRouteResponse, status_code=201)
async def create_route(data: ProxyRouteCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = ProxyRoute(**data.model_dump())
    db.add(route)
    await db.commit()
    await db.refresh(route)
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    try:
        await k8s_ingress.sync_ingress(route, db)
    except Exception:
        pass
    return route


@router.get("/{route_id}", response_model=ProxyRouteResponse)
async def get_route(route_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(ProxyRoute, route_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.put("/{route_id}", response_model=ProxyRouteResponse)
async def update_route(route_id: uuid.UUID, data: ProxyRouteUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(ProxyRoute, route_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Route not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(route, key, value)
    await db.commit()
    await db.refresh(route)
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    try:
        await k8s_ingress.sync_ingress(route, db)
    except Exception:
        pass
    return route


@router.delete("/{route_id}", status_code=204)
async def delete_route(route_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(ProxyRoute, route_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Route not found")
    try:
        await k8s_ingress.delete_ingress(route, db)
    except Exception:
        pass
    await db.delete(route)
    await db.commit()
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass


@router.post("/{route_id}/sync-ingress")
async def sync_route_ingress(route_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(ProxyRoute, route_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Route not found")
    try:
        await k8s_ingress.sync_ingress(route, db)
        return {"message": f"Ingress synced for {route.name}"}
    except Exception as e:
        return {"message": f"Sync failed: {e}"}
