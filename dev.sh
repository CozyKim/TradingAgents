#!/usr/bin/env bash
# TradingAgents — backend(uvicorn) + frontend(Next.js) 동시 실행 스크립트
#
# 사용법:
#   ./dev.sh                # 일반 실행
#   ./dev.sh --fake         # WEB_FAKE_RUNNER=true (LLM 비용 없이 가짜 러너)
#   BACKEND_PORT=8001 WEB_PORT=3001 ./dev.sh
#
# Ctrl+C 한 번으로 두 프로세스가 함께 종료된다.

set -euo pipefail

# ── 설정 ───────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="${ROOT_DIR}/web"
BACKEND_PORT="${BACKEND_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
LOG_DIR="${ROOT_DIR}/.logs"
mkdir -p "${LOG_DIR}"

# --fake 플래그 처리
FAKE_RUNNER="${WEB_FAKE_RUNNER:-false}"
for arg in "$@"; do
  case "${arg}" in
    --fake) FAKE_RUNNER=true ;;
    -h|--help)
      sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done
export WEB_FAKE_RUNNER="${FAKE_RUNNER}"

# ── 사전 검증 ─────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  echo "[dev.sh] 'uv'가 설치되어 있지 않다. https://docs.astral.sh/uv/ 참고." >&2
  exit 1
fi

if [[ ! -d "${WEB_DIR}/node_modules" ]]; then
  echo "[dev.sh] web/node_modules가 없다. 'cd web && npm install' 후 다시 실행." >&2
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "[dev.sh] .env가 없다. DEV.md의 'One-time setup' 절차를 먼저 진행." >&2
  exit 1
fi

# ── 종료 처리 ─────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo
  echo "[dev.sh] 종료 신호 수신 — 자식 프로세스 정리 중..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  # graceful 대기 후 SIGKILL
  sleep 1
  for pid in "${PIDS[@]}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  echo "[dev.sh] 정상 종료."
}
trap cleanup EXIT INT TERM

# ── 실행 ──────────────────────────────────────────────────────────────
echo "[dev.sh] WEB_FAKE_RUNNER=${WEB_FAKE_RUNNER}"
echo "[dev.sh] backend → http://localhost:${BACKEND_PORT}  (logs: ${LOG_DIR}/backend.log)"
echo "[dev.sh] web     → http://localhost:${WEB_PORT}     (logs: ${LOG_DIR}/web.log)"
echo

# 백엔드 (stdout/stderr는 prefix를 붙여 콘솔 + 파일 양쪽으로)
(
  cd "${ROOT_DIR}"
  uv run uvicorn tradingagents_web.main:app --reload --port "${BACKEND_PORT}" 2>&1 \
    | tee "${LOG_DIR}/backend.log" \
    | sed -u 's/^/[backend] /'
) &
PIDS+=($!)

# 프론트
(
  cd "${WEB_DIR}"
  PORT="${WEB_PORT}" npm run dev 2>&1 \
    | tee "${LOG_DIR}/web.log" \
    | sed -u 's/^/[web]     /'
) &
PIDS+=($!)

# 둘 중 하나라도 죽으면 전체 종료
wait -n
echo "[dev.sh] 자식 프로세스 중 하나가 종료됨 → 전체 정리."
exit 1
