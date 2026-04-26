from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

from tradingagents_web.services.crypto import decrypt_secret, encrypt_secret


def test_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)

    plaintext = "sk-very-secret-api-key"
    encrypted = encrypt_secret(plaintext)
    assert encrypted != plaintext.encode()
    assert decrypt_secret(encrypted) == plaintext


def test_decrypt_with_wrong_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    key1 = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key1)
    encrypted = encrypt_secret("hello")

    key2 = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key2)
    with pytest.raises(InvalidToken):
        decrypt_secret(encrypted)


def test_round_trip_loads_key_from_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("WEB_ENCRYPTION_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath(".env").write_text(f"ENCRYPTION_KEY={key}\n", encoding="utf-8")

    encrypted = encrypt_secret("telegram-token")

    assert decrypt_secret(encrypted) == "telegram-token"
