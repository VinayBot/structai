"""drop device_hash from users

Revision ID: 8635c7e3b687
Revises: f9d6896bc34e
Create Date: 2026-10-03 05:15:42.459914

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8635c7e3b687'
down_revision: str | None = 'f9d6896bc34e'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_device_hash"))
        batch_op.drop_column("device_hash")


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("device_hash", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_device_hash"), ["device_hash"], unique=False)
