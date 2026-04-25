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
