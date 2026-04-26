"""Unit tests for services.db_admin."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tradingagents_web.services import db_admin


def _make_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, password_hash TEXT)")
    conn.commit()
    conn.close()


def test_validate_sqlite_accepts_real_db(tmp_path: Path) -> None:
    db = tmp_path / "ok.db"
    _make_sqlite(db)
    db_admin.validate_sqlite(db, required_tables=("users",))


def test_validate_sqlite_rejects_random_file(tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a sqlite file at all")
    with pytest.raises(db_admin.DatabaseValidationError):
        db_admin.validate_sqlite(junk, required_tables=("users",))


def test_validate_sqlite_rejects_missing_table(tmp_path: Path) -> None:
    db = tmp_path / "incomplete.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    with pytest.raises(db_admin.DatabaseValidationError, match="users"):
        db_admin.validate_sqlite(db, required_tables=("users",))


def test_validate_sqlite_rejects_corrupt_db(tmp_path: Path) -> None:
    db = tmp_path / "broken.db"
    _make_sqlite(db)
    raw = db.read_bytes()
    db.write_bytes(raw[:32] + b"\x00" * (len(raw) - 32))
    with pytest.raises(db_admin.DatabaseValidationError):
        db_admin.validate_sqlite(db, required_tables=("users",))


def test_swap_database_replaces_target_file_atomically(tmp_path: Path) -> None:
    target = tmp_path / "live.db"
    staging = tmp_path / "incoming.db"
    target.write_bytes(b"old")
    staging.write_bytes(b"new")
    sidecars = [
        target.with_name(target.name + "-wal"),
        target.with_name(target.name + "-shm"),
    ]
    for s in sidecars:
        s.write_bytes(b"sidecar")

    db_admin.swap_database(target, staging)

    assert target.read_bytes() == b"new"
    assert not staging.exists()
    for s in sidecars:
        assert not s.exists(), f"WAL/SHM sidecar should be removed: {s}"


def test_swap_database_raises_when_staging_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        db_admin.swap_database(tmp_path / "missing.db", tmp_path / "nope.db")


def test_run_restore_replaces_db_and_calls_scheduler_hooks(tmp_path: Path) -> None:
    target = tmp_path / "live.db"
    _make_sqlite(target)
    conn = sqlite3.connect(target)
    conn.execute("INSERT INTO users(id, password_hash) VALUES (1, 'OLD')")
    conn.commit()
    conn.close()

    staging = tmp_path / "staging.db"
    _make_sqlite(staging)
    conn = sqlite3.connect(staging)
    conn.execute("INSERT INTO users(id, password_hash) VALUES (1, 'NEW')")
    conn.commit()
    conn.close()

    calls: list[str] = []
    db_admin.run_restore(
        target=target,
        staging=staging,
        required_tables=("users",),
        stop_workers=lambda: calls.append("stop"),
        dispose_engine=lambda: calls.append("dispose"),
        start_workers=lambda: calls.append("start"),
    )

    assert calls == ["stop", "dispose", "start"]
    conn = sqlite3.connect(target)
    row = conn.execute("SELECT password_hash FROM users WHERE id=1").fetchone()
    conn.close()
    assert row[0] == "NEW"


def test_run_restore_invalid_staging_does_not_touch_target(tmp_path: Path) -> None:
    target = tmp_path / "live.db"
    _make_sqlite(target)
    target_before = target.read_bytes()

    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not sqlite")

    calls: list[str] = []
    with pytest.raises(db_admin.DatabaseValidationError):
        db_admin.run_restore(
            target=target,
            staging=junk,
            required_tables=("users",),
            stop_workers=lambda: calls.append("stop"),
            dispose_engine=lambda: calls.append("dispose"),
            start_workers=lambda: calls.append("start"),
        )
    # Validation failed BEFORE stop/dispose hooks fire and BEFORE swap.
    assert calls == []
    assert target.read_bytes() == target_before
