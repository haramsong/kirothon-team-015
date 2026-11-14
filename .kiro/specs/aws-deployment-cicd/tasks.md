# Implementation Plan: AWS Deployment CI/CD

## Overview

GitHub OIDC 부트스트랩부터 CI, CD, 최초 실제 배포, GitHub repository variables, `workflow_dispatch`, 운영·롤백 문서까지 점진적으로 구현합니다. 각 leaf task는 선행 검증을 통과한 뒤 해당 task 파일만 독립 commit으로 만들고 `origin/main`에 push합니다. 계정 `462747820533`, 리전 `ap-northeast-2`, 저장소 `haramsong/my-own-fridge`, branch `main` 중 하나라도 다르면 AWS 변경과 Git commit/push를 중단합니다.

## Tasks

- [x] 1. 배포 대상 안전 경계를 구현한다
  - [x] 1.1 공통 배포 설정과 AWS·GitHub 대상 검사 스크립트를 작성한다
    - `scripts/deployment/config.sh`에 승인된 account, region, local profile, repository, branch, stack 이름을 readonly 값으로 정의한다.
    - `scripts/deployment/assert-target.sh`에 local STS account/region과 GitHub repository/ref의 정확 일치 검사를 구현한다.
    - 실패 시 AWS 변경 command runner가 호출되지 않도록 함수 경계를 분리하고 모든 shell 입력을 quote한다.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 1.2 승인 대상 검사 property test를 작성한다
    - **Property 1: 승인 대상만 변경 허용**
    - Hypothesis로 account, region, repository, ref 조합을 100개 이상 생성하고 정확히 일치할 때만 변경 runner가 허용되는지 검사한다.
    - **Validates: Requirements 1.2, 1.3, 1.5, 1.6, 1.7, 5.4**

  - [x] 1.3 Git branch·remote·stage 범위 검사 스크립트를 작성한다
    - HTTPS와 SSH remote를 `haramsong/my-own-fridge`로 정규화하고 현재 branch가 `main`인지 검사한다.
    - task별 허용 경로만 stage할 수 있는 allowlist interface를 제공하고 force push 및 hook 우회 flag를 거부한다.
    - 기존 작업 트리의 MVP 스펙 및 designer agent 변경을 stage 대상에서 제외한다.
    - _Requirements: 1.8, 7.2, 7.3, 7.5, 7.7_

  - [ ]* 1.4 Git 변경 범위 property test를 작성한다
    - **Property 5: Git 변경 범위 제한**
    - 임의 branch, remote URL, 변경 경로와 task allowlist를 100개 이상 생성해 승인된 target과 허용 경로만 stage되는지 검사한다.
    - **Validates: Requirements 7.2, 7.3, 7.5**

- [x] 2. OIDC 부트스트랩을 구현한다
  - [x] 2.1 별도 OIDC Bootstrap CloudFormation 템플릿을 작성한다
    - `infra/github-oidc-bootstrap.yaml`에 조건부 GitHub OIDC provider, repository·branch 제한 deployment role, 암호화된 SAM artifact bucket을 정의한다.
    - trust policy의 audience와 subject를 각각 `sts.amazonaws.com`, `repo:haramsong/my-own-fridge:ref:refs/heads/main`으로 정확히 제한한다.
    - 관리자 관리형 policy 없이 Application Stack, SAM artifact, 정적 S3, CloudFront 배포에 필요한 action을 개별 열거한다.
    - role ARN, artifact bucket, provider ARN output을 정의하고 장기 AWS key는 포함하지 않는다.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.12_

  - [x] 2.2 OIDC bootstrap script를 작성한다
    - `scripts/deployment/bootstrap-oidc.sh`에 `default` profile STS 확인, 기존 GitHub provider 0/1개 판정, template validation, stack deploy/wait, output 검증을 순서대로 구현한다.
    - 모든 로컬 AWS 명령에 `--profile default --region ap-northeast-2`를 명시한다.
    - provider 중복, 잘못된 account, template 오류 또는 stack 실패 뒤에는 후속 변경을 실행하지 않는다.
    - _Requirements: 1.2, 1.3, 2.8, 2.9, 2.10_

  - [ ]* 2.3 Bootstrap 템플릿과 스크립트 자동 검사를 작성한다
    - OIDC URL, audience, wildcard 없는 subject, role action allowlist, outputs, artifact bucket 보안 속성을 검사한다.
    - 정상 template과 subject·권한 변조 fixture를 검사하고 shellcheck를 실행한다.
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.11, 2.12_

