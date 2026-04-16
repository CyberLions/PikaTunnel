import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import StreamRoute, ProxyRoute, ClusterSettings, TLSCertificate
from app.services.k8s_ingress import _get_k8s_clients, _get_settings

logger = logging.getLogger(__name__)


async def _desired_ports(db: AsyncSession) -> list[dict]:
    """Compute the k8s Service port list from current routes.

    Always includes 80 (HTTP). Adds 443 if any enabled ProxyRoute can do TLS
    (has ssl_enabled plus either a named cert or a cert path). Adds one port
    per enabled StreamRoute.listen_port.
    """
    ports: list[dict] = [
        {"name": "http", "port": 80, "target_port": 80, "protocol": "TCP"},
    ]

    proxy_rows = (await db.execute(
        select(ProxyRoute).where(ProxyRoute.enabled == True)
    )).scalars().all()
    needs_https = False
    cert_names = {
        c.name for c in (await db.execute(select(TLSCertificate))).scalars().all()
    }
    for r in proxy_rows:
        if not r.ssl_enabled:
            continue
        if (r.ssl_cert_name and r.ssl_cert_name in cert_names) or (r.ssl_cert_path and r.ssl_key_path):
            needs_https = True
            break
    if needs_https:
        ports.append({"name": "https", "port": 443, "target_port": 443, "protocol": "TCP"})

    stream_rows = (await db.execute(
        select(StreamRoute).where(StreamRoute.enabled == True)
    )).scalars().all()
    seen: set[tuple[int, str]] = set()
    for s in stream_rows:
        proto = (s.protocol.value if hasattr(s.protocol, "value") else str(s.protocol)).upper()
        key = (s.listen_port, proto)
        if key in seen:
            continue
        seen.add(key)
        # Port names must be DNS-1123 and <=15 chars
        name = f"{proto.lower()}-{s.listen_port}"[:15]
        ports.append({
            "name": name,
            "port": s.listen_port,
            "target_port": s.listen_port,
            "protocol": proto,
        })
    return ports


async def sync_service_ports(db: AsyncSession) -> dict:
    settings = await _get_settings(db)
    if not settings or (not settings.k8s_api_url and not settings.k8s_in_cluster):
        return {"synced": False, "error": "Kubernetes cluster is not configured"}
    service_name = settings.k8s_loadbalancer_service_name
    if not service_name:
        return {"synced": False, "error": "k8s_loadbalancer_service_name is not set in cluster settings"}

    desired = await _desired_ports(db)

    def _patch() -> dict:
        from kubernetes.client import V1ServicePort
        from kubernetes.client.exceptions import ApiException

        _, core_api = _get_k8s_clients(settings)
        try:
            svc = core_api.read_namespaced_service(service_name, settings.k8s_namespace)
        except ApiException as e:
            return {"synced": False, "error": f"read service failed: {e.status} {e.reason}"}

        svc.spec.ports = [
            V1ServicePort(
                name=p["name"],
                port=p["port"],
                target_port=p["target_port"],
                protocol=p["protocol"],
            )
            for p in desired
        ]

        try:
            core_api.replace_namespaced_service(service_name, settings.k8s_namespace, svc)
        except ApiException as e:
            return {"synced": False, "error": f"replace service failed: {e.status} {e.reason}"}

        return {"synced": True, "ports": desired}

    try:
        return await asyncio.to_thread(_patch)
    except Exception as e:
        return {"synced": False, "error": str(e)}
