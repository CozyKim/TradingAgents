import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tradingagents_web.auth import verify_password


@pytest.fixture()
def cli_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a fresh sqlite DB and reload the db module so SessionLocal binds it.

    Returns (cli_app, db_module) so tests can query the same engine the CLI uses.
    """
    db_file = tmp_path / "cli.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)

    # Reload db so engine is rebuilt against the new env var.
    from tradingagents_web import db as db_mod

    importlib.reload(db_mod)

    # Create tables on the fresh engine.
    from tradingagents_web.models import Base

    Base.metadata.create_all(db_mod.engine)

    # The CLI uses lazy imports of db, so it will pick up the reloaded module.
    from tradingagents_web.cli import app as _app

    return _app, db_mod


def test_set_password_creates_user(cli_app) -> None:
    app, db_mod = cli_app
    from tradingagents_web.models import User

    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="hunter2!\nhunter2!\n")
    assert result.exit_code == 0, result.output

    with db_mod.SessionLocal() as session:
        user = session.query(User).first()
        assert user is not None
        assert verify_password("hunter2!", user.password_hash)


def test_set_password_updates_existing(cli_app) -> None:
    app, db_mod = cli_app
    from tradingagents_web.models import User

    runner = CliRunner()
    runner.invoke(app, ["set-password"], input="firstpass\nfirstpass\n")
    result = runner.invoke(app, ["set-password"], input="secondpass\nsecondpass\n")
    assert result.exit_code == 0

    with db_mod.SessionLocal() as session:
        user = session.query(User).first()
        assert verify_password("secondpass", user.password_hash)


def test_set_password_mismatch(cli_app) -> None:
    app, _ = cli_app
    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="abcdefgh\nzzzzzzzz\n")
    assert result.exit_code != 0
    assert "match" in result.output.lower()


def test_set_password_too_short(cli_app) -> None:
    app, _ = cli_app
    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="abc\nabc\n")
    assert result.exit_code != 0
    assert "8 characters" in result.output


def test_set_password_refuses_pipe_to_prod_db(cli_app, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard: piped (non-TTY) set-password against the prod DB must abort."""
    app, db_mod = cli_app
    from tradingagents_web import cli as cli_mod
    from tradingagents_web.models import User

    # Treat the test's tmp DB AS the prod DB by redirecting the guard's sentinel.
    prod_path = Path(db_mod.engine.url.database).resolve()  # type: ignore[arg-type]
    monkeypatch.setattr(cli_mod, "PROD_DB_PATH", prod_path)

    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="hunter2!\nhunter2!\n")
    assert result.exit_code == 2, result.output
    assert "Refusing to overwrite the production password" in result.output

    # And no user was created — the original DB is untouched.
    with db_mod.SessionLocal() as session:
        assert session.query(User).first() is None


def test_set_password_allow_prod_overwrite_flag(cli_app, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard bypass: --allow-prod-overwrite flag lets the pipe through."""
    app, db_mod = cli_app
    from tradingagents_web import cli as cli_mod
    from tradingagents_web.models import User

    prod_path = Path(db_mod.engine.url.database).resolve()  # type: ignore[arg-type]
    monkeypatch.setattr(cli_mod, "PROD_DB_PATH", prod_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["set-password", "--allow-prod-overwrite"],
        input="hunter2!\nhunter2!\n",
    )
    assert result.exit_code == 0, result.output

    with db_mod.SessionLocal() as session:
        user = session.query(User).first()
        assert user is not None
        assert verify_password("hunter2!", user.password_hash)


def test_set_password_allow_prod_overwrite_env(cli_app, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard bypass: TRADINGAGENTS_ALLOW_PROD_OVERWRITE=1 also lets the pipe through."""
    app, db_mod = cli_app
    from tradingagents_web import cli as cli_mod

    prod_path = Path(db_mod.engine.url.database).resolve()  # type: ignore[arg-type]
    monkeypatch.setattr(cli_mod, "PROD_DB_PATH", prod_path)
    monkeypatch.setenv(cli_mod.PROD_GUARD_ENV, "1")

    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="hunter2!\nhunter2!\n")
    assert result.exit_code == 0, result.output
