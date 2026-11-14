#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/deployment/assert-target.sh
source "${SCRIPT_DIR}/assert-target.sh"

run_bootstrap_deploy() {
  "${SCRIPT_DIR}/bootstrap-oidc.sh"
}

run_application_deploy() {
  "${SCRIPT_DIR}/deploy-application.sh"
}

main() {
  if (( $# != 0 )); then
    printf '최초 배포 스크립트는 인자를 받지 않습니다.\n' >&2
    return 2
  fi

  printf '최초 배포 대상: account=%s, region=%s, repository=%s, branch=%s\n' \
    "${EXPECTED_AWS_ACCOUNT}" "${AWS_REGION}" "${GITHUB_REPOSITORY}" "${DEPLOY_BRANCH}"

  "${SCRIPT_DIR}/assert-git-target.sh" assert
  assert_local_aws_target
  run_bootstrap_deploy
  run_application_deploy
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
