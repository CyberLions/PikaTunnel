"""add k8s ingress fields to proxy_routes

Revision ID: 004
Revises: 003
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proxy_routes", sa.Column("k8s_ingress_enabled", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("proxy_routes", sa.Column("k8s_cloudflare_proxied", sa.Boolean(), nullable=True))
    op.add_column("proxy_routes", sa.Column("k8s_cert_manager_enabled", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("proxy_routes", sa.Column("k8s_cluster_issuer", sa.String(255), nullable=True))
    op.add_column("proxy_routes", sa.Column("k8s_authentik_enabled", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("proxy_routes", sa.Column("k8s_proxy_body_size", sa.String(50), nullable=True))
    op.add_column("proxy_routes", sa.Column("k8s_proxy_read_timeout", sa.String(50), nullable=True))
    op.add_column("proxy_routes", sa.Column("k8s_proxy_send_timeout", sa.String(50), nullable=True))
    op.add_column("proxy_routes", sa.Column("k8s_proxy_connect_timeout", sa.String(50), nullable=True))
    op.add_column("proxy_routes", sa.Column("k8s_custom_annotations", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("proxy_routes", "k8s_custom_annotations")
    op.drop_column("proxy_routes", "k8s_proxy_connect_timeout")
    op.drop_column("proxy_routes", "k8s_proxy_send_timeout")
    op.drop_column("proxy_routes", "k8s_proxy_read_timeout")
    op.drop_column("proxy_routes", "k8s_proxy_body_size")
    op.drop_column("proxy_routes", "k8s_authentik_enabled")
    op.drop_column("proxy_routes", "k8s_cluster_issuer")
    op.drop_column("proxy_routes", "k8s_cert_manager_enabled")
    op.drop_column("proxy_routes", "k8s_cloudflare_proxied")
    op.drop_column("proxy_routes", "k8s_ingress_enabled")
