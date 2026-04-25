"""tradingagents-web CLI entry point."""
import typer
from rich.console import Console

app = typer.Typer(help="TradingAgents Web administration CLI")
console = Console()


@app.command("version")
def version() -> None:
    """Show the CLI version."""
    from importlib.metadata import version as _version

    try:
        console.print(_version("tradingagents-web"))
    except Exception:
        console.print("unknown")


@app.command("set-password")
def set_password() -> None:
    """Create or update the single user's login password."""
    # Lazy imports so tests can swap the engine via env vars + module reload.
    from tradingagents_web.auth import hash_password
    from tradingagents_web.db import SessionLocal
    from tradingagents_web.models import User

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
