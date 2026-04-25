# TradingAgents Web — M1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웹 앱의 기반(인증·DB·디자인 시스템·반응형 셸)을 구축한다. 사용자가 로그인하면 빈 Dashboard와 사이드바(데스크톱) / 탭바(모바일)가 보이는 곳까지.

**Architecture:** FastAPI(`tradingagents_web/`) + SQLite + alembic 백엔드, Next.js 14 App Router + Tailwind + shadcn/ui 프런트엔드. DB 기반 세션 쿠키로 인증. docker-compose로 두 컨테이너 부팅.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x, alembic, bcrypt, cryptography(Fernet), Typer, pytest. Next.js 14, TypeScript, TailwindCSS, shadcn/ui, TanStack Query.

**Spec:** [docs/superpowers/specs/2026-04-25-tradingagents-web-design.md](../specs/2026-04-25-tradingagents-web-design.md)

**Out of scope (다른 플랜에서):** 분석 실행 + SSE 스트림(M2), Portfolio + Schedules(M3), Alerts + Telegram(M4), PWA + 폴리싱(M5).

---

## File Structure

신규 백엔드 패키지 `tradingagents_web/`:

```
tradingagents_web/
├── __init__.py
├── main.py              # FastAPI 앱 부트
├── config.py            # Pydantic Settings (env)
├── db.py                # SQLAlchemy engine + SessionLocal
├── auth.py              # bcrypt + 세션 관리 유틸 + DI
├── cli.py               # Typer CLI (set-password)
├── api/
│   ├── __init__.py
│   ├── health.py        # GET /api/health
│   └── auth.py          # POST /api/auth/{login,logout,me}
├── models/
│   ├── __init__.py
│   ├── base.py          # DeclarativeBase + 공통 컬럼
│   ├── user.py          # User
│   └── session.py       # Session (DB-backed)
└── services/
    └── crypto.py        # Fernet 래퍼 (M2+에서 API 키 암호화에 사용)

migrations/              # alembic
├── env.py
├── script.py.mako
└── versions/
    └── 0001_initial.py

tests/web/
├── __init__.py
├── conftest.py          # 테스트 DB + TestClient 픽스처
├── test_auth.py
├── test_health.py
└── test_cli.py
```

신규 프런트엔드 (`web/` 신규 디렉토리):

```
web/
├── package.json
├── next.config.mjs
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── components.json      # shadcn/ui
├── middleware.ts        # 보호 라우트
├── app/
│   ├── layout.tsx       # 루트 (폰트, 토큰)
│   ├── globals.css      # 디자인 토큰 + Tailwind
│   ├── (auth)/
│   │   └── login/
│   │       └── page.tsx
│   └── (workspace)/
│       ├── layout.tsx   # 사이드바 + 탭바 셸
│       └── page.tsx     # 빈 Dashboard
├── components/
│   ├── ui/              # shadcn — button, input, card, label
│   ├── nav/
│   │   ├── sidebar.tsx
│   │   └── tab-bar.tsx
│   └── shared/
│       └── logo.tsx
└── lib/
    ├── api.ts           # fetch 래퍼
    └── utils.ts         # cn() 헬퍼
```

기존 변경:

- `pyproject.toml`: 새 의존성 + 새 CLI 엔트리포인트 추가
- `.env.example`: `ENCRYPTION_KEY`, `WEB_DATABASE_URL`, `WEB_SESSION_SECRET` 추가
- `Dockerfile.api`(신규), `Dockerfile.web`(신규), `docker-compose.yml`(신규 또는 수정)
- `DEV.md`(신규): 로컬 개발 빠른 시작 가이드

---

## Task 1: 백엔드 의존성 + 패키지 스켈레톤

**Files:**
- Modify: `pyproject.toml`
- Create: `tradingagents_web/__init__.py`
- Create: `tradingagents_web/api/__init__.py`
- Create: `tradingagents_web/models/__init__.py`
- Create: `tradingagents_web/services/__init__.py`
- Create: `tests/web/__init__.py`

- [ ] **Step 1: pyproject.toml에 의존성 추가**

`[project] dependencies` 리스트에 다음을 추가하고, 알파벳 순으로 끼워 넣는다:

```toml
    "alembic>=1.13",
    "bcrypt>=4.1",
    "cryptography>=43.0",
    "fastapi>=0.115",
    "itsdangerous>=2.2",
    "pydantic-settings>=2.5",
    "python-multipart>=0.0.9",
    "sqlalchemy>=2.0",
    "uvicorn[standard]>=0.32",
```

`[dependency-groups] dev`에 추가:

```toml
    "httpx>=0.27",
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
```

`[project.scripts]`에 추가:

```toml
tradingagents-web = "tradingagents_web.cli:app"
```

`[tool.setuptools.packages.find] include` 리스트에 `"tradingagents_web*"` 추가.

- [ ] **Step 2: 빈 패키지 파일 생성**

```bash
touch tradingagents_web/__init__.py
touch tradingagents_web/api/__init__.py
touch tradingagents_web/models/__init__.py
touch tradingagents_web/services/__init__.py
touch tests/web/__init__.py
```

- [ ] **Step 3: 의존성 설치 검증**

Run: `uv sync` (또는 `pip install -e ".[dev]"`)
Expected: 새 패키지들이 모두 설치됨, 기존 deps와 충돌 없음.

- [ ] **Step 4: 커밋**

```bash
git add pyproject.toml tradingagents_web/ tests/web/
git commit -m "feat(web): scaffold tradingagents_web package and add dependencies"
```

---

## Task 2: Configuration 모듈

**Files:**
- Create: `tradingagents_web/config.py`
- Modify: `.env.example`
- Test: `tests/web/test_config.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_config.py`:

