"""Tests for the Setting ORM model."""
import pytest
import sqlalchemy.exc

from tradingagents_web.models import Setting


def test_plain_value_row(app_with_test_db):
    """Plain text value row: value persisted, encrypted_value is None, updated_at set."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        row = Setting(key="alerts.signal_change", value="true")
        db.add(row)
        db.commit()
        db.refresh(row)

        fetched = db.query(Setting).filter_by(key="alerts.signal_change").one()
        assert fetched.value == "true"
        assert fetched.encrypted_value is None
        assert fetched.updated_at is not None
    finally:
        db.close()


def test_encrypted_value_row(app_with_test_db):
    """Encrypted binary value row: encrypted_value persisted, value is None."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        row = Setting(key="telegram_bot_token", encrypted_value=b"\x00\x01\x02")
        db.add(row)
        db.commit()
        db.refresh(row)

        fetched = db.query(Setting).filter_by(key="telegram_bot_token").one()
        assert fetched.value is None
        assert fetched.encrypted_value == b"\x00\x01\x02"
    finally:
        db.close()


def test_primary_key_uniqueness(app_with_test_db):
    """Inserting two rows with the same key must raise an integrity error."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(Setting(key="duplicate_key", value="first"))
        db.commit()

        db.add(Setting(key="duplicate_key", value="second"))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.commit()
    finally:
        db.close()
