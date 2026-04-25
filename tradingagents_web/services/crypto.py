"""Symmetric encryption for stored secrets (LLM API keys, Telegram tokens)."""
import os

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    """Load Fernet instance from ENCRYPTION_KEY env var.

    Read fresh each call so tests can override via monkeypatch.
    """
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> bytes:
    """Encrypt a string secret. Returns raw bytes for DB BLOB storage."""
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_secret(ciphertext: bytes) -> str:
    """Decrypt previously-encrypted bytes. Raises on tampered/invalid data."""
    return _get_fernet().decrypt(ciphertext).decode("utf-8")