```python
import os

import pytest

from tradingagents_web.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("WEB_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)
    settings = Settings()
    assert settings.database_url == "sqlite:///test.db"
    assert settings.session_secret.get_secret_value() == "x" * 32


def test_settings_session_max_age_default() -> None:
    os.environ.setdefault("WEB_SESSION_SECRET", "x" * 32)
    os.environ.setdefault("ENCRYPTION_KEY", "y" * 44)
    settings = Settings()
    # 30일 = 2592000초
    assert settings.session_max_age_seconds == 30 * 24 * 3600
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_config.py -v`
Expected: FAIL — `ImportError: tradingagents_web.config`

- [ ] **Step 3: Settings 구현**

`tradingagents_web/config.py`:

```python
"""Application configuration loaded from environment variables."""
from pathlib import Path

from pydantic import SecretStr
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
    )

    # Storage
    database_url: str = "sqlite:///./tradingagents_web.db"
    data_dir: Path = Path.home() / ".tradingagents"

    # Auth / sessions
    session_secret: SecretStr = SecretStr("change-me-in-production-32chars-min")
    session_cookie_name: str = "tradingagents_session"
    session_max_age_seconds: int = 30 * 24 * 3600  # 30 days sliding

    # Encryption (for stored API keys, used in M2+)
    encryption_key: SecretStr = SecretStr("")

    # Misc
    cors_allow_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_prefix = "WEB_"
```

`.env.example` 끝에 다음 섹션 추가:

```bash
# === Web (M1+) ===
WEB_DATABASE_URL=sqlite:////root/.tradingagents/web.db
WEB_SESSION_SECRET=replace-with-32+-char-random-string
ENCRYPTION_KEY=replace-with-fernet-key-from-Fernet.generate_key
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_config.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/config.py tests/web/test_config.py .env.example
git commit -m "feat(web): add Settings module with env-based configuration"
```

---

## Task 3: SQLAlchemy Base + DB 세션 팩토리

**Files:**
- Create: `tradingagents_web/db.py`
- Create: `tradingagents_web/models/base.py`
- Test: `tests/web/test_db.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_db.py`:

```python
from sqlalchemy import text

from tradingagents_web.db import SessionLocal, engine


def test_engine_is_configured() -> None:
    assert engine is not None
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_factory_yields_session() -> None:
    with SessionLocal() as session:
        result = session.execute(text("SELECT 2")).scalar()
        assert result == 2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_db.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Base + db 구현**

`tradingagents_web/models/base.py`:

```python
"""Declarative base for all ORM models."""
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC now (for default values)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all models. Provides naming convention for constraints."""

    pass


class TimestampMixin:
    """Adds created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
```

`tradingagents_web/db.py`:

```python
"""Database engine and session factory."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tradingagents_web.config import Settings

_settings = Settings()

# SQLite needs check_same_thread=False for multi-threaded access (FastAPI)
connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    _settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

# Enable WAL mode for SQLite (required for APScheduler concurrency in M3+)
if _settings.database_url.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _enable_wal(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_db.py -v`
Expected: PASS (테스트 후 `tradingagents_web.db` 파일 생성됨 — gitignore에 추가)

- [ ] **Step 5: gitignore 업데이트 + 커밋**

`.gitignore` 끝에 추가:

```
*.db
*.db-shm
*.db-wal
```

```bash
git add tradingagents_web/db.py tradingagents_web/models/base.py tests/web/test_db.py .gitignore
git commit -m "feat(web): add SQLAlchemy engine, session factory, and base model"
```

---

## Task 4: User + Session 모델

**Files:**
- Create: `tradingagents_web/models/user.py`
- Create: `tradingagents_web/models/session.py`
- Modify: `tradingagents_web/models/__init__.py`
- Test: `tests/web/test_models.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_models.py`:

```python
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tradingagents_web.models import Base, Session as SessionModel, User
from tradingagents_web.models.base import utcnow


def _setup_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_user_can_be_created() -> None:
    db = _setup_db()
    user = User(password_hash="hashed")
    db.add(user)
    db.commit()
    assert user.id == 1
    assert user.created_at is not None


def test_session_links_to_user() -> None:
    db = _setup_db()
    user = User(password_hash="hashed")
    db.add(user)
    db.commit()
    sess = SessionModel(
        id="abc123", user_id=user.id, expires_at=utcnow() + timedelta(days=30)
    )
    db.add(sess)
    db.commit()
    assert sess.user_id == user.id
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_models.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: User 모델 구현**

`tradingagents_web/models/user.py`:

```python
"""Single-user account model."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """The single account for this deployment.

    Single-user app: there is only ever one row in this table.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 4: Session 모델 구현**

`tradingagents_web/models/session.py`:

```python
"""DB-backed session for cookie auth (revocable on logout)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from tradingagents_web.models.base import Base, utcnow


class Session(Base):
    """Server-side session record.

    `id` is the random opaque token stored in the user's cookie. We compare
    against this row and check `expires_at` on every protected request.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 5: `models/__init__.py` exports**

```python
"""ORM model exports."""
from tradingagents_web.models.base import Base, TimestampMixin
from tradingagents_web.models.session import Session
from tradingagents_web.models.user import User

__all__ = ["Base", "TimestampMixin", "Session", "User"]
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `pytest tests/web/test_models.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/models/ tests/web/test_models.py
git commit -m "feat(web): add User and Session ORM models"
```

---

## Task 5: Alembic 초기 마이그레이션

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_initial.py`
- Test: `tests/web/test_migrations.py`

- [ ] **Step 1: alembic.ini 생성**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = sqlite:///./tradingagents_web.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: migrations/env.py 생성**

```python
"""Alembic environment — uses Settings.database_url and our Base metadata."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from tradingagents_web.config import Settings
from tradingagents_web.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with our Settings (env-driven)
settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-friendly ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: script.py.mako 템플릿 생성**

`migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: 초기 마이그레이션 작성**

`migrations/versions/0001_initial.py`:

```python
"""initial schema: users, sessions

Revision ID: 0001
Revises:
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
```

- [ ] **Step 5: 마이그레이션 검증 테스트**

`tests/web/test_migrations.py`:

```python
import subprocess
from pathlib import Path


