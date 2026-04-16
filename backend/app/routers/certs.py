import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import TLSCertificate, ProxyRoute
from app.schemas import (
    TLSCertificateCreate, TLSCertificateUpdate,
    TLSCertificateResponse, TLSCertificateSummary,
)
from app.services import nginx_config
from app.services.oidc import require_admin

router = APIRouter(prefix="/api/v1/certs", tags=["certs"])


def _validate_pem_cert(text: str) -> None:
    if "-----BEGIN CERTIFICATE" not in text:
        raise HTTPException(status_code=400, detail="Input does not look like a PEM certificate")


def _validate_pem_key(text: str) -> None:
    if "-----BEGIN" not in text or "PRIVATE KEY" not in text:
        raise HTTPException(status_code=400, detail="Input does not look like a PEM private key")


def _source_of(cert: TLSCertificate) -> str:
    return "path" if cert.cert_path else "inline"


def _to_response(cert: TLSCertificate) -> TLSCertificateResponse:
    return TLSCertificateResponse(
        id=cert.id,
        name=cert.name,
        description=cert.description,
        source=_source_of(cert),
        cert_pem=cert.cert_pem,
        cert_path=cert.cert_path,
        key_path=cert.key_path,
        has_key=bool(cert.key_pem or cert.key_path),
        created_at=cert.created_at,
        updated_at=cert.updated_at,
    )


def _to_summary(cert: TLSCertificate) -> TLSCertificateSummary:
    return TLSCertificateSummary(
        id=cert.id,
        name=cert.name,
        description=cert.description,
        source=_source_of(cert),
        cert_path=cert.cert_path,
        created_at=cert.created_at,
        updated_at=cert.updated_at,
    )


def _apply_source(cert: TLSCertificate, data: dict) -> None:
    """Populate exactly one of the two backing sources on `cert` from `data`.

    Raises HTTPException(400) if neither or both are provided.
    """
    cert_pem = data.get("cert_pem") or None
    key_pem = data.get("key_pem") or None
    cert_path = (data.get("cert_path") or "").strip() or None
    key_path = (data.get("key_path") or "").strip() or None

    has_inline = bool(cert_pem or key_pem)
    has_path = bool(cert_path or key_path)
    if has_inline and has_path:
        raise HTTPException(status_code=400, detail="Provide either PEM bodies or file paths, not both")
    if not has_inline and not has_path:
        raise HTTPException(status_code=400, detail="Provide either (cert_pem + key_pem) or (cert_path + key_path)")

    if has_inline:
        if not cert_pem or not key_pem:
            raise HTTPException(status_code=400, detail="Both cert_pem and key_pem are required for an inline cert")
        _validate_pem_cert(cert_pem)
        _validate_pem_key(key_pem)
        cert.cert_pem, cert.key_pem = cert_pem, key_pem
        cert.cert_path, cert.key_path = None, None
    else:
        if not cert_path or not key_path:
            raise HTTPException(status_code=400, detail="Both cert_path and key_path are required for a mounted cert")
        cert.cert_path, cert.key_path = cert_path, key_path
        cert.cert_pem, cert.key_pem = None, None


@router.get("", response_model=list[TLSCertificateSummary])
async def list_certs(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(select(TLSCertificate).order_by(TLSCertificate.name))
    return [_to_summary(c) for c in result.scalars().all()]


@router.post("", response_model=TLSCertificateResponse, status_code=201)
async def create_cert(data: TLSCertificateCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    existing = (await db.execute(
        select(TLSCertificate).where(TLSCertificate.name == data.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Certificate '{data.name}' already exists")

    cert = TLSCertificate(name=data.name, description=data.description)
    _apply_source(cert, data.model_dump())
    db.add(cert)
    await db.commit()
    await db.refresh(cert)

    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass

    return _to_response(cert)


@router.get("/{cert_id}", response_model=TLSCertificateResponse)
async def get_cert(cert_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    cert = await db.get(TLSCertificate, cert_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return _to_response(cert)


@router.put("/{cert_id}", response_model=TLSCertificateResponse)
async def update_cert(cert_id: uuid.UUID, data: TLSCertificateUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    cert = await db.get(TLSCertificate, cert_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    fields = data.model_dump(exclude_unset=True)
    if "description" in fields:
        cert.description = fields["description"] or ""

    if any(k in fields for k in ("cert_pem", "key_pem", "cert_path", "key_path")):
        # Merge existing + updates so caller can change just one half.
        merged = {
            "cert_pem": fields.get("cert_pem", cert.cert_pem),
            "key_pem": fields.get("key_pem", cert.key_pem),
            "cert_path": fields.get("cert_path", cert.cert_path),
            "key_path": fields.get("key_path", cert.key_path),
        }
        # If the update explicitly switches source type, discard the old source.
        if ("cert_path" in fields or "key_path" in fields) and not fields.get("cert_pem") and not fields.get("key_pem"):
            merged["cert_pem"] = None
            merged["key_pem"] = None
        elif ("cert_pem" in fields or "key_pem" in fields) and not fields.get("cert_path") and not fields.get("key_path"):
            merged["cert_path"] = None
            merged["key_path"] = None
        _apply_source(cert, merged)

    await db.commit()
    await db.refresh(cert)
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    return _to_response(cert)


@router.delete("/{cert_id}", status_code=204)
async def delete_cert(cert_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    cert = await db.get(TLSCertificate, cert_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    in_use = (await db.execute(
        select(ProxyRoute.name).where(ProxyRoute.ssl_cert_name == cert.name)
    )).scalars().all()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Certificate '{cert.name}' is still referenced by routes: {', '.join(in_use)}",
        )

    await db.delete(cert)
    await db.commit()
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
