#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/deployment/config.sh
source "${SCRIPT_DIR}/config.sh"

readonly -a PROTECTED_STAGE_PATHS=(
  '.kiro/specs/refrigerator-management-mvp'
  '.kiro/agents/designer.json'
)

fail_git_check() {
  printf 'Git 안전 검사 실패: %s\n' "$1" >&2
  return 1
}

normalize_github_remote() {
  local remote_url="$1"
  local repository_path=''

  case "${remote_url}" in
    https://github.com/*)
      repository_path="${remote_url#https://github.com/}"
      ;;
    git@github.com:*)
      repository_path="${remote_url#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      repository_path="${remote_url#ssh://git@github.com/}"
      ;;
    *)
      fail_git_check "지원하지 않는 origin URL입니다: ${remote_url:-<empty>}"
      return 1
      ;;
  esac

  repository_path="${repository_path%/}"
  repository_path="${repository_path%.git}"

  if [[ ! "${repository_path}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    fail_git_check "origin URL에서 저장소를 정확히 식별할 수 없습니다: ${remote_url}"
    return 1
  fi

  printf '%s\n' "${repository_path}"
}

assert_git_target_values() {
  local actual_branch="$1"
  local actual_remote="$2"
  local actual_repository

  if [[ "${actual_branch}" != "${DEPLOY_BRANCH}" ]]; then
    fail_git_check "branch가 승인된 값과 다릅니다 (expected=${DEPLOY_BRANCH}, actual=${actual_branch:-<detached>})"
    return 1
  fi

  actual_repository="$(normalize_github_remote "${actual_remote}")" || return 1
  if [[ "${actual_repository}" != "${GITHUB_REPOSITORY}" ]]; then
    fail_git_check "origin 저장소가 승인된 값과 다릅니다 (expected=${GITHUB_REPOSITORY}, actual=${actual_repository})"
    return 1
  fi
}

assert_current_git_target() {
  local actual_branch
  local actual_remote

  actual_branch="$(git branch --show-current)" || return 1
  actual_remote="$(git remote get-url origin)" || return 1
  assert_git_target_values "${actual_branch}" "${actual_remote}"
}

is_protected_stage_path() {
  local path="$1"
  local protected_path

  for protected_path in "${PROTECTED_STAGE_PATHS[@]}"; do
    if [[ "${path}" == "${protected_path}" || "${path}" == "${protected_path}/"* ]]; then
      return 0
    fi
  done
  return 1
}

validate_stage_path() {
  local path="$1"

  if [[ -z "${path}" || "${path}" == /* || "${path}" == '.' || "${path}" == '..' \
    || "${path}" == ../* || "${path}" == */../* || "${path}" == */.. \
    || "${path}" == :* || "${path}" == *'*'* || "${path}" == *'?'* || "${path}" == *'['* ]]; then
    fail_git_check "stage 경로는 저장소 기준의 정확한 파일 경로여야 합니다: ${path:-<empty>}"
    return 1
  fi

  if is_protected_stage_path "${path}"; then
    fail_git_check "이 작업에서 stage가 금지된 경로입니다: ${path}"
    return 1
  fi
}

path_is_allowlisted() {
  local candidate="$1"
  shift
  local allowed_path

  for allowed_path in "$@"; do
    if [[ "${candidate}" == "${allowed_path}" ]]; then
      return 0
    fi
  done
  return 1
}

assert_staged_paths_allowed() {
  if (( $# == 0 )); then
    fail_git_check 'task allowlist가 비어 있습니다.'
    return 2
  fi

  local staged_path
  while IFS= read -r -d '' staged_path; do
    if ! path_is_allowlisted "${staged_path}" "$@"; then
      fail_git_check "allowlist 밖의 파일이 이미 stage되어 있습니다: ${staged_path}"
      return 1
    fi
  done < <(git diff --cached --name-only --diff-filter=ACDMRTUXB -z)
}

stage_task_paths() {
  if (( $# == 0 )); then
    fail_git_check 'stage할 task 파일 경로가 필요합니다.'
    return 2
  fi

  assert_current_git_target || return 1

  local repository_root
  repository_root="$(git rev-parse --show-toplevel)" || return 1

  local path
  for path in "$@"; do
    validate_stage_path "${path}" || return 1
    if [[ "${path}" == */ || -d "${repository_root}/${path}" ]]; then
      fail_git_check "stage allowlist에는 디렉터리가 아닌 정확한 파일 경로만 사용할 수 있습니다: ${path}"
      return 1
    fi
  done

  assert_staged_paths_allowed "$@" || return 1
  git -C "${repository_root}" add -- "$@"
  assert_staged_paths_allowed "$@"
}

assert_safe_git_flags() {
  local argument

  for argument in "$@"; do
    case "${argument}" in
      --force|--force=*|--force-with-lease|--force-with-lease=*|--force-if-includes|-f)
        fail_git_check "force push 옵션을 사용할 수 없습니다: ${argument}"
        return 1
        ;;
      --no-verify|-n)
        fail_git_check "Git hook 우회 옵션을 사용할 수 없습니다: ${argument}"
        return 1
        ;;
      +*)
        fail_git_check "강제 refspec을 사용할 수 없습니다: ${argument}"
        return 1
        ;;
    esac
  done
}

safe_git_commit() {
  if (( $# == 0 )); then
    fail_git_check 'commit 옵션과 메시지가 필요합니다.'
    return 2
  fi

  assert_current_git_target || return 1
  assert_safe_git_flags "$@" || return 1
  git commit "$@"
}

safe_git_push() {
  if (( $# != 0 )); then
    assert_safe_git_flags "$@" || return 1
    fail_git_check 'push 대상은 origin main으로 고정되어 있어 추가 인자를 받을 수 없습니다.'
    return 2
  fi

  assert_current_git_target || return 1
  git push origin "${DEPLOY_BRANCH}"
}

print_usage() {
  cat <<'EOF'
사용법:
  assert-git-target.sh assert
  assert-git-target.sh stage <task-file> [<task-file> ...]
  assert-git-target.sh check-flags [<git-option> ...]
  assert-git-target.sh commit <git-commit-option> ...
  assert-git-target.sh push
EOF
}

main() {
  local command="${1:-}"
  if (( $# > 0 )); then
    shift
  fi

  case "${command}" in
    assert)
      (( $# == 0 )) || { print_usage >&2; return 2; }
      assert_current_git_target
      ;;
    stage)
      stage_task_paths "$@"
      ;;
    check-flags)
      assert_safe_git_flags "$@"
      ;;
    commit)
      safe_git_commit "$@"
      ;;
    push)
      safe_git_push "$@"
      ;;
    *)
      print_usage >&2
      return 2
      ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
