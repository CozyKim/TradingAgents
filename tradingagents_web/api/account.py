"""Account/settings API: backup, restore, password, sessions."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user
from tradingagents_web.db import get_db
from tradingagents_web.models import User

router = APIRouter(prefix="/api/settings/account", tags=["account"])


def _resolve_sqlite_path(db: OrmSession) -> Path:
    """Return the on-disk SQLite path for the engine bound to ``db``.

    Uses the session's bound engine (rather than the module-level engine) so
    that test overrides which point ``get_db`` at a tmpdir SQLite file resolve
    correctly.

    Args:
        db: The active SQLAlchemy ORM session.

    Returns:
        Absolute path to the SQLite file backing this session.

    Raises:
        HTTPException: 409 if the bound engine is not SQLite, or if the
            database is in-memory / has no on-disk file.
    """
    bind = db.get_bind()
    url = bind.url
    if url.drivername.split("+")[0] != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Backup/restore only supported on SQLite deployments.",
        )
    target = url.database or ""
    if not target or target == ":memory:":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No on-disk database file to back up.",
        )
    return Path(target).resolve()


@router.get("/backup")
def backup_database(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[OrmSession, Depends(get_db)],
) -> FileResponse:
    """Return the live SQLite file as an attachment, after merging the WAL.

    A ``wal_checkpoint(TRUNCATE)`` is executed first so the on-disk main file
    contains all committed pages from the write-ahead log. The file is then
    streamed back as ``application/octet-stream`` with a timestamped filename.

    Args:
        _user: The authenticated user (enforced via dependency).
        db: The active SQLAlchemy ORM session, used to resolve the SQLite path.

    Returns:
        FileResponse streaming the SQLite database file as an attachment.

    Raises:
        HTTPException: 404 if the resolved file does not exist on disk;
            409 if the bound engine is not an on-disk SQLite database.
    """
    path = _resolve_sqlite_path(db)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"tradingagents-backup-{stamp}.db"
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=filename,
    )
