import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models import ProtocolType


class ProxyRouteCreate(BaseModel):
    name: str
    host: str
    path: str = "/"
    destination: str
    port: int = 80
    ssl_enabled: bool = False
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    enabled: bool = True
    groups: str = ""
    k8s_ingress_enabled: bool = False
    k8s_cloudflare_proxied: bool | None = None
    k8s_cert_manager_enabled: bool = False
    k8s_cluster_issuer: str | None = None
    k8s_authentik_enabled: bool = False
    k8s_proxy_body_size: str | None = None
    k8s_proxy_read_timeout: str | None = None
    k8s_proxy_send_timeout: str | None = None
    k8s_proxy_connect_timeout: str | None = None
    k8s_custom_annotations: dict | None = None


class ProxyRouteUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    path: str | None = None
    destination: str | None = None
    port: int | None = None
    ssl_enabled: bool | None = None
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    enabled: bool | None = None
    groups: str | None = None
    k8s_ingress_enabled: bool | None = None
    k8s_cloudflare_proxied: bool | None = None
    k8s_cert_manager_enabled: bool | None = None
    k8s_cluster_issuer: str | None = None
    k8s_authentik_enabled: bool | None = None
    k8s_proxy_body_size: str | None = None
    k8s_proxy_read_timeout: str | None = None
    k8s_proxy_send_timeout: str | None = None
    k8s_proxy_connect_timeout: str | None = None
    k8s_custom_annotations: dict | None = None


class ProxyRouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    host: str
    path: str
    destination: str
    port: int
    ssl_enabled: bool
    ssl_cert_path: str | None
    ssl_key_path: str | None
    enabled: bool
    groups: str
    k8s_ingress_enabled: bool
    k8s_cloudflare_proxied: bool | None
    k8s_cert_manager_enabled: bool
    k8s_cluster_issuer: str | None
    k8s_authentik_enabled: bool
    k8s_proxy_body_size: str | None
    k8s_proxy_read_timeout: str | None
    k8s_proxy_send_timeout: str | None
    k8s_proxy_connect_timeout: str | None
    k8s_custom_annotations: dict | None
    created_at: datetime
    updated_at: datetime


class StreamRouteCreate(BaseModel):
    name: str
    destination: str
    port: int
    listen_port: int
    protocol: ProtocolType = ProtocolType.tcp
    proxy_protocol: bool = False
    enabled: bool = True
    groups: str = ""


class StreamRouteUpdate(BaseModel):
    name: str | None = None
    destination: str | None = None
    port: int | None = None
    listen_port: int | None = None
    protocol: ProtocolType | None = None
    proxy_protocol: bool | None = None
    enabled: bool | None = None
    groups: str | None = None


class StreamRouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    destination: str
    port: int
    listen_port: int
    protocol: ProtocolType
    proxy_protocol: bool
    enabled: bool
    groups: str
    created_at: datetime
    updated_at: datetime


class VPNConfigCreate(BaseModel):
    name: str
    vpn_type: str = "openvpn"
    enabled: bool = False
    config_data: dict = {}


class VPNConfigUpdate(BaseModel):
    name: str | None = None
    vpn_type: str | None = None
    enabled: bool | None = None
    config_data: dict | None = None


class VPNConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    vpn_type: str
    enabled: bool
    config_data: dict
    status: str
    created_at: datetime
    updated_at: datetime


class VPNStatusResponse(BaseModel):
    id: uuid.UUID
    name: str
    vpn_type: str
    status: str


class OIDCProviderCreate(BaseModel):
    name: str
    issuer_url: str
    client_id: str
    client_secret: str
    scopes: str = "openid profile email"
    groups_claim: str = "groups"
    enabled: bool = True


class OIDCProviderUpdate(BaseModel):
    name: str | None = None
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str | None = None
    groups_claim: str | None = None
    enabled: bool | None = None


class OIDCProviderResponse(BaseModel):
    id: str
    name: str
    issuer_url: str
    client_id: str
    scopes: str
    groups_claim: str
    admin_group: str
    enabled: bool
    source: str
    read_only: bool
    created_at: datetime
    updated_at: datetime


class UserInfo(BaseModel):
    sub: str
    email: str | None = None
    name: str | None = None
    groups: list[str] = []
    admin_group: str | None = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int


class NginxHealthInfo(BaseModel):
    running: bool
    config_valid: bool


class VPNHealthInfo(BaseModel):
    enabled: bool
    status: str


class HealthResponse(BaseModel):
    status: str
    database: bool
    nginx: NginxHealthInfo
    vpn: VPNHealthInfo


class ClusterSettingsUpdate(BaseModel):
    k8s_api_url: str | None = None
    k8s_token: str | None = None
    k8s_ca_cert: str | None = None
    k8s_namespace: str | None = None
    k8s_in_cluster: bool | None = None
    default_ingress_class: str | None = None
    default_cluster_issuer: str | None = None
    default_cloudflare_proxied: bool | None = None
    backend_service_name: str | None = None
    backend_service_port: int | None = None
    authentik_outpost_url: str | None = None
    authentik_signin_url: str | None = None
    authentik_response_headers: str | None = None
    authentik_auth_snippet: str | None = None


class ClusterSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    k8s_api_url: str | None
    k8s_namespace: str
    k8s_in_cluster: bool
    default_ingress_class: str
    default_cluster_issuer: str
    default_cloudflare_proxied: bool
    backend_service_name: str
    backend_service_port: int
    authentik_outpost_url: str | None
    authentik_signin_url: str | None
    authentik_response_headers: str
    authentik_auth_snippet: str | None
    has_token: bool = False
    has_ca_cert: bool = False


class NginxConfigResponse(BaseModel):
    http_config: str
    stream_config: str


class NginxStatusResponse(BaseModel):
    running: bool
    pid: int | None = None
