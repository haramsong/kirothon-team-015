#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PYTHON="${BACKEND_PYTHON:-${ROOT_DIR}/backend/.venv/bin/python}"
VITE_BIN="${ROOT_DIR}/frontend/node_modules/.bin/vite"
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/my-own-fridge-smoke.XXXXXX")"
BACKEND_PID=""
FRONTEND_PID=""

terminate_process() {
  local pid="$1"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  fi
  if [[ -n "${pid}" ]]; then
    wait "${pid}" 2>/dev/null || true
  fi
}

cleanup() {
  terminate_process "${FRONTEND_PID}"
  terminate_process "${BACKEND_PID}"
  rm -rf "${LOG_DIR}"
}

show_logs() {
  local exit_code=$?
  echo "로컬 smoke 검증이 실패했습니다." >&2
  for log_file in "${LOG_DIR}"/*.log; do
    if [[ -f "${log_file}" ]]; then
      echo "--- $(basename "${log_file}") ---" >&2
      tail -n 40 "${log_file}" >&2
    fi
  done
  return "${exit_code}"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  for _ in {1..60}; do
    if curl --fail --silent --show-error --max-time 2 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "${name} 서버가 준비 시간 안에 응답하지 않았습니다: ${url}" >&2
  return 1
}

trap cleanup EXIT
trap show_logs ERR

if [[ ! -x "${BACKEND_PYTHON}" ]]; then
  echo "백엔드 Python 실행 파일이 없습니다: ${BACKEND_PYTHON}" >&2
  exit 1
fi
if [[ ! -x "${VITE_BIN}" ]]; then
  echo "Vite 실행 파일이 없습니다. frontend 의존성을 먼저 설치해 주세요." >&2
  exit 1
fi

cd "${ROOT_DIR}"
env \
  -u AWS_PROFILE \
  -u AWS_ACCESS_KEY_ID \
  -u AWS_SECRET_ACCESS_KEY \
  -u AWS_SESSION_TOKEN \
  APP_ENV=test \
  CORS_ORIGINS="http://localhost:${FRONTEND_PORT}" \
  AWS_EC2_METADATA_DISABLED=true \
  "${BACKEND_PYTHON}" -m uvicorn app.main:app \
    --app-dir backend --host 127.0.0.1 --port "${BACKEND_PORT}" \
    >"${LOG_DIR}/uvicorn.log" 2>&1 &
BACKEND_PID=$!

VITE_API_BASE_URL="http://127.0.0.1:${BACKEND_PORT}" \
  "${VITE_BIN}" "${ROOT_DIR}/frontend" \
  --host 127.0.0.1 --port "${FRONTEND_PORT}" --strictPort \
  >"${LOG_DIR}/vite.log" 2>&1 &
FRONTEND_PID=$!

wait_for_url "uvicorn" "http://127.0.0.1:${BACKEND_PORT}/api/health"
wait_for_url "Vite" "http://127.0.0.1:${FRONTEND_PORT}/"

HEALTH_RESPONSE="$(curl --fail --silent --show-error --max-time 3 \
  "http://127.0.0.1:${BACKEND_PORT}/api/health")"
if [[ "${HEALTH_RESPONSE}" != *'"status":"ok"'* ]]; then
  echo "API health 응답이 예상과 다릅니다: ${HEALTH_RESPONSE}" >&2
  exit 1
fi

SPA_RESPONSE="$(curl --fail --silent --show-error --max-time 3 \
  "http://127.0.0.1:${FRONTEND_PORT}/")"
if [[ "${SPA_RESPONSE}" != *'<div id="root"></div>'* ]] || \
   [[ "${SPA_RESPONSE}" != *'<title>나만의 냉장고</title>'* ]]; then
  echo "Vite SPA index 응답에서 앱 진입점을 확인하지 못했습니다." >&2
  exit 1
fi

CORS_HEADERS="$(curl --silent --show-error --dump-header - --output /dev/null --max-time 3 \
  --request OPTIONS \
  --header "Origin: http://localhost:${FRONTEND_PORT}" \
  --header "Access-Control-Request-Method: GET" \
  --header "Access-Control-Request-Headers: Content-Type,X-Device-Id" \
  "http://127.0.0.1:${BACKEND_PORT}/api/health")"
if ! grep -Eiq "^access-control-allow-origin: http://localhost:${FRONTEND_PORT}\r?$" <<<"${CORS_HEADERS}"; then
  echo "CORS 응답에 허용 origin이 없습니다." >&2
  exit 1
fi
if ! grep -Eiq '^access-control-allow-headers:.*content-type' <<<"${CORS_HEADERS}" || \
   ! grep -Eiq '^access-control-allow-headers:.*x-device-id' <<<"${CORS_HEADERS}"; then
  echo "CORS 응답에 필수 요청 헤더 허용값이 없습니다." >&2
  exit 1
fi

# 성공 경로에서도 여기서 명시적으로 종료해 프로세스 정리를 검증합니다.
terminate_process "${FRONTEND_PID}"
terminate_process "${BACKEND_PID}"
if kill -0 "${FRONTEND_PID}" 2>/dev/null || kill -0 "${BACKEND_PID}" 2>/dev/null; then
  echo "임시 개발 서버 프로세스가 종료되지 않았습니다." >&2
  exit 1
fi
FRONTEND_PID=""
BACKEND_PID=""

echo "로컬 smoke 검증 통과: API health, SPA index, CORS, 프로세스 종료"
