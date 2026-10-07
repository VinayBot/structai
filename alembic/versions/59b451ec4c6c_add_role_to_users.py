"""add role to users

Revision ID: 59b451ec4c6c
Revises: 29ea509843ad
Create Date: 2026-10-07 16:29:55.100882

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '59b451ec4c6c'
down_revision: str | None = '29ea509843ad'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=16), server_default="user", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("role")
