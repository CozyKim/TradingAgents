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


def test_migration_0004_alerts_settings(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "mig_0004.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")

    # Upgrade to revision 0004.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0004"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"alembic upgrade 0004 failed: {result.stderr}"
    assert db_file.exists()

    engine = sa.create_engine(f"sqlite:///{db_file}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())

    # Both new tables must exist.
    assert "alerts" in tables, "alerts table must exist after upgrade 0004"
    assert "settings" in tables, "settings table must exist after upgrade 0004"

    # --- alerts columns ---
    alerts_col_names = {col["name"] for col in inspector.get_columns("alerts")}
    for col in {"id", "type", "ticker", "analysis_id", "schedule_id", "payload", "read", "created_at"}:
        assert col in alerts_col_names, f"alerts.{col} column missing"

    # --- alerts indexes ---
    alerts_index_names = {idx["name"] for idx in inspector.get_indexes("alerts")}
    assert "ix_alerts_read_created" in alerts_index_names, "ix_alerts_read_created missing"
    assert "ix_alerts_ticker" in alerts_index_names, "ix_alerts_ticker missing"
    assert "ix_alerts_type" in alerts_index_names, "ix_alerts_type missing"

    # --- settings columns ---
    settings_col_names = {col["name"] for col in inspector.get_columns("settings")}
    for col in {"key", "value", "encrypted_value", "updated_at"}:
        assert col in settings_col_names, f"settings.{col} column missing"

    # --- downgrade back to 0003 removes both tables ---
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0003"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"alembic downgrade to 0003 failed: {result.stderr}"

    engine2 = sa.create_engine(f"sqlite:///{db_file}")
    tables_after = set(sa.inspect(engine2).get_table_names())
    assert "alerts" not in tables_after, "alerts table must be removed after downgrade"
    assert "settings" not in tables_after, "settings table must be removed after downgrade"
