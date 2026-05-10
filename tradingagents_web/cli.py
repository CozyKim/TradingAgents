"""tradingagents-web CLI entry point."""
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from sqlalchemy.engine.url import make_url

app = typer.Typer(help="TradingAgents Web administration CLI")
console = Console()

PROD_DB_PATH = (Path.home() / ".tradingagents" / "web.db").resolve()
PROD_GUARD_ENV = "TRADINGAGENTS_ALLOW_PROD_OVERWRITE"


def _resolved_sqlite_path(database_url: str) -> Path | None:
    """Return the absolute path of the sqlite DB the URL points at, or None for non-sqlite."""
    try:
        url = make_url(database_url)
    except Exception:
        return None
    if not url.drivername.startswith("sqlite") or not url.database:
        return None
    return Path(url.database).expanduser().resolve()


def _is_prod_db(database_url: str) -> bool:
    """True iff the URL points at the canonical user-home production DB."""
    path = _resolved_sqlite_path(database_url)
    return path is not None and path == PROD_DB_PATH


@app.command("version")
def version() -> None:
    """Show the CLI version."""
    from importlib.metadata import version as _version

    try:
        console.print(_version("tradingagents-web"))
    except Exception:
        console.print("unknown")


@app.command("set-password")
def set_password(
    allow_prod_overwrite: bool = typer.Option(
        False,
        "--allow-prod-overwrite",
        help=(
            "Bypass the production-DB guard. Required when the resolved "
            "WEB_DATABASE_URL points at ~/.tradingagents/web.db AND stdin is "
            "non-interactive (piped). Use only if you really mean to overwrite "
            "the production password."
        ),
    ),
) -> None:
    """Create or update the single user's login password.

    Guard:
      Refuses to run in non-interactive mode (piped stdin) when the resolved
      database URL points at the canonical production DB
      (``~/.tradingagents/web.db``). This prevents agents and scripts from
      silently resetting the live login password — the exact failure mode that
      occurred on 2026-05-09 when an automated E2E setup ran
      ``printf 'test1234\\ntest1234\\n' | tradingagents-web set-password``
      against the production DB.

      Override with ``--allow-prod-overwrite`` (or env var
      ``TRADINGAGENTS_ALLOW_PROD_OVERWRITE=1``) when the overwrite is
      intentional.
    """
    # Lazy imports so tests can swap the engine via env vars + module reload.
    from tradingagents_web.auth import hash_password
    from tradingagents_web.config import Settings
    from tradingagents_web.db import SessionLocal
    from tradingagents_web.models import User

    settings = Settings()
    is_prod = _is_prod_db(settings.database_url)
    is_pipe = not sys.stdin.isatty()
    env_allow = os.environ.get(PROD_GUARD_ENV, "").lower() in {"1", "true", "yes"}

    if is_prod and is_pipe and not (allow_prod_overwrite or env_allow):
        console.print(
            "[red]Refusing to overwrite the production password non-interactively.[/red]\n"
            f"  database_url resolves to: {PROD_DB_PATH}\n"
            "  stdin is piped (non-TTY).\n\n"
            "If this is intentional, re-run with [bold]--allow-prod-overwrite[/bold] "
            f"or set [bold]{PROD_GUARD_ENV}=1[/bold].\n"
            "For tests/E2E, point [bold]WEB_DATABASE_URL[/bold] at an isolated DB "
            "(e.g. sqlite:///./tradingagents_web_e2e.db) before running this command."
        )
        raise typer.Exit(code=2)

    if is_prod and not is_pipe and not (allow_prod_overwrite or env_allow):
        console.print(
            "[yellow]You are about to overwrite the production login password.[/yellow]"
        )
        console.print(f"  database_url resolves to: {PROD_DB_PATH}")
        confirm = typer.prompt(
            "Type [OVERWRITE] to continue (anything else aborts)", default="", show_default=False
        )
        if confirm.strip() != "OVERWRITE":
            console.print("[red]Aborted.[/red]")
            raise typer.Exit(code=1)

    password = typer.prompt("New password", hide_input=True)
    confirm = typer.prompt("Confirm password", hide_input=True)
    if password != confirm:
        console.print("[red]Passwords do not match.[/red]")
        raise typer.Exit(code=1)
    if len(password) < 8:
        console.print("[red]Password must be at least 8 characters.[/red]")
        raise typer.Exit(code=1)

    with SessionLocal() as session:
        user = session.query(User).first()
        if user is None:
            user = User(password_hash=hash_password(password))
            session.add(user)
            console.print("[green]Created user with new password.[/green]")
        else:
            user.password_hash = hash_password(password)
            console.print("[green]Updated existing user password.[/green]")
        session.commit()


if __name__ == "__main__":
    app()
