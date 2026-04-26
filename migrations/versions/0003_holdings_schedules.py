"""holdings + schedules tables, analyses.schedule_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25 00:00:02.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column("monitor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # SQLite does not support ALTER TABLE ADD CONSTRAINT, so the unique
        # constraint is declared inline at table-creation time.
        sa.UniqueConstraint("ticker", name="uq_holdings_ticker"),
    )
    op.create_index("ix_holdings_ticker", "holdings", ["ticker"])

    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("cron_expr", sa.String(length=64), nullable=False),
        sa.Column("preset", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'user'")),
        sa.Column("holding_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schedules_ticker", "schedules", ["ticker"])
    op.create_index("ix_schedules_active", "schedules", ["active"])

    with op.batch_alter_table("analyses") as batch:
        batch.add_column(sa.Column("schedule_id", sa.Integer(), nullable=True))
        batch.create_index("ix_analyses_schedule_id", ["schedule_id"])


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch:
        batch.drop_index("ix_analyses_schedule_id")
        batch.drop_column("schedule_id")

    op.drop_index("ix_schedules_active", table_name="schedules")
    op.drop_index("ix_schedules_ticker", table_name="schedules")
    op.drop_table("schedules")

    op.drop_index("ix_holdings_ticker", table_name="holdings")
    # uq_holdings_ticker was declared inline at table creation; dropping the
    # table removes it (SQLite does not support ALTER TABLE DROP CONSTRAINT).
    op.drop_table("holdings")
