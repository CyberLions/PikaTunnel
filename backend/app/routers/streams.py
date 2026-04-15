import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import StreamRoute
from app.schemas import StreamRouteCreate, StreamRouteUpdate, StreamRouteResponse
from app.services import nginx_config
from app.services.oidc import get_current_user, user_has_group

router = APIRouter(prefix="/api/v1/streams", tags=["streams"])


@router.get("", response_model=dict)
async def list_streams(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = select(StreamRoute)
    if enabled is not None:
        query = query.where(StreamRoute.enabled == enabled)

    result = await db.execute(query)
    all_streams = result.scalars().all()

    visible = [s for s in all_streams if user_has_group(user, s.groups)]
    total = len(visible)

    start = (page - 1) * per_page
    items = [StreamRouteResponse.model_validate(s) for s in visible[start:start + per_page]]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("", response_model=StreamRouteResponse, status_code=201)
async def create_stream(data: StreamRouteCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = StreamRoute(**data.model_dump())
    db.add(route)
    await db.commit()
    await db.refresh(route)
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    return route


@router.get("/{stream_id}", response_model=StreamRouteResponse)
async def get_stream(stream_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(StreamRoute, stream_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Stream route not found")
    return route


@router.put("/{stream_id}", response_model=StreamRouteResponse)
async def update_stream(stream_id: uuid.UUID, data: StreamRouteUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(StreamRoute, stream_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Stream route not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(route, key, value)
    await db.commit()
    await db.refresh(route)
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    return route


@router.delete("/{stream_id}", status_code=204)
async def delete_stream(stream_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    route = await db.get(StreamRoute, stream_id)
    if not route or not user_has_group(user, route.groups):
        raise HTTPException(status_code=404, detail="Stream route not found")
    await db.delete(route)
    await db.commit()
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
