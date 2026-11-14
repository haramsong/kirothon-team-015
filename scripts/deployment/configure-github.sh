#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment/assert-target.sh
source "${SCRIPT_DIR}/assert-target.sh"

readonly -a REPOSITORY_VARIABLE_ALLOWLIST=(
  'AWS_ROLE_ARN'
  'AWS_REGION'
  'SAM_STACK_NAME'
  'SAM_ARTIFACT_BUCKET'
)

print_manual_variable_commands() {
  local role_arn="$1"
  local artifact_bucket="$2"

  printf 'GitHub CLI 인증 후 다음 명령을 수동으로 실행하세요:\n' >&2
  printf '  gh variable set AWS_ROLE_ARN --repo %q --body %q\n' \
    "${GITHUB_REPOSITORY}" "${role_arn}" >&2
  printf '  gh variable set AWS_REGION --repo %q --body %q\n' \
    "${GITHUB_REPOSITORY}" "${AWS_REGION}" >&2
  printf '  gh variable set SAM_STACK_NAME --repo %q --body %q\n' \
    "${GITHUB_REPOSITORY}" "${SAM_STACK_NAME}" >&2
  printf '  gh variable set SAM_ARTIFACT_BUCKET --repo %q --body %q\n' \
    "${GITHUB_REPOSITORY}" "${artifact_bucket}" >&2
  printf '  gh variable list --repo %q --json name,value\n' \
    "${GITHUB_REPOSITORY}" >&2
}

require_local_read_commands() {
  local command_name
  for command_name in aws git; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      printf '필수 명령을 찾을 수 없습니다: %s\n' "${command_name}" >&2
      return 1
    fi
  done
}

read_bootstrap_output() {
  local output_key="$1"

  aws cloudformation describe-stacks \
    --stack-name "${BOOTSTRAP_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue | [0]" \
    --output text \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

read_and_validate_bootstrap_outputs() {
  local role_arn
  local artifact_bucket

  role_arn="$(read_bootstrap_output 'GitHubDeploymentRoleArn')" || return 1
  artifact_bucket="$(read_bootstrap_output 'SamArtifactBucketName')" || return 1

  if [[ ! "${role_arn}" =~ ^arn:aws:iam::${EXPECTED_AWS_ACCOUNT}:role/my-own-fridge-github-deploy$ ]]; then
    printf 'Bootstrap Role ARN 형식이 올바르지 않습니다: %s\n' \
      "${role_arn:-<empty>}" >&2
    return 1
  fi

  if [[ "${artifact_bucket}" == 'None' || "${artifact_bucket}" == 'null' \
    || ! "${artifact_bucket}" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]]; then
    printf 'SAM artifact bucket 이름 형식이 올바르지 않습니다: %s\n' \
      "${artifact_bucket:-<empty>}" >&2
    return 1
  fi

  printf '%s\t%s\n' "${role_arn}" "${artifact_bucket}"
}

is_allowed_repository_variable() {
  local candidate="$1"
  local allowed_name

  for allowed_name in "${REPOSITORY_VARIABLE_ALLOWLIST[@]}"; do
    if [[ "${candidate}" == "${allowed_name}" ]]; then
      return 0
    fi
  done
  return 1
}

set_repository_variable() {
  local name="$1"
  local value="$2"

  if ! is_allowed_repository_variable "${name}"; then
    printf '허용되지 않은 repository variable 이름입니다: %s\n' "${name}" >&2
    return 1
  fi
  if [[ -z "${value}" ]]; then
    printf 'repository variable 값이 비어 있습니다: %s\n' "${name}" >&2
    return 1
  fi

  gh variable set "${name}" \
    --repo "${GITHUB_REPOSITORY}" \
    --body "${value}"
}

assert_github_cli_ready() {
  if ! command -v gh >/dev/null 2>&1; then
    printf 'GitHub CLI(gh)를 찾을 수 없어 repository variables를 변경하지 않습니다.\n' >&2
    return 1
  fi

  if ! gh auth status --hostname github.com >/dev/null; then
    printf 'GitHub CLI가 github.com에 인증되지 않아 repository variables를 변경하지 않습니다.\n' >&2
    return 1
  fi
}

assert_github_repository_target() {
  local actual_repository

  actual_repository="$(gh repo view "${GITHUB_REPOSITORY}" \
    --json nameWithOwner \
    --jq '.nameWithOwner')" || return 1

  if [[ "${actual_repository}" != "${GITHUB_REPOSITORY}" ]]; then
    printf 'GitHub 저장소가 승인된 값과 다릅니다 (expected=%s, actual=%s).\n' \
      "${GITHUB_REPOSITORY}" "${actual_repository:-<empty>}" >&2
    return 1
  fi
}

read_repository_variables() {
  gh variable list \
    --repo "${GITHUB_REPOSITORY}" \
    --json name,value \
    --jq '.[] | [.name, .value] | @tsv'
}

find_variable_value() {
  local variable_list="$1"
  local expected_name="$2"
  local name
  local value

  while IFS=$'\t' read -r name value; do
    if [[ "${name}" == "${expected_name}" ]]; then
      printf '%s\n' "${value}"
      return 0
    fi
  done <<< "${variable_list}"
  return 1
}

assert_repository_variable_value() {
  local variable_list="$1"
  local expected_name="$2"
  local expected_value="$3"
  local actual_value

  actual_value="$(find_variable_value "${variable_list}" "${expected_name}")" || {
    printf '필수 repository variable이 없습니다: %s\n' "${expected_name}" >&2
    return 1
  }

  if [[ "${actual_value}" != "${expected_value}" ]]; then
    printf 'repository variable 값이 다릅니다: %s\n' "${expected_name}" >&2
    return 1
  fi
}

configure_and_verify_variables() {
  local role_arn="$1"
  local artifact_bucket="$2"
  local variable_list

  set_repository_variable 'AWS_ROLE_ARN' "${role_arn}"
  set_repository_variable 'AWS_REGION' "${AWS_REGION}"
  set_repository_variable 'SAM_STACK_NAME' "${SAM_STACK_NAME}"
  set_repository_variable 'SAM_ARTIFACT_BUCKET' "${artifact_bucket}"

  variable_list="$(read_repository_variables)" || return 1
  assert_repository_variable_value "${variable_list}" 'AWS_ROLE_ARN' "${role_arn}"
  assert_repository_variable_value "${variable_list}" 'AWS_REGION' "${AWS_REGION}"
  assert_repository_variable_value "${variable_list}" 'SAM_STACK_NAME' "${SAM_STACK_NAME}"
  assert_repository_variable_value "${variable_list}" 'SAM_ARTIFACT_BUCKET' "${artifact_bucket}"

  printf '승인된 repository variables 네 개를 설정하고 조회 결과를 검증했습니다.\n'
}

main() {
  if (( $# != 0 )); then
    printf '이 스크립트는 variable 이름이나 값을 인자로 받지 않습니다.\n' >&2
    return 2
  fi

  local outputs
  local role_arn
  local artifact_bucket

  require_local_read_commands
  "${SCRIPT_DIR}/assert-git-target.sh" assert
  assert_local_aws_target
  outputs="$(read_and_validate_bootstrap_outputs)" || return 1
  IFS=$'\t' read -r role_arn artifact_bucket <<< "${outputs}"

  if ! assert_github_cli_ready; then
    print_manual_variable_commands "${role_arn}" "${artifact_bucket}"
    return 1
  fi
  assert_github_repository_target
  configure_and_verify_variables "${role_arn}" "${artifact_bucket}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
