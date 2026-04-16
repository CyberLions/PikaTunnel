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


def _validate_pem(text: str, kind: str) -> None:
    marker = f"-----BEGIN {kind}"
    if marker not in text:
        raise HTTPException(status_code=400, detail=f"Input does not look like a PEM {kind.lower()} block")


@router.get("", response_model=list[TLSCertificateSummary])
async def list_certs(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(select(TLSCertificate).order_by(TLSCertificate.name))
    return result.scalars().all()


@router.post("", response_model=TLSCertificateResponse, status_code=201)
async def create_cert(data: TLSCertificateCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    _validate_pem(data.cert_pem, "CERTIFICATE")
    # key may be RSA/EC/PRIVATE — accept any "-----BEGIN ... PRIVATE KEY-----"
    if "-----BEGIN" not in data.key_pem or "PRIVATE KEY" not in data.key_pem:
        raise HTTPException(status_code=400, detail="Input does not look like a PEM private key block")

    existing = (await db.execute(
        select(TLSCertificate).where(TLSCertificate.name == data.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Certificate '{data.name}' already exists")

    cert = TLSCertificate(**data.model_dump())
    db.add(cert)
    await db.commit()
    await db.refresh(cert)

    # Re-render nginx so any routes that were already referencing this name start working.
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass

    return cert


@router.get("/{cert_id}", response_model=TLSCertificateResponse)
async def get_cert(cert_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    cert = await db.get(TLSCertificate, cert_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cert


@router.put("/{cert_id}", response_model=TLSCertificateResponse)
async def update_cert(cert_id: uuid.UUID, data: TLSCertificateUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    cert = await db.get(TLSCertificate, cert_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    fields = data.model_dump(exclude_unset=True)
    if "cert_pem" in fields:
        _validate_pem(fields["cert_pem"], "CERTIFICATE")
    if "key_pem" in fields and ("-----BEGIN" not in fields["key_pem"] or "PRIVATE KEY" not in fields["key_pem"]):
        raise HTTPException(status_code=400, detail="Input does not look like a PEM private key block")
    for k, v in fields.items():
        setattr(cert, k, v)
    await db.commit()
    await db.refresh(cert)
    try:
        await nginx_config.generate_and_reload(db)
    except Exception:
        pass
    return cert


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
