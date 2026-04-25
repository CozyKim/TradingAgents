import pytest
from cryptography.fernet import Fernet

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
    with pytest.raises(Exception):  # InvalidToken
        decrypt_secret(encrypted)
