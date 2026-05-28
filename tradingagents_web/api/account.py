"""Account/settings API: backup, restore, password, sessions."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import (
    get_current_user,
    hash_password,
    require_xhr,
    verify_password,
)
from tradingagents_web.config import Settings
from tradingagents_web.db import get_db
from tradingagents_web.models import Session as SessionModel
from tradingagents_web.models import User
from tradingagents_web.schemas.account import (
    PasswordChangeRequest,
    PasswordChangeResponse,
    RestoreResponse,
    SessionItem,
    SessionListResponse,
)
from tradingagents_web.services import db_admin
from tradingagents_web.services import scheduler as scheduler_module

router = APIRouter(prefix="/api/settings/account", tags=["account"])

_settings = Settings()

_REQUIRED_TABLES: tuple[str, ...] = (
    "users",
    "sessions",
    "analyses",
    "holdings",
    "schedules",
    "alerts",
    "settings",
    # M6 sector analysis — backups taken before that migration will fail
    # restore validation, which is the safe behavior: refusing them surfaces
    # the schema mismatch instead of silently breaking /api/sectors.
    "sectors",
    "sector_runs",
    "sector_reports",
)


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
    url = db.get_bind().engine.url
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


def _mask_token(token: str) -> str:
    """Return a short fingerprint that's safe to render in the UI."""
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}…{token[-4:]}"


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


@router.put("/password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> PasswordChangeResponse:
    """Change the single user's password and optionally revoke other sessions.

    Args:
        payload: Current and new password; ``revoke_other_sessions`` defaults
            to True so that all logged-in devices are signed out.
        request: Used to read the current session cookie so it survives the
            revoke step (the caller stays signed in).
        db: Active SQLAlchemy session.
        user: Authenticated user (raises 401 otherwise).
        _csrf: CSRF guard.

    Returns:
        ``PasswordChangeResponse(ok=True)`` on success.

    Raises:
        HTTPException: 401 if ``current_password`` does not match.
    """
    if not verify_password(payload.current_password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password.get_secret_value())
    if payload.revoke_other_sessions:
        current_token = request.cookies.get(_settings.session_cookie_name)
        q = db.query(SessionModel).filter_by(user_id=user.id)
        if current_token:
            q = q.filter(SessionModel.id != current_token)
        q.delete(synchronize_session=False)
    db.commit()
    return PasswordChangeResponse(ok=True)


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SessionListResponse:
    """List every active session for the current user, newest expiry first.

    Tokens are never returned in full. The current cookie's session is
    marked with ``is_current=True`` so the UI can disable a self-revoke.
    """
    current_token = request.cookies.get(_settings.session_cookie_name) or ""
    rows = (
        db.query(SessionModel)
        .filter_by(user_id=user.id)
        .order_by(SessionModel.expires_at.desc())
        .all()
    )
    items = [
        SessionItem(
            id_masked=_mask_token(s.id),
            expires_at=s.expires_at,
            is_current=(s.id == current_token),
        )
        for s in rows
    ]
    return SessionListResponse(sessions=items)


@router.post("/sessions/revoke-others", response_model=PasswordChangeResponse)
def revoke_other_sessions(
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> PasswordChangeResponse:
    """Delete every session row for this user except the caller's cookie."""
    current_token = request.cookies.get(_settings.session_cookie_name) or ""
    db.query(SessionModel).filter(
        SessionModel.user_id == user.id,
        SessionModel.id != current_token,
    ).delete(synchronize_session=False)
    db.commit()
    return PasswordChangeResponse(ok=True)


def _stop_scheduler() -> bool:
    """Shut down the in-process scheduler if one is running.

    Returns:
        ``True`` if a scheduler was actually stopped (i.e. one was
        registered before this call). ``False`` when no scheduler had
        been initialized — tests run in this mode because the FastAPI
        lifespan is not entered, so there is nothing to restart later.
    """
    try:
        svc = scheduler_module.get_scheduler()
    except RuntimeError:
        return False
    svc.shutdown()
    scheduler_module.set_scheduler(None)
    return True


def _start_scheduler() -> None:
    """Re-create + bootstrap the scheduler from the (possibly-replaced) DB.

    Imported lazily to avoid pulling APScheduler into modules that don't
    need it.
    """
    from tradingagents_web.config import Settings as _AppSettings
    from tradingagents_web.db import SessionLocal as _SessionLocal
    from tradingagents_web.services import auto_runner as _auto_runner
    from tradingagents_web.services.scheduler import SchedulerService as _SchedulerService

    settings = _AppSettings()
    svc = _SchedulerService(
        tz=settings.schedule_tz,
        grace_seconds=settings.scheduler_grace_seconds,
    )

    async def _on_trigger(schedule_id: int) -> None:
        # Discard ``trigger_run``'s ``str | None`` return so the callable
        # matches ``TriggerCallback = Callable[[int], Awaitable[None]]``.
        await _auto_runner.trigger_run(schedule_id)

    svc.set_trigger_callback(_on_trigger)
    scheduler_module.set_scheduler(svc)
    svc.start()
    db = _SessionLocal()
    try:
        svc.bootstrap(db)
    finally:
        db.close()


@router.post("/restore", response_model=RestoreResponse)
async def restore_database(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> RestoreResponse:
    """Replace the live SQLite file with an uploaded backup.

    Steps:
      1. Resolve the bound engine's file path.
      2. Stream the upload into a sibling staging file.
      3. Run ``db_admin.run_restore`` which validates the staging file,
         stops the scheduler, disposes the bound engine, swaps the file
         in place, and finally restarts the scheduler.

    Out of scope: undoing a partial restore. If swap fails after the
    engine is disposed but before the file is replaced, the live DB is
    intact (only metadata was touched). The next request reopens it.

    Raises:
        HTTPException: 400 if the upload fails validation; 409 if the
            deployment is not on-disk SQLite.
    """
    target = _resolve_sqlite_path(db)
    staging = target.with_name("restore.staging.db")
    try:
        with staging.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    bound_engine = db.get_bind().engine

    def _dispose() -> None:
        bound_engine.dispose()

    # Track whether we actually stopped a scheduler so we only restart
    # one if one existed. Tests don't enter the lifespan and therefore
    # never have a scheduler — restarting one would leak APScheduler
    # state across test cases (stale event-loop reference).
    was_running: dict[str, bool] = {"v": False}

    def _stop() -> None:
        was_running["v"] = _stop_scheduler()

    def _start() -> None:
        if was_running["v"]:
            _start_scheduler()

    try:
        db_admin.run_restore(
            target=target,
            staging=staging,
            required_tables=_REQUIRED_TABLES,
            stop_workers=_stop,
            dispose_engine=_dispose,
            start_workers=_start,
        )
    except db_admin.DatabaseValidationError as exc:
        if staging.exists():
            staging.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RestoreResponse(ok=True, detail="Database restored. All sessions revoked.")
