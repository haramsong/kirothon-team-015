#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SMOKE_SCRIPT="${SMOKE_SCRIPT:-${ROOT_DIR}/scripts/smoke-local.sh}"
VERIFY_SCRIPT="${VERIFY_SCRIPT:-${ROOT_DIR}/scripts/verify-all.sh}"
SAM_BIN="${SAM_BIN:-sam}"

run_phase() {
  local label="$1"
  shift

  echo
  echo "==> ${label}"
  set +e
  "$@"
  local status=$?
  set -e

  if (( status != 0 )); then
    echo "검증 실패 (${status}): ${label}" >&2
    exit "${status}"
  fi
}

if [[ ! -x "${SMOKE_SCRIPT}" ]]; then
  echo "로컬 smoke 검증 스크립트를 실행할 수 없습니다: ${SMOKE_SCRIPT}" >&2
  exit 1
fi
if [[ ! -x "${VERIFY_SCRIPT}" ]]; then
  echo "전체 자동 검증 스크립트를 실행할 수 없습니다: ${VERIFY_SCRIPT}" >&2
  exit 1
fi
if [[ "${SAM_BIN}" == */* ]]; then
  if [[ ! -x "${SAM_BIN}" ]]; then
    echo "SAM CLI 실행 파일을 찾을 수 없습니다: ${SAM_BIN}" >&2
    exit 1
  fi
elif ! command -v "${SAM_BIN}" >/dev/null 2>&1; then
  echo "SAM CLI를 찾을 수 없습니다: ${SAM_BIN}" >&2
  exit 1
fi

# 배포 전 로컬 애플리케이션과 전체 테스트를 먼저 확인합니다.
run_phase "Vite+uvicorn 로컬 smoke" "${SMOKE_SCRIPT}"
run_phase "전체 자동 테스트와 프로덕션 빌드" "${VERIFY_SCRIPT}"

# 앞선 두 검증이 성공한 경우에만 SAM 템플릿을 검증하고 빌드합니다.
run_phase "SAM 템플릿 검증" \
  "${SAM_BIN}" validate --profile default --region ap-northeast-2
run_phase "SAM 로컬 빌드" \
  "${SAM_BIN}" build --profile default --region ap-northeast-2

echo
echo "로컬 smoke, 전체 자동 테스트, SAM 검증과 빌드를 모두 통과했습니다."