- [x] 3. CI를 구현한다
  - [x] 3.1 GitHub Actions CI workflow와 runtime 고정 파일을 작성한다
    - `.nvmrc`에 Node 22를 고정하고 `.github/workflows/ci.yml`에 pull request, `main` push, `workflow_dispatch` trigger를 정의한다.
    - Python 3.13, Node 22와 SAM CLI를 설정하고 backend tests, frontend tests, typecheck, production build, `sam validate`, `sam build`를 비대화형으로 실행한다.
    - workflow permission을 `contents: read`로 제한하고 OIDC 및 AWS deployment credential 단계를 넣지 않는다.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [x] 3.2 실행 가능한 로컬 CI 검증 스크립트를 작성한다
    - `scripts/validate-ci.sh`에서 기존 `scripts/verify-all.sh`를 재사용하고 SAM template validate/build와 deployment spec test를 한 번씩 실행한다.
    - watcher와 개발 서버를 시작하지 않고 선행 명령 실패 시 즉시 non-zero로 종료한다.
    - 로컬 SAM/AWS 명령에는 `default` profile과 `ap-northeast-2`를 명시한다.
    - _Requirements: 3.6, 3.7, 3.9, 3.10_

  - [ ]* 3.3 CI workflow와 로컬 validator 테스트를 작성한다
    - YAML 1.2 workflow parser 또는 고정 버전 workflow linter로 trigger, permission, runtime, 검증 command를 확인한다.
    - local validator가 모든 필수 명령을 순서대로 호출하고 실패 exit code를 보존하는지 mock으로 검사한다.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 3.9, 3.10_

- [x] 4. Checkpoint - CI와 OIDC 정적 검증을 완료한다
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. CD 배포 로직을 구현한다
  - [x] 5.1 Application Stack 및 frontend 배포 스크립트를 작성한다
    - `scripts/deployment/deploy-application.sh`에 target guard, Bootstrap output 조회, SAM build/deploy, Application output parser를 구현한다.
    - ApiUrl 주입 frontend build, 대상 stack output S3 sync, CloudFront invalidation을 선행 성공 순서대로 실행하고 S3 `--delete`는 사용하지 않는다.
    - `scripts/deployment/first-deploy.sh`에서 bootstrap 성공 후 application deploy를 호출하고 삭제·force 동작을 포함하지 않는다.
    - 모든 로컬 AWS CLI와 SAM 명령에 `--profile default --region ap-northeast-2`를 명시한다.
    - _Requirements: 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 5.2 필수 stack output property test를 작성한다
    - **Property 3: 필수 stack output 완전성**
    - 임의 CloudFormation output map을 100개 이상 생성해 ApiUrl, StaticBucketName, DistributionId가 모두 non-empty일 때만 frontend deployment context가 생성되는지 검사한다.
    - **Validates: Requirements 4.8, 4.9**

  - [x] 5.3 GitHub Actions CD workflow를 작성한다
    - `.github/workflows/cd.yml`에 `main` push와 `workflow_dispatch`, `contents: read`, `id-token: write`, `cancel-in-progress: false` concurrency를 정의한다.
    - repository/ref 및 variable 검사, OIDC role 수임, STS account/region 검사, 전체 CI 검증, SAM deploy를 순서대로 연결한다.
    - stack outputs 조회 후 `VITE_API_BASE_URL` frontend build, S3 sync, CloudFront invalidation을 정확한 순서로 연결한다.
    - `AWS_ROLE_ARN`, `AWS_REGION`, `SAM_STACK_NAME`, `SAM_ARTIFACT_BUCKET` repository variables만 사용하고 access key secret/file을 만들지 않는다.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, 4.14, 4.16_

  - [ ]* 5.4 CD workflow 정적·단위 테스트를 작성한다
    - trigger, 최소 permissions, concurrency, allowed account, repository/ref guard, 단계 순서와 output gate를 검사한다.
    - access key reference, credential file write, S3 `--delete`, guard 이전 mutating command가 없는지 검사한다.
    - _Requirements: 1.4, 1.5, 1.6, 1.7, 4.1, 4.2, 4.3, 4.5, 4.6, 4.13, 4.14, 4.15, 4.16_

  - [ ]* 5.5 Bootstrap·Application fail-fast property test를 작성한다
    - **Property 2: 배포 단계의 선행 성공과 fail-fast**
    - 임의 최초 실패 위치를 100개 이상 생성해 실행 trace 순서와 실패 후 CloudFormation, SAM, S3, CloudFront 변경 호출 0회를 검사한다.
    - **Validates: Requirements 2.8, 2.9, 4.13, 5.1, 5.3**

