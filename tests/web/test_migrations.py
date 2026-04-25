import subprocess
from pathlib import Path


def test_migrations_run_clean(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("WEB_SESSION_SECRET", "x" * 32)
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic upgrade failed: {result.stderr}"
    assert db_file.exists()
