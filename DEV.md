# TradingAgents Web — Local Development

## One-time setup

```bash
# 1. Install Python deps (uv recommended)
uv sync

# 2. Install frontend deps
(cd web && npm install)

# 3. Generate secrets and copy env
cp .env.example .env
uv run python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
uv run python -c "import secrets; print('WEB_SESSION_SECRET=' + secrets.token_urlsafe(32))" >> .env
# (Edit .env to remove the placeholder ENCRYPTION_KEY/WEB_SESSION_SECRET lines.)

# 4. Run migrations + create initial password
uv run alembic upgrade head
uv run tradingagents-web set-password
```

## Run (two terminals)

```bash
# Terminal 1: backend
uv run uvicorn tradingagents_web.main:app --reload --port 8000

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
uv run pytest tests/web/ -v       # backend
cd web && npm run typecheck       # frontend type check
cd web && npm run build           # frontend build
```

## M2 — Run/History

### Quick demo (no LLM cost, fake runner)

1. `WEB_FAKE_RUNNER=true uv run uvicorn tradingagents_web.main:app --reload`
2. `cd web && npm run dev`
3. 브라우저 `http://localhost:3000`. 로그인 후:
   - `/run`에서 ticker `AAPL`, 분석가 4종 체크 → "Run"
   - `/run/<id>`로 자동 이동, 가짜 진행과 verdict 확인
   - `/history`에서 방금 분석이 목록에 보이는지 확인 → 클릭 → 상세 보고서

### Real run (LLM 비용 발생)

`WEB_FAKE_RUNNER=false`로 두고(기본) 환경변수에 LLM provider 키 설정. M2는 `tradingagents/default_config.py`의 기본 모델을 사용한다. 모델 변경 UI는 M5에서 추가 예정.