- [x] 6. 최초 실제 AWS 배포를 수행하고 기록한다
  - [x] 6.1 승인된 AWS 계정에서 OIDC Bootstrap Stack을 실제 배포한다
    - 먼저 `aws sts get-caller-identity --profile default --region ap-northeast-2` 결과가 `462747820533`인지 확인한다.
    - git remote와 branch 확인 후 bootstrap script를 실행하고 `my-own-fridge-github-oidc` stack, role ARN, artifact bucket, trust policy를 확인한다.
    - 계정, 리전, 저장소 또는 branch가 다르면 배포하지 않고 중단한다.
    - 비밀값을 제외한 검증 결과를 `docs/aws-deployment-validation.md`에 기록한다.
    - _Requirements: 1.2, 1.3, 2.8, 2.9, 2.10, 5.1_

  - [x] 6.2 Application Stack과 frontend를 최초 실제 배포한다
    - `first-deploy.sh` 또는 검증된 개별 script로 `my-own-fridge` SAM stack을 배포하고 세 stack output을 확인한다.
    - ApiUrl을 주입해 frontend를 build하고 stack output의 StaticBucketName에 sync한 뒤 DistributionId를 invalidation한다.
    - 삭제 명령과 S3 `--delete`를 사용하지 않고 배포 revision 및 non-secret output 검증 결과를 validation 문서에 기록한다.
    - _Requirements: 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 5.2, 5.3, 5.4_

  - [ ]* 6.3 최초 배포 smoke test를 실행하고 결과를 기록한다
    - Bootstrap/Application stack status, ApiUrl health response, S3 `index.html`, CloudFront distribution과 invalidation 상태를 대표 1회 확인한다.
    - 기기 ID 또는 재고 내용 같은 사용자 데이터와 자격 증명을 로그나 문서에 기록하지 않는다.
    - _Requirements: 2.10, 4.7, 4.8, 4.11, 4.12_

- [x] 7. GitHub repository 설정과 수동 CD 검증을 구현한다
  - [x] 7.1 GitHub variables 및 workflow dispatch 스크립트를 작성한다
    - `scripts/deployment/configure-github.sh`에서 `gh auth status`와 target을 확인하고 네 repository variable을 allowlist 방식으로 설정·조회한다.
    - `scripts/deployment/dispatch-cd.sh`에서 `cd.yml`, repository, `main` ref를 명시해 실행하고 run conclusion과 head SHA를 검증한다.
    - `gh`가 없거나 인증되지 않으면 변경 전 실패하고 동일한 수동 명령을 표시하며 AWS key 이름은 입력으로 받지 않는다.
    - _Requirements: 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12_

  - [ ]* 7.2 GitHub 설정 스크립트 단위 테스트를 작성한다
    - `gh` 사용 가능/누락/미인증, 잘못된 repo/ref, 변수 누락, workflow 실패와 SHA 불일치 사례를 mock으로 검사한다.
    - 승인된 네 변수 외 설정 호출과 실패 이후 후속 GitHub 변경 호출이 없는지 확인한다.
    - _Requirements: 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12_

  - [x] 7.3 Repository variables를 실제 설정하고 workflow_dispatch를 검증한다
    - 가능하면 `gh variable set/list`, `gh workflow run`, `gh run watch/view`를 사용해 `haramsong/my-own-fridge`의 네 변수를 설정하고 CD를 `main`에서 실행한다.
    - run conclusion이 success이고 head SHA가 dispatch 직전 `origin/main` SHA와 같은지 확인한다.
    - 실제 stack outputs, ApiUrl build, S3 sync와 invalidation 완료를 확인하고 non-secret 결과를 validation 문서에 추가한다.
    - `gh`를 사용할 수 없으면 저장소를 변경하지 않고 수동 명령과 미완료 상태를 기록한다.
    - _Requirements: 4.2, 4.4, 4.5, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12_

