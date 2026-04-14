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


class StreamRouteUpdate(BaseModel):
    name: str | None = None
    destination: str | None = None
    port: int | None = None
    listen_port: int | None = None
    protocol: ProtocolType | None = None
    proxy_protocol: bool | None = None
    enabled: bool | None = None


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
    created_at: datetime
    updated_at: datetime


class VPNConfigCreate(BaseModel):
    name: str
    vpn_type: str = "pritunl"
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
    enabled: bool = True


class OIDCProviderUpdate(BaseModel):
    name: str | None = None
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str | None = None
    enabled: bool | None = None


class OIDCProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    issuer_url: str
    client_id: str
    scopes: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class UserInfo(BaseModel):
    sub: str
    email: str | None = None
    name: str | None = None


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


class NginxConfigResponse(BaseModel):
    http_config: str
    stream_config: str


class NginxStatusResponse(BaseModel):
    running: bool
    pid: int | None = None
