"""Low-level helpers for SQLite backup/restore admin operations.

These helpers validate uploaded SQLite files and atomically swap them in
place. The orchestrator (`run_restore`) wires them together with
caller-supplied scheduler/engine lifecycle hooks.

Nothing here touches the FastAPI app, the SQLAlchemy engine, or the
scheduler directly — that wiring is the caller's responsibility.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable, Iterable
from pathlib import Path

# SQLite 3 file format magic header (first 16 bytes of every valid DB).
SQLITE_MAGIC: bytes = b"SQLite format 3\x00"


class DatabaseValidationError(ValueError):
    """Raised when a candidate SQLite file fails validation checks."""


def validate_sqlite(path: Path, *, required_tables: Iterable[str]) -> None:
    """Validate that ``path`` is a healthy SQLite DB containing required tables.

    The file is opened read-only via SQLite's URI form so the validation
    cannot accidentally mutate the candidate database.

    Args:
        path: Filesystem path to the candidate SQLite database file.
        required_tables: Iterable of table names that MUST exist in the DB.

    Raises:
        DatabaseValidationError: If the file is missing, too small, lacks the
            SQLite magic header, fails ``PRAGMA integrity_check``, cannot be
            opened by sqlite3, or is missing any of ``required_tables``.
    """
    if not path.exists() or not path.is_file():
        raise DatabaseValidationError(f"file does not exist: {path}")

    if path.stat().st_size < len(SQLITE_MAGIC):
        raise DatabaseValidationError(f"file too small to be a SQLite DB: {path}")

    with path.open("rb") as fh:
        header = fh.read(len(SQLITE_MAGIC))
    if header != SQLITE_MAGIC:
        raise DatabaseValidationError(f"not a SQLite 3 database (bad magic): {path}")

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise DatabaseValidationError(f"sqlite3 could not open {path}: {exc}") from exc

    try:
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as exc:
            raise DatabaseValidationError(f"integrity check failed for {path}: {exc}") from exc
        if not integrity or integrity[0] != "ok":
            raise DatabaseValidationError(f"integrity check did not return 'ok' for {path}: {integrity}")

        try:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        except sqlite3.Error as exc:
            raise DatabaseValidationError(f"could not list tables in {path}: {exc}") from exc

        present = {row[0] for row in rows}
        for table in required_tables:
            if table not in present:
                raise DatabaseValidationError(f"required table missing: {table}")
    finally:
        conn.close()


def swap_database(target: Path, staging: Path) -> None:
    """Atomically replace ``target`` with ``staging`` and clean WAL/SHM sidecars.

    Caller responsibility:
        Before calling this function the caller MUST have stopped any worker
        processes/threads that hold the SQLAlchemy engine and disposed the
        engine itself. Otherwise open file handles on the old DB (and stale
        WAL/SHM sidecars) will cause data corruption or inconsistency.

    Args:
        target: Path to the live DB file that will be replaced.
        staging: Path to the validated replacement DB file.

    Raises:
        FileNotFoundError: If ``staging`` does not exist.
    """
    if not staging.exists():
        raise FileNotFoundError(f"staging file does not exist: {staging}")

    target.parent.mkdir(parents=True, exist_ok=True)

    for suffix in ("-wal", "-shm"):
        sidecar = target.with_name(target.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

    # `shutil.move` is atomic when source and destination are on the same
    # filesystem (rename(2)); otherwise it falls back to copy + remove.
    shutil.move(str(staging), str(target))


def run_restore(
    *,
    target: Path,
    staging: Path,
    required_tables: Iterable[str],
    stop_workers: Callable[[], None],
    dispose_engine: Callable[[], None],
    start_workers: Callable[[], None],
) -> None:
    """Validate, then swap a SQLite DB while pausing the scheduler/engine.

    Order of operations is strictly:
        1. ``validate_sqlite(staging, required_tables=...)``
        2. ``stop_workers()``
        3. ``dispose_engine()``
        4. ``swap_database(target, staging)``
        5. ``start_workers()`` — guaranteed to run via ``finally``

    If validation fails the scheduler hooks are NOT touched and the live DB
    is untouched. If steps 2–4 raise, ``start_workers`` still fires so the
    application is not left in a stopped state.

    Args:
        target: Path to the live DB file to be replaced.
        staging: Path to the candidate replacement DB file.
        required_tables: Tables that must exist in the staging DB.
        stop_workers: Callable that stops scheduler/background workers.
        dispose_engine: Callable that disposes the SQLAlchemy engine.
        start_workers: Callable that restarts scheduler/background workers.

    Raises:
        DatabaseValidationError: If the staging DB fails validation. The live
            DB and scheduler are left untouched.
        FileNotFoundError: If ``staging`` disappears between validation and
            swap.
    """
    validate_sqlite(staging, required_tables=required_tables)

    try:
        stop_workers()
        dispose_engine()
        swap_database(target, staging)
    finally:
        start_workers()


__all__ = [
    "DatabaseValidationError",
    "SQLITE_MAGIC",
    "run_restore",
    "swap_database",
    "validate_sqlite",
]
