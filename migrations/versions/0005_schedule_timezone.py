"""schedules.timezone column

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-26 00:00:01.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Pre-existing rows were created when SchedulerService had a single global
# timezone (default America/New_York). We backfill that exact value so their
# firing semantics remain unchanged after this column starts driving the
# scheduler. New rows default to Asia/Seoul at the application layer.
LEGACY_TZ = "America/New_York"


def upgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.add_column(
            sa.Column(
                "timezone",
                sa.String(length=64),
                nullable=False,
                server_default=sa.text(f"'{LEGACY_TZ}'"),
            )
        )
    # Drop the server_default so the model-side default ("Asia/Seoul") wins
    # for INSERTs while existing rows keep the backfilled value.
    with op.batch_alter_table("schedules") as batch:
        batch.alter_column("timezone", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch:
        batch.drop_column("timezone")
