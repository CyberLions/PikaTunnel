import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ProxyRoute
from app.schemas import ProxyRouteCreate, ProxyRouteUpdate, ProxyRouteResponse
from app.services import nginx_config

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@router.get("", response_model=dict)
async def list_routes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(ProxyRoute)
    count_query = select(func.count(ProxyRoute.id))
    if enabled is not None:
        query = query.where(ProxyRoute.enabled == enabled)
        count_query = count_query.where(ProxyRoute.enabled == enabled)

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    items = [ProxyRouteResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("", response_model=ProxyRouteResponse, status_code=201)
async def create_route(data: ProxyRouteCreate, db: AsyncSession = Depends(get_db)):
    route = ProxyRoute(**data.model_dump())
    db.add(route)
    await db.commit()
    await db.refresh(route)
    await nginx_config.generate_and_reload(db)
    return route


@router.get("/{route_id}", response_model=ProxyRouteResponse)
async def get_route(route_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    route = await db.get(ProxyRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.put("/{route_id}", response_model=ProxyRouteResponse)
async def update_route(route_id: uuid.UUID, data: ProxyRouteUpdate, db: AsyncSession = Depends(get_db)):
    route = await db.get(ProxyRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(route, key, value)
    await db.commit()
    await db.refresh(route)
    await nginx_config.generate_and_reload(db)
    return route


@router.delete("/{route_id}", status_code=204)
async def delete_route(route_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    route = await db.get(ProxyRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    await db.delete(route)
    await db.commit()
    await nginx_config.generate_and_reload(db)
