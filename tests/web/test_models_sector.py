"""Tests for the Sector / SectorRun / SectorReport ORM models."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tradingagents_web.models import Sector, SectorReport, SectorRun


def test_sector_unique_slug(app_with_test_db):
    """동일 slug 두 개를 삽입하면 IntegrityError가 발생해야 한다."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(
            Sector(
                slug="semiconductors",
                name="반도체",
                description="메모리/파운드리/팹리스",
                keywords=["DRAM", "NAND", "foundry"],
                is_preset=True,
            )
        )
        db.commit()

        db.add(
            Sector(
                slug="semiconductors",  # 중복 slug
                name="중복 섹터",
                keywords=[],
                is_preset=False,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_sector_report_unique_version_per_sector(app_with_test_db):
    """동일 (sector_id, version) 조합의 두 SectorReport는 IntegrityError를 발생시켜야 한다."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sector = Sector(
            slug="ev-battery",
            name="이차전지",
            keywords=["battery", "EV"],
            is_preset=True,
        )
        db.add(sector)
        db.commit()
        db.refresh(sector)

        run1 = SectorRun(
            id="run-1",
            sector_id=sector.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
        )
        run2 = SectorRun(
            id="run-2",
            sector_id=sector.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
        )
        db.add_all([run1, run2])
        db.commit()

        db.add(
            SectorReport(
                sector_id=sector.id,
                run_id=run1.id,
                version=1,
                report_md="# report 1",
                value_chain_mermaid="graph LR; A-->B",
                companies=[{"ticker": "LGES.KS", "name": "LG에너지솔루션"}],
                outlook_summary="positive",
                candidate_tickers=[{"ticker": "LGES.KS"}],
            )
        )
        db.commit()

        db.add(
            SectorReport(
                sector_id=sector.id,
                run_id=run2.id,
                version=1,  # 동일 (sector_id, version) → 충돌
                report_md="# report 2",
                value_chain_mermaid="graph LR; B-->C",
                companies=[],
                outlook_summary="neutral",
                candidate_tickers=[],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_preset_sectors_seeded(tmp_path, monkeypatch):
    """The add-sectors migration seeds 6 preset sectors via bulk_insert."""
    REPO_ROOT = Path(__file__).resolve().parents[2]
    db_file = tmp_path / "seed.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"alembic upgrade failed: {result.stderr}"

    engine = sa.create_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        rows = conn.execute(
            sa.text("SELECT slug FROM sectors WHERE is_preset = 1")
        ).all()
    slugs = {r[0] for r in rows}
    assert slugs >= {
        "ai", "power", "semiconductor-memory",
        "semiconductor-logic", "robotics", "space",
    }
