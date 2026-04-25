"""analyses table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25 00:00:01.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("llm_provider", sa.String(length=32), nullable=False),
        sa.Column("llm_deep_model", sa.String(length=64), nullable=False),
        sa.Column("llm_quick_model", sa.String(length=64), nullable=False),
        sa.Column("debate_rounds", sa.Integer(), nullable=False),
        sa.Column("analysts", sa.JSON(), nullable=False),
        sa.Column("final_state", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=2048), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", name="uq_analyses_run_id"),
    )
    op.create_index("ix_analyses_ticker", "analyses", ["ticker"])
    op.create_index("ix_analyses_ticker_created", "analyses", ["ticker", "created_at"])
    op.create_index("ix_analyses_status", "analyses", ["status"])


def downgrade() -> None:
    op.drop_index("ix_analyses_status", table_name="analyses")
    op.drop_index("ix_analyses_ticker_created", table_name="analyses")
    op.drop_index("ix_analyses_ticker", table_name="analyses")
    op.drop_table("analyses")