def test_migrations_run_clean(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("WEB_SESSION_SECRET", "x" * 32)
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic upgrade failed: {result.stderr}"
    assert db_file.exists()
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `pytest tests/web/test_migrations.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add alembic.ini migrations/ tests/web/test_migrations.py
git commit -m "feat(web): add alembic with initial users/sessions migration"
```

---

## Task 6: 비밀번호 해싱 + 세션 토큰 유틸

**Files:**
- Create: `tradingagents_web/auth.py`
- Test: `tests/web/test_auth_utils.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_auth_utils.py`:

```python
from tradingagents_web.auth import (
    generate_session_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    password = "correct horse battery staple"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_session_token_is_random() -> None:
    a = generate_session_token()
    b = generate_session_token()
    assert a != b
    assert len(a) >= 32  # at least 32 chars of entropy
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_auth_utils.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: 구현**

`tradingagents_web/auth.py`:

```python
"""Authentication utilities: password hashing, session tokens, FastAPI deps."""
import secrets
from datetime import timedelta

import bcrypt

from tradingagents_web.config import Settings
from tradingagents_web.models.base import utcnow

_settings = Settings()


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (cost=12 default)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verify against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure random session ID (URL-safe)."""
    return secrets.token_urlsafe(32)


def session_expiry() -> "datetime":
    """Return the expiry datetime for a freshly issued session."""
    return utcnow() + timedelta(seconds=_settings.session_max_age_seconds)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_auth_utils.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/auth.py tests/web/test_auth_utils.py
git commit -m "feat(web): add password hashing and session token utilities"
```

---

## Task 7: Crypto 서비스 (Fernet)

**Files:**
- Create: `tradingagents_web/services/crypto.py`
- Test: `tests/web/test_crypto.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_crypto.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_crypto.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: 구현**

`tradingagents_web/services/crypto.py`:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_crypto.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/crypto.py tests/web/test_crypto.py
git commit -m "feat(web): add Fernet-based secret encryption helper"
```

---

## Task 8: CLI `set-password` 명령

**Files:**
- Create: `tradingagents_web/cli.py`
- Test: `tests/web/test_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_cli.py`:

```python
import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tradingagents_web.auth import verify_password


@pytest.fixture()
def cli_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a fresh sqlite DB and reload the db module so SessionLocal binds it.

    Returns (cli_app, db_module) so tests can query the same engine the CLI uses.
    """
    db_file = tmp_path / "cli.db"
    monkeypatch.setenv("WEB_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("WEB_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("ENCRYPTION_KEY", "y" * 44)

    # Reload db so engine is rebuilt against the new env var.
    from tradingagents_web import db as db_mod

    importlib.reload(db_mod)

    # Create tables on the fresh engine.
    from tradingagents_web.models import Base

    Base.metadata.create_all(db_mod.engine)

    # The CLI uses lazy imports of db, so it will pick up the reloaded module.
    from tradingagents_web.cli import app as _app

    return _app, db_mod


def test_set_password_creates_user(cli_app) -> None:
    app, db_mod = cli_app
    from tradingagents_web.models import User

    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="hunter2!\nhunter2!\n")
    assert result.exit_code == 0, result.output

    with db_mod.SessionLocal() as session:
        user = session.query(User).first()
        assert user is not None
        assert verify_password("hunter2!", user.password_hash)


def test_set_password_updates_existing(cli_app) -> None:
    app, db_mod = cli_app
    from tradingagents_web.models import User

    runner = CliRunner()
    runner.invoke(app, ["set-password"], input="firstpass\nfirstpass\n")
    result = runner.invoke(app, ["set-password"], input="secondpass\nsecondpass\n")
    assert result.exit_code == 0

    with db_mod.SessionLocal() as session:
        user = session.query(User).first()
        assert verify_password("secondpass", user.password_hash)


def test_set_password_mismatch(cli_app) -> None:
    app, _ = cli_app
    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="abcdefgh\nzzzzzzzz\n")
    assert result.exit_code != 0
    assert "match" in result.output.lower()


def test_set_password_too_short(cli_app) -> None:
    app, _ = cli_app
    runner = CliRunner()
    result = runner.invoke(app, ["set-password"], input="abc\nabc\n")
    assert result.exit_code != 0
    assert "8 characters" in result.output
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_cli.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: 구현**

`tradingagents_web/cli.py`:

```python
"""tradingagents-web CLI entry point."""
import typer
from rich.console import Console

app = typer.Typer(help="TradingAgents Web administration CLI")
console = Console()


@app.command("set-password")
def set_password() -> None:
    """Create or update the single user's login password."""
    # Lazy imports so tests can swap the engine via env vars + module reload.
    from tradingagents_web.auth import hash_password
    from tradingagents_web.db import SessionLocal
    from tradingagents_web.models import User

    password = typer.prompt("New password", hide_input=True)
    confirm = typer.prompt("Confirm password", hide_input=True)
    if password != confirm:
        console.print("[red]Passwords do not match.[/red]")
        raise typer.Exit(code=1)
    if len(password) < 8:
        console.print("[red]Password must be at least 8 characters.[/red]")
        raise typer.Exit(code=1)

    with SessionLocal() as session:
        user = session.query(User).first()
        if user is None:
            user = User(password_hash=hash_password(password))
            session.add(user)
            console.print("[green]Created user with new password.[/green]")
        else:
            user.password_hash = hash_password(password)
            console.print("[green]Updated existing user password.[/green]")
        session.commit()


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_cli.py -v`
Expected: PASS (3개)

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/cli.py tests/web/test_cli.py
git commit -m "feat(web): add 'tradingagents-web set-password' CLI command"
```

---

## Task 9: 세션 관리 + 인증 의존성

**Files:**
- Modify: `tradingagents_web/auth.py` (확장)
- Test: `tests/web/test_session_helpers.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/web/test_session_helpers.py`:

```python
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tradingagents_web.auth import (
    create_session,
    delete_session,
    get_session_by_token,
    sliding_extend,
)
from tradingagents_web.models import Base, Session as SessionModel, User
from tradingagents_web.models.base import utcnow


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    user = User(password_hash="x")
    session.add(user)
    session.commit()
    return session


