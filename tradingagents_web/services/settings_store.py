"""Read/write helpers for the Setting key-value table.

The notifier and the settings API both depend on this module — keep it the
single source of truth for which keys exist and which keys are encrypted.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.models import Setting
from tradingagents_web.services.crypto import decrypt_secret, encrypt_secret

# Every notification key the system understands. Adding a new key requires
# updating both this dict (for defaults) and ENCRYPTED_KEYS if sensitive.
NOTIFICATION_DEFAULTS: dict[str, Any] = {
    "telegram_bot_token": None,
    "telegram_chat_id": None,
    "alert_on_signal_change": True,
    "alert_on_run_completed": False,
    "alert_on_run_failed": True,
    "alert_on_schedule_failed": True,
    "confidence_change_threshold": 0.10,
}

ENCRYPTED_KEYS: frozenset[str] = frozenset({"telegram_bot_token"})


def load_notification_config(db: OrmSession) -> dict[str, Any]:
    """Return the merged notification config: defaults overlaid with stored rows.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict with all NOTIFICATION_DEFAULTS keys plus the synthetic
        ``telegram_bot_token_set: bool`` flag derived from token presence.
    """
    cfg = dict(NOTIFICATION_DEFAULTS)
    rows = db.query(Setting).filter(Setting.key.in_(NOTIFICATION_DEFAULTS.keys())).all()
    for row in rows:
        if row.key in ENCRYPTED_KEYS:
            cfg[row.key] = (
                decrypt_secret(row.encrypted_value) if row.encrypted_value else None
            )
        else:
            cfg[row.key] = json.loads(row.value) if row.value is not None else None
    cfg["telegram_bot_token_set"] = cfg.get("telegram_bot_token") is not None
    return cfg


def save_notification_config(
    db: OrmSession, *, updates: Mapping[str, Any]
) -> None:
    """Apply a partial update to the notification config and commit.

    Unknown keys raise KeyError. None values for non-encrypted keys clear them
    (delete the row); for encrypted keys, an empty string clears as well.

    Args:
        db: SQLAlchemy session.
        updates: Partial mapping of NOTIFICATION_DEFAULTS keys to new values.

    Raises:
        KeyError: If a key in ``updates`` is not present in NOTIFICATION_DEFAULTS.
    """
    for key, value in updates.items():
        if key not in NOTIFICATION_DEFAULTS:
            raise KeyError(f"Unknown notification setting: {key!r}")

        row = db.get(Setting, key)
        if key in ENCRYPTED_KEYS:
            if value in (None, ""):
                if row is not None:
                    db.delete(row)
            else:
                cipher = encrypt_secret(str(value))
                if row is None:
                    row = Setting(key=key, encrypted_value=cipher)
                    db.add(row)
                else:
                    row.encrypted_value = cipher
                    row.value = None
        else:
            if value is None:
                if row is not None:
                    db.delete(row)
            else:
                serialized = json.dumps(value)
                if row is None:
                    row = Setting(key=key, value=serialized)
                    db.add(row)
                else:
                    row.value = serialized
                    row.encrypted_value = None
    db.commit()
