import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Enum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProtocolType(str, enum.Enum):
    tcp = "tcp"
    udp = "udp"


class ProxyRoute(Base):
    __tablename__ = "proxy_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), default="/")
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=80)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ssl_cert_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ssl_key_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    groups: Mapped[str] = mapped_column(Text, default="", server_default="")
    k8s_ingress_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    k8s_cloudflare_proxied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    k8s_cert_manager_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    k8s_cluster_issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    k8s_authentik_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    k8s_proxy_body_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    k8s_proxy_read_timeout: Mapped[str | None] = mapped_column(String(50), nullable=True)
    k8s_proxy_send_timeout: Mapped[str | None] = mapped_column(String(50), nullable=True)
    k8s_proxy_connect_timeout: Mapped[str | None] = mapped_column(String(50), nullable=True)
    k8s_custom_annotations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StreamRoute(Base):
    __tablename__ = "stream_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    listen_port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[ProtocolType] = mapped_column(Enum(ProtocolType), default=ProtocolType.tcp)
    proxy_protocol: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    groups: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VPNConfig(Base):
    __tablename__ = "vpn_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    vpn_type: Mapped[str] = mapped_column(String(50), default="openvpn")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config_data: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="disconnected")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ClusterSettings(Base):
    __tablename__ = "cluster_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    k8s_api_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    k8s_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    k8s_ca_cert: Mapped[str | None] = mapped_column(Text, nullable=True)
    k8s_namespace: Mapped[str] = mapped_column(String(255), default="default")
    k8s_in_cluster: Mapped[bool] = mapped_column(Boolean, default=False)
    default_ingress_class: Mapped[str] = mapped_column(String(255), default="nginx")
    default_cluster_issuer: Mapped[str] = mapped_column(String(255), default="letsencrypt-cloudflare")
    default_cloudflare_proxied: Mapped[bool] = mapped_column(Boolean, default=False)
    backend_service_name: Mapped[str] = mapped_column(String(255), default="pikatunnel")
    backend_service_port: Mapped[int] = mapped_column(Integer, default=80)
    authentik_outpost_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    authentik_signin_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    authentik_response_headers: Mapped[str] = mapped_column(Text, default="Set-Cookie,X-authentik-username,X-authentik-groups,X-authentik-email,X-authentik-name,X-authentik-uid")
    authentik_auth_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class OIDCProvider(Base):
    __tablename__ = "oidc_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    issuer_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(String(1024), default="openid profile email")
    groups_claim: Mapped[str] = mapped_column(String(255), default="groups")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
