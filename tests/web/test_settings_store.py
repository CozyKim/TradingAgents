"""Tests for settings_store: round-trip + encryption + partial updates."""
import pytest
from cryptography.fernet import Fernet

from tradingagents_web.models import Setting
from tradingagents_web.services import settings_store


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_load_notification_defaults_when_empty(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        cfg = settings_store.load_notification_config(db)
        assert cfg["alert_on_signal_change"] is True
        assert cfg["alert_on_run_failed"] is True
        assert cfg["alert_on_run_completed"] is False
        assert cfg["alert_on_schedule_failed"] is True
        assert cfg["confidence_change_threshold"] == pytest.approx(0.10)
        assert cfg["telegram_bot_token"] is None
        assert cfg["telegram_chat_id"] is None
        assert cfg["telegram_bot_token_set"] is False
    finally:
        db.close()


def test_save_and_round_trip(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db,
            updates={
                "telegram_bot_token": "secret-bot-token",
                "telegram_chat_id": "12345",
                "alert_on_signal_change": False,
                "confidence_change_threshold": 0.25,
            },
        )
        cfg = settings_store.load_notification_config(db)
        assert cfg["telegram_bot_token"] == "secret-bot-token"
        assert cfg["telegram_bot_token_set"] is True
        assert cfg["telegram_chat_id"] == "12345"
        assert cfg["alert_on_signal_change"] is False
        assert cfg["confidence_change_threshold"] == pytest.approx(0.25)
    finally:
        db.close()


def test_token_stored_encrypted_not_plaintext(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db, updates={"telegram_bot_token": "sensitive-token-xyz"}
        )
        row = db.get(Setting, "telegram_bot_token")
        assert row is not None
        assert row.value is None
        assert row.encrypted_value is not None
        assert b"sensitive-token-xyz" not in row.encrypted_value
    finally:
        db.close()


def test_partial_update_preserves_others(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db, updates={"telegram_chat_id": "111"}
        )
        settings_store.save_notification_config(
            db, updates={"alert_on_run_completed": True}
        )
        cfg = settings_store.load_notification_config(db)
        assert cfg["telegram_chat_id"] == "111"
        assert cfg["alert_on_run_completed"] is True
    finally:
        db.close()


def test_unknown_key_raises(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        with pytest.raises(KeyError):
            settings_store.save_notification_config(
                db, updates={"nonsense_key": True}
            )
    finally:
        db.close()


def test_clear_token_via_empty_string(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db, updates={"telegram_bot_token": "first-token"}
        )
        settings_store.save_notification_config(
            db, updates={"telegram_bot_token": ""}
        )
        cfg = settings_store.load_notification_config(db)
        assert cfg["telegram_bot_token"] is None
        assert cfg["telegram_bot_token_set"] is False
        assert db.get(Setting, "telegram_bot_token") is None
    finally:
        db.close()


def test_unknown_key_in_second_position_does_not_partially_apply(app_with_test_db):
    """Validate-before-mutate guarantees no leak when a later key is bad."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        with pytest.raises(KeyError):
            settings_store.save_notification_config(
                db,
                updates={
                    "alert_on_signal_change": False,  # valid (would mutate)
                    "nonsense_key": True,             # invalid (must abort)
                },
            )
        # The valid mutation must NOT have leaked through.
        cfg = settings_store.load_notification_config(db)
        assert cfg["alert_on_signal_change"] is True  # default preserved
    finally:
        db.close()


def test_clear_token_via_none(app_with_test_db):
    """None and empty string both clear an encrypted key."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db, updates={"telegram_bot_token": "first-token"}
        )
        settings_store.save_notification_config(
            db, updates={"telegram_bot_token": None}
        )
        cfg = settings_store.load_notification_config(db)
        assert cfg["telegram_bot_token"] is None
        assert cfg["telegram_bot_token_set"] is False
        assert db.get(Setting, "telegram_bot_token") is None
    finally:
        db.close()


def test_empty_string_preserved_for_non_encrypted_key(app_with_test_db):
    """Plain keys keep "" verbatim — empty string is a valid value, not a clear."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db, updates={"telegram_chat_id": ""}
        )
        cfg = settings_store.load_notification_config(db)
        assert cfg["telegram_chat_id"] == ""
        # The row must still exist (was not deleted).
        assert db.get(Setting, "telegram_chat_id") is not None
    finally:
        db.close()
