"""add chat_messages table

Revision ID: 4fdb78a7d4ca
Revises: 0005
Create Date: 2026-05-09 06:42:31.591466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4fdb78a7d4ca'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content_blocks", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("tool_name", sa.String(64), nullable=True),
        sa.Column(
            "partial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "cancelled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("error", sa.String(2048), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("model_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "analysis_id",
            "sequence",
            name="uq_chat_messages_analysis_sequence",
        ),
    )
    op.create_index(
        "ix_chat_messages_analysis_id",
        "chat_messages",
        ["analysis_id"],
    )
    op.create_index(
        "ix_chat_messages_turn_id",
        "chat_messages",
        ["turn_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_turn_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_analysis_id", table_name="chat_messages")
    op.drop_table("chat_messages")
