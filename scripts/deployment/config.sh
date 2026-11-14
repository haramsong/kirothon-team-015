#!/usr/bin/env bash
set -Eeuo pipefail

readonly EXPECTED_AWS_ACCOUNT='462747820533'
readonly AWS_REGION='ap-northeast-2'
readonly AWS_PROFILE='default'
readonly GITHUB_REPOSITORY='haramsong/kirothon-team-015'
readonly DEPLOY_BRANCH='main'
readonly DEPLOY_REF="refs/heads/${DEPLOY_BRANCH}"
readonly BOOTSTRAP_STACK_NAME='my-own-fridge-github-oidc'
readonly SAM_STACK_NAME='my-own-fridge'