- [x] 8. 운영·롤백 문서와 문서 검증을 완성한다
  - [x] 8.1 AWS 배포 운영·롤백 runbook을 작성한다
    - `docs/aws-deployment-runbook.md`에 사전 점검, OIDC bootstrap, 최초 배포, repository variables, 자동·수동 CD, 실패 진단을 작성한다.
    - 이전 검증 revision의 `git revert`와 `workflow_dispatch` 재배포, stack/API/S3/CloudFront 확인, `UPDATE_ROLLBACK_FAILED` 수동 승인 경계를 설명한다.
    - 일반 rollback에서 Bootstrap Stack, IAM role, OIDC provider 삭제를 제외하고 모든 로컬 AWS/SAM 예시에 `default` profile과 region을 포함한다.
    - 비밀값을 workflow, GitHub variables/secrets, 환경 파일, Git 이력에 저장하지 않는 절차를 포함한다.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 8.2 로컬 운영 명령 property test를 작성한다
    - **Property 4: 로컬 운영 명령의 대상 명시**
    - runbook과 local deployment script에서 임의로 추출한 AWS/SAM 변경 명령 모두에 `--profile default`와 `--region ap-northeast-2`가 있는지 100개 이상 생성·검사한다.
    - **Validates: Requirements 5.2, 6.6**

  - [ ]* 8.3 운영 문서와 비밀 방지 정적 검사를 작성한다
    - 필수 section, account/region/repository mismatch 중단, rollback 확인 명령, bootstrap 제외 범위를 검사한다.
    - workflow, template, scripts, docs에서 장기 AWS access key 값과 금지 credential file write pattern을 검사한다.
    - _Requirements: 2.12, 4.16, 5.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.7, 6.8_

- [-] 9. Final checkpoint - 전체 자동 검증과 배포 기록을 확인한다
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- `*`가 붙은 테스트 sub-task는 빠른 MVP 진행 시 선택적으로 건너뛸 수 있습니다.
- Property test는 각 속성당 최소 100회 실행하고 `Feature: aws-deployment-cicd, Property N: ...` annotation을 포함합니다.
- 모든 non-checkpoint leaf task는 시작 전에 `main`과 `origin=haramsong/my-own-fridge`를 확인합니다. 완료 후 task 관련 파일만 stage하여 Independent_Commit을 만들고 `git push origin main`을 수행합니다.
- 기존 작업 트리의 `.kiro/specs/refrigerator-management-mvp/tasks.md`, `.kiro/specs/refrigerator-management-mvp/tasks.meta.json`, `.kiro/agents/designer.json`은 이 계획의 commit에 포함하지 않습니다.
- commit 또는 push가 실패하면 다음 task로 진행하지 않습니다. `--amend`, `--no-verify`, force push는 사용하지 않습니다.
- 실제 AWS/GitHub 변경 task는 승인된 계정, 리전, 저장소, branch가 모두 일치할 때만 실행하며 stack, bucket, role 또는 provider 삭제를 수행하지 않습니다.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4"] },
    { "id": 4, "tasks": ["2.1"] },
    { "id": 5, "tasks": ["2.2"] },
    { "id": 6, "tasks": ["2.3"] },
    { "id": 7, "tasks": ["3.1"] },
    { "id": 8, "tasks": ["3.2"] },
    { "id": 9, "tasks": ["3.3"] },
    { "id": 10, "tasks": ["5.1"] },
    { "id": 11, "tasks": ["5.2"] },
    { "id": 12, "tasks": ["5.3"] },
    { "id": 13, "tasks": ["5.4"] },
    { "id": 14, "tasks": ["5.5"] },
    { "id": 15, "tasks": ["6.1"] },
    { "id": 16, "tasks": ["6.2"] },
    { "id": 17, "tasks": ["6.3"] },
    { "id": 18, "tasks": ["7.1"] },
    { "id": 19, "tasks": ["7.2"] },
    { "id": 20, "tasks": ["7.3"] },
    { "id": 21, "tasks": ["8.1"] },
    { "id": 22, "tasks": ["8.2"] },
    { "id": 23, "tasks": ["8.3"] }
  ]
}
```
