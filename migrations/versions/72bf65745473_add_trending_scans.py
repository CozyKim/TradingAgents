"""add trending_scans

Revision ID: 72bf65745473
Revises: 866f0acf360c
Create Date: 2026-05-30 03:05:36.038909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '72bf65745473'
down_revision: Union[str, None] = '866f0acf360c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trending_scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sectors", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_trending_scans_created_at", "trending_scans", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_trending_scans_created_at", table_name="trending_scans")
    op.drop_table("trending_scans")
