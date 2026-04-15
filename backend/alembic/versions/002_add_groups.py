"""add groups to routes and groups_claim to oidc_providers

Revision ID: 002
Revises: 001
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proxy_routes", sa.Column("groups", sa.Text(), server_default="", nullable=False))
    op.add_column("stream_routes", sa.Column("groups", sa.Text(), server_default="", nullable=False))
    op.add_column("oidc_providers", sa.Column("groups_claim", sa.String(255), server_default="groups", nullable=False))


def downgrade() -> None:
    op.drop_column("oidc_providers", "groups_claim")
    op.drop_column("stream_routes", "groups")
    op.drop_column("proxy_routes", "groups")
