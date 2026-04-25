import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

# alembic.ini lives at the repo root; resolve relative to this test file.
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_migrations_run_clean(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")

    # Use `python -m alembic` so the test does not depend on `alembic` being
    # on PATH (Windows / non-activated venvs / nested test runners).
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"alembic upgrade failed: {result.stderr}"
    assert db_file.exists()

    # Verify the actual schema, not just that the file was created.
    engine = sa.create_engine(f"sqlite:///{db_file}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert "users" in tables
    assert "sessions" in tables
    assert any(
        idx["name"] == "ix_sessions_user_id"
        for idx in inspector.get_indexes("sessions")
    )

    # --- 0002: analyses table ---
    assert "analyses" in tables, "analyses table must exist after upgrade head"

    analyses_index_names = {idx["name"] for idx in inspector.get_indexes("analyses")}
    assert "ix_analyses_ticker" in analyses_index_names
    assert "ix_analyses_ticker_created" in analyses_index_names
    assert "ix_analyses_status" in analyses_index_names

    # Verify that the unique constraint on run_id actually rejects duplicates.
    meta = sa.MetaData()
    meta.reflect(bind=engine, only=["analyses"])
    analyses_tbl = meta.tables["analyses"]

    with engine.begin() as conn:
        # Insert a first row — must succeed.
        conn.execute(
            analyses_tbl.insert().values(
                run_id="test-run-id-001",
                ticker="AAPL",
                analysis_date=date(2026, 1, 1),
                status="pending",
                llm_provider="openai",
                llm_deep_model="gpt-4o",
                llm_quick_model="gpt-4o-mini",
                debate_rounds=1,
                analysts='["market"]',
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            )
        )

    # Insert a second row with the same run_id — must raise IntegrityError.
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                analyses_tbl.insert().values(
                    run_id="test-run-id-001",
                    ticker="TSLA",
                    analysis_date=date(2026, 1, 2),
                    status="pending",
                    llm_provider="openai",
                    llm_deep_model="gpt-4o",
                    llm_quick_model="gpt-4o-mini",
                    debate_rounds=1,
                    analysts='["market"]',
                    created_at=datetime(2026, 1, 1, 1, 0, 0),
                )
            )
