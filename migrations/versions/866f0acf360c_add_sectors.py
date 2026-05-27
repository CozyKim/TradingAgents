"""add sectors

Revision ID: 866f0acf360c
Revises: 4fdb78a7d4ca
Create Date: 2026-05-28 01:40:03.093147

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "866f0acf360c"
down_revision: Union[str, None] = "4fdb78a7d4ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRESET_SECTORS = [
    {
        "slug": "ai",
        "name": "AI · 인공지능",
        "description": "AI 가속기·파운데이션 모델·인프라 전반",
        "keywords": ["AI accelerator", "GPU", "foundation models", "NVIDIA", "OpenAI"],
    },
    {
        "slug": "power",
        "name": "전력 · 그리드",
        "description": "AI 데이터센터 전력·송배전·HVDC·트랜스포머",
        "keywords": ["power grid", "transformer", "HVDC", "AI data center power"],
    },
    {
        "slug": "semiconductor-memory",
        "name": "반도체 — 메모리",
        "description": "DRAM·NAND·HBM 메모리 사이클",
        "keywords": ["DRAM", "NAND", "HBM", "Samsung", "SK Hynix", "Micron"],
    },
    {
        "slug": "semiconductor-logic",
        "name": "반도체 — 비메모리",
        "description": "파운드리·팹리스·EUV·소재·장비",
        "keywords": ["foundry", "fabless", "EUV", "TSMC", "ASML", "Applied Materials"],
    },
    {
        "slug": "robotics",
        "name": "로봇",
        "description": "휴머노이드·산업용 로봇",
        "keywords": ["humanoid", "industrial robot", "Boston Dynamics", "Tesla Optimus"],
    },
    {
        "slug": "space",
        "name": "우주",
        "description": "발사체·위성·우주 인프라",
        "keywords": ["launch vehicle", "satellite", "SpaceX", "Rocket Lab", "Starlink"],
    },
]


def upgrade() -> None:
    op.create_table(
        "sectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("is_preset", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sectors_slug", "sectors", ["slug"], unique=True)

    op.create_table(
        "sector_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("sector_id", sa.Integer(),
                  sa.ForeignKey("sectors.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("llm_quick_model", sa.String(length=64), nullable=True),
        sa.Column("llm_deep_model", sa.String(length=64), nullable=True),
        sa.Column("search_call_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_sector_runs_sector_id", "sector_runs", ["sector_id"])

    op.create_table(
        "sector_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sector_id", sa.Integer(),
                  sa.ForeignKey("sectors.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("run_id", sa.String(length=36),
                  sa.ForeignKey("sector_runs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("report_md", sa.Text(), nullable=False),
        sa.Column("value_chain_mermaid", sa.Text(), nullable=False),
        sa.Column("companies", sa.JSON(), nullable=False),
        sa.Column("outlook_summary", sa.Text(), nullable=False),
        sa.Column("candidate_tickers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_sector_reports_run_id"),
        sa.UniqueConstraint("sector_id", "version", name="uq_sector_report_version"),
    )
    op.create_index("ix_sector_reports_sector_id", "sector_reports", ["sector_id"])

    # Seed preset sectors
    now = datetime.now(timezone.utc)
    sectors_tbl = sa.table(
        "sectors",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("keywords", sa.JSON),
        sa.column("is_preset", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        sectors_tbl,
        [
            {
                "slug": p["slug"],
                "name": p["name"],
                "description": p["description"],
                "keywords": p["keywords"],
                "is_preset": True,
                "created_at": now,
            }
            for p in PRESET_SECTORS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_sector_reports_sector_id", table_name="sector_reports")
    op.drop_table("sector_reports")
    op.drop_index("ix_sector_runs_sector_id", table_name="sector_runs")
    op.drop_table("sector_runs")
    op.drop_index("ix_sectors_slug", table_name="sectors")
    op.drop_table("sectors")
