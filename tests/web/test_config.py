import pytest

from tradingagents_web.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("WEB_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    settings = Settings()
    assert settings.database_url == "sqlite:///test.db"
    assert settings.session_secret.get_secret_value() == "x" * 32


def test_settings_session_max_age_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    monkeypatch.delenv("WEB_SESSION_MAX_AGE_SECONDS", raising=False)
    settings = Settings()
    # 30일 = 2592000초
    assert settings.session_max_age_seconds == 30 * 24 * 3600
