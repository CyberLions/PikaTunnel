import csv
import io
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ProxyRoute
from app.schemas import ProxyRouteCreate, ProxyRouteUpdate, ProxyRouteResponse
from app.services import nginx_config
from app.services import k8s_ingress
from app.services.oidc import get_current_user, user_has_group

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


CSV_FIELDS = [
    "name", "host", "path", "destination", "port",
    "ssl_enabled", "ssl_cert_name", "ssl_cert_path", "ssl_key_path",
    "enabled", "groups",
    "k8s_ingress_enabled", "k8s_cloudflare_proxied",
    "k8s_cert_manager_enabled", "k8s_cluster_issuer",
    "k8s_authentik_enabled",
    "k8s_proxy_body_size", "k8s_proxy_read_timeout",
    "k8s_proxy_send_timeout", "k8s_proxy_connect_timeout",
    "k8s_custom_annotations",
]


def _bool_to_cell(v: bool | None) -> str:
    if v is None:
        return ""
    return "true" if v else "false"


def _cell_to_bool(s: str | None, default: bool = False) -> bool:
    if s is None or s.strip() == "":
        return default
    return s.strip().lower() in ("1", "true", "yes", "y", "t")


def _cell_to_optional_bool(s: str | None) -> bool | None:
    if s is None or s.strip() == "":
        return None
    return s.strip().lower() in ("1", "true", "yes", "y", "t")


def _route_to_row(r: ProxyRoute) -> dict:
    return {
        "name": r.name,
        "host": r.host,
        "path": r.path,
        "destination": r.destination,
        "port": r.port,
        "ssl_enabled": _bool_to_cell(r.ssl_enabled),
        "ssl_cert_name": r.ssl_cert_name or "",
        "ssl_cert_path": r.ssl_cert_path or "",
        "ssl_key_path": r.ssl_key_path or "",
        "enabled": _bool_to_cell(r.enabled),
        "groups": r.groups or "",
        "k8s_ingress_enabled": _bool_to_cell(r.k8s_ingress_enabled),
        "k8s_cloudflare_proxied": _bool_to_cell(r.k8s_cloudflare_proxied),
        "k8s_cert_manager_enabled": _bool_to_cell(r.k8s_cert_manager_enabled),
        "k8s_cluster_issuer": r.k8s_cluster_issuer or "",
        "k8s_authentik_enabled": _bool_to_cell(r.k8s_authentik_enabled),
        "k8s_proxy_body_size": r.k8s_proxy_body_size or "",
        "k8s_proxy_read_timeout": r.k8s_proxy_read_timeout or "",
        "k8s_proxy_send_timeout": r.k8s_proxy_send_timeout or "",
        "k8s_proxy_connect_timeout": r.k8s_proxy_connect_timeout or "",
        "k8s_custom_annotations": json.dumps(r.k8s_custom_annotations) if r.k8s_custom_annotations else "",
    }


def _row_to_route_fields(row: dict) -> dict:
    def s(key: str) -> str:
        return (row.get(key) or "").strip()

    name = s("name")
    host = s("host")
    destination = s("destination")
    if not name or not host or not destination:
        raise ValueError("name, host, and destination are required")

    port_raw = s("port")
    port = int(port_raw) if port_raw else 80

    annotations_raw = s("k8s_custom_annotations")
    annotations = json.loads(annotations_raw) if annotations_raw else None

    cert_name = s("ssl_cert_name") or None
    # If a named cert is referenced, enable SSL automatically unless explicitly set.
    ssl_cell = row.get("ssl_enabled")
    ssl_enabled = _cell_to_bool(ssl_cell, default=bool(cert_name)) if ssl_cell not in (None, "") else bool(cert_name)

    return {
        "name": name,
        "host": host,
        "path": s("path") or "/",
        "destination": destination,
        "port": port,
        "ssl_enabled": ssl_enabled,
        "ssl_cert_name": cert_name,
        "ssl_cert_path": s("ssl_cert_path") or None,
        "ssl_key_path": s("ssl_key_path") or None,
        "enabled": _cell_to_bool(row.get("enabled"), default=True),
        "groups": s("groups"),
        "k8s_ingress_enabled": _cell_to_bool(row.get("k8s_ingress_enabled")),
        "k8s_cloudflare_proxied": _cell_to_optional_bool(row.get("k8s_cloudflare_proxied")),
        "k8s_cert_manager_enabled": _cell_to_bool(row.get("k8s_cert_manager_enabled")),
        "k8s_cluster_issuer": s("k8s_cluster_issuer") or None,
        "k8s_authentik_enabled": _cell_to_bool(row.get("k8s_authentik_enabled")),
        "k8s_proxy_body_size": s("k8s_proxy_body_size") or None,
        "k8s_proxy_read_timeout": s("k8s_proxy_read_timeout") or None,
        "k8s_proxy_send_timeout": s("k8s_proxy_send_timeout") or None,
        "k8s_proxy_connect_timeout": s("k8s_proxy_connect_timeout") or None,
        "k8s_custom_annotations": annotations,
    }


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


@router.get("/export.csv")
async def export_routes_csv(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(select(ProxyRoute))
    all_routes = result.scalars().all()
    visible = [r for r in all_routes if user_has_group(user, r.groups)]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for r in visible:
        writer.writerow(_route_to_row(r))

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="routes.csv"'},
    )


@router.post("/import")
async def import_routes_csv(
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
    touched_routes: list[ProxyRoute] = []

    for i, row in enumerate(reader, start=2):  # start=2 to account for header row
        try:
            fields = _row_to_route_fields(row)
        except Exception as e:
            skipped += 1
            errors.append(f"row {i}: {e}")
            continue

        existing = (await db.execute(
            select(ProxyRoute).where(ProxyRoute.name == fields["name"])
        )).scalar_one_or_none()

        if existing:
            if not user_has_group(user, existing.groups):
                skipped += 1
                errors.append(f"row {i}: not authorized for existing route '{fields['name']}'")
                continue
            for k, v in fields.items():
                setattr(existing, k, v)
            touched_routes.append(existing)
            updated += 1
        else:
            route = ProxyRoute(**fields)
            db.add(route)
            touched_routes.append(route)
            created += 1

    await db.commit()

    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass

    for route in touched_routes:
        if route.k8s_ingress_enabled:
            try:
                await k8s_ingress.sync_ingress(route, db)
            except Exception:
                pass

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