def test_create_session_returns_token(db: Session) -> None:
    user = db.query(User).first()
    token = create_session(db, user.id)
    assert isinstance(token, str)
    found = db.query(SessionModel).filter_by(id=token).first()
    assert found is not None
    assert found.user_id == user.id


def test_get_session_by_token_returns_none_when_expired(db: Session) -> None:
    user = db.query(User).first()
    expired = SessionModel(
        id="expired", user_id=user.id, expires_at=utcnow() - timedelta(seconds=1)
    )
    db.add(expired)
    db.commit()
    assert get_session_by_token(db, "expired") is None


def test_sliding_extend(db: Session) -> None:
    user = db.query(User).first()
    token = create_session(db, user.id)
    sess = db.query(SessionModel).filter_by(id=token).first()
    original_exp = sess.expires_at
    sliding_extend(db, sess)
    db.refresh(sess)
    assert sess.expires_at >= original_exp


def test_delete_session(db: Session) -> None:
    user = db.query(User).first()
    token = create_session(db, user.id)
    delete_session(db, token)
    assert db.query(SessionModel).filter_by(id=token).first() is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_session_helpers.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: `tradingagents_web/auth.py`에 추가**

기존 `auth.py` 끝에 다음을 추가:

```python
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.db import get_db
from tradingagents_web.models import Session as SessionModel, User


def create_session(db: OrmSession, user_id: int) -> str:
    """Persist a new session row and return its token."""
    token = generate_session_token()
    sess = SessionModel(id=token, user_id=user_id, expires_at=session_expiry())
    db.add(sess)
    db.commit()
    return token


def get_session_by_token(db: OrmSession, token: str) -> SessionModel | None:
    """Look up an active (non-expired) session row."""
    sess = db.query(SessionModel).filter_by(id=token).first()
    if sess is None:
        return None
    if sess.expires_at <= utcnow():
        return None
    return sess


def sliding_extend(db: OrmSession, sess: SessionModel) -> None:
    """Extend session expiry on use (sliding window)."""
    sess.expires_at = session_expiry()
    db.commit()


def delete_session(db: OrmSession, token: str) -> None:
    """Remove a session row (logout)."""
    db.query(SessionModel).filter_by(id=token).delete()
    db.commit()


def get_current_user(
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
) -> User:
    """FastAPI dependency: return current user or raise 401."""
    token = request.cookies.get(_settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    sess = get_session_by_token(db, token)
    if sess is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired")
    user = db.query(User).filter_by(id=sess.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User missing")
    sliding_extend(db, sess)
    return user
```

또한 `auth.py` 상단 import에 `from tradingagents_web.models.base import utcnow` 추가 (이미 있으면 skip).

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/web/test_session_helpers.py -v`
Expected: PASS (4개)

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/auth.py tests/web/test_session_helpers.py
git commit -m "feat(web): add session helpers and get_current_user dependency"
```

---

## Task 10: Health 엔드포인트 + FastAPI 앱 부트

**Files:**
- Create: `tradingagents_web/api/health.py`
- Create: `tradingagents_web/main.py`
- Test: `tests/web/conftest.py`
- Test: `tests/web/test_health.py`

- [ ] **Step 1: pytest 픽스처 (conftest)**

`tests/web/conftest.py`:

```python
"""Shared fixtures for web tests."""
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradingagents_web.db import get_db
from tradingagents_web.models import Base


@pytest.fixture()
def app_with_test_db(tmp_path: Path):
    """Build a FastAPI app whose DB dependency points at a fresh sqlite file."""
    from tradingagents_web.main import create_app

    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db() -> Generator:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    return app, TestSessionLocal


@pytest.fixture()
def client(app_with_test_db) -> TestClient:
    app, _ = app_with_test_db
    return TestClient(app)
```

- [ ] **Step 2: 실패하는 health 테스트**

`tests/web/test_health.py`:

```python
def test_health_returns_ok(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `pytest tests/web/test_health.py -v`
Expected: FAIL — `ImportError` from create_app

- [ ] **Step 4: health 라우터 구현**

`tradingagents_web/api/health.py`:

```python
"""Liveness/readiness endpoint."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: FastAPI 앱 팩토리**

`tradingagents_web/main.py`:

```python
"""FastAPI application factory and entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradingagents_web.api import health
from tradingagents_web.config import Settings


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="TradingAgents Web",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `pytest tests/web/test_health.py -v`
Expected: PASS

- [ ] **Step 7: 수동 부팅 검증**

Run: `uvicorn tradingagents_web.main:app --reload --port 8000`
브라우저에서 `http://localhost:8000/api/health` → `{"status":"ok"}` 응답 확인. Ctrl+C로 종료.

- [ ] **Step 8: 커밋**

```bash
git add tradingagents_web/main.py tradingagents_web/api/health.py tests/web/conftest.py tests/web/test_health.py
git commit -m "feat(web): add FastAPI app factory and /api/health endpoint"
```

---

## Task 11: 인증 API 엔드포인트

**Files:**
- Create: `tradingagents_web/api/auth.py`
- Modify: `tradingagents_web/main.py` (router 등록)
- Test: `tests/web/test_auth_api.py`

- [ ] **Step 1: 실패하는 테스트**

`tests/web/test_auth_api.py`:

```python
from fastapi.testclient import TestClient

from tradingagents_web.auth import hash_password
from tradingagents_web.models import User


def _seed_user(SessionLocal, password: str) -> None:
    with SessionLocal() as db:
        db.add(User(password_hash=hash_password(password)))
        db.commit()


def test_login_with_correct_password_sets_cookie(app_with_test_db) -> None:
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "hunter2"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "tradingagents_session" in response.cookies


def test_login_with_wrong_password_returns_401(app_with_test_db) -> None:
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "wrong"})
    assert response.status_code == 401


def test_login_when_no_user_returns_503(app_with_test_db) -> None:
    app, _SessionLocal = app_with_test_db
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "anything"})
    assert response.status_code == 503


def test_me_requires_auth(app_with_test_db) -> None:
    app, _SessionLocal = app_with_test_db
    client = TestClient(app)
    assert client.get("/api/auth/me").status_code == 401


def test_full_flow_login_me_logout(app_with_test_db) -> None:
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    client.post("/api/auth/login", json={"password": "hunter2"})
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"id": 1}

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/web/test_auth_api.py -v`
Expected: FAIL (라우터 미등록)

