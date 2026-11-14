#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment/config.sh
source "${SCRIPT_DIR}/config.sh"

readonly CD_WORKFLOW='cd.yml'
readonly DISPATCH_RUN_LOOKUP_ATTEMPTS="${DISPATCH_RUN_LOOKUP_ATTEMPTS:-10}"
readonly DISPATCH_RUN_LOOKUP_DELAY_SECONDS="${DISPATCH_RUN_LOOKUP_DELAY_SECONDS:-2}"

print_manual_dispatch_commands() {
  local expected_sha="$1"

  printf 'GitHub CLI 인증 후 다음 명령을 수동으로 실행하세요:\n' >&2
  printf '  gh workflow run %q --repo %q --ref %q\n' \
    "${CD_WORKFLOW}" "${GITHUB_REPOSITORY}" "${DEPLOY_BRANCH}" >&2
  printf '  gh run list --workflow %q --repo %q --event workflow_dispatch --branch %q --commit %q\n' \
    "${CD_WORKFLOW}" "${GITHUB_REPOSITORY}" "${DEPLOY_BRANCH}" "${expected_sha}" >&2
  printf '  gh run watch <RUN_ID> --repo %q --exit-status\n' \
    "${GITHUB_REPOSITORY}" >&2
  printf '  gh run view <RUN_ID> --repo %q --json conclusion,headSha,url\n' \
    "${GITHUB_REPOSITORY}" >&2
}

require_dispatch_read_commands() {
  if ! command -v git >/dev/null 2>&1; then
    printf '필수 명령을 찾을 수 없습니다: git\n' >&2
    return 1
  fi
}

assert_github_cli_ready() {
  if ! command -v gh >/dev/null 2>&1; then
    printf 'GitHub CLI(gh)를 찾을 수 없어 workflow를 실행하지 않습니다.\n' >&2
    return 1
  fi

  if ! gh auth status --hostname github.com >/dev/null; then
    printf 'GitHub CLI가 github.com에 인증되지 않아 workflow를 실행하지 않습니다.\n' >&2
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

read_origin_main_sha() {
  local remote_line
  local remote_sha
  local remote_ref

  remote_line="$(git ls-remote --exit-code origin "${DEPLOY_REF}")" || return 1
  IFS=$'\t ' read -r remote_sha remote_ref <<< "${remote_line}"

  if [[ ! "${remote_sha}" =~ ^[0-9a-f]{40}$ || "${remote_ref}" != "${DEPLOY_REF}" ]]; then
    printf 'origin/main revision을 정확히 확인할 수 없습니다.\n' >&2
    return 1
  fi
  printf '%s\n' "${remote_sha}"
}

resolve_expected_sha() {
  local requested_sha="${1:-}"
  local origin_sha

  origin_sha="$(read_origin_main_sha)" || return 1
  if [[ -n "${requested_sha}" && "${requested_sha}" != "${origin_sha}" ]]; then
    printf '요청한 revision이 현재 origin/main과 다릅니다 (expected=%s, actual=%s).\n' \
      "${origin_sha}" "${requested_sha}" >&2
    return 1
  fi
  printf '%s\n' "${origin_sha}"
}

list_matching_run_ids() {
  local expected_sha="$1"

  gh run list \
    --workflow "${CD_WORKFLOW}" \
    --repo "${GITHUB_REPOSITORY}" \
    --event workflow_dispatch \
    --branch "${DEPLOY_BRANCH}" \
    --commit "${expected_sha}" \
    --limit 20 \
    --json databaseId \
    --jq '.[].databaseId'
}

run_id_is_in_list() {
  local candidate="$1"
  local existing_ids="$2"
  local existing_id

  while IFS= read -r existing_id; do
    if [[ -n "${existing_id}" && "${candidate}" == "${existing_id}" ]]; then
      return 0
    fi
  done <<< "${existing_ids}"
  return 1
}

find_new_dispatch_run_id() {
  local expected_sha="$1"
  local previous_ids="$2"
  local attempt
  local current_ids
  local candidate

  for (( attempt = 1; attempt <= DISPATCH_RUN_LOOKUP_ATTEMPTS; attempt += 1 )); do
    current_ids="$(list_matching_run_ids "${expected_sha}")" || return 1
    while IFS= read -r candidate; do
      if [[ -n "${candidate}" ]] && ! run_id_is_in_list "${candidate}" "${previous_ids}"; then
        printf '%s\n' "${candidate}"
        return 0
      fi
    done <<< "${current_ids}"
    sleep "${DISPATCH_RUN_LOOKUP_DELAY_SECONDS}"
  done

  printf '새 workflow_dispatch run ID를 찾지 못했습니다.\n' >&2
  return 1
}

read_run_result() {
  local run_id="$1"

  gh run view "${run_id}" \
    --repo "${GITHUB_REPOSITORY}" \
    --json conclusion,headSha,url \
    --jq '[.conclusion, .headSha, .url] | @tsv'
}

watch_and_verify_run() {
  local run_id="$1"
  local expected_sha="$2"
  local watch_status=0
  local result
  local conclusion
  local head_sha
  local url

  gh run watch "${run_id}" \
    --repo "${GITHUB_REPOSITORY}" \
    --exit-status || watch_status=$?

  result="$(read_run_result "${run_id}")" || return 1
  IFS=$'\t' read -r conclusion head_sha url <<< "${result}"

  if [[ "${conclusion}" != 'success' ]]; then
    printf 'CD workflow가 성공하지 않았습니다 (conclusion=%s, url=%s).\n' \
      "${conclusion:-<empty>}" "${url:-<empty>}" >&2
    return 1
  fi
  if (( watch_status != 0 )); then
    printf 'CD workflow 대기 명령이 실패했습니다 (run_id=%s).\n' "${run_id}" >&2
    return "${watch_status}"
  fi
  if [[ "${head_sha}" != "${expected_sha}" ]]; then
    printf 'CD workflow head SHA가 요청 revision과 다릅니다 (expected=%s, actual=%s).\n' \
      "${expected_sha}" "${head_sha:-<empty>}" >&2
    return 1
  fi

  printf 'CD workflow 검증 성공: run_id=%s head_sha=%s url=%s\n' \
    "${run_id}" "${head_sha}" "${url}"
}

main() {
  if (( $# > 1 )); then
    printf '사용법: dispatch-cd.sh [origin-main-sha]\n' >&2
    return 2
  fi

  local expected_sha
  local previous_run_ids
  local run_id

  require_dispatch_read_commands
  "${SCRIPT_DIR}/assert-git-target.sh" assert
  expected_sha="$(resolve_expected_sha "${1:-}")" || return 1

  if ! assert_github_cli_ready; then
    print_manual_dispatch_commands "${expected_sha}"
    return 1
  fi
  assert_github_repository_target

  previous_run_ids="$(list_matching_run_ids "${expected_sha}")" || return 1
  gh workflow run "${CD_WORKFLOW}" \
    --repo "${GITHUB_REPOSITORY}" \
    --ref "${DEPLOY_BRANCH}"
  run_id="$(find_new_dispatch_run_id "${expected_sha}" "${previous_run_ids}")" || return 1
  watch_and_verify_run "${run_id}" "${expected_sha}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
