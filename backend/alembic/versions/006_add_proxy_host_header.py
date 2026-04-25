"""add proxy_host_header to proxy_routes

Revision ID: 006
Revises: 005
Create Date: 2026-04-25 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proxy_routes", sa.Column("proxy_host_header", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("proxy_routes", "proxy_host_header")