- [ ] **Step 3: 인증 라우터 구현**

`tradingagents_web/api/auth.py`:

```python
"""Login / logout / current-user API."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from tradingagents_web.auth import (
    create_session,
    delete_session,
    get_current_user,
    verify_password,
)
from tradingagents_web.config import Settings
from tradingagents_web.db import get_db
from tradingagents_web.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
_settings = Settings()


class LoginRequest(BaseModel):
    password: SecretStr


class LoginResponse(BaseModel):
    ok: bool


class MeResponse(BaseModel):
    id: int


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    user = db.query(User).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No user account configured. Run `tradingagents-web set-password`.",
        )
    if not verify_password(body.password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token = create_session(db, user.id)
    response.set_cookie(
        key=_settings.session_cookie_name,
        value=token,
        max_age=_settings.session_max_age_seconds,
        httponly=True,
        secure=False,  # set True in production behind TLS
        samesite="strict",
        path="/",
    )
    return LoginResponse(ok=True)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, bool]:
    token = request.cookies.get(_settings.session_cookie_name)
    if token:
        delete_session(db, token)
    response.delete_cookie(key=_settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(id=user.id)
```

- [ ] **Step 4: `main.py`에 라우터 등록**

`tradingagents_web/main.py`의 `create_app()` 안에서 `app.include_router(health.router)` 다음 줄에 추가:

```python
    from tradingagents_web.api import auth as auth_api
    app.include_router(auth_api.router)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/web/test_auth_api.py -v`
Expected: PASS (5개)

- [ ] **Step 6: 전체 백엔드 테스트 실행**

Run: `pytest tests/web/ -v`
Expected: 모든 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/api/auth.py tradingagents_web/main.py tests/web/test_auth_api.py
git commit -m "feat(web): add login/logout/me endpoints with cookie sessions"
```

---

## Task 12: 백엔드 Dockerfile

**Files:**
- Create: `Dockerfile.api`
- Create: `.dockerignore` 추가 (없으면)

- [ ] **Step 1: Dockerfile.api 작성**

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
COPY tradingagents/ ./tradingagents/
COPY tradingagents_web/ ./tradingagents_web/
COPY migrations/ ./migrations/
COPY alembic.ini ./

RUN pip install --upgrade pip && pip install -e .

EXPOSE 8000

# Run migrations then start server
CMD alembic upgrade head && \
    uvicorn tradingagents_web.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: `.dockerignore`에 추가**

기존 `.dockerignore`에 다음 추가 (없는 줄만):

```
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.venv/
*.db
*.db-shm
*.db-wal
node_modules/
web/.next/
```

- [ ] **Step 3: 빌드 테스트**

Run: `docker build -f Dockerfile.api -t tradingagents-api:dev .`
Expected: 빌드 성공.

Run: `docker run --rm -e ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") -e WEB_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))") -p 8000:8000 tradingagents-api:dev`
이후 `curl http://localhost:8000/api/health` → `{"status":"ok"}`. Ctrl+C로 종료.

- [ ] **Step 4: 커밋**

```bash
git add Dockerfile.api .dockerignore
git commit -m "feat(web): add backend Dockerfile"
```

---

## Task 13: 프런트엔드 프로젝트 초기화

**Files:**
- Create: `web/package.json`
- Create: `web/next.config.mjs`
- Create: `web/tsconfig.json`
- Create: `web/postcss.config.mjs`
- Create: `web/tailwind.config.ts`
- Create: `web/.gitignore`

- [ ] **Step 1: package.json 작성**

`web/package.json`:

```json
{
  "name": "tradingagents-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@radix-ui/react-label": "^2.1.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@tanstack/react-query": "^5.59.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "lucide-react": "^0.453.0",
    "next": "14.2.15",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "tailwind-merge": "^2.5.4"
  },
  "devDependencies": {
    "@types/node": "^22.7.0",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^8.57.1",
    "eslint-config-next": "14.2.15",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.6.2"
  }
}
```

- [ ] **Step 2: next.config.mjs**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`
            : "http://localhost:8000/api/:path*",
      },
    ];
  },
};
export default nextConfig;
```

- [ ] **Step 3: tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: postcss.config.mjs**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: tailwind.config.ts (디자인 토큰)**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          0: "#0a0a0b",
          1: "#111114",
          2: "#18181c",
        },
        border: {
          1: "#1f1f24",
          2: "#25252b",
        },
        text: {
          1: "#e8e8ea",
          2: "#a0a0a8",
          3: "#6b6b74",
        },
        accent: { DEFAULT: "#4f8cff", muted: "#1a2f4a" },
        signal: {
          buy: "#34d399",
          sell: "#f87171",
          hold: "#fbbf24",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
    },
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 6: web/.gitignore**

```
node_modules/
.next/
.env*.local
next-env.d.ts
out/
```

- [ ] **Step 7: 의존성 설치 검증**

Run: `cd web && npm install`
Expected: 설치 성공, 에러 없음.

- [ ] **Step 8: 커밋**

```bash
git add web/package.json web/package-lock.json web/next.config.mjs web/tsconfig.json web/postcss.config.mjs web/tailwind.config.ts web/.gitignore
git commit -m "feat(web): initialize Next.js 14 frontend with Tailwind tokens"
```

---

## Task 14: globals.css + 루트 레이아웃 + lib/utils

**Files:**
- Create: `web/app/globals.css`
- Create: `web/app/layout.tsx`
- Create: `web/lib/utils.ts`
- Create: `web/lib/api.ts`

