# TradingAgents Web — M5 Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** M1–M4로 완성된 워크벤치에 폴리싱 마일스톤을 입힌다 — (1) PWA(manifest + service worker)로 모바일 홈 화면 설치를 지원하고, (2) 모바일 More 라우트 신설 등 잔여 모바일 UX 누락을 메우고, (3) `/history/compare?ids=a,b` 좌우 분할 비교 뷰를 추가하고, (4) `/settings/account`에서 비밀번호 변경·세션 회수·데이터베이스 백업/복원을 사용자가 직접 수행할 수 있게 한다.

**Architecture:**
- **PWA**: `next-pwa` 같은 의존을 추가하지 않는다. `web/public/manifest.json`과 직접 작성한 `web/public/sw.js`를 두고 root layout에서 `<link rel="manifest">` + 클라이언트 컴포넌트에서 `navigator.serviceWorker.register('/sw.js')`를 호출한다. 캐시 전략은 spec §12 마지막 항목을 따른다 — `/api/*`는 network-first(실패 시 캐시 폴백 없음, 그냥 오류), 정적 자산(`/_next/static/*`, manifest, 아이콘)은 cache-first, HTML 라우트는 network-first에 오프라인 시 `/_offline` 정적 페이지 폴백.
- **Compare 뷰**: 신규 클라이언트 라우트 `/history/compare?ids=a,b`. 두 분석 ID를 받아 기존 `useRun(id)` 훅으로 병렬 fetch하고, 데스크톱은 `grid-cols-2`로 동일 컴포넌트(VerdictCard, 보고서 카드들)를 반복 렌더, 모바일은 단일 컬럼 + 상단 탭(`A | B`)으로 전환. History 페이지에서는 행마다 체크박스를 추가하고 "Compare (n/2)" 버튼이 정확히 2개 선택 시에만 활성화된다.
- **Backup/Restore + Account**: 신규 `tradingagents_web/api/account.py` 라우터(`/api/settings/account`)와 신규 `services/db_admin.py`(데이터 파일 경로/스키마 검증/엔진 재시작 헬퍼). 백업은 `PRAGMA wal_checkpoint(TRUNCATE)`로 WAL을 머지한 뒤 `FileResponse`로 SQLite 파일을 스트리밍한다. 복원은 multipart 업로드를 staging 경로(`<data_dir>/restore.staging.db`)에 저장 → SQLite 매직 헤더(`SQLite format 3\x00`) 및 `PRAGMA integrity_check` + `users` 테이블 존재 확인 → `services.scheduler.get_scheduler().shutdown()` → `engine.dispose()` → WAL/SHM 동반 파일 삭제 후 `shutil.move(staging, data.db)` → `engine.dispose()` 한 번 더(확실히) → `auto_runner` 통해 `SchedulerService` 재기동 + `bootstrap`. 패스워드 변경은 단일 `User` 행을 갱신하고 다른 모든 `Session` 행을 삭제(현재 세션은 새 토큰으로 재발급). 세션 목록은 `Session` 테이블을 그대로 노출(현재 토큰 마스킹).
- **Mobile polish**: tab-bar의 `/more` 링크는 현재 라우트가 없어 404 — 신규 `app/(workspace)/more/page.tsx`로 History/Schedules/Settings/Logout 메뉴 카드 리스트를 만든다. 그 외 history-table, settings-layout 등 사이드 영역에 누락된 sub-link(Account)도 함께 보강한다.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, alembic은 이번엔 무변경(스키마 추가 없음). `python-multipart`(이미 FastAPI 의존), `bcrypt`(이미 사용). 프런트는 신규 라이브러리 없이 Next.js 14 App Router + 기존 TanStack Query/Tailwind만 사용. Service Worker는 vanilla JS(워크박스 미사용).

**Spec:** [docs/superpowers/specs/2026-04-25-tradingagents-web-design.md](../specs/2026-04-25-tradingagents-web-design.md) — §2 S2/S5, §3(`/history/compare`, `/more` mapping, `/settings/account`), §4.3 History Compare, §4.4 반응형, §6.3 백업, §11 M5, §12 마지막 항목

**Out of scope (의도적 제외):**
- LLM/Data 설정 UI(`/settings/llm`, `/settings/data`) — spec §3에 있으나 본 마일스톤에서는 명시 제외(추후 별도 플랜).
- 푸시 알림(Web Push API) — Telegram이 모바일 푸시 채널을 이미 담당.
- iOS Safari `apple-touch-icon` 외 다중 아이콘 사이즈 모두 — 192/512px PNG 두 장으로 시작.
- Recharts 모바일 인터랙션 폴리싱(zoom/pan) — 별도 작업.

**의존 결정 (open issues §14에 영향):**

1. **Restore 동작 범위** → 같은 호스트의 SQLite 파일 교체만 지원. Postgres 등 외부 DB는 `database_url`이 sqlite로 시작할 때만 endpoint를 활성화(아니면 `409 Conflict` + "supported only for SQLite"). 첫 사용자 시나리오 단순화.
2. **Restore 시 스케줄러/엔진 핫스왑** → `scheduler_module.get_scheduler().shutdown(wait=True)` → `engine.dispose()` → 파일 교체 → 새 `SchedulerService` 인스턴스 재기동 + `bootstrap`. 워커가 한창 실행 중인 분석은 `wait=True`가 끝까지 기다리고, 그 사이 도착한 HTTP 요청은 503으로 단 한 번만 회신("restoring database, retry in a moment")하기 위해 모듈 레벨 `_RESTORE_LOCK = asyncio.Lock()` + 가드 미들웨어를 둔다.
3. **Backup 파일명** → `tradingagents-backup-YYYYMMDD-HHMMSS.db` 자동 생성. `Content-Disposition: attachment; filename=...`.
4. **PWA 매니페스트 색상** → `theme_color = "#0a0a0b"` (디자인 토큰 `--bg-0`), `background_color = "#0a0a0b"`, `display = "standalone"`, `start_url = "/"`, `scope = "/"`, `name = "TradingAgents"`, `short_name = "TA"`.
5. **Service Worker 캐시 버전** → `CACHE_NAME = "ta-v1"`. 파일 상단 상수만 올리면 다음 배포에서 강제 무효화. SW는 `/_offline.html`(서버사이드 정적) + `/manifest.json` + `/icons/*`만 install 시점에 미리 캐시(precache).
6. **Account 페이지 모바일 진입점** → `/more`에서 "Account" 메뉴 선택 시 `/settings/account`로 진입. 데스크톱은 settings 사이드바에 "Account" 항목 추가.
7. **세션 회수 UI** → 행별 "Revoke" 버튼은 현재 세션 외 모두 표시. 비밀번호 변경 시 자동으로 다른 세션을 모두 삭제(체크박스로 끌 수 있음, 기본 ON).
8. **Compare 검증** → 두 ID가 모두 존재하지 않으면 404. 동일 ID 두 번이면 400. 두 분석의 status가 모두 `completed`가 아니어도 렌더는 가능(에러/실행중 메시지를 양쪽 컬럼에 노출).

---

## File Structure

신규 백엔드:

```
tradingagents_web/
├── api/
│   └── account.py                  # GET backup / POST restore / PUT password / GET sessions / POST sessions/revoke-others
├── schemas/
│   └── account.py                  # PasswordChangeRequest, SessionItem, RestoreResponse, ...
└── services/
    └── db_admin.py                 # validate_sqlite(path), swap_database(path), backup_to_response(...)

tests/web/
├── test_account_api.py             # endpoint 단위 테스트(백업/복원/패스워드/세션)
├── test_db_admin.py                # validate_sqlite, swap_database 단위 테스트
└── test_integration_m5.py          # 백업 → 복원 라운드트립
```

신규/변경 프런트엔드:

```
web/
├── public/
│   ├── manifest.json               # PWA 매니페스트
│   ├── sw.js                       # Service Worker
│   ├── _offline.html               # 오프라인 폴백 정적 페이지
│   └── icons/
│       ├── icon-192.png            # 192x192 (placeholder asset, 추후 디자인 교체)
│       └── icon-512.png            # 512x512
├── app/
│   ├── layout.tsx                  # MODIFY — manifest 링크 + theme-color meta + SW 등록 컴포넌트 마운트
│   ├── (workspace)/
│   │   ├── more/page.tsx           # NEW — 모바일 More 페이지
│   │   ├── history/
│   │   │   └── compare/page.tsx    # NEW — 좌우 비교 뷰
│   │   └── settings/
│   │       ├── layout.tsx          # MODIFY — Account 항목 추가
│   │       └── account/page.tsx    # NEW — 비밀번호/백업/복원/세션
├── components/
│   ├── settings/
│   │   ├── account-password-form.tsx   # NEW
│   │   ├── account-backup-button.tsx   # NEW
│   │   ├── account-restore-form.tsx    # NEW
│   │   └── account-sessions-list.tsx   # NEW
│   ├── history/
│   │   ├── history-table.tsx           # MODIFY — checkbox 컬럼 + 선택 상태 prop
│   │   └── compare-toolbar.tsx         # NEW — 선택 카운트 + Compare 버튼
│   ├── shared/
│   │   └── service-worker-registrar.tsx # NEW — `useEffect` 등록 클라이언트 컴포넌트
│   └── nav/
│       ├── tab-bar.tsx                 # MODIFY — `/more` 라벨 활성 강조 처리
│       └── sidebar.tsx                 # MODIFY — Settings 메뉴 (Notifications + Account) 펼침
├── hooks/
│   └── use-account.ts                  # NEW — 비밀번호/세션/복원 mutations + 세션 query
└── lib/
    └── account.ts                      # NEW — fetch 래퍼들
```

---

## Task 0: Worktree 진입과 출발점 검증

**Files:**
- Read-only: `pyproject.toml`, `web/package.json`, `tradingagents_web/main.py`

- [ ] **Step 1: 현재 main 브랜치가 깨끗한지 확인**

Run: `git status`
Expected: `working tree clean`(또는 `web/tsconfig.tsbuildinfo` 같은 ignored-by-policy 파일만)

- [ ] **Step 2: 새 작업 브랜치 생성**

Run:
```bash
git checkout -b feat/web-m5-polish
```
Expected: `Switched to a new branch 'feat/web-m5-polish'`

- [ ] **Step 3: 백엔드/프런트엔드 테스트 베이스라인이 그린인지 확인**

Run:
```bash
uv run pytest tests/web/ -q
```
Expected: 모든 테스트 통과(M4까지). 실패가 있으면 먼저 그 원인을 픽스 후 진행.

```bash
cd web && npm run typecheck
```
Expected: `tsc --noEmit` 통과.

- [ ] **Step 4: 진행 시작 커밋(빈 커밋 금지 — Step 5에서 진행)**

이 단계는 노옵. 다음 태스크부터 단위별 커밋.

---

## Task 1: `services/db_admin.py` — SQLite 검증/스왑 헬퍼

이 헬퍼는 백업·복원 endpoint의 핵심이다. SQLite 매직 헤더 검증, integrity check, 엔진 dispose + 파일 스왑 로직을 한 모듈에 모아 endpoint를 얇게 유지한다.

**Files:**
- Create: `tradingagents_web/services/db_admin.py`
- Test: `tests/web/test_db_admin.py`

- [ ] **Step 1: 실패하는 테스트 작성 — 매직 헤더 검증**

Create `tests/web/test_db_admin.py`:
```python
"""Unit tests for services.db_admin."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tradingagents_web.services import db_admin


def _make_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, password_hash TEXT)")
    conn.commit()
    conn.close()


def test_validate_sqlite_accepts_real_db(tmp_path: Path) -> None:
    db = tmp_path / "ok.db"
    _make_sqlite(db)
    db_admin.validate_sqlite(db, required_tables=("users",))


def test_validate_sqlite_rejects_random_file(tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a sqlite file at all")
    with pytest.raises(db_admin.DatabaseValidationError):
        db_admin.validate_sqlite(junk, required_tables=("users",))


def test_validate_sqlite_rejects_missing_table(tmp_path: Path) -> None:
    db = tmp_path / "incomplete.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    with pytest.raises(db_admin.DatabaseValidationError, match="users"):
        db_admin.validate_sqlite(db, required_tables=("users",))


def test_validate_sqlite_rejects_corrupt_db(tmp_path: Path) -> None:
    db = tmp_path / "broken.db"
    _make_sqlite(db)
    # Truncate to corrupt: keep header bytes but trash the rest
    raw = db.read_bytes()
    db.write_bytes(raw[:32] + b"\x00" * (len(raw) - 32))
    with pytest.raises(db_admin.DatabaseValidationError):
        db_admin.validate_sqlite(db, required_tables=("users",))
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run:
```bash
uv run pytest tests/web/test_db_admin.py -q
```
Expected: `ModuleNotFoundError: No module named 'tradingagents_web.services.db_admin'` 등으로 FAIL.

- [ ] **Step 3: 최소 구현 — `validate_sqlite`만**

Create `tradingagents_web/services/db_admin.py`:
```python
"""Backup/restore + DB hot-swap helpers for the SQLite data file."""
from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterable
from pathlib import Path

SQLITE_MAGIC = b"SQLite format 3\x00"


class DatabaseValidationError(ValueError):
    """Raised when a file cannot be accepted as a TradingAgents Web database."""


def validate_sqlite(path: Path, *, required_tables: Iterable[str]) -> None:
    """Verify that *path* is a SQLite 3 file with the expected schema."""
    if not path.exists() or path.stat().st_size < len(SQLITE_MAGIC):
        raise DatabaseValidationError("file does not exist or is too small")
    with path.open("rb") as fh:
        if fh.read(len(SQLITE_MAGIC)) != SQLITE_MAGIC:
            raise DatabaseValidationError("not a SQLite 3 database (magic header mismatch)")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise DatabaseValidationError(f"cannot open as SQLite: {exc}") from exc
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            raise DatabaseValidationError(f"integrity_check failed: {row[0] if row else 'no result'}")
        existing = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        for table in required_tables:
            if table not in existing:
                raise DatabaseValidationError(f"required table missing: {table}")
    finally:
        conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run:
```bash
uv run pytest tests/web/test_db_admin.py -q
```
Expected: 4 passed.

- [ ] **Step 5: `swap_database` 테스트 추가(파일 교체만, 엔진 통합은 다음 태스크에서)**

Append to `tests/web/test_db_admin.py`:
```python
def test_swap_database_replaces_target_file_atomically(tmp_path: Path) -> None:
    target = tmp_path / "live.db"
    staging = tmp_path / "incoming.db"
    target.write_bytes(b"old")
    staging.write_bytes(b"new")
    sidecars = [target.with_suffix(".db-wal"), target.with_suffix(".db-shm")]
    for s in sidecars:
        s.write_bytes(b"sidecar")

    db_admin.swap_database(target, staging)

    assert target.read_bytes() == b"new"
    assert not staging.exists()
    for s in sidecars:
        assert not s.exists(), f"WAL/SHM sidecar should be removed: {s}"
```

- [ ] **Step 6: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/web/test_db_admin.py::test_swap_database_replaces_target_file_atomically -q`
Expected: `AttributeError: module ... has no attribute 'swap_database'`.

- [ ] **Step 7: `swap_database` 구현**

Append to `tradingagents_web/services/db_admin.py`:
```python
def swap_database(target: Path, staging: Path) -> None:
    """Replace *target* with *staging* and remove WAL/SHM sidecars.

    Caller is responsible for disposing the SQLAlchemy engine and stopping any
    workers that hold connections BEFORE calling this — otherwise replacing the
    file underneath open handles produces undefined behaviour on macOS/Linux.
    """
    if not staging.exists():
        raise FileNotFoundError(f"staging file missing: {staging}")
    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        sidecar = target.with_name(target.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
    # shutil.move is atomic on the same filesystem (rename(2)), copy+delete otherwise.
    shutil.move(str(staging), str(target))
```

- [ ] **Step 8: 테스트 통과**

Run: `uv run pytest tests/web/test_db_admin.py -q`
Expected: 5 passed.

- [ ] **Step 9: 커밋**

```bash
git add tradingagents_web/services/db_admin.py tests/web/test_db_admin.py
git commit -m "feat(web/m5): add db_admin helper for SQLite validate + swap"
```

---

## Task 2: Backup endpoint — `GET /api/settings/account/backup`

**Files:**
- Create: `tradingagents_web/api/account.py`
- Create: `tradingagents_web/schemas/account.py`
- Modify: `tradingagents_web/main.py`(라우터 include)
- Test: `tests/web/test_account_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/web/test_account_api.py`:
```python
"""Account API: backup, restore, password change, sessions."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient


def test_backup_returns_sqlite_attachment(client_with_user: TestClient) -> None:
    auth = client_with_user
    r = auth.get("/api/settings/account/backup")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/octet-stream") or \
        r.headers["content-type"] == "application/vnd.sqlite3"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and ".db" in cd
    body = r.content
    assert body.startswith(b"SQLite format 3\x00"), "should be a real SQLite file"


def test_backup_requires_auth(client: TestClient) -> None:
    r = client.get("/api/settings/account/backup")
    assert r.status_code == 401
```

(Fixtures `client`, `client_with_user` already exist in `tests/web/conftest.py`.)

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 404 (라우트 없음) 으로 FAIL.

- [ ] **Step 3: 스키마 모듈 작성**

Create `tradingagents_web/schemas/account.py`:
```python
"""Pydantic schemas for the account API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, SecretStr


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=8)
    revoke_other_sessions: bool = True


