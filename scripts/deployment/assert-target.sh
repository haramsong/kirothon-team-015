#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment/config.sh
source "${SCRIPT_DIR}/config.sh"

fail_target_check() {
  local label="$1"
  local expected="$2"
  local actual="$3"

  printf '배포 대상 불일치: %s (expected=%s, actual=%s)\n' \
    "${label}" "${expected}" "${actual:-<empty>}" >&2
  return 1
}

assert_exact_target_value() {
  local label="$1"
  local expected="$2"
  local actual="$3"

  if [[ "${actual}" != "${expected}" ]]; then
    fail_target_check "${label}" "${expected}" "${actual}"
  fi
}

assert_aws_target_values() {
  local actual_account="$1"
  local actual_region="$2"

  assert_exact_target_value 'AWS account' "${EXPECTED_AWS_ACCOUNT}" "${actual_account}" || return 1
  assert_exact_target_value 'AWS region' "${AWS_REGION}" "${actual_region}" || return 1
}

read_local_aws_account() {
  aws sts get-caller-identity \
    --query 'Account' \
    --output 'text' \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

read_local_aws_region() {
  aws configure get region \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

assert_local_aws_target() {
  local actual_account
  local actual_region

  actual_account="$(read_local_aws_account)" || return 1
  actual_region="$(read_local_aws_region)" || return 1
  assert_aws_target_values "${actual_account}" "${actual_region}"
}

assert_github_target() {
  local actual_repository="$1"
  local actual_ref="$2"
  local actual_account="$3"
  local actual_region="$4"

  assert_exact_target_value 'GitHub repository' "${GITHUB_REPOSITORY}" "${actual_repository}" || return 1
  assert_exact_target_value 'GitHub ref' "${DEPLOY_REF}" "${actual_ref}" || return 1
  assert_aws_target_values "${actual_account}" "${actual_region}"
}

require_command_to_run() {
  if (( $# == 0 )); then
    printf '대상 검사 후 실행할 명령이 없습니다.\n' >&2
    return 2
  fi
}

run_after_local_target_check() {
  require_command_to_run "$@" || return $?
  assert_local_aws_target || return 1
  "$@"
}

run_after_github_target_check() {
  if (( $# < 5 )); then
    printf 'GitHub 대상 네 값과 실행할 명령이 모두 필요합니다.\n' >&2
    return 2
  fi

  local actual_repository="$1"
  local actual_ref="$2"
  local actual_account="$3"
  local actual_region="$4"
  shift 4

  require_command_to_run "$@" || return $?
  assert_github_target \
    "${actual_repository}" \
    "${actual_ref}" \
    "${actual_account}" \
    "${actual_region}" || return 1
  "$@"
}
