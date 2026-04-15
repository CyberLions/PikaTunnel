"""add cluster_settings table

Revision ID: 003
Revises: 002
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cluster_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("k8s_api_url", sa.String(1024), nullable=True),
        sa.Column("k8s_token", sa.Text(), nullable=True),
        sa.Column("k8s_ca_cert", sa.Text(), nullable=True),
        sa.Column("k8s_namespace", sa.String(255), server_default="default"),
        sa.Column("k8s_in_cluster", sa.Boolean(), server_default="false"),
        sa.Column("default_ingress_class", sa.String(255), server_default="nginx"),
        sa.Column("default_cluster_issuer", sa.String(255), server_default="letsencrypt-cloudflare"),
        sa.Column("default_cloudflare_proxied", sa.Boolean(), server_default="false"),
        sa.Column("backend_service_name", sa.String(255), server_default="pikatunnel"),
        sa.Column("backend_service_port", sa.Integer(), server_default="80"),
        sa.Column("authentik_outpost_url", sa.String(1024), nullable=True),
        sa.Column("authentik_signin_url", sa.String(1024), nullable=True),
        sa.Column("authentik_response_headers", sa.Text(), server_default="Set-Cookie,X-authentik-username,X-authentik-groups,X-authentik-email,X-authentik-name,X-authentik-uid"),
        sa.Column("authentik_auth_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("cluster_settings")