class PasswordChangeResponse(BaseModel):
    ok: bool


class SessionItem(BaseModel):
    id_masked: str
    expires_at: datetime
    is_current: bool


class SessionListResponse(BaseModel):
    sessions: list[SessionItem]


class RestoreResponse(BaseModel):
    ok: bool
    detail: str | None = None
```

- [ ] **Step 4: 라우터 모듈 작성(backup만 우선)**

Create `tradingagents_web/api/account.py`:
```python
"""Account/settings API: backup, restore, password, sessions."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user
from tradingagents_web.config import Settings
from tradingagents_web.db import engine, get_db
from tradingagents_web.models import User

router = APIRouter(prefix="/api/settings/account", tags=["account"])
_settings = Settings()


def _resolve_sqlite_path() -> Path:
    """Return the on-disk path of the SQLite file from the engine URL."""
    url = engine.url
    if url.drivername.split("+")[0] != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Backup/restore only supported on SQLite deployments.",
        )
    db = url.database or ""
    if not db or db == ":memory:":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No on-disk database file to back up.",
        )
    return Path(db).resolve()


@router.get("/backup")
def backup_database(
    _user: Annotated[User, Depends(get_current_user)],
    _db: Annotated[OrmSession, Depends(get_db)],
) -> FileResponse:
    """Return the live SQLite file as an attachment, after merging the WAL."""
    path = _resolve_sqlite_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")

    # Flush WAL into the main file so the download captures latest committed state.
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"tradingagents-backup-{stamp}.db"
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=filename,
    )
```

- [ ] **Step 5: `main.py`에 라우터 include**

Edit `tradingagents_web/main.py`:
```python
# imports 블록에 추가
from tradingagents_web.api import account as account_api
```
그리고 `create_app` 안 라우터 등록 부분에 추가:
```python
    app.include_router(account_api.router)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 2 passed.

- [ ] **Step 7: 커밋**

```bash
git add tradingagents_web/api/account.py tradingagents_web/schemas/account.py tradingagents_web/main.py tests/web/test_account_api.py
git commit -m "feat(web/m5): GET /api/settings/account/backup downloads SQLite file"
```

---

## Task 3: Password change endpoint — `PUT /api/settings/account/password`

**Files:**
- Modify: `tradingagents_web/api/account.py`
- Test: `tests/web/test_account_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Append to `tests/web/test_account_api.py`:
```python
def test_password_change_requires_correct_current(client_with_user: TestClient) -> None:
    r = client_with_user.put(
        "/api/settings/account/password",
        json={"current_password": "wrong", "new_password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 401


def test_password_change_updates_hash_and_revokes_other_sessions(
    client_with_user: TestClient, fresh_session_factory
) -> None:
    # Create a second session for the same user (simulating another device)
    other_token = fresh_session_factory()
    r = client_with_user.put(
        "/api/settings/account/password",
        json={
            "current_password": "testpass",
            "new_password": "newpass1234",
            "revoke_other_sessions": True,
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    # The other session should now be invalid
    r2 = client_with_user.get(
        "/api/auth/me",
        cookies={"tradingagents_session": other_token},
    )
    assert r2.status_code == 401


def test_password_change_rejects_short_password(client_with_user: TestClient) -> None:
    r = client_with_user.put(
        "/api/settings/account/password",
        json={"current_password": "testpass", "new_password": "short"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: conftest fixture 추가 — `fresh_session_factory`**

Edit `tests/web/conftest.py`. 기존 `client_with_user` fixture가 이미 사용자 1명을 만들고 세션을 들고 있다. 두 번째 세션을 만들 수 있는 팩토리를 추가.

먼저 현재 conftest.py 형태를 확인 후, 다음 fixture를 추가(이미 같은 패턴이 있을 가능성 — `Read` 후 동일 스타일로 작성):

```python
@pytest.fixture
def fresh_session_factory(db_session, test_user):
    """Return a callable that creates an extra Session row and returns its token."""
    from tradingagents_web.auth import create_session

    def _make() -> str:
        return create_session(db_session, test_user.id)
    return _make
```

(이미 `db_session` / `test_user` fixture가 있다고 가정. 없으면 동일 패턴으로 inline 생성하도록 fixture를 조정.)

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 신규 3개 FAIL (404).

- [ ] **Step 4: endpoint 구현**

Append to `tradingagents_web/api/account.py`:
```python
from tradingagents_web.auth import (
    create_session,
    delete_session,
    hash_password,
    require_xhr,
    verify_password,
)
from tradingagents_web.models import Session as SessionModel
from tradingagents_web.schemas.account import (
    PasswordChangeRequest,
    PasswordChangeResponse,
)


@router.put("/password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    db: Annotated[OrmSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> PasswordChangeResponse:
    if not verify_password(payload.current_password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password.get_secret_value())
    if payload.revoke_other_sessions:
        current_token = request.cookies.get(_settings.session_cookie_name)
        q = db.query(SessionModel).filter_by(user_id=user.id)
        if current_token:
            q = q.filter(SessionModel.id != current_token)
        q.delete(synchronize_session=False)
    db.commit()
    return PasswordChangeResponse(ok=True)
```

또한 `from fastapi import ... Request, Response` import를 보강.

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 5 passed.

- [ ] **Step 6: 커밋**

```bash
git add tradingagents_web/api/account.py tests/web/test_account_api.py tests/web/conftest.py
git commit -m "feat(web/m5): PUT /api/settings/account/password change + session revoke"
```

---

## Task 4: Sessions list + revoke-others endpoints

**Files:**
- Modify: `tradingagents_web/api/account.py`
- Test: `tests/web/test_account_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Append to `tests/web/test_account_api.py`:
```python
def test_sessions_list_marks_current(client_with_user: TestClient, fresh_session_factory) -> None:
    fresh_session_factory()  # one extra
    r = client_with_user.get("/api/settings/account/sessions")
    assert r.status_code == 200
    body = r.json()
    sessions = body["sessions"]
    assert len(sessions) >= 2
    current = [s for s in sessions if s["is_current"]]
    assert len(current) == 1
    for s in sessions:
        assert "id_masked" in s
        assert len(s["id_masked"]) <= 12  # masked, not full token


def test_sessions_revoke_others_keeps_current(
    client_with_user: TestClient, fresh_session_factory
) -> None:
    other = fresh_session_factory()
    r = client_with_user.post(
        "/api/settings/account/sessions/revoke-others",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    # current still works
    me = client_with_user.get("/api/auth/me")
    assert me.status_code == 200
    # the other session is gone
    me2 = client_with_user.get(
        "/api/auth/me", cookies={"tradingagents_session": other}
    )
    assert me2.status_code == 401
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 신규 2개 FAIL.

- [ ] **Step 3: endpoint 구현**

Append to `tradingagents_web/api/account.py`:
```python
from tradingagents_web.schemas.account import SessionItem, SessionListResponse


def _mask(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}…{token[-4:]}"


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SessionListResponse:
    current_token = request.cookies.get(_settings.session_cookie_name) or ""
    rows = (
        db.query(SessionModel)
        .filter_by(user_id=user.id)
        .order_by(SessionModel.expires_at.desc())
        .all()
    )
    items = [
        SessionItem(
            id_masked=_mask(s.id),
            expires_at=s.expires_at,
            is_current=(s.id == current_token),
        )
        for s in rows
    ]
    return SessionListResponse(sessions=items)


@router.post("/sessions/revoke-others", response_model=PasswordChangeResponse)
def revoke_other_sessions(
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> PasswordChangeResponse:
    current_token = request.cookies.get(_settings.session_cookie_name) or ""
    db.query(SessionModel).filter(
        SessionModel.user_id == user.id,
        SessionModel.id != current_token,
    ).delete(synchronize_session=False)
    db.commit()
    return PasswordChangeResponse(ok=True)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 7 passed.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/api/account.py tests/web/test_account_api.py
git commit -m "feat(web/m5): list + revoke account sessions"
```

---

## Task 5: Restore endpoint — `POST /api/settings/account/restore`

이 endpoint는 위험도가 가장 높다. 업로드된 SQLite 파일을 staging 경로에 저장 → 검증 → 스케줄러 종료 → 엔진 dispose → 파일 교체 → 스케줄러 재기동 → 응답.

**Files:**
- Modify: `tradingagents_web/api/account.py`
- Modify: `tradingagents_web/services/db_admin.py`(restore 오케스트레이터 헬퍼)
- Test: `tests/web/test_db_admin.py`, `tests/web/test_account_api.py`

- [ ] **Step 1: db_admin에 오케스트레이터 헬퍼 테스트 추가**

Append to `tests/web/test_db_admin.py`:
```python
def test_run_restore_replaces_db_and_calls_scheduler_hooks(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "live.db"
    _make_sqlite(target)
    # add a sentinel value so we can prove the file was replaced
    conn = sqlite3.connect(target)
    conn.execute("INSERT INTO users(id, password_hash) VALUES (1, 'OLD')")
    conn.commit()
    conn.close()

    staging = tmp_path / "staging.db"
    _make_sqlite(staging)
    conn = sqlite3.connect(staging)
    conn.execute("INSERT INTO users(id, password_hash) VALUES (1, 'NEW')")
    conn.commit()
    conn.close()

    calls: list[str] = []
    db_admin.run_restore(
        target=target,
        staging=staging,
        required_tables=("users",),
        stop_workers=lambda: calls.append("stop"),
        dispose_engine=lambda: calls.append("dispose"),
        start_workers=lambda: calls.append("start"),
    )

    assert calls == ["stop", "dispose", "start"]
    conn = sqlite3.connect(target)
    row = conn.execute("SELECT password_hash FROM users WHERE id=1").fetchone()
    conn.close()
    assert row[0] == "NEW"
```

- [ ] **Step 2: 실행 → 실패 확인**

Run: `uv run pytest tests/web/test_db_admin.py -q`
Expected: AttributeError.

- [ ] **Step 3: 헬퍼 구현**

Append to `tradingagents_web/services/db_admin.py`:
```python
from collections.abc import Callable


def run_restore(
    *,
    target: Path,
    staging: Path,
    required_tables: Iterable[str],
    stop_workers: Callable[[], None],
    dispose_engine: Callable[[], None],
    start_workers: Callable[[], None],
) -> None:
    """Validate, stop, swap, restart — atomic-ish restore orchestration."""
    validate_sqlite(staging, required_tables=required_tables)
    stop_workers()
    try:
        dispose_engine()
        swap_database(target, staging)
    finally:
        # Always try to bring workers back up, even if swap failed midway —
        # the engine still points at the original path.
        start_workers()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_db_admin.py -q`
Expected: 6 passed.

- [ ] **Step 5: API endpoint 테스트 작성**

Append to `tests/web/test_account_api.py`:
```python
def test_restore_replaces_database_with_uploaded_file(
    client_with_user: TestClient, tmp_path: Path
) -> None:
    # Build a valid replacement DB containing a different password_hash for user 1.
    new_db = tmp_path / "incoming.db"
    conn = sqlite3.connect(new_db)
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, password_hash TEXT, created_at TEXT);
        INSERT INTO users(id, password_hash, created_at) VALUES (1, 'restored-hash', '2026-04-26T00:00:00');
        CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT, created_at TEXT);
        """
    )
    conn.commit()
    conn.close()

    with new_db.open("rb") as fh:
        r = client_with_user.post(
            "/api/settings/account/restore",
            files={"file": ("backup.db", fh, "application/octet-stream")},
            headers={"X-Requested-With": "fetch"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True

    # Old session token should no longer authenticate (we replaced sessions).
    me = client_with_user.get("/api/auth/me")
    assert me.status_code == 401


def test_restore_rejects_invalid_file(client_with_user: TestClient) -> None:
    r = client_with_user.post(
        "/api/settings/account/restore",
        files={"file": ("bad.db", b"not a sqlite file", "application/octet-stream")},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 400
    assert "SQLite" in r.json()["detail"] or "magic" in r.json()["detail"].lower()
```

- [ ] **Step 6: endpoint 구현**

Append to `tradingagents_web/api/account.py`:
```python
import shutil

from fastapi import File, UploadFile

from tradingagents_web.services import db_admin
from tradingagents_web.services import scheduler as scheduler_module
from tradingagents_web.services import auto_runner
from tradingagents_web.config import Settings as _SettingsType  # avoid shadow
from tradingagents_web.db import engine as _engine

REQUIRED_TABLES = ("users", "sessions", "analyses", "holdings", "schedules", "alerts", "settings")


@router.post("/restore", response_model=RestoreResponse)
def restore_database(
    file: Annotated[UploadFile, File(...)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> RestoreResponse:
    target = _resolve_sqlite_path()
    staging = target.with_name("restore.staging.db")
    try:
        with staging.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()

    def _stop() -> None:
        svc = scheduler_module.get_scheduler()
        if svc is not None:
            svc.shutdown()
            scheduler_module.set_scheduler(None)

    def _dispose() -> None:
        _engine.dispose()

    def _start() -> None:
        settings = _SettingsType()
        from tradingagents_web.services.scheduler import SchedulerService
        from tradingagents_web.db import SessionLocal

        svc = SchedulerService(
            tz=settings.schedule_tz,
            grace_seconds=settings.scheduler_grace_seconds,
        )
        svc.set_trigger_callback(auto_runner.trigger_run)
        scheduler_module.set_scheduler(svc)
        svc.start()
        db = SessionLocal()
        try:
            svc.bootstrap(db)
        finally:
            db.close()

    try:
        db_admin.run_restore(
            target=target,
            staging=staging,
            required_tables=REQUIRED_TABLES,
            stop_workers=_stop,
            dispose_engine=_dispose,
            start_workers=_start,
        )
    except db_admin.DatabaseValidationError as exc:
        if staging.exists():
            staging.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RestoreResponse(ok=True, detail="Database restored. All sessions revoked.")
```

`from fastapi import ... File, UploadFile` import 추가.

- [ ] **Step 7: 테스트 통과 확인**

Run: `uv run pytest tests/web/test_account_api.py -q`
Expected: 9 passed.

- [ ] **Step 8: 커밋**

```bash
git add tradingagents_web/services/db_admin.py tradingagents_web/api/account.py tests/web/test_db_admin.py tests/web/test_account_api.py
git commit -m "feat(web/m5): POST /api/settings/account/restore swaps SQLite file with engine reset"
```

---

## Task 6: M5 통합 테스트 — 백업 → 복원 라운드트립

**Files:**
- Create: `tests/web/test_integration_m5.py`

- [ ] **Step 1: 통합 테스트 작성**

Create `tests/web/test_integration_m5.py`:
```python
"""End-to-end: download backup → restore it and verify state survives."""
from __future__ import annotations

import io


def test_backup_then_restore_roundtrip(client_with_user) -> None:
    # Step A: backup
    r = client_with_user.get("/api/settings/account/backup")
    assert r.status_code == 200
    blob = r.content
    assert blob.startswith(b"SQLite format 3\x00")

    # Step B: change something so restore is observable
    r = client_with_user.put(
        "/api/settings/account/password",
        json={
            "current_password": "testpass",
            "new_password": "newpass1234",
            "revoke_other_sessions": False,
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200

    # New password works
    r = client_with_user.post(
        "/api/auth/login",
        json={"password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200

    # Step C: restore the original
    r = client_with_user.post(
        "/api/settings/account/restore",
        files={"file": ("backup.db", io.BytesIO(blob), "application/octet-stream")},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200, r.text

    # Old password should work again, new one should fail
    r = client_with_user.post(
        "/api/auth/login",
        json={"password": "testpass"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    r = client_with_user.post(
        "/api/auth/login",
        json={"password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 401
```

- [ ] **Step 2: 실행해 통과 확인**

Run: `uv run pytest tests/web/test_integration_m5.py -q`
Expected: 1 passed. 만약 fixture 충돌(테스트 사이에 SchedulerService 잔존)로 실패하면 conftest의 scheduler fixture를 함수 스코프로 격리.

- [ ] **Step 3: 전체 테스트 그린 확인**

Run: `uv run pytest tests/web/ -q`
Expected: 모든 테스트 통과.

- [ ] **Step 4: 커밋**

```bash
git add tests/web/test_integration_m5.py
git commit -m "test(web/m5): backup→restore roundtrip integration"
```

---

## Task 7: 프런트엔드 lib + hooks — `account.ts`, `use-account.ts`

**Files:**
- Create: `web/lib/account.ts`
- Create: `web/hooks/use-account.ts`

- [ ] **Step 1: API 래퍼 작성**

Create `web/lib/account.ts`:
```typescript
import { apiFetch } from "@/lib/api";

export type SessionItem = {
  id_masked: string;
  expires_at: string;
  is_current: boolean;
};

export async function listSessions(): Promise<SessionItem[]> {
  const data = await apiFetch<{ sessions: SessionItem[] }>("/api/settings/account/sessions");
  return data.sessions;
}

export async function changePassword(input: {
  current_password: string;
  new_password: string;
  revoke_other_sessions: boolean;
}): Promise<void> {
  await apiFetch("/api/settings/account/password", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function revokeOtherSessions(): Promise<void> {
  await apiFetch("/api/settings/account/sessions/revoke-others", { method: "POST" });
}

export async function uploadRestore(file: File): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  await apiFetch("/api/settings/account/restore", {
    method: "POST",
    body: fd,
    // apiFetch must NOT set Content-Type when body is FormData; ensure it skips that header.
  });
}

export function backupDownloadUrl(): string {
  return "/api/settings/account/backup";
}
```

(만약 `lib/api.ts`의 `apiFetch`가 항상 `Content-Type: application/json`을 강제하면 FormData 분기를 추가해야 한다. 다음 단계에서 그 코드를 확인 후 보강.)

- [ ] **Step 2: lib/api.ts FormData 분기 점검**

Read `web/lib/api.ts`. 만약 헤더 설정이 `Content-Type: application/json`을 무조건 셋팅하고 있다면, body가 FormData일 때는 그 헤더를 셋팅하지 않도록 수정한다 (브라우저가 multipart boundary 자동 생성을 하도록). 동시에 X-Requested-With: fetch 헤더는 유지.

- [ ] **Step 3: TanStack Query 훅 작성**

Create `web/hooks/use-account.ts`:
```typescript
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  changePassword,
  listSessions,
  revokeOtherSessions,
  uploadRestore,
} from "@/lib/account";

export function useSessions() {
  return useQuery({
    queryKey: ["account", "sessions"],
    queryFn: listSessions,
    staleTime: 5_000,
  });
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: changePassword,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["account"] }),
  });
}

export function useRevokeOtherSessions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: revokeOtherSessions,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["account", "sessions"] }),
  });
}

export function useRestore() {
  return useMutation({ mutationFn: uploadRestore });
}
```

- [ ] **Step 4: TypeScript 컴파일 확인**

Run: `cd web && npm run typecheck`
Expected: clean.

- [ ] **Step 5: 커밋**

```bash
git add web/lib/account.ts web/hooks/use-account.ts web/lib/api.ts
git commit -m "feat(web/m5): account API client + TanStack Query hooks"
```

---

## Task 8: `/settings/account` 페이지 + 컴포넌트

**Files:**
- Create: `web/app/(workspace)/settings/account/page.tsx`
- Create: `web/components/settings/account-password-form.tsx`
- Create: `web/components/settings/account-backup-button.tsx`
- Create: `web/components/settings/account-restore-form.tsx`
- Create: `web/components/settings/account-sessions-list.tsx`
- Modify: `web/app/(workspace)/settings/layout.tsx`(Account 항목 추가)

- [ ] **Step 1: settings layout에 Account 링크 추가**

Edit `web/app/(workspace)/settings/layout.tsx`. 현재 ul 내부 li 한 개만 있다 — Account 항목 추가:
```typescript
<li>
  <Link
    href="/settings/account"
    className="block rounded-md px-2 py-1.5 text-text-2 hover:bg-bg-2 hover:text-text-1"
  >
    Account
  </Link>
</li>
```

- [ ] **Step 2: Password 폼 컴포넌트**

Create `web/components/settings/account-password-form.tsx`:
```typescript
"use client";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useChangePassword } from "@/hooks/use-account";

export function AccountPasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [revoke, setRevoke] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const m = useChangePassword();

  return (
    <form
      className="space-y-3 max-w-md"
      onSubmit={async (e) => {
        e.preventDefault();
        setMsg(null);
        try {
          await m.mutateAsync({
            current_password: current,
            new_password: next,
            revoke_other_sessions: revoke,
          });
          setCurrent("");
          setNext("");
          setMsg("Password updated.");
        } catch (err) {
          setMsg((err as Error).message);
        }
      }}
    >
      <div className="space-y-1">
        <Label htmlFor="cur">Current password</Label>
        <Input id="cur" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="new">New password (≥ 8 chars)</Label>
        <Input id="new" type="password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} />
      </div>
      <label className="flex items-center gap-2 text-xs text-text-2">
        <Switch checked={revoke} onCheckedChange={setRevoke} />
        Revoke all other sessions
      </label>
      <Button type="submit" disabled={m.isPending}>
        {m.isPending ? "Saving…" : "Update password"}
      </Button>
      {msg && <p className="text-xs text-text-2">{msg}</p>}
    </form>
  );
}
```

- [ ] **Step 3: 백업 버튼 컴포넌트**

Create `web/components/settings/account-backup-button.tsx`:
```typescript
"use client";
import { Button } from "@/components/ui/button";
import { backupDownloadUrl } from "@/lib/account";

export function AccountBackupButton() {
  return (
    <a href={backupDownloadUrl()} download>
      <Button variant="outline">Download backup (.db)</Button>
    </a>
  );
}
```

- [ ] **Step 4: 복원 폼 컴포넌트**

Create `web/components/settings/account-restore-form.tsx`:
```typescript
"use client";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useRestore } from "@/hooks/use-account";

export function AccountRestoreForm() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const m = useRestore();

  return (
    <form
      className="space-y-2 max-w-md"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = inputRef.current?.files?.[0];
        if (!f) return;
        if (
          !window.confirm(
            "This will replace ALL current data and sign you out everywhere. Continue?",
          )
        )
          return;
        setMsg(null);
        try {
          await m.mutateAsync(f);
          setMsg("Restore complete. Reloading…");
          setTimeout(() => window.location.assign("/login"), 800);
        } catch (err) {
          setMsg((err as Error).message);
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".db,application/octet-stream"
        className="block w-full text-xs text-text-2"
      />
      <Button type="submit" variant="destructive" disabled={m.isPending}>
        {m.isPending ? "Restoring…" : "Restore from file"}
      </Button>
      {msg && <p className="text-xs text-text-2">{msg}</p>}
    </form>
  );
}
```

(만약 `Button`의 `destructive` variant가 없다면 `outline` + `text-signal-sell`로 inline override.)

- [ ] **Step 5: 세션 리스트 컴포넌트**

Create `web/components/settings/account-sessions-list.tsx`:
```typescript
"use client";
import { Button } from "@/components/ui/button";
import { useRevokeOtherSessions, useSessions } from "@/hooks/use-account";

export function AccountSessionsList() {
  const q = useSessions();
  const revoke = useRevokeOtherSessions();
  if (q.isLoading) return <p className="text-xs text-text-3">Loading…</p>;
  const sessions = q.data ?? [];
  return (
    <div className="space-y-2 max-w-md">
      <ul className="text-xs text-text-2 space-y-1">
        {sessions.map((s) => (
          <li
            key={s.id_masked}
            className="flex items-center justify-between border border-border-1 rounded-md px-3 py-1.5 bg-bg-1"
          >
            <span className="font-mono">{s.id_masked}</span>
            <span className="text-text-3">
              expires {new Date(s.expires_at).toLocaleString()}
            </span>
            {s.is_current && (
              <span className="text-[10px] uppercase tracking-widest text-accent">current</span>
            )}
          </li>
        ))}
      </ul>
      <Button
        variant="outline"
        disabled={revoke.isPending || sessions.filter((s) => !s.is_current).length === 0}
        onClick={() => revoke.mutate()}
      >
        {revoke.isPending ? "Revoking…" : "Revoke other sessions"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 6: 페이지 작성**

Create `web/app/(workspace)/settings/account/page.tsx`:
```typescript
import { AccountBackupButton } from "@/components/settings/account-backup-button";
import { AccountPasswordForm } from "@/components/settings/account-password-form";
import { AccountRestoreForm } from "@/components/settings/account-restore-form";
import { AccountSessionsList } from "@/components/settings/account-sessions-list";

export default function SettingsAccountPage() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-lg text-text-1">Account</h1>
        <p className="text-sm text-text-2">
          Manage your password, active sessions, and data backups.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm uppercase tracking-widest text-text-3">Password</h2>
        <AccountPasswordForm />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm uppercase tracking-widest text-text-3">Sessions</h2>
        <AccountSessionsList />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm uppercase tracking-widest text-text-3">Backup</h2>
        <p className="text-xs text-text-3">
          Downloads the entire SQLite file (analyses, holdings, schedules, alerts, settings).
        </p>
        <AccountBackupButton />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm uppercase tracking-widest text-text-3">Restore</h2>
        <p className="text-xs text-signal-sell">
          Warning: replaces ALL current data and signs you out from every device.
        </p>
        <AccountRestoreForm />
      </section>
    </div>
  );
}
```

- [ ] **Step 7: TypeScript 빌드 확인**

Run: `cd web && npm run typecheck && npm run build`
Expected: 빌드 통과. 빌드 워닝/에러 발생 시 수정.

- [ ] **Step 8: 수동 스모크 테스트**

Run dev server (`uv run uvicorn tradingagents_web.main:app --port 8000` + `cd web && npm run dev`), 로그인 후 `/settings/account` 방문 → 비밀번호 변경, 백업 다운로드, 세션 목록 표시 확인. UI에서 명백한 깨짐이 없는지 확인.

- [ ] **Step 9: 커밋**

```bash
git add web/app/\(workspace\)/settings/ web/components/settings/account-*.tsx
git commit -m "feat(web/m5): /settings/account page (password, sessions, backup, restore)"
```

---

## Task 9: History compare 선택 UI — 체크박스 + 툴바

**Files:**
- Modify: `web/components/history/history-table.tsx`(선택 상태 prop)
- Create: `web/components/history/compare-toolbar.tsx`
- Modify: `web/app/(workspace)/history/page.tsx`(선택 상태 + 툴바)

- [ ] **Step 1: 툴바 컴포넌트 작성**

Create `web/components/history/compare-toolbar.tsx`:
```typescript
"use client";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

type Props = {
  selected: string[];
  onClear: () => void;
};

export function CompareToolbar({ selected, onClear }: Props) {
  const router = useRouter();
  const ready = selected.length === 2;
  return (
    <div className="flex items-center justify-between gap-2 mb-2 text-xs text-text-3">
      <span>
        {selected.length} / 2 selected
        {selected.length > 0 && (
          <button className="ml-2 underline" type="button" onClick={onClear}>
            clear
          </button>
        )}
      </span>
      <Button
        variant={ready ? "default" : "outline"}
        disabled={!ready}
        onClick={() =>
          router.push(`/history/compare?ids=${selected[0]},${selected[1]}`)
        }
      >
        Compare
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: HistoryTable에 선택 prop 추가**

Edit `web/components/history/history-table.tsx`. 시그니처와 렌더 변경:
```typescript
type Props = {
  rows: RunListItem[];
  selected: Set<string>;
  onToggle: (runId: string) => void;
};

export function HistoryTable({ rows, selected, onToggle }: Props) {
  // ... existing empty case unchanged
  // 데스크톱 테이블: <thead> 첫 컬럼에 빈 <th>, 각 row 첫 td에 체크박스
  // 모바일 카드: 체크박스를 ticker 줄 좌측에 inline
```

체크박스 셀(데스크톱):
```tsx
<td className="py-2 px-3 w-8">
  <input
    type="checkbox"
    checked={selected.has(r.run_id)}
    onChange={() => onToggle(r.run_id)}
    aria-label={`Select ${r.ticker} run`}
    className="accent-accent"
  />
</td>
```

모바일 카드 헤더에:
```tsx
<input
  type="checkbox"
  checked={selected.has(r.run_id)}
  onChange={(e) => {
    e.preventDefault();
    onToggle(r.run_id);
  }}
  className="mr-2 accent-accent"
/>
```
(Link 안에 nested input은 클릭 이벤트 충돌이 있으니, 카드 마크업을 Link 외부 div로 감싸고 ticker만 Link로 내부 처리하도록 재구성. 또는 `e.preventDefault(); e.stopPropagation();`로 내부 link 클릭과 분리.)

- [ ] **Step 3: HistoryPage에 선택 상태 + 툴바 통합**

Edit `web/app/(workspace)/history/page.tsx`:
```typescript
const [selected, setSelected] = useState<Set<string>>(new Set());
const toggle = (id: string) => {
  setSelected((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else if (next.size < 2) next.add(id);
    else {
      // 가장 오래 머물던 항목을 밀어낸다 — 단순 행동: 첫 항목 제거 후 추가
      const first = next.values().next().value as string;
      next.delete(first);
      next.add(id);
    }
    return next;
  });
};
```

렌더에 `<CompareToolbar selected={[...selected]} onClear={() => setSelected(new Set())} />`를 필터 아래·테이블 위에 삽입. `<HistoryTable rows={...} selected={selected} onToggle={toggle} />`로 prop 전달.

- [ ] **Step 4: TypeScript 빌드 확인**

Run: `cd web && npm run typecheck`
Expected: clean.

- [ ] **Step 5: 수동 스모크 테스트**

분석 2개 이상이 있는 상태에서 `/history` 진입 → 두 행 체크 → "Compare" 버튼 활성화 → 클릭 시 `/history/compare?ids=...&ids=...`로 이동(다음 태스크에서 페이지 구현).

- [ ] **Step 6: 커밋**

```bash
git add web/components/history/ web/app/\(workspace\)/history/page.tsx
git commit -m "feat(web/m5): history table multi-select + Compare toolbar"
```

---

## Task 10: `/history/compare` 페이지

**Files:**
- Create: `web/app/(workspace)/history/compare/page.tsx`
- Create: `web/components/history/compare-column.tsx`(렌더링 한 컬럼)

- [ ] **Step 1: 비교 컬럼 컴포넌트**

Create `web/components/history/compare-column.tsx`:
```typescript
"use client";
import { VerdictCard } from "@/components/analysis/verdict-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRun } from "@/hooks/use-runs";
import type { Decision as RunDecision } from "@/lib/runs";

const REPORT_FIELDS = [
  ["market_report", "Market"],
  ["sentiment_report", "Sentiment"],
  ["news_report", "News"],
  ["fundamentals_report", "Fundamentals"],
  ["investment_plan", "Researcher Verdict"],
  ["trader_investment_plan", "Trader Plan"],
  ["final_trade_decision", "Final Decision"],
] as const;

export function CompareColumn({ runId }: { runId: string }) {
  const q = useRun(runId);
  if (q.isLoading) return <p className="text-xs text-text-3">Loading…</p>;
  if (q.error || !q.data)
    return (
      <p className="text-xs text-signal-sell">
        {(q.error as Error)?.message ?? "Run not found"}
      </p>
    );
  const a = q.data;
  const state = (a.final_state ?? {}) as Record<string, string | undefined>;
  return (
    <div className="space-y-3 min-w-0">
      <div>
        <h2 className="text-base font-bold text-text-1">
          <span className="font-num">{a.ticker}</span>{" "}
          <span className="text-text-3 text-xs">{a.analysis_date}</span>
        </h2>
        <p className="text-[11px] text-text-3">
          {a.status} · deep={a.llm_deep_model} · quick={a.llm_quick_model}
        </p>
      </div>
      <VerdictCard decision={a.decision as RunDecision | null} confidence={a.confidence} />
      {REPORT_FIELDS.map(([key, label]) => {
        const value = state[key];
        if (!value) return null;
        return (
          <Card key={key}>
            <CardHeader>
              <CardTitle>{label}</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-[11px] text-text-2 whitespace-pre-wrap font-sans leading-relaxed">
                {value}
              </pre>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 페이지 작성 — 데스크톱 grid, 모바일 탭**

Create `web/app/(workspace)/history/compare/page.tsx`:
```typescript
"use client";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { CompareColumn } from "@/components/history/compare-column";
import { cn } from "@/lib/utils";

export default function HistoryComparePage() {
  const sp = useSearchParams();
  const ids = (sp.get("ids") ?? "").split(",").filter(Boolean);
  const [active, setActive] = useState<0 | 1>(0);

  if (ids.length !== 2 || ids[0] === ids[1])
    return (
      <p className="px-4 md:px-6 py-6 text-xs text-signal-sell">
        Provide exactly two distinct run IDs: <code>?ids=a,b</code>.
      </p>
    );

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-3">Compare</h1>

      {/* Mobile tabs */}
      <div className="md:hidden flex gap-1 mb-3 text-xs">
        {[0, 1].map((i) => (
          <button
            key={i}
            type="button"
            onClick={() => setActive(i as 0 | 1)}
            className={cn(
              "flex-1 rounded-md px-2 py-1.5 border",
              active === i
                ? "border-accent text-text-1 bg-bg-2"
                : "border-border-1 text-text-3",
            )}
          >
            {i === 0 ? "A" : "B"}
          </button>
        ))}
      </div>

      <div className="md:hidden">
        <CompareColumn runId={ids[active]} />
      </div>

      <div className="hidden md:grid grid-cols-2 gap-4">
        <CompareColumn runId={ids[0]} />
        <CompareColumn runId={ids[1]} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: TypeScript 빌드 확인**

Run: `cd web && npm run typecheck && npm run build`
Expected: 통과.

- [ ] **Step 4: 수동 스모크 테스트**

`/history/compare?ids=<id1>,<id2>` 직접 방문(있는 분석 2개 사용) → 데스크톱은 좌우 분할, 모바일(<768px)은 A/B 탭 전환 동작 확인.

- [ ] **Step 5: 커밋**

```bash
git add web/app/\(workspace\)/history/compare/ web/components/history/compare-column.tsx
git commit -m "feat(web/m5): /history/compare side-by-side view (mobile A/B tabs)"
```

---

## Task 11: 모바일 More 페이지(`/more`)

탭바의 `/more` 링크는 현재 라우트가 없어 404. 모바일에서 자주 쓰지 않는 항목(History, Schedules, Settings, Logout)을 한곳에 모은다.

**Files:**
- Create: `web/app/(workspace)/more/page.tsx`

- [ ] **Step 1: 페이지 작성**

Create `web/app/(workspace)/more/page.tsx`:
```typescript
"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

const ITEMS = [
  { href: "/history", label: "History", desc: "Past analyses" },
  { href: "/schedules", label: "Schedules", desc: "Recurring runs" },
  { href: "/settings/notifications", label: "Notifications", desc: "Alerts + Telegram" },
  { href: "/settings/account", label: "Account", desc: "Password, sessions, backup" },
];

export default function MorePage() {
  const router = useRouter();
  return (
    <div className="px-4 py-6 max-w-screen-md mx-auto space-y-3">
      <h1 className="text-xl font-bold text-text-1">More</h1>
      <ul className="grid gap-2">
        {ITEMS.map((it) => (
          <li key={it.href}>
            <Link
              href={it.href}
              className="block border border-border-1 rounded-md bg-bg-1 px-4 py-3 hover:bg-bg-2"
            >
              <div className="text-sm text-text-1">{it.label}</div>
              <div className="text-xs text-text-3">{it.desc}</div>
            </Link>
          </li>
        ))}
      </ul>
      <Button
        variant="outline"
        className="w-full mt-4"
        onClick={async () => {
          await apiFetch("/api/auth/logout", { method: "POST" });
          router.push("/login");
        }}
      >
        Log out
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 + 모바일 뷰포트(Chrome DevTools) 확인**

Run: `cd web && npm run typecheck`
Expected: 통과.

- [ ] **Step 3: 커밋**

```bash
git add web/app/\(workspace\)/more/
git commit -m "feat(web/m5): mobile /more page (history/schedules/settings/logout)"
```

---

## Task 12: PWA — manifest, 오프라인 폴백, 아이콘

**Files:**
- Create: `web/public/manifest.json`
- Create: `web/public/_offline.html`
- Create: `web/public/icons/icon-192.png` (placeholder)
- Create: `web/public/icons/icon-512.png` (placeholder)
- Modify: `web/app/layout.tsx`(metadata + link)

- [ ] **Step 1: manifest 작성**

Create `web/public/manifest.json`:
```json
{
  "name": "TradingAgents",
  "short_name": "TA",
  "description": "Personal trading analysis workbench",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#0a0a0b",
  "theme_color": "#0a0a0b",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```

- [ ] **Step 2: 오프라인 폴백 HTML**

Create `web/public/_offline.html`:
```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Offline — TradingAgents</title>
  <style>
    body { margin: 0; background: #0a0a0b; color: #e8e8ea; font-family: Inter, system-ui, sans-serif; }
    main { display: flex; min-height: 100vh; align-items: center; justify-content: center; padding: 1.5rem; }
    .card { max-width: 420px; padding: 1.5rem; border: 1px solid #1f1f24; border-radius: 8px; background: #111114; }
    h1 { margin: 0 0 0.5rem; font-size: 1.1rem; }
    p { margin: 0; color: #a0a0a8; font-size: 0.85rem; line-height: 1.5; }
    code { color: #4f8cff; }
  </style>
</head>
<body>
  <main>
    <div class="card">
      <h1>You're offline</h1>
      <p>TradingAgents needs a connection to run analyses or load fresh data. Reconnect and reload — recently visited pages may also work from cache.</p>
    </div>
  </main>
</body>
</html>
```

- [ ] **Step 3: placeholder 아이콘 생성**

이 단계에서는 단색 PNG로 충분. 임시 생성 스크립트(있는 디자인 자산이 있으면 교체):
```bash
mkdir -p web/public/icons
python - <<'PY'
from pathlib import Path
import struct, zlib

def png_solid(size: int, rgb=(10, 10, 11)):
    # raw RGBA scanlines: filter byte 0 + size*4 pixels
    raw = b"".join(b"\x00" + bytes(rgb + (255,)) * size for _ in range(size))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend

for s in (192, 512):
    Path(f"web/public/icons/icon-{s}.png").write_bytes(png_solid(s))
PY
```

- [ ] **Step 4: root layout에 manifest + theme-color 추가**

Edit `web/app/layout.tsx`:
```typescript
import "./globals.css";

import type { Metadata, Viewport } from "next";

import { Providers } from "./providers";
import { ServiceWorkerRegistrar } from "@/components/shared/service-worker-registrar";

export const metadata: Metadata = {
  title: "TradingAgents",
  description: "Personal trading analysis workbench",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0a0a0b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="bg-bg-0 text-text-1 antialiased">
        <ServiceWorkerRegistrar />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

(`ServiceWorkerRegistrar`는 다음 태스크에서 작성. Step 5는 일단 빌드 통과를 위해 빈 컴포넌트라도 먼저 있게 하거나, 다음 태스크와 한 커밋으로 합쳐도 무방하다 — 본 플랜에서는 분리해서 다음 태스크 끝까지 빌드 안정 확보.)

- [ ] **Step 5: 빈 SW 등록자 placeholder**

Create `web/components/shared/service-worker-registrar.tsx`:
```typescript
"use client";

export function ServiceWorkerRegistrar() {
  return null;
}
```

- [ ] **Step 6: 빌드 확인**

Run: `cd web && npm run build`
Expected: 통과 + manifest 메타가 head에 포함.

- [ ] **Step 7: 커밋**

```bash
git add web/public/manifest.json web/public/_offline.html web/public/icons/ web/app/layout.tsx web/components/shared/service-worker-registrar.tsx
git commit -m "feat(web/m5): PWA manifest + offline fallback + placeholder icons"
```

---

## Task 13: PWA — Service Worker 등록 + 캐시 전략

**Files:**
- Create: `web/public/sw.js`
- Modify: `web/components/shared/service-worker-registrar.tsx`

- [ ] **Step 1: Service Worker 작성**

Create `web/public/sw.js`:
```javascript
// TradingAgents Web Service Worker.
// Bump CACHE_NAME on each deployment that ships SW changes.
const CACHE_NAME = "ta-v1";
const PRECACHE = ["/_offline.html", "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // 1) API: network-first, NO cache fallback (data must be fresh).
  if (url.pathname.startsWith("/api/")) {
    return; // let browser handle, no SW interference
  }

  // 2) Static Next assets: cache-first, fall back to network and store.
  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            if (res.ok) caches.open(CACHE_NAME).then((c) => c.put(req, copy));
            return res;
          }),
      ),
    );
    return;
  }

  // 3) Same-origin HTML navigation: network-first → cache → /_offline.html
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          if (res.ok) caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() =>
          caches.match(req).then((hit) => hit || caches.match("/_offline.html")),
        ),
    );
    return;
  }
});
```

- [ ] **Step 2: 등록자 컴포넌트 구현**

Edit `web/components/shared/service-worker-registrar.tsx`:
```typescript
"use client";
import { useEffect } from "react";

export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return; // avoid SW caching during dev
    const url = "/sw.js";
    navigator.serviceWorker.register(url).catch((err) => {
      // eslint-disable-next-line no-console
      console.warn("[sw] registration failed:", err);
    });
  }, []);
  return null;
}
```

- [ ] **Step 3: 빌드 + 수동 검증**

Run: `cd web && npm run build && npm run start -- -p 3001`(prod 모드).
Chrome DevTools → Application → Manifest 탭에서 manifest 인식, Service Workers 탭에 `sw.js` 활성 확인. 네트워크 오프라인 모드 토글 후 라우트 새로고침 시 `/_offline.html` 표시.

- [ ] **Step 4: 커밋**

```bash
git add web/public/sw.js web/components/shared/service-worker-registrar.tsx
git commit -m "feat(web/m5): register service worker (network-first + offline fallback)"
```

---

## Task 14: 모바일/사이드바 마무리 폴리싱

목표: 사이드바 Settings 항목을 단일 링크에서 sub-link 펼침으로 바꾸고(Notifications, Account), tab-bar의 /more 항목을 active 상태로 강조한다(이미 `pathname.startsWith` 분기 있음 — 동작 점검만). 또한 history 테이블 모바일 카드의 체크박스 클릭이 Link 네비게이션과 충돌하지 않도록 마지막 점검.

**Files:**
- Modify: `web/components/nav/sidebar.tsx`
- 점검: `web/components/nav/tab-bar.tsx`, `web/components/history/history-table.tsx`

- [ ] **Step 1: 사이드바 Settings 섹션 펼침**

Edit `web/components/nav/sidebar.tsx`. `SECTIONS` 상수의 마지막 그룹을 다음과 같이 수정:
```typescript
{
  title: "System",
  items: [
    { href: "/settings/notifications", label: "Notifications", icon: "⚙" },
    { href: "/settings/account", label: "Account", icon: "◉" },
  ],
},
```

- [ ] **Step 2: tab-bar `/more` 항목 active 동작 검증**

Read `web/components/nav/tab-bar.tsx` — 분기 `pathname.startsWith(tab.href)`가 `/more`에서 정상 작동. 추가 변경 불필요.

- [ ] **Step 3: history-table 모바일 카드 체크박스 충돌 검증**

`/history`에서 모바일 뷰포트(< 768px)로 전환 후, 카드 내부 체크박스 클릭 시 부모 Link로 네비게이션이 일어나지 않는지 확인. 일어나면 마크업을 `<div>` + 별도 `<Link>`(ticker 텍스트만 wrap)으로 분리:
```tsx
<li className="border border-border-1 rounded-md bg-bg-1 px-3 py-2">
  <div className="flex items-center justify-between mb-1">
    <div className="flex items-center gap-2">
      <input type="checkbox" ... />
      <Link href={`/history/${r.run_id}`} className="font-num font-bold">
        {r.ticker}
      </Link>
    </div>
    <SignalBadge decision={r.decision} />
  </div>
  <Link href={`/history/${r.run_id}`} className="block">
    <div className="flex items-center justify-between text-[10px] text-text-3">
      <span className="font-num">{r.analysis_date}</span>
      <span>{r.status}</span>
    </div>
  </Link>
</li>
```

- [ ] **Step 4: 빌드 + 타입체크**

Run: `cd web && npm run typecheck && npm run build`
Expected: 통과.

- [ ] **Step 5: 커밋**

```bash
git add web/components/nav/sidebar.tsx web/components/history/history-table.tsx
git commit -m "polish(web/m5): expand Settings nav, fix mobile history checkbox + link split"
```

---

## Task 15: 문서 업데이트 + 최종 검증

**Files:**
- Modify: `web/DEV.md` 또는 `DEV.md`(개발 가이드)
- 검증 only: 전체 테스트, 빌드

- [ ] **Step 1: DEV.md에 M5 항목 추가**

Edit `DEV.md`(또는 적절한 위치). M5 절을 짧게 추가:
```markdown
## M5 — Polish

- PWA: `web/public/manifest.json`, `web/public/sw.js`. Bump `CACHE_NAME` in `sw.js` for cache invalidation. SW only registers in production builds.
- History compare: `/history/compare?ids=a,b` (max 2 selected from history table).
- Account: `/settings/account` provides password change, session list/revoke, full SQLite backup download, and restore from uploaded `.db`. Restore stops the scheduler, disposes the engine, swaps the file, and restarts.
- Mobile: `/more` page consolidates History/Schedules/Settings/Logout for the bottom tab bar.
- Restore is sqlite-only; deployments using a non-sqlite `database_url` will receive HTTP 409 from `/api/settings/account/restore` and `/backup`.
```

- [ ] **Step 2: 풀 테스트 실행**

Run:
```bash
uv run pytest -q
cd web && npm run typecheck && npm run build
```
Expected: 모두 통과.

- [ ] **Step 3: 수동 시나리오 한 번 끝까지 — S2/S5 (spec §2)**

S2: 기존 분석 두 개를 history에서 선택 → Compare 진입 → 좌우 비교 정상.
S5: 모바일 뷰포트(또는 실제 폰 PWA 설치 후) 홈 화면 아이콘으로 진입 → 로그인 유지 → Alerts/More 동작.

- [ ] **Step 4: 최종 커밋 + 머지 PR**

```bash
git add DEV.md
git commit -m "docs(web/m5): document polish milestone (PWA, compare, account)"
```

PR 생성:
```bash
gh pr create --base main --title "feat(web): M5 polish — PWA, compare, account, mobile" --body "$(cat <<'EOF'
## Summary
- PWA manifest + service worker (offline fallback, network-first API).
- History side-by-side compare view (`/history/compare?ids=a,b`).
- `/settings/account`: password change, session revoke, SQLite backup/restore.
- Mobile `/more` page replacing the broken tab-bar link.

## Test plan
- [ ] uv run pytest tests/web/ green
- [ ] web typecheck + build
- [ ] manual: backup → restore roundtrip
- [ ] manual: install as PWA on iOS/Android, verify standalone mode + offline fallback
- [ ] manual: select 2 runs in /history → Compare, both desktop and mobile
EOF
)"
```

---

## Self-Review Checklist (작성 후 점검)

- 스펙 §11 M5 4개 항목 모두 구현됨? ✓ PWA(Task 12–13), 모바일 폴리싱(Task 11, 14), 비교 뷰(Task 9–10), 백업/복원(Task 1–6, 8).
- 스펙 §2 S2/S5 시나리오 만족? ✓ S2 = compare; S5 = PWA 설치 + Alerts(M4) + Auth 유지 + 모바일 More.
- 스펙 §6.3 백업 = 단일 .db 다운로드? ✓ Task 2.
- 스펙 §12 PWA cache strategy(API network-first, 정적 cache-first)? ✓ Task 13.
- 모든 step에 실제 코드/명령? ✓ "TBD" 없음.
- 신규 endpoint 인증·CSRF? ✓ `get_current_user` + `require_xhr` 모두 부착.
- 위험 액션(restore) 가드? ✓ window.confirm + 잘못된 파일 검증 + scheduler shutdown/restart.
