"""add oauth fields to users

Revision ID: 8ab38bfb4aa5
Revises: 59b451ec4c6c
Create Date: 2026-10-07 19:13:28.262970

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8ab38bfb4aa5'
down_revision: str | None = '59b451ec4c6c'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("oauth_provider", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("oauth_subject", sa.String(length=255), nullable=True))
        batch_op.alter_column(
            "hashed_password", existing_type=sa.VARCHAR(length=255), nullable=True
        )
        batch_op.create_unique_constraint(
            "uq_users_oauth_identity", ["oauth_provider", "oauth_subject"]
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_oauth_identity", type_="unique")
        batch_op.alter_column(
            "hashed_password", existing_type=sa.VARCHAR(length=255), nullable=False
        )
        batch_op.drop_column("oauth_subject")
        batch_op.drop_column("oauth_provider")
