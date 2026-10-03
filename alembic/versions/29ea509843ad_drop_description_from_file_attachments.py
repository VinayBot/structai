"""drop description from file_attachments

Revision ID: 29ea509843ad
Revises: 8635c7e3b687
Create Date: 2026-10-03 10:28:56.950065

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '29ea509843ad'
down_revision: str | None = '8635c7e3b687'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("file_attachments", schema=None) as batch_op:
        batch_op.drop_column("description")


def downgrade() -> None:
    with op.batch_alter_table("file_attachments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.String(), nullable=True))
