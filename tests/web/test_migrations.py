import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

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
