#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/deployment/config.sh
source "${ROOT_DIR}/scripts/deployment/config.sh"

readonly BACKEND_PYTHON="${BACKEND_PYTHON:-${ROOT_DIR}/backend/.venv/bin/python}"
readonly SAM_BIN="${SAM_BIN:-sam}"

run_phase() {
  local label="$1"
  shift

  printf '\n==> %s\n' "${label}"
  "$@"
}

if [[ ! -x "${ROOT_DIR}/scripts/verify-all.sh" ]]; then
  printf '전체 검증 스크립트를 실행할 수 없습니다: %s\n' "${ROOT_DIR}/scripts/verify-all.sh" >&2
  exit 1
fi

if [[ ! -x "${BACKEND_PYTHON}" ]]; then
  printf '백엔드 Python 실행 파일이 없습니다: %s\n' "${BACKEND_PYTHON}" >&2
  exit 1
fi

if [[ "${SAM_BIN}" == */* ]]; then
  if [[ ! -x "${SAM_BIN}" ]]; then
    printf 'SAM CLI 실행 파일이 없습니다: %s\n' "${SAM_BIN}" >&2
    exit 1
  fi
elif ! command -v "${SAM_BIN}" >/dev/null 2>&1; then
  printf 'SAM CLI를 찾을 수 없습니다: %s\n' "${SAM_BIN}" >&2
  exit 1
fi

cd "${ROOT_DIR}"

# 비대화형 애플리케이션 테스트, 타입 검사와 프로덕션 빌드를 재사용합니다.
run_phase "전체 애플리케이션 검증" \
  env BACKEND_PYTHON="${BACKEND_PYTHON}" "${ROOT_DIR}/scripts/verify-all.sh"

run_phase "배포 자동화 스펙 테스트" \
  "${BACKEND_PYTHON}" -m pytest "${ROOT_DIR}/tests/deployment"

run_phase "SAM 템플릿 검증" \
  "${SAM_BIN}" validate \
  --template-file "${ROOT_DIR}/template.yaml" \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}"

run_phase "SAM 애플리케이션 빌드" \
  "${SAM_BIN}" build \
  --template-file "${ROOT_DIR}/template.yaml" \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}"

printf '\n로컬 CI 검증을 모두 통과했습니다.\n'
