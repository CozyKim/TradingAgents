import pytest

from tradingagents_web.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    settings = Settings()
    assert settings.database_url == "sqlite:///test.db"


def test_settings_session_max_age_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    monkeypatch.delenv("WEB_SESSION_MAX_AGE_SECONDS", raising=False)
    settings = Settings()
    # 30일 = 2592000초
    assert settings.session_max_age_seconds == 30 * 24 * 3600


def test_cookie_secure_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    monkeypatch.delenv("WEB_COOKIE_SECURE", raising=False)
    settings = Settings()
    assert settings.cookie_secure is False


def test_cookie_secure_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    monkeypatch.setenv("WEB_COOKIE_SECURE", "true")
    settings = Settings()
    assert settings.cookie_secure is True


def test_settings_includes_schedule_tz_default():
    from tradingagents_web.config import Settings

    s = Settings()
    assert s.schedule_tz == "America/New_York"
    assert s.scheduler_grace_seconds == 60