- [ ] **Step 1: globals.css**

`web/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    color-scheme: dark;
  }
  html, body {
    background-color: #0a0a0b;
    color: #e8e8ea;
    font-family: Inter, system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  /* numbers + tickers */
  .font-num {
    font-family: "JetBrains Mono", "SF Mono", Consolas, monospace;
    font-variant-numeric: tabular-nums;
  }
  /* signal badges */
  .badge-buy { @apply bg-signal-buy/15 text-signal-buy; }
  .badge-sell { @apply bg-signal-sell/15 text-signal-sell; }
  .badge-hold { @apply bg-signal-hold/15 text-signal-hold; }
}
```

- [ ] **Step 2: 루트 layout.tsx**

`web/app/layout.tsx`:

```tsx
import "./globals.css";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TradingAgents",
  description: "Personal trading analysis workbench",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="bg-bg-0 text-text-1 antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 3: lib/utils.ts**

`web/lib/utils.ts`:

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 4: lib/api.ts**

`web/lib/api.ts`:

```typescript
/**
 * Thin fetch wrapper that always sends cookies and parses JSON.
 * Throws an Error with the API's `detail` message on non-2xx.
 */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
    ...init,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail ?? response.statusText;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}
```

- [ ] **Step 5: 빌드 검증**

Run: `cd web && npm run typecheck`
Expected: 에러 없음.

Run: `cd web && npm run build`
Expected: 빌드 성공 (이 시점에서 페이지가 없으면 Next가 경고할 수 있으나 통과).

- [ ] **Step 6: 커밋**

```bash
git add web/app/globals.css web/app/layout.tsx web/lib/
git commit -m "feat(web): add Tailwind globals, root layout, fetch wrapper"
```

---

## Task 15: shadcn/ui 베이스 컴포넌트

**Files:**
- Create: `web/components.json`
- Create: `web/components/ui/button.tsx`
- Create: `web/components/ui/input.tsx`
- Create: `web/components/ui/label.tsx`
- Create: `web/components/ui/card.tsx`

> 참고: shadcn CLI를 안 쓰고 수동으로 컴포넌트를 추가한다(다크 토큰을 우리 것에 맞춤). 추후 CLI를 쓰려면 `components.json`이 필요하다.

- [ ] **Step 1: components.json**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": false
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

- [ ] **Step 2: components/ui/button.tsx**

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-accent text-white hover:bg-accent/90",
        outline: "border border-border-1 bg-bg-1 hover:bg-bg-2",
        ghost: "hover:bg-bg-2",
        destructive: "bg-signal-sell/20 text-signal-sell hover:bg-signal-sell/30",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";
```

- [ ] **Step 3: components/ui/input.tsx**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-9 w-full rounded-md border border-border-1 bg-bg-1 px-3 py-1 text-sm text-text-1 placeholder:text-text-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
```

- [ ] **Step 4: components/ui/label.tsx**

```tsx
"use client";
import * as LabelPrimitive from "@radix-ui/react-label";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-xs uppercase tracking-wider text-text-3", className)}
    {...props}
  />
));
Label.displayName = "Label";
```

- [ ] **Step 5: components/ui/card.tsx**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-border-1 bg-bg-1", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-4 border-b border-border-1", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-sm font-semibold text-text-1", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...props} />;
}
```

- [ ] **Step 6: 타입체크 + 커밋**

Run: `cd web && npm run typecheck`
Expected: 통과.

```bash
git add web/components.json web/components/ui/
git commit -m "feat(web): add shadcn-style base UI components (Button/Input/Label/Card)"
```

---

## Task 16: 로그인 페이지

**Files:**
- Create: `web/app/(auth)/login/page.tsx`

