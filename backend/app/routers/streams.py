import csv
import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import StreamRoute, ProtocolType
from app.schemas import StreamRouteCreate, StreamRouteUpdate, StreamRouteResponse
from app.services import nginx_config
from app.services.k8s_service import sync_service_ports
from app.services.oidc import get_current_user, user_has_group

router = APIRouter(prefix="/api/v1/streams", tags=["streams"])


CSV_FIELDS = [
    "name", "destination", "port", "listen_port",
    "protocol", "proxy_protocol", "enabled", "groups",
]


def _bool_to_cell(v: bool) -> str:
    return "true" if v else "false"


def _cell_to_bool(s: str | None, default: bool = False) -> bool:
    if s is None or s.strip() == "":
        return default
    return s.strip().lower() in ("1", "true", "yes", "y", "t")


def _stream_to_row(s: StreamRoute) -> dict:
    return {
        "name": s.name,
        "destination": s.destination,
        "port": s.port,
        "listen_port": s.listen_port,
        "protocol": s.protocol.value if hasattr(s.protocol, "value") else str(s.protocol),
        "proxy_protocol": _bool_to_cell(s.proxy_protocol),
        "enabled": _bool_to_cell(s.enabled),
        "groups": s.groups or "",
    }


def _row_to_stream_fields(row: dict) -> dict:
    def s(key: str) -> str:
        return (row.get(key) or "").strip()

    name = s("name")
    destination = s("destination")
    port_raw = s("port")
    listen_raw = s("listen_port")
    if not name or not destination or not port_raw or not listen_raw:
        raise ValueError("name, destination, port, and listen_port are required")

    proto_raw = s("protocol").lower() or "tcp"
    if proto_raw not in ("tcp", "udp"):
        raise ValueError(f"protocol must be tcp or udp, got {proto_raw!r}")

    return {
        "name": name,
        "destination": destination,
        "port": int(port_raw),
        "listen_port": int(listen_raw),
        "protocol": ProtocolType(proto_raw),
        "proxy_protocol": _cell_to_bool(row.get("proxy_protocol")),
        "enabled": _cell_to_bool(row.get("enabled"), default=True),
        "groups": s("groups"),
    }


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
    try:
        await sync_service_ports(db)
    except Exception:
        pass
    return route


@router.get("/export.csv")
async def export_streams_csv(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(select(StreamRoute))
    all_streams = result.scalars().all()
    visible = [s for s in all_streams if user_has_group(user, s.groups)]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for s in visible:
        writer.writerow(_stream_to_row(s))

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="streams.csv"'},
    )


@router.post("/import")
async def import_streams_csv(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    raw = await request.body()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is missing required 'name' header")

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        try:
            fields = _row_to_stream_fields(row)
        except Exception as e:
            skipped += 1
            errors.append(f"row {i}: {e}")
            continue

        existing = (await db.execute(
            select(StreamRoute).where(StreamRoute.name == fields["name"])
        )).scalar_one_or_none()

        if existing:
            if not user_has_group(user, existing.groups):
                skipped += 1
                errors.append(f"row {i}: not authorized for existing stream '{fields['name']}'")
                continue
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(StreamRoute(**fields))
            created += 1

    await db.commit()

    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    try:
        await sync_service_ports(db)
    except Exception:
        pass

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}


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
    try:
        await sync_service_ports(db)
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
    try:
        await sync_service_ports(db)
    except Exception:
        pass
