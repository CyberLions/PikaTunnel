import pytest
import uuid
from unittest.mock import MagicMock
from app.services.k8s_ingress import _sanitize_name, _build_ingress
from app.models import ProxyRoute, ClusterSettings


class TestSanitizeName:
    def test_simple_name(self):
        assert _sanitize_name("my-route") == "my-route"

    def test_dots_become_dashes(self):
        assert _sanitize_name("hash.psuccso.org") == "hash-psuccso-org"

    def test_spaces_and_special_chars(self):
        result = _sanitize_name("My Route (wss)")
        assert result == "my-route--wss" or result == "my-route-wss"

    def test_truncates_long_names(self):
        name = "a" * 100
        assert len(_sanitize_name(name)) == 63

    def test_strips_leading_trailing_dashes(self):
        assert _sanitize_name("--test--") == "test"

    def test_empty_fallback(self):
        assert _sanitize_name("!!!") == "pika-route"


class TestBuildIngress:
    def _make_route(self, **overrides):
        defaults = dict(
            id=uuid.uuid4(),
            name="test-route",
            host="test.example.com",
            path="/",
            destination="10.0.0.1",
            port=80,
            ssl_enabled=False,
            ssl_cert_path=None,
            ssl_key_path=None,
            enabled=True,
            groups="",
            k8s_ingress_enabled=True,
            k8s_cloudflare_proxied=None,
            k8s_cert_manager_enabled=False,
            k8s_cluster_issuer=None,
            k8s_authentik_enabled=False,
            k8s_proxy_body_size=None,
            k8s_proxy_read_timeout=None,
            k8s_proxy_send_timeout=None,
            k8s_proxy_connect_timeout=None,
            k8s_custom_annotations=None,
        )
        defaults.update(overrides)
        route = MagicMock(spec=ProxyRoute)
        for k, v in defaults.items():
            setattr(route, k, v)
        return route

    def _make_settings(self, **overrides):
        defaults = dict(
            k8s_namespace="pritunl",
            default_ingress_class="nginx",
            default_cluster_issuer="letsencrypt-cloudflare",
            default_cloudflare_proxied=False,
            backend_service_name="pikatunnel",
            backend_service_port=80,
            authentik_outpost_url="http://ak-outpost.svc:9000/outpost.goauthentik.io/auth/nginx",
            authentik_signin_url="https://{host}/outpost.goauthentik.io/start?rd=$scheme://$http_host$escaped_request_uri",
            authentik_response_headers="Set-Cookie,X-authentik-username",
            authentik_auth_snippet="proxy_set_header X-Forwarded-Host $http_host;",
        )
        defaults.update(overrides)
        settings = MagicMock(spec=ClusterSettings)
        for k, v in defaults.items():
            setattr(settings, k, v)
        return settings

    def test_basic_ingress(self):
        route = self._make_route()
        settings = self._make_settings()
        ingress = _build_ingress(route, settings)

        assert ingress.metadata.name == "test-route"
        assert ingress.metadata.namespace == "pritunl"
        assert ingress.metadata.labels["app.kubernetes.io/managed-by"] == "pikatunnel"
        assert ingress.spec.ingress_class_name == "nginx"
        assert len(ingress.spec.rules) == 1
        assert ingress.spec.rules[0].host == "test.example.com"
        assert ingress.spec.tls is None

    def test_cloudflare_proxied_default(self):
        route = self._make_route(k8s_cloudflare_proxied=None)
        settings = self._make_settings(default_cloudflare_proxied=True)
        ingress = _build_ingress(route, settings)
        assert ingress.metadata.annotations["external-dns.alpha.kubernetes.io/cloudflare-proxied"] == "true"

    def test_cloudflare_proxied_override(self):
        route = self._make_route(k8s_cloudflare_proxied=False)
        settings = self._make_settings(default_cloudflare_proxied=True)
        ingress = _build_ingress(route, settings)
        assert ingress.metadata.annotations["external-dns.alpha.kubernetes.io/cloudflare-proxied"] == "false"

    def test_cert_manager(self):
        route = self._make_route(k8s_cert_manager_enabled=True)
        settings = self._make_settings()
        ingress = _build_ingress(route, settings)
        assert ingress.metadata.annotations["cert-manager.io/cluster-issuer"] == "letsencrypt-cloudflare"
        assert ingress.spec.tls is not None
        assert ingress.spec.tls[0].hosts == ["test.example.com"]
        assert ingress.spec.tls[0].secret_name == "test-route-tls"

    def test_cert_manager_custom_issuer(self):
        route = self._make_route(k8s_cert_manager_enabled=True, k8s_cluster_issuer="my-issuer")
        settings = self._make_settings()
        ingress = _build_ingress(route, settings)
        assert ingress.metadata.annotations["cert-manager.io/cluster-issuer"] == "my-issuer"

    def test_authentik(self):
        route = self._make_route(k8s_authentik_enabled=True, host="hash.psuccso.org")
        settings = self._make_settings()
        ingress = _build_ingress(route, settings)
        annotations = ingress.metadata.annotations
        assert "nginx.ingress.kubernetes.io/auth-url" in annotations
        assert "nginx.ingress.kubernetes.io/auth-signin" in annotations
        assert "hash.psuccso.org" in annotations["nginx.ingress.kubernetes.io/auth-signin"]
        assert "nginx.ingress.kubernetes.io/auth-response-headers" in annotations
        assert "nginx.ingress.kubernetes.io/auth-snippet" in annotations

    def test_proxy_timeouts(self):
        route = self._make_route(
            k8s_proxy_body_size="0",
            k8s_proxy_read_timeout="600",
            k8s_proxy_send_timeout="600",
            k8s_proxy_connect_timeout="600",
        )
        settings = self._make_settings()
        ingress = _build_ingress(route, settings)
        annotations = ingress.metadata.annotations
        assert annotations["nginx.ingress.kubernetes.io/proxy-body-size"] == "0"
        assert annotations["nginx.ingress.kubernetes.io/proxy-read-timeout"] == "600"

    def test_custom_annotations(self):
        route = self._make_route(k8s_custom_annotations={"custom.io/key": "value"})
        settings = self._make_settings()
        ingress = _build_ingress(route, settings)
        assert ingress.metadata.annotations["custom.io/key"] == "value"

    def test_backend_service(self):
        route = self._make_route()
        settings = self._make_settings(backend_service_name="my-proxy", backend_service_port=8080)
        ingress = _build_ingress(route, settings)
        backend = ingress.spec.rules[0].http.paths[0].backend
        assert backend.service.name == "my-proxy"
        assert backend.service.port.number == 8080
