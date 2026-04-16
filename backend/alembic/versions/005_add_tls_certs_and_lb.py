"""add tls_certificates table, proxy_routes.ssl_cert_name, and cluster_settings.k8s_loadbalancer_service_name

Revision ID: 005
Revises: 004
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tls_certificates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cert_pem", sa.Text(), nullable=False),
        sa.Column("key_pem", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("proxy_routes", sa.Column("ssl_cert_name", sa.String(255), nullable=True))
    op.add_column(
        "cluster_settings",
        sa.Column("k8s_loadbalancer_service_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cluster_settings", "k8s_loadbalancer_service_name")
    op.drop_column("proxy_routes", "ssl_cert_name")
    op.drop_table("tls_certificates")
