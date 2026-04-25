"""Application configuration loaded from environment variables."""
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    All sensitive values are loaded from environment variables. Never commit
    a populated .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="WEB_",
    )

    # Storage
    database_url: str = "sqlite:///./tradingagents_web.db"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".tradingagents")

    # Auth / sessions
    session_secret: SecretStr = SecretStr("change-me-in-production-32chars-min")
    session_cookie_name: str = "tradingagents_session"
    session_max_age_seconds: int = 30 * 24 * 3600  # 30 days sliding

    # Encryption (for stored API keys, used in M2+)
    encryption_key: SecretStr = SecretStr("")

    # Misc
    cors_allow_origins: list[str] = ["http://localhost:3000"]
