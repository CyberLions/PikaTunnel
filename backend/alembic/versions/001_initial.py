"""initial

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proxy_routes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("path", sa.String(1024), server_default="/"),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), server_default="80"),
        sa.Column("ssl_enabled", sa.Boolean(), server_default="false"),
        sa.Column("ssl_cert_path", sa.String(1024), nullable=True),
        sa.Column("ssl_key_path", sa.String(1024), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "stream_routes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("listen_port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.Enum("tcp", "udp", name="protocoltype"), server_default="tcp"),
        sa.Column("proxy_protocol", sa.Boolean(), server_default="false"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "vpn_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vpn_type", sa.String(50), server_default="pritunl"),
        sa.Column("enabled", sa.Boolean(), server_default="false"),
        sa.Column("config_data", sa.JSON(), server_default="{}"),
        sa.Column("status", sa.String(50), server_default="disconnected"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "oidc_providers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("issuer_url", sa.String(1024), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("client_secret", sa.Text(), nullable=False),
        sa.Column("scopes", sa.String(1024), server_default="openid profile email"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("oidc_providers")
    op.drop_table("vpn_configs")
    op.drop_table("stream_routes")
    op.drop_table("proxy_routes")
    op.execute("DROP TYPE IF EXISTS protocoltype")
