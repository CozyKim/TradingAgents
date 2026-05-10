#!/usr/bin/env bash
# Idempotently prepare a Playwright/E2E sandbox at ./tradingagents_web_e2e.db.
#
# Why this exists:
#   - On 2026-05-09 an automated E2E setup ran
#       printf 'test1234\ntest1234\n' | uv run tradingagents-web set-password
#     against the production DB at ~/.tradingagents/web.db, silently
#     overwriting the live login password.
#   - This script is the *only* sanctioned way to seed an E2E DB. It refuses
#     to run if WEB_DATABASE_URL would resolve to ~/.tradingagents/web.db,
#     and it always writes to a relative-path sqlite file inside the working
#     tree.
#
# Usage:
#   scripts/setup_e2e.sh                # creates ./tradingagents_web_e2e.db
#   E2E_PASSWORD=somethingelse scripts/setup_e2e.sh
#
# Env:
#   E2E_PASSWORD   default "test1234" — must match web/tests/e2e/*.ts.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

ENV_FILE="${ROOT_DIR}/.env.test"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[setup_e2e] ${ENV_FILE} missing. Re-clone or restore .env.test." >&2
  exit 1
fi

# Load .env.test into the current shell so `uv run` sees the test config.
# `set -a` exports every assignment; we restore the prior state afterwards.
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# Defense in depth: even if .env.test was tampered with, refuse to touch
# the production DB.
HOME_DB="${HOME}/.tradingagents/web.db"
case "${WEB_DATABASE_URL:-}" in
  *"${HOME_DB}"*)
    echo "[setup_e2e] REFUSING — WEB_DATABASE_URL points at production DB:" >&2
    echo "             ${WEB_DATABASE_URL}" >&2
    echo "             expected a relative sqlite path inside the working tree." >&2
    exit 2
    ;;
esac

E2E_PASSWORD="${E2E_PASSWORD:-test1234}"

echo "[setup_e2e] WEB_DATABASE_URL = ${WEB_DATABASE_URL}"
echo "[setup_e2e] running alembic upgrade head"
uv run alembic upgrade head >/dev/null

echo "[setup_e2e] seeding password"
# The DB is the e2e sandbox (not prod), so the cli guard does not fire and
# stdin can be piped safely.
printf '%s\n%s\n' "${E2E_PASSWORD}" "${E2E_PASSWORD}" \
  | uv run tradingagents-web set-password >/dev/null

echo "[setup_e2e] ready. backend should be started with:"
echo "             set -a && source .env.test && set +a && \\"
echo "               uv run uvicorn tradingagents_web.main:app --port 8000"
