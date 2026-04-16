import asyncio
import logging
import re
import tempfile
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ProxyRoute, ClusterSettings

logger = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    """Convert route name to a valid K8s resource name."""
    s = re.sub(r"[^a-z0-9-]", "-", name.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:63] or "pika-route"


def _get_k8s_clients(settings: ClusterSettings):
    """Build K8s API client from cluster settings. Returns (NetworkingV1Api, CoreV1Api)."""
    from kubernetes import client, config as k8s_config

    if settings.k8s_in_cluster:
        k8s_config.load_incluster_config()
        return client.NetworkingV1Api(), client.CoreV1Api()

    configuration = client.Configuration()
    configuration.host = settings.k8s_api_url
    configuration.api_key = {"authorization": f"Bearer {settings.k8s_token}"}

    if settings.k8s_ca_cert:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
        tmp.write(settings.k8s_ca_cert.encode())
        tmp.close()
        configuration.ssl_ca_cert = tmp.name
    else:
        configuration.verify_ssl = False

    api_client = client.ApiClient(configuration)
    return client.NetworkingV1Api(api_client), client.CoreV1Api(api_client)


def _build_ingress(route: ProxyRoute, settings: ClusterSettings):
    from kubernetes.client import (
        V1Ingress, V1IngressSpec, V1IngressRule, V1HTTPIngressRuleValue,
        V1HTTPIngressPath, V1IngressBackend, V1IngressServiceBackend,
        V1ServiceBackendPort, V1IngressTLS, V1ObjectMeta,
    )

    name = _sanitize_name(route.name)
    annotations = {"pikatunnel.dev/managed": "true"}

    # External DNS / Cloudflare
    proxied = route.k8s_cloudflare_proxied if route.k8s_cloudflare_proxied is not None else settings.default_cloudflare_proxied
    annotations["external-dns.alpha.kubernetes.io/cloudflare-proxied"] = str(proxied).lower()

    # Cert-Manager
    if route.k8s_cert_manager_enabled:
        issuer = route.k8s_cluster_issuer or settings.default_cluster_issuer
        annotations["cert-manager.io/cluster-issuer"] = issuer

    # Authentik
    if route.k8s_authentik_enabled and settings.authentik_outpost_url:
        annotations["nginx.ingress.kubernetes.io/auth-url"] = settings.authentik_outpost_url
        if settings.authentik_signin_url:
            signin = settings.authentik_signin_url.replace("{host}", route.host)
            annotations["nginx.ingress.kubernetes.io/auth-signin"] = signin
        if settings.authentik_response_headers:
            annotations["nginx.ingress.kubernetes.io/auth-response-headers"] = settings.authentik_response_headers
        if settings.authentik_auth_snippet:
            annotations["nginx.ingress.kubernetes.io/auth-snippet"] = settings.authentik_auth_snippet

    # Proxy settings
    if route.k8s_proxy_body_size:
        annotations["nginx.ingress.kubernetes.io/proxy-body-size"] = route.k8s_proxy_body_size
    if route.k8s_proxy_read_timeout:
        annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] = route.k8s_proxy_read_timeout
    if route.k8s_proxy_send_timeout:
        annotations["nginx.ingress.kubernetes.io/proxy-send-timeout"] = route.k8s_proxy_send_timeout
    if route.k8s_proxy_connect_timeout:
        annotations["nginx.ingress.kubernetes.io/proxy-connect-timeout"] = route.k8s_proxy_connect_timeout

    # Custom annotations
    if route.k8s_custom_annotations:
        annotations.update(route.k8s_custom_annotations)

    tls = None
    if route.k8s_cert_manager_enabled:
        tls = [V1IngressTLS(hosts=[route.host], secret_name=f"{name}-tls")]

    return V1Ingress(
        metadata=V1ObjectMeta(
            name=name,
            namespace=settings.k8s_namespace,
            labels={
                "app.kubernetes.io/managed-by": "pikatunnel",
                "pikatunnel.dev/route-id": str(route.id),
            },
            annotations=annotations,
        ),
        spec=V1IngressSpec(
            ingress_class_name=settings.default_ingress_class,
            rules=[
                V1IngressRule(
                    host=route.host,
                    http=V1HTTPIngressRuleValue(
                        paths=[
                            V1HTTPIngressPath(
                                path=route.path,
                                path_type="Prefix",
                                backend=V1IngressBackend(
                                    service=V1IngressServiceBackend(
                                        name=settings.backend_service_name,
                                        port=V1ServiceBackendPort(number=settings.backend_service_port),
                                    )
                                ),
                            )
                        ]
                    ),
                )
            ],
            tls=tls,
        ),
    )


async def _get_settings(db: AsyncSession) -> ClusterSettings | None:
    result = await db.execute(select(ClusterSettings).limit(1))
    return result.scalar_one_or_none()


async def sync_ingress(route: ProxyRoute, db: AsyncSession) -> None:
    settings = await _get_settings(db)
    if not settings or (not settings.k8s_api_url and not settings.k8s_in_cluster):
        return

    if not route.k8s_ingress_enabled or not route.enabled:
        await delete_ingress(route, db)
        return

    name = _sanitize_name(route.name)
    ingress = _build_ingress(route, settings)

    def _sync():
        net_api, _ = _get_k8s_clients(settings)
        try:
            net_api.read_namespaced_ingress(name, settings.k8s_namespace)
            net_api.replace_namespaced_ingress(name, settings.k8s_namespace, ingress)
            logger.info("Updated ingress %s", name)
        except Exception:
            try:
                net_api.create_namespaced_ingress(settings.k8s_namespace, ingress)
                logger.info("Created ingress %s", name)
            except Exception as e:
                logger.error("Failed to create ingress %s: %s", name, e)

    await asyncio.to_thread(_sync)


async def delete_ingress(route: ProxyRoute, db: AsyncSession) -> None:
    settings = await _get_settings(db)
    if not settings or (not settings.k8s_api_url and not settings.k8s_in_cluster):
        return

    name = _sanitize_name(route.name)

    def _delete():
        net_api, _ = _get_k8s_clients(settings)
        try:
            net_api.delete_namespaced_ingress(name, settings.k8s_namespace)
            logger.info("Deleted ingress %s", name)
        except Exception:
            pass

    await asyncio.to_thread(_delete)


async def test_connection(db: AsyncSession) -> dict:
    settings = await _get_settings(db)
    if not settings:
        return {"connected": False, "error": "No cluster settings found"}

    def _test():
        from kubernetes import client
        net_api, _ = _get_k8s_clients(settings)
        version = client.VersionApi(net_api.api_client).get_code()
        return {"connected": True, "version": version.git_version}

    try:
        return await asyncio.to_thread(_test)
    except Exception as e:
        return {"connected": False, "error": str(e)}
