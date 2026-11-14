#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly APPLICATION_TEMPLATE="${ROOT_DIR}/template.yaml"
readonly BUILT_APPLICATION_TEMPLATE="${ROOT_DIR}/.aws-sam/build/template.yaml"
readonly FRONTEND_DIRECTORY="${ROOT_DIR}/frontend"
readonly FRONTEND_BUILD_DIRECTORY="${FRONTEND_DIRECTORY}/dist"

# shellcheck source=scripts/deployment/assert-target.sh
source "${SCRIPT_DIR}/assert-target.sh"

require_application_deploy_commands() {
  local command_name
  for command_name in aws git sam npm; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      printf '필수 명령을 찾을 수 없습니다: %s\n' "${command_name}" >&2
      return 1
    fi
  done
}

read_bootstrap_artifact_bucket() {
  aws cloudformation describe-stacks \
    --stack-name "${BOOTSTRAP_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='SamArtifactBucketName'].OutputValue | [0]" \
    --output text \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

validate_bucket_name() {
  local label="$1"
  local bucket_name="$2"

  if [[ -z "${bucket_name}" || "${bucket_name}" == 'None' || "${bucket_name}" == 'null' \
    || ! "${bucket_name}" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]]; then
    printf '%s 이름 형식이 올바르지 않습니다: %s\n' \
      "${label}" "${bucket_name:-<empty>}" >&2
    return 1
  fi
}

read_and_validate_bootstrap_artifact_bucket() {
  local artifact_bucket

  artifact_bucket="$(read_bootstrap_artifact_bucket)" || return 1
  validate_bucket_name 'SAM artifact bucket' "${artifact_bucket}" || return 1
  printf '%s\n' "${artifact_bucket}"
}

build_application() {
  sam build \
    --template-file "${APPLICATION_TEMPLATE}" \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

deploy_application_stack() {
  local artifact_bucket="$1"

  sam deploy \
    --template-file "${BUILT_APPLICATION_TEMPLATE}" \
    --stack-name "${SAM_STACK_NAME}" \
    --s3-bucket "${artifact_bucket}" \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

read_application_output_rows() {
  aws cloudformation describe-stacks \
    --stack-name "${SAM_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl' || OutputKey=='StaticBucketName' || OutputKey=='DistributionId'].[OutputKey,OutputValue]" \
    --output text \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

require_non_empty_output() {
  local output_key="$1"
  local output_value="$2"

  if [[ -z "${output_value}" || "${output_value}" == 'None' || "${output_value}" == 'null' ]]; then
    printf 'Application Stack 필수 output이 없거나 비어 있습니다: %s\n' \
      "${output_key}" >&2
    return 1
  fi
}

parse_required_application_outputs() {
  local output_rows="$1"
  local output_key
  local output_value
  local api_url=''
  local static_bucket=''
  local distribution_id=''

  while IFS=$'\t' read -r output_key output_value; do
    case "${output_key}" in
      ApiUrl) api_url="${output_value}" ;;
      StaticBucketName) static_bucket="${output_value}" ;;
      DistributionId) distribution_id="${output_value}" ;;
      '') ;;
    esac
  done <<< "${output_rows}"

  require_non_empty_output 'ApiUrl' "${api_url}" || return 1
  require_non_empty_output 'StaticBucketName' "${static_bucket}" || return 1
  require_non_empty_output 'DistributionId' "${distribution_id}" || return 1

  if [[ ! "${api_url}" =~ ^https://[^[:space:]]+$ ]]; then
    printf 'ApiUrl 형식이 올바르지 않습니다: %s\n' "${api_url}" >&2
    return 1
  fi
  validate_bucket_name 'StaticBucketName' "${static_bucket}" || return 1
  if [[ ! "${distribution_id}" =~ ^[A-Z0-9]{8,32}$ ]]; then
    printf 'DistributionId 형식이 올바르지 않습니다: %s\n' \
      "${distribution_id}" >&2
    return 1
  fi

  printf '%s\t%s\t%s\n' "${api_url%/}" "${static_bucket}" "${distribution_id}"
}

read_required_application_outputs() {
  local output_rows

  output_rows="$(read_application_output_rows)" || return 1
  parse_required_application_outputs "${output_rows}"
}

build_frontend() {
  local api_url="$1"

  VITE_API_BASE_URL="${api_url}" npm --prefix "${FRONTEND_DIRECTORY}" run build
}

sync_frontend() {
  local static_bucket="$1"

  aws s3 sync \
    "${FRONTEND_BUILD_DIRECTORY}" \
    "s3://${static_bucket}" \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}"
}

invalidate_frontend_cache() {
  local distribution_id="$1"

  aws cloudfront create-invalidation \
    --distribution-id "${distribution_id}" \
    --paths '/*' \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}" \
    >/dev/null
}

main() {
  if (( $# != 0 )); then
    printf '이 스크립트는 인자를 받지 않습니다.\n' >&2
    return 2
  fi

  local artifact_bucket
  local application_outputs
  local api_url
  local static_bucket
  local distribution_id

  require_application_deploy_commands
  "${SCRIPT_DIR}/assert-git-target.sh" assert
  assert_local_aws_target

  artifact_bucket="$(read_and_validate_bootstrap_artifact_bucket)"
  build_application
  deploy_application_stack "${artifact_bucket}"

  application_outputs="$(read_required_application_outputs)"
  IFS=$'\t' read -r api_url static_bucket distribution_id <<< "${application_outputs}"

  build_frontend "${api_url}"
  sync_frontend "${static_bucket}"
  invalidate_frontend_cache "${distribution_id}"

  printf 'Application Stack 및 frontend 배포가 완료되었습니다.\n'
  printf 'ApiUrl=%s\n' "${api_url}"
  printf 'StaticBucketName=%s\n' "${static_bucket}"
  printf 'DistributionId=%s\n' "${distribution_id}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