- [ ] **Step 1: 로그인 페이지 구현**

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      router.replace("/");
      router.refresh();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Login failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-bg-0 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-base">TradingAgents</CardTitle>
          <p className="text-xs text-text-3">Personal trading analysis workbench</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoFocus
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
              />
            </div>
            {error && <p className="text-xs text-signal-sell">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
```

- [ ] **Step 2: 빌드 검증**

Run: `cd web && npm run build`
Expected: 빌드 성공.

- [ ] **Step 3: 커밋**

```bash
git add web/app/\(auth\)/
git commit -m "feat(web): add login page"
```

---

## Task 17: 사이드바 + 탭바 + 워크스페이스 셸

**Files:**
- Create: `web/components/shared/logo.tsx`
- Create: `web/components/nav/sidebar.tsx`
- Create: `web/components/nav/tab-bar.tsx`
- Create: `web/app/(workspace)/layout.tsx`
- Create: `web/app/(workspace)/page.tsx`

- [ ] **Step 1: Logo**

`web/components/shared/logo.tsx`:

```tsx
export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="h-2 w-2 rounded-full bg-accent" aria-hidden />
      {!collapsed && <span className="text-sm font-bold text-text-1">TradingAgents</span>}
    </div>
  );
}
```

- [ ] **Step 2: Sidebar (데스크톱 전용)**

`web/components/nav/sidebar.tsx`:

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/shared/logo";

type NavItem = { href: string; label: string; icon: string };

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { href: "/", label: "Dashboard", icon: "▦" },
      { href: "/run", label: "Run Analysis", icon: "▶" },
      { href: "/history", label: "History", icon: "▤" },
    ],
  },
  {
    title: "Tracking",
    items: [
      { href: "/portfolio", label: "Portfolio", icon: "◈" },
      { href: "/schedules", label: "Schedules", icon: "◷" },
      { href: "/alerts", label: "Alerts", icon: "⚑" },
    ],
  },
  {
    title: "System",
    items: [{ href: "/settings/llm", label: "Settings", icon: "⚙" }],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:w-[180px] flex-col border-r border-border-1 bg-bg-1 py-4 px-2">
      <div className="pb-4 border-b border-border-1 mb-3">
        <Logo />
      </div>
      <nav className="flex flex-col gap-3">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="px-2 pb-1 text-[10px] uppercase tracking-widest text-text-3">
              {section.title}
            </div>
            <ul className="flex flex-col gap-0.5">
              {section.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs",
                        active
                          ? "bg-bg-2 text-text-1"
                          : "text-text-2 hover:bg-bg-2 hover:text-text-1",
                      )}
                    >
                      <span aria-hidden>{item.icon}</span>
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 3: TabBar (모바일 전용, FAB 포함)**

`web/components/nav/tab-bar.tsx`:

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

type Tab = { href: string; label: string; icon: string };

const TABS: Tab[] = [
  { href: "/", label: "Home", icon: "▦" },
  { href: "/portfolio", label: "Portfolio", icon: "◈" },
  { href: "/run", label: "Run", icon: "+" },
  { href: "/alerts", label: "Alerts", icon: "⚑" },
  { href: "/more", label: "More", icon: "≡" },
];

export function TabBar() {
  const pathname = usePathname();
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-30 grid grid-cols-5 border-t border-border-1 bg-bg-1 pb-[env(safe-area-inset-bottom)]"
      aria-label="Primary"
    >
      {TABS.map((tab, i) => {
        const isFab = i === 2;
        const active =
          tab.href === "/"
            ? pathname === "/"
            : pathname.startsWith(tab.href);

        if (isFab) {
          return (
            <div key={tab.href} className="flex justify-center -mt-5">
              <Link
                href={tab.href}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-white shadow-lg shadow-accent/30 hover:bg-accent/90"
                aria-label={tab.label}
              >
                <span className="text-lg leading-none">{tab.icon}</span>
              </Link>
            </div>
          );
        }
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "flex flex-col items-center gap-0.5 py-2 text-[10px]",
              active ? "text-accent" : "text-text-3",
            )}
          >
            <span className="text-base leading-none" aria-hidden>{tab.icon}</span>
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 4: Workspace layout**

`web/app/(workspace)/layout.tsx`:

```tsx
import { Sidebar } from "@/components/nav/sidebar";
import { TabBar } from "@/components/nav/tab-bar";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-bg-0">
      <Sidebar />
      <main className="flex-1 pb-20 md:pb-0">{children}</main>
      <TabBar />
    </div>
  );
}
```

- [ ] **Step 5: 빈 Dashboard 페이지**

`web/app/(workspace)/page.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">Dashboard</h1>
      <p className="text-xs text-text-3 mb-6">Personal workbench</p>
      <Card>
        <CardHeader>
          <CardTitle>Welcome</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-2">
            M1 foundation is up. Run analysis, history, portfolio, and more arrive in M2+.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: 빌드 + 수동 검증**

Run: `cd web && npm run build && npm run dev`
브라우저 `http://localhost:3000` → `/login`으로 redirect는 다음 Task에서. 지금은 `/`로 가면 Dashboard가 보임. 모바일 너비(<768px)에서 사이드바가 사라지고 탭바가 등장해야 함.
Ctrl+C로 종료.

- [ ] **Step 7: 커밋**

```bash
git add web/components/ web/app/\(workspace\)/
git commit -m "feat(web): add responsive sidebar, mobile tab bar, and workspace shell"
```

---

## Task 18: 보호 라우트 미들웨어

**Files:**
- Create: `web/middleware.ts`

- [ ] **Step 1: 미들웨어 작성**

`web/middleware.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  if (pathname.startsWith("/api") || pathname.startsWith("/_next")) {
    return NextResponse.next();
  }

  const session = request.cookies.get("tradingagents_session");
  if (!session) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    // Run on all paths except static files
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)).*)",
  ],
};
```

- [ ] **Step 2: 수동 검증**

백엔드(`uvicorn tradingagents_web.main:app --port 8000`)와 프런트(`cd web && npm run dev`)를 띄운 다음:

1. 브라우저에서 `http://localhost:3000/` 접속 → `/login`으로 리다이렉트.
2. CLI로 비밀번호 설정: `tradingagents-web set-password` (예: hunter2).
3. 로그인 폼에 hunter2 입력 → Dashboard로 이동.
4. 새 탭에서 `http://localhost:3000/portfolio` → 인증 쿠키가 있으니 워크스페이스 셸이 보임 (404가 나는데 미들웨어는 통과).
5. DevTools에서 `tradingagents_session` 쿠키 삭제 → 새로고침 → `/login`으로 리다이렉트.

- [ ] **Step 3: 커밋**

```bash
git add web/middleware.ts
git commit -m "feat(web): add Next.js middleware to protect workspace routes"
```

---

## Task 19: 프런트엔드 Dockerfile

**Files:**
- Create: `Dockerfile.web`

- [ ] **Step 1: Dockerfile.web 작성**

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs

EXPOSE 3000
CMD ["npm", "run", "start"]
```

- [ ] **Step 2: 빌드 검증**

Run: `docker build -f Dockerfile.web -t tradingagents-web:dev .`
Expected: 빌드 성공.

- [ ] **Step 3: 커밋**

```bash
git add Dockerfile.web
git commit -m "feat(web): add frontend Dockerfile (Next.js standalone build)"
```

---

## Task 20: docker-compose.yml + DEV 가이드

**Files:**
- Modify (or create): `docker-compose.yml`
- Create: `DEV.md`

- [ ] **Step 1: 기존 compose 파일 확인**

Run: `cat docker-compose.yml`

기존이 단일 `tradingagents` 서비스만 있으면 다음으로 교체. 기존 서비스가 있으면 보존하면서 새 두 서비스를 추가.

- [ ] **Step 2: docker-compose.yml 업데이트**

```yaml
services:
  tradingagents:
    build: .
    image: tradingagents:dev
    env_file:
      - .env
    profiles: ["cli"]
    volumes:
      - ~/.tradingagents:/root/.tradingagents

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    image: tradingagents-api:dev
    env_file: .env
    environment:
      WEB_DATABASE_URL: sqlite:////data/tradingagents_web.db
    volumes:
      - tradingagents_data:/data
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 10s
      timeout: 3s
      retries: 5

  web:
    build:
      context: .
      dockerfile: Dockerfile.web
    image: tradingagents-web:dev
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
    ports:
      - "3000:3000"
    depends_on:
      api:
        condition: service_healthy

