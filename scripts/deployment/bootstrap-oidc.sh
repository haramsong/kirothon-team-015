#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly BOOTSTRAP_TEMPLATE="${ROOT_DIR}/infra/github-oidc-bootstrap.yaml"
readonly GITHUB_OIDC_URL='token.actions.githubusercontent.com'

# shellcheck source=scripts/deployment/assert-target.sh
source "${SCRIPT_DIR}/assert-target.sh"

require_bootstrap_commands() {
  local command_name
  for command_name in aws git; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      printf '필수 명령을 찾을 수 없습니다: %s\n' "${command_name}" >&2
      return 1
    fi
  done
}

find_existing_github_oidc_provider() {
  local provider_list
  local provider_arn
  local provider_url
  local -a matching_providers=()

  provider_list="$(aws iam list-open-id-connect-providers \
    --query 'OpenIDConnectProviderList[].Arn' \
    --output text \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}")" || return 1

  for provider_arn in ${provider_list}; do
    provider_url="$(aws iam get-open-id-connect-provider \
      --open-id-connect-provider-arn "${provider_arn}" \
      --query 'Url' \
      --output text \
      --profile "${AWS_PROFILE}" \
      --region "${AWS_REGION}")" || return 1

    if [[ "${provider_url}" == "${GITHUB_OIDC_URL}" ]]; then
      matching_providers+=("${provider_arn}")
    fi
  done

  if (( ${#matching_providers[@]} > 1 )); then
    printf 'GitHub Actions OIDC 공급자가 여러 개 발견되어 중단합니다:\n' >&2
    printf '  %s\n' "${matching_providers[@]}" >&2
    return 1
  fi

  if (( ${#matching_providers[@]} == 1 )); then
    provider_arn="${matching_providers[0]}"
    if [[ ! "${provider_arn}" =~ ^arn:aws:iam::${EXPECTED_AWS_ACCOUNT}:oidc-provider/token\.actions\.githubusercontent\.com$ ]]; then
      printf '기존 GitHub OIDC 공급자 ARN이 승인 계정 또는 URL과 다릅니다: %s\n' \
        "${provider_arn}" >&2
      return 1
    fi
    printf '%s\n' "${provider_arn}"
  fi
}

validate_bootstrap_template() {
  aws cloudformation validate-template \
    --template-body "file://${BOOTSTRAP_TEMPLATE}" \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}" \
    >/dev/null
}

deploy_bootstrap_stack() {
  local existing_provider_arn="$1"

  aws cloudformation deploy \
    --template-file "${BOOTSTRAP_TEMPLATE}" \
    --stack-name "${BOOTSTRAP_STACK_NAME}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      "GitHubOwner=${GITHUB_REPOSITORY%%/*}" \
      "GitHubRepository=${GITHUB_REPOSITORY##*/}" \
      "GitHubBranch=${DEPLOY_BRANCH}" \
      "ApplicationStackName=${SAM_STACK_NAME}" \
      "ExistingGitHubOidcProviderArn=${existing_provider_arn}" \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

wait_for_bootstrap_stack() {
  aws cloudformation wait stack-exists \
    --stack-name "${BOOTSTRAP_STACK_NAME}" \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

read_stack_output() {
  local output_key="$1"

  aws cloudformation describe-stacks \
    --stack-name "${BOOTSTRAP_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue | [0]" \
    --output text \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

validate_and_print_bootstrap_outputs() {
  local role_arn
  local artifact_bucket

  role_arn="$(read_stack_output 'GitHubDeploymentRoleArn')" || return 1
  artifact_bucket="$(read_stack_output 'SamArtifactBucketName')" || return 1

  if [[ ! "${role_arn}" =~ ^arn:aws:iam::${EXPECTED_AWS_ACCOUNT}:role/my-own-fridge-github-deploy$ ]]; then
    printf 'Bootstrap Role ARN 형식이 올바르지 않습니다: %s\n' "${role_arn:-<empty>}" >&2
    return 1
  fi

  if [[ "${artifact_bucket}" == 'None' || "${artifact_bucket}" == 'null' \
    || ! "${artifact_bucket}" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]]; then
    printf 'SAM artifact bucket 이름 형식이 올바르지 않습니다: %s\n' \
      "${artifact_bucket:-<empty>}" >&2
    return 1
  fi

  printf '{\n'
  printf '  "GitHubDeploymentRoleArn": "%s",\n' "${role_arn}"
  printf '  "SamArtifactBucketName": "%s"\n' "${artifact_bucket}"
  printf '}\n'
}

main() {
  local existing_provider_arn

  require_bootstrap_commands
  "${SCRIPT_DIR}/assert-git-target.sh" assert
  assert_local_aws_target

  existing_provider_arn="$(find_existing_github_oidc_provider)"
  validate_bootstrap_template
  deploy_bootstrap_stack "${existing_provider_arn}"
  wait_for_bootstrap_stack
  validate_and_print_bootstrap_outputs
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