volumes:
  tradingagents_data:
```

> 기존 `ollama` 프로파일이 있다면 그대로 유지한다.

- [ ] **Step 3: DEV.md 작성**

```markdown
# TradingAgents Web — Local Development

## One-time setup

```bash
# 1. Install Python deps (uv recommended)
uv sync

# 2. Install frontend deps
(cd web && npm install)

# 3. Generate secrets and copy env
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
python -c "import secrets; print('WEB_SESSION_SECRET=' + secrets.token_urlsafe(32))" >> .env
# (Edit .env to remove duplicate ENCRYPTION_KEY/WEB_SESSION_SECRET placeholders.)

# 4. Run migrations + create initial password
alembic upgrade head
tradingagents-web set-password
```

## Run (two terminals)

```bash
# Terminal 1: backend
uvicorn tradingagents_web.main:app --reload --port 8000

# Terminal 2: frontend
cd web && npm run dev
```

Open http://localhost:3000 — you'll be redirected to /login.

## Run via docker-compose

```bash
docker compose up --build api web
```

The api service runs migrations automatically on start. To set the initial password
inside the container:

```bash
docker compose exec api tradingagents-web set-password
```

## Tests

```bash
pytest tests/web/ -v          # backend
cd web && npm run typecheck   # frontend type check
```
```

- [ ] **Step 4: 통합 검증**

Run: `docker compose up --build api web`
다른 터미널에서:

```bash
docker compose exec api tradingagents-web set-password
# 비밀번호 설정 후
curl http://localhost:8000/api/health
# {"status":"ok"}
```

브라우저 `http://localhost:3000` → 로그인 → Dashboard 셸 보임. 모바일/데스크톱 너비 토글 동작 확인.

- [ ] **Step 5: 커밋**

```bash
git add docker-compose.yml DEV.md
git commit -m "feat(web): add docker-compose stack and DEV.md quickstart"
```

---

## Task 21: M1 종합 통합 테스트

**Files:**
- Create: `tests/web/test_integration_m1.py`

- [ ] **Step 1: 통합 테스트 작성**

```python
"""End-to-end backend test simulating the M1 happy path.

Covers: no-user-yet → set-password CLI → login → /me → logout.
"""
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradingagents_web.auth import hash_password
from tradingagents_web.db import get_db
from tradingagents_web.main import create_app
from tradingagents_web.models import Base, User


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    db_file = tmp_path / "m1.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override

    # Seed user (simulating CLI set-password)
    with TestSessionLocal() as db:
        db.add(User(password_hash=hash_password("hunter2")))
        db.commit()

    yield TestClient(app)


def test_m1_happy_path(client: TestClient) -> None:
    # 1. /me before login → 401
    assert client.get("/api/auth/me").status_code == 401

    # 2. Login
    r = client.post("/api/auth/login", json={"password": "hunter2"})
    assert r.status_code == 200

    # 3. /me succeeds
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"id": 1}

    # 4. Logout
    out = client.post("/api/auth/logout")
    assert out.status_code == 200

    # 5. /me again → 401
    assert client.get("/api/auth/me").status_code == 401


def test_m1_invalid_password_returns_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401
```

- [ ] **Step 2: 전체 테스트 실행**

Run: `pytest tests/web/ -v`
Expected: 모든 테스트 PASS (config, db, models, migrations, auth_utils, crypto, cli, session_helpers, health, auth_api, integration_m1).

- [ ] **Step 3: 프런트엔드 타입체크 + 빌드**

Run: `cd web && npm run typecheck && npm run build`
Expected: 둘 다 통과.

- [ ] **Step 4: 커밋 + M1 마무리**

```bash
git add tests/web/test_integration_m1.py
git commit -m "test(web): add M1 happy path integration test"
git tag m1-foundation
```

---

## M1 완료 기준 (Definition of Done)

- [ ] `pytest tests/web/ -v`가 모두 PASS
- [ ] `cd web && npm run typecheck`이 통과
- [ ] `cd web && npm run build`가 통과
- [ ] `docker compose up --build api web` 후 `curl http://localhost:8000/api/health` → `{"status":"ok"}`
- [ ] 브라우저 `http://localhost:3000`에서 로그인 → Dashboard 셸 도달
- [ ] 데스크톱(≥768px)에서 좌측 사이드바, 모바일(<768px)에서 하단 탭바 + 중앙 FAB이 보임
- [ ] 로그아웃 후 보호 라우트 접근 시 `/login`으로 리다이렉트
- [ ] `tradingagents-web set-password`로 비밀번호 변경 가능

---

## Spec Coverage Check

| Spec 섹션 | 다루는 Task |
|---|---|
| §5.2 백엔드 모듈 (auth, db, services/crypto, models, api) | T1, T3, T4, T7, T9, T10, T11 |
| §5.3 프런트엔드 모듈 (app/(auth), app/(workspace), components/{ui,nav}, lib) | T13, T14, T15, T16, T17 |
| §6 데이터 모델 (users, sessions) | T4, T5 |
| §7 인증 (bcrypt, 세션 쿠키, samesite=strict, httponly) | T6, T9, T11 |
| §7 보안 (Fernet 암호화 — M2에서 사용 시작) | T7 |
| §4 디자인 토큰 + 폰트 + 시그널 색 | T13, T14 |
| §3.1 사이드바 ↔ 탭바 매핑 | T17 |
| §11 마일스톤 M1 | 전체 플랜 |

다음 플랜에서 다룰 것 (out of scope):
- M2: `analyses` 모델, `/run`, SSE 스트림, 히스토리 화면
- M3: `holdings`, `schedules`, APScheduler
- M4: `alerts`, Telegram notifier
- M5: PWA, 비교 뷰, 백업/복원, 모바일 폴리싱
