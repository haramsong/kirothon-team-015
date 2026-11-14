# AWS 배포 검증 기록

## Task 1.1: 공통 배포 설정과 대상 검사

- 승인 AWS 계정: `462747820533`
- 승인 리전: `ap-northeast-2`
- 로컬 AWS 프로파일: `default`
- 승인 저장소: `haramsong/my-own-fridge`
- 승인 브랜치와 ref: `main`, `refs/heads/main`
- Bootstrap Stack: `my-own-fridge-github-oidc`
- Application Stack: `my-own-fridge`

### 구현 결과

- `scripts/deployment/config.sh`에 승인 대상과 stack 이름을 읽기 전용 상수로 정의했습니다.
- `scripts/deployment/assert-target.sh`에서 로컬 STS 계정, configured region, GitHub repository/ref, OIDC 수임 계정/리전을 정확히 비교합니다.
- 로컬 검사는 `aws sts get-caller-identity --profile default --region ap-northeast-2`와 같은 고정 프로파일·리전을 사용합니다.
- 대상 검사를 통과한 뒤에만 전달받은 변경 명령을 호출하도록 검사 함수와 실행 함수의 경계를 분리했습니다.

### 검증 결과

| 검사 | 결과 |
| --- | --- |
| `bash -n` 셸 구문 검사 | 통과 |
| 대상 검사 단위 테스트 | 7개 통과 |
| 실제 로컬 STS 계정 및 configured region 검사 | 통과 |
| 현재 Git branch `main` | 일치 |
| `origin` 저장소 `haramsong/my-own-fridge` | 일치 |
| `shellcheck` | 로컬 미설치로 미실행 |

실제 로컬 검사는 읽기 전용 AWS 조회만 수행했으며 CloudFormation, SAM, S3 또는 CloudFront 변경 명령은 실행하지 않았습니다. 장기 AWS 액세스 키나 비밀값은 이 문서에 기록하지 않았습니다.

## Task 1.3: Git branch·remote·stage 범위 검사

### 구현 결과

- `scripts/deployment/assert-git-target.sh`에서 HTTPS, SCP 형식 SSH, `ssh://` 형식 GitHub origin을 `owner/repository`로 정규화하고 `haramsong/my-own-fridge`와 정확히 비교합니다.
- 현재 branch가 `main`이고 origin이 승인된 저장소일 때만 stage, commit, push 인터페이스를 실행합니다.
- `stage_task_paths`는 저장소 기준의 정확한 파일 경로만 allowlist로 받고, 기존 staged 파일까지 allowlist 안에 있는지 검사한 후 `git add --`를 실행합니다. 디렉터리, 절대·상위 경로, glob, Git pathspec은 거부합니다.
- `.kiro/specs/refrigerator-management-mvp` 아래 전체 경로와 `.kiro/agents/designer.json`은 allowlist에 넣어도 stage할 수 없습니다.
- `--force`, `--force-with-lease`, 강제 refspec, `--no-verify`, `-n`을 거부하며 push 대상은 `origin main`으로 고정했습니다.

### 검증 결과

| 검사 | 결과 |
| --- | --- |
| `bash -n scripts/deployment/assert-git-target.sh` | 통과 |
| Git 대상·stage 범위 단위 테스트와 기존 대상 검사 | 31개 통과 |
| 현재 branch | `main` 일치 |
| 현재 origin | `https://github.com/haramsong/my-own-fridge.git` 일치 |
| 기존 MVP 스펙 및 agent 변경 보존 | stage 대상에서 제외됨 |

이 작업은 AWS 변경 명령을 실행하지 않았습니다. 이후 로컬 AWS 명령이 필요한 작업은 `default` 프로파일과 `ap-northeast-2` 리전을 사용합니다.

## Task 2.1: 별도 OIDC Bootstrap CloudFormation 템플릿

### 구현 결과

- `infra/github-oidc-bootstrap.yaml`에 기존 GitHub Actions OIDC 공급자 ARN이 없을 때만 공급자를 생성하는 조건을 정의했습니다.
- OIDC 공급자의 URL은 `https://token.actions.githubusercontent.com`, client ID는 `sts.amazonaws.com`으로 고정했습니다.
- 배포 역할의 신뢰 정책은 audience를 `sts.amazonaws.com`, subject를 `repo:haramsong/my-own-fridge:ref:refs/heads/main`과 정확히 일치하도록 제한했습니다.
- SAM 아티팩트 버킷에 AES-256 서버 측 암호화, 모든 퍼블릭 액세스 차단, Bucket Owner Enforced, 버전 관리를 적용하고 삭제·교체 시 보존하도록 구성했습니다.
- 관리자 관리형 정책 없이 Application Stack, SAM 아티팩트, Lambda, DynamoDB, HTTP API, 정적 S3와 CloudFront 배포에 필요한 작업을 inline policy에 개별 열거했습니다.
- `GitHubDeploymentRoleArn`, `SamArtifactBucketName`, `OidcProviderArn` output을 정의했습니다.
- 장기 AWS 액세스 키, 비밀 액세스 키 또는 자격 증명 파일 설정은 포함하지 않았습니다.

### 검증 결과

| 검사 | 명령 | 결과 |
| --- | --- | --- |
| 승인 계정 확인 | `aws sts get-caller-identity --query Account --output text --profile default --region ap-northeast-2` | `462747820533` 일치 |
| 필수 신뢰 조건·output·금지 패턴 정적 검사 | 로컬 Python 정적 검사 | 통과 |
| CloudFormation 원격 템플릿 검증 | `aws cloudformation validate-template --template-body file://infra/github-oidc-bootstrap.yaml --profile default --region ap-northeast-2` | 통과 |
| SAM 기본 검증 | `sam validate --template-file infra/github-oidc-bootstrap.yaml --profile default --region ap-northeast-2` | 통과 |
| SAM lint 검증 | `sam validate --lint --template-file infra/github-oidc-bootstrap.yaml --profile default --region ap-northeast-2` | 통과 |

검증에서는 STS와 CloudFormation의 읽기 전용 API만 호출했으며 stack, IAM 역할, OIDC 공급자 또는 S3 버킷을 생성하거나 변경하지 않았습니다. 모든 로컬 AWS와 SAM 명령은 `default` 프로파일과 `ap-northeast-2` 리전을 명시했습니다.
## Task 2.2: OIDC Bootstrap 실행 스크립트

### 구현 결과

- `scripts/deployment/bootstrap-oidc.sh`는 Git branch와 origin을 먼저 검사한 뒤 `aws sts get-caller-identity --profile default --region ap-northeast-2`와 configured region으로 승인 계정을 확인합니다.
- IAM의 OIDC 공급자를 읽기 전용으로 조회하여 `token.actions.githubusercontent.com` 공급자가 없으면 새 공급자를 생성하도록 빈 parameter를 전달하고, 하나면 승인 계정 ARN만 재사용합니다. 둘 이상이거나 ARN 형식이 다르면 template 검증과 stack 배포 전에 중단합니다.
- 대상 및 공급자 검사를 통과한 경우에만 CloudFormation template 검증, `my-own-fridge-github-oidc` stack 배포, stack waiter, output 조회를 순서대로 실행합니다.
- `GitHubDeploymentRoleArn`은 승인 계정과 역할 이름을, `SamArtifactBucketName`은 S3 bucket 이름 형식을 검증한 뒤 비밀이 아닌 두 output만 JSON으로 출력합니다.
- 모든 AWS CLI 호출에 `--profile default --region ap-northeast-2`를 명시했으며, 장기 AWS access key 또는 credential file을 사용하지 않습니다.

### 검증 결과

| 검사 | 결과 |
| --- | --- |
| `bash -n scripts/deployment/bootstrap-oidc.sh` | 통과 |
| 기존 대상 검사 및 bootstrap 단위 테스트 | 13개 통과 |
| 잘못된 AWS account 뒤 후속 호출 차단 | 통과 |
| OIDC 공급자 중복 뒤 template/deploy 차단 | 통과 |
| template 검증 실패 뒤 stack 조회/deploy 차단 | 통과 |
| deploy 또는 waiter 실패 뒤 output 조회 차단 | 통과 |
| 모든 fake AWS 호출의 profile/region 고정 검사 | `default`, `ap-northeast-2` 일치 |

이 Task에서는 fake `aws`·`git` 실행 파일을 사용한 단위 테스트와 셸 구문 검사만 수행했습니다. 실제 AWS API 호출, CloudFormation stack 배포, IAM 역할·OIDC 공급자 생성 및 S3 bucket 생성은 수행하지 않았으며 Task 6.1에서 승인 대상을 다시 확인한 후 실행합니다.

## Task 3.1: GitHub Actions CI workflow와 runtime 고정

### 구현 결과

- 루트 `.nvmrc`에 Node.js major version `22`를 고정했습니다.
- `.github/workflows/ci.yml`은 `main` 대상 pull request, `main` push 및 `workflow_dispatch`에서 동일한 검증 job을 실행합니다.
- workflow는 Python 3.13, `.nvmrc`의 Node.js 22 및 AWS SAM CLI를 설정한 뒤 lockfile 기반 프론트엔드 설치와 백엔드 개발 의존성 설치를 수행합니다.
- 백엔드 테스트, 프론트엔드 비대화형 테스트, TypeScript 검사, production build, 배포 자동화 테스트, SAM template 검증 및 SAM build를 선행 성공 순서대로 실행합니다.
- workflow 권한은 `contents: read`만 허용합니다. `id-token: write`, AWS 배포 자격 증명 설정, 장기 AWS access key 및 AWS 변경 명령은 포함하지 않았습니다.
- CI의 SAM 검증은 자격 증명 없이 `ap-northeast-2`를 명시합니다. 로컬 AWS/SAM 작업은 기존 규칙대로 `default` profile과 `ap-northeast-2`를 사용합니다.

### 검증 결과

| 검사 | 결과 |
| --- | --- |
| workflow trigger, 권한, runtime 및 금지 자격 증명 패턴 정적 검사 | 통과 |
| 백엔드 테스트 | 91개 통과 |
| 프론트엔드 테스트 | 48개 통과 |
| TypeScript 검사 및 production build | 통과 (Node.js 22.22.0) |
| 배포 자동화 테스트 | 37개 통과 |
| `sam validate` 및 `sam build` | 통과 (`--profile default --region ap-northeast-2`) |

검증 과정에서는 AWS 자격 증명을 설정하거나 AWS 리소스를 생성·변경하지 않습니다.

## Task 3.2: 실행 가능한 로컬 CI 검증 스크립트

### 구현 결과

- `scripts/validate-ci.sh`에서 기존 `scripts/verify-all.sh`를 먼저 호출해 백엔드·프론트엔드 테스트, TypeScript 검사와 프로덕션 빌드를 비대화형으로 재사용합니다.
- 애플리케이션 검증 성공 후 배포 자동화 스펙 테스트, SAM 템플릿 검증, SAM 애플리케이션 빌드를 각각 한 번씩 순서대로 실행합니다.
- `set -Eeuo pipefail`과 직렬 단계 실행으로 선행 명령이 실패하면 해당 종료 코드를 유지한 채 즉시 중단하며 watcher 또는 개발 서버를 시작하지 않습니다.
- SAM 검증과 빌드는 공통 배포 설정의 `default` 프로파일과 `ap-northeast-2` 리전을 명시합니다.

### 실제 실행 결과

| 검사 | 결과 |
| --- | --- |
| 핵심 데모 종단 간 테스트 | 3개 통과 |
| 핵심 백엔드 테스트 | 77개 통과 |
| 핵심 프론트엔드 테스트 | 44개 통과 |
| 선택 식단 백엔드 테스트 | 11개 통과 |
| 선택 식단 프론트엔드 테스트 | 4개 통과 |
| TypeScript 검사 및 프로덕션 빌드 | 통과 |
| 배포 자동화 스펙 테스트 | 37개 통과 |
| `sam validate --profile default --region ap-northeast-2` | 통과 |
| `sam build --profile default --region ap-northeast-2` | 통과 |

실제 검증은 `./scripts/validate-ci.sh`로 수행했으며 종료 코드는 0이었습니다. SAM 명령은 로컬 빌드와 템플릿 검증만 수행했고 AWS 리소스를 생성하거나 변경하지 않았습니다.

## Task 5.1: Application Stack 및 frontend 배포 스크립트

### 구현 결과

- `scripts/deployment/deploy-application.sh`는 승인된 Git branch·origin과 로컬 AWS 계정·리전을 먼저 검사한 뒤 Bootstrap Stack의 `SamArtifactBucketName` output을 조회하고 형식을 검증합니다.
- 대상 검사와 Bootstrap output 검증 성공 후에만 SAM build와 `my-own-fridge` Application Stack deploy를 실행합니다.
- Application Stack의 `ApiUrl`, `StaticBucketName`, `DistributionId`를 한 번의 output 조회 결과에서 파싱하며, 세 값이 모두 존재하고 형식 검증을 통과해야 frontend 배포를 시작합니다.
- `ApiUrl`의 마지막 `/`를 제거해 `VITE_API_BASE_URL`로 주입하고 production build, stack output 대상 S3 sync, CloudFront `/*` invalidation을 순서대로 실행합니다.
- S3 sync에 `--delete`를 사용하지 않으며, 각 단계가 실패하면 뒤따르는 배포 단계를 실행하지 않습니다.
- `scripts/deployment/first-deploy.sh`는 대상 검사를 먼저 수행하고 Bootstrap 배포가 성공한 경우에만 Application Stack과 frontend 배포를 호출합니다. 인자를 받지 않으므로 force 또는 삭제 옵션을 전달할 수 없습니다.
- 모든 로컬 AWS CLI와 SAM 명령은 `--profile default --region ap-northeast-2`를 명시합니다.

### 검증 결과

| 검사 | 결과 |
| --- | --- |
| 두 배포 스크립트 `bash -n` 구문 검사 | 통과 |
| 전체 배포 자동화 단위 테스트 | 49개 통과 |
| 대상 불일치 시 stack·배포 호출 차단 | 통과 |
| Bootstrap output, SAM build/deploy, Application output, frontend build, S3 sync 실패 시 후속 단계 차단 | 통과 |
| ApiUrl 주입 및 stack output 기반 S3·CloudFront 대상 사용 | 통과 |
| 모든 fake AWS CLI·SAM 호출의 profile/region 고정 | `default`, `ap-northeast-2` 일치 |
| S3 `--delete`, stack/bucket 삭제 및 force 동작 부재 | 통과 |

검증은 fake `aws`, `sam`, `npm`, `git` 실행 파일을 사용한 단위 테스트와 셸 구문 검사만 수행했습니다. 실제 CloudFormation/SAM 배포, S3 동기화 또는 CloudFront invalidation은 수행하지 않았으며, 구현한 스크립트의 실제 실행은 Task 6.2에서 수행합니다.
## Task 5.3: GitHub Actions CD workflow

### 구현 결과

- `.github/workflows/cd.yml`은 `main` push와 `workflow_dispatch`에서 실행되며, workflow 권한을 `contents: read`, `id-token: write`로 제한했습니다.
- `my-own-fridge-production` concurrency group에 `cancel-in-progress: false`를 적용해 진행 중인 운영 배포를 취소하지 않고 직렬화했습니다.
- AWS 변경 전에 저장소 `haramsong/my-own-fridge`, ref `refs/heads/main`과 `AWS_ROLE_ARN`, `AWS_REGION`, `SAM_STACK_NAME`, `SAM_ARTIFACT_BUCKET` repository variables의 존재 및 승인된 형식을 검사합니다.
- `aws-actions/configure-aws-credentials@v4`로만 OIDC 역할을 수임하고 `allowed-account-ids: 462747820533`을 적용했습니다. AWS access key secret 또는 credential file은 정의하지 않았습니다.
- OIDC 수임 후 STS 계정과 `ap-northeast-2` 리전을 다시 검사한 다음 Python 3.13, Node.js 22, 백엔드·프론트엔드 테스트, TypeScript 검사, 프론트엔드 검증 build, 배포 자동화 테스트와 SAM validate/build를 순서대로 실행합니다.
- 검증 성공 후에만 Bootstrap output으로 설정된 artifact bucket을 사용해 `my-own-fridge` Application Stack을 배포합니다.
- 한 번의 CloudFormation output 조회에서 `ApiUrl`, `StaticBucketName`, `DistributionId`를 추출하고 세 값의 형식을 모두 검증한 뒤에만 API URL 주입 frontend build, stack output 대상 S3 sync, CloudFront `/*` invalidation을 순서대로 실행합니다.
- S3 sync에는 `--delete`를 사용하지 않으며, 각 단계는 선행 명령 실패 시 즉시 중단됩니다.
- 로컬 AWS CLI와 SAM 작업에는 `default` 프로파일과 `ap-northeast-2` 리전을 사용합니다. GitHub Actions에서는 로컬 프로파일이나 장기 자격 증명 없이 OIDC 단기 자격 증명만 사용합니다.

### 정적 검증 결과

| 검사 | 결과 |
| --- | --- |
| YAML 구문 파싱 | 통과 |
| trigger, 최소 permissions, concurrency 검사 | 통과 |
| 저장소·ref·네 repository variable allowlist 검사 | 통과 |
| OIDC action, 허용 계정 및 STS 계정·리전 검사 | 통과 |
| 전체 CI 검증과 SAM deploy 단계 순서 검사 | 통과 |
| 세 Application Stack output gate 및 frontend 배포 순서 검사 | 통과 |
| access key secret/file, `secrets.*`, S3 `--delete` 금지 검사 | 통과 |
| 기존 배포 자동화 테스트 | 49개 통과 |
| `git diff --check` | 통과 |

이 Task의 검증은 workflow 정적 검사와 기존 로컬 단위 테스트만 수행했습니다. 실제 OIDC 수임, SAM 배포, S3 동기화 및 CloudFront invalidation은 실행하지 않았습니다. repository variables 또는 OIDC Bootstrap이 아직 준비되지 않은 상태에서 push로 CD가 시작되면, 배포 대상과 변수 검사 또는 OIDC 수임 단계에서 AWS 변경 전에 안전하게 실패합니다.

## Task 6.1: 승인된 AWS 계정의 OIDC Bootstrap 실제 배포

### 배포 대상 확인

| 항목 | 확인 결과 |
| --- | --- |
| AWS profile | `default` |
| AWS account | `462747820533` 일치 |
| AWS region | `ap-northeast-2` 일치 |
| Git branch | `main` 일치 |
| Git remote | `https://github.com/haramsong/my-own-fridge.git` 일치 |
| 기존 GitHub OIDC provider | 승인 계정의 `token.actions.githubusercontent.com` 공급자 1개 재사용 |

모든 대상 검사는 AWS 변경 명령보다 먼저 수행했습니다. 계정, 리전, 저장소 및 branch가 승인값과 일치한 경우에만 CloudFormation 배포를 진행했습니다. 로컬 AWS 명령에는 모두 `--profile default --region ap-northeast-2`를 명시했습니다.

### 실제 배포 결과

| 항목 | 결과 |
| --- | --- |
| Stack name | `my-own-fridge-github-oidc` |
| Stack status | `CREATE_COMPLETE` |
| Stack ID | `arn:aws:cloudformation:ap-northeast-2:462747820533:stack/my-own-fridge-github-oidc/16eab1d0-dff4-11f1-a41f-06fff1dc9bab` |
| 생성 시각 | `2026-11-14T06:24:47.532000+00:00` |
| GitHub deployment role | `arn:aws:iam::462747820533:role/my-own-fridge-github-deploy` |
| SAM artifact bucket | `my-own-fridge-github-oidc-samartifactbucket-vctylgw6itbg` |
| OIDC provider | `arn:aws:iam::462747820533:oidc-provider/token.actions.githubusercontent.com` |

배포 역할의 최대 session duration은 3,600초입니다. 실제 IAM trust policy에서 다음 제한을 확인했습니다.

- Federated principal: 승인 계정의 `token.actions.githubusercontent.com` OIDC provider
- Action: `sts:AssumeRoleWithWebIdentity`
- Audience: `sts.amazonaws.com` 정확 일치
- Subject: `repo:haramsong/my-own-fridge:ref:refs/heads/main` 정확 일치

SAM artifact bucket은 `AES256` 서버 측 암호화, versioning `Enabled`, 네 public access block 항목 `true`, object ownership `BucketOwnerEnforced`로 확인했습니다.

### 실제 실행 중 확인한 호환성 문제와 복구

최초 `bootstrap-oidc.sh` 실행은 현재 AWS CLI가 `aws cloudformation deploy`의 `--no-confirm-changeset` 옵션을 지원하지 않아 CloudFormation 변경 전에 중단되었습니다. 같은 검사를 다시 수행하고 해당 미지원 옵션만 제외한 명령으로 배포했으나, IAM Role의 한글 `Description`이 IAM 허용 문자 범위를 벗어나 Role 생성이 실패했고 Stack은 `ROLLBACK_COMPLETE`가 되었습니다.

운영자 승인을 받은 뒤 이번 실패로 생성된 `ROLLBACK_COMPLETE` Stack과 비어 있는 보존 artifact bucket만 정리했습니다. 기존 OIDC provider와 다른 AWS 리소스는 삭제하거나 변경하지 않았습니다. IAM Role 설명을 배포 중에만 ASCII 문자열로 바꾼 템플릿으로 다시 검증·배포하여 `CREATE_COMPLETE`를 확인했고, 로컬 템플릿은 기존 내용으로 복원했습니다. 권한 추가 또는 확대는 수행하지 않았습니다.

이 기록에는 AWS access key, secret access key, session token 또는 사용자 데이터가 포함되지 않습니다.
## Task 6.1 후속: OIDC Bootstrap 재현 결함 영구 수정

### 수정 내용

- 현재 AWS CLI가 지원하지 않는 `aws cloudformation deploy --no-confirm-changeset`를 제거했습니다. 비대화형 배포는 기본 change set 자동 실행 동작과 `--no-fail-on-empty-changeset`를 사용합니다.
- `GitHubDeploymentRole`의 IAM `Description`을 허용 문자 범위에 맞는 ASCII 문구 `GitHub Actions OIDC deployment role for my-own-fridge`로 변경했습니다.
- 회귀 테스트에서 deploy 호출에 `--no-confirm-changeset`가 없고 `--no-fail-on-empty-changeset`가 있는지 검사하며, IAM 역할 설명의 정확한 값과 ASCII 여부를 검사합니다.
- IAM action, resource, trust policy를 변경하지 않았으므로 권한 확대는 없습니다.

### 검증과 실제 재실행 결과

| 검사 | 결과 |
| --- | --- |
| 승인 계정 사전 검사 | `aws sts get-caller-identity --profile default --region ap-northeast-2` 결과 `462747820533` 일치 |
| Git 대상 검사 | branch `main`, origin `haramsong/my-own-fridge` 일치 |
| `bash -n scripts/deployment/bootstrap-oidc.sh` | 통과 |
| Bootstrap 회귀 테스트 | 7개 통과 |
| CloudFormation template 검증 | 통과 (`--profile default --region ap-northeast-2`) |
| 수정 스크립트의 기존 Stack 첫 재실행 | 성공, `UPDATE_COMPLETE` |
| 동일 입력 두 번째 재실행 | 성공, `No changes to deploy` |
| 최종 Stack 상태 | `UPDATE_COMPLETE` |
| IAM Role description | `GitHub Actions OIDC deployment role for my-own-fridge` |
| GitHub deployment role | `arn:aws:iam::462747820533:role/my-own-fridge-github-deploy` |
| SAM artifact bucket | `my-own-fridge-github-oidc-samartifactbucket-vctylgw6itbg` |
| OIDC provider | `arn:aws:iam::462747820533:oidc-provider/token.actions.githubusercontent.com` |

실제 재실행 전마다 `default` 프로파일과 `ap-northeast-2` 리전으로 계정을 확인했습니다. Stack, 역할, 공급자 또는 버킷 삭제, force 동작, IAM 권한 추가는 수행하지 않았습니다.

## Task 6.2: Application Stack과 frontend 최초 실제 배포

### 배포 대상 재검증

| 항목 | 확인 결과 |
| --- | --- |
| AWS profile | `default` |
| AWS account | `462747820533` 일치 |
| AWS region | `ap-northeast-2` 일치 |
| Git repository | `haramsong/my-own-fridge` 일치 |
| Git branch | `main` 일치 |
| 배포 시작 직전 revision | `ab1c43c9af19383d4327830db80d70058afc1043` |

`aws sts get-caller-identity --profile default --region ap-northeast-2`, configured region, Git branch와 origin을 AWS 변경 전에 다시 검사했습니다. 배포 중 HEAD에 추가된 후속 commit은 문서와 스펙 파일만 변경했으며 배포한 애플리케이션 입력 파일은 바꾸지 않았습니다.

### 실제 배포 결과

검증된 `scripts/deployment/deploy-application.sh`를 실행해 Bootstrap Stack output의 SAM artifact bucket을 사용한 `sam build`와 `sam deploy`, Application Stack output 검증, API URL 주입 frontend production build, S3 sync, CloudFront invalidation을 순서대로 수행했습니다.

| 항목 | 결과 |
| --- | --- |
| Application Stack | `my-own-fridge` |
| Stack status | `CREATE_COMPLETE` |
| Stack 생성 시각 | `2026-11-14T06:31:29.949000+00:00` |
| ApiUrl | `https://wt6ej9b4a7.execute-api.ap-northeast-2.amazonaws.com` |
| API health | `GET /api/health` 성공, status `ok` |
| StaticBucketName | `my-own-fridge-staticbucket-zfaosmep1kz8` |
| DistributionId | `E1I42HBY0SR8ZO` |
| CloudFront URL | `https://d2pkazqqygwla0.cloudfront.net` |
| CloudFront distribution status | `Deployed`, enabled |
| CloudFront URL 응답 | HTTPS 요청 성공 |
| Invalidation ID | `I6GUFBZ5S14LSNPPI5WBLCC84O` |
| Invalidation path/status | `/*`, `Completed` |

frontend build에는 stack output의 ApiUrl에서 마지막 `/`를 제거한 값을 `VITE_API_BASE_URL`로 주입했습니다. 생성된 `frontend/dist`를 stack output의 정적 버킷에 동기화한 뒤 같은 stack output의 배포 ID에 invalidation을 생성했습니다. 삭제 명령과 S3 `--delete`는 사용하지 않았습니다. 모든 로컬 AWS CLI와 SAM 명령에는 `--profile default --region ap-northeast-2`를 사용했으며 자격 증명이나 사용자 데이터는 기록하지 않았습니다.

## Task 7.1: GitHub variables 및 workflow dispatch 스크립트

### 구현 결과

- `scripts/deployment/configure-github.sh`는 Git branch·origin과 로컬 AWS 계정·리전을 먼저 검사하고, Bootstrap Stack의 `GitHubDeploymentRoleArn`과 `SamArtifactBucketName` output 형식을 확인합니다.
- GitHub CLI의 `github.com` 인증과 대상 저장소 `haramsong/my-own-fridge`를 확인한 뒤에만 `AWS_ROLE_ARN`, `AWS_REGION`, `SAM_STACK_NAME`, `SAM_ARTIFACT_BUCKET` 네 repository variable을 고정 allowlist로 설정합니다.
- variable 이름과 값은 인자로 받지 않으며, 네 변수를 설정한 뒤 `gh variable list --repo haramsong/my-own-fridge --json name,value` 결과에서 값까지 다시 검증합니다. AWS access key 또는 secret access key 이름은 allowlist에 포함하지 않았습니다.
- `scripts/deployment/dispatch-cd.sh`는 현재 `origin/main` SHA를 읽고 선택적 인자로 전달한 SHA와 일치하는지 확인합니다. 기존 run ID 목록을 저장한 뒤 `cd.yml`을 저장소 `haramsong/my-own-fridge`의 `main` ref로 실행하고 새 run ID만 선택합니다.
- 새 run을 `gh run watch --exit-status`로 기다린 뒤 `gh run view` 결과의 `conclusion=success`와 `headSha=origin/main SHA`를 모두 검증합니다.
- `gh`가 없거나 인증되지 않았으면 repository variable 설정이나 workflow dispatch 전에 실패하고, 같은 대상과 값으로 실행할 수동 `gh` 명령을 표시합니다.
- 모든 로컬 AWS CLI 조회에는 `haram`이 아닌 `default` 프로파일과 `ap-northeast-2` 리전을 명시했습니다.

### 검증 결과

| 검사 | 결과 |
| --- | --- |
| `bash -n` 셸 구문 검사 | 두 스크립트 모두 통과 |
| GitHub 설정·dispatch 단위 테스트 | 11개 통과 |
| 네 repository variable allowlist 및 조회 검증 | 통과 |
| AWS access key 이름 인자·설정 거부 | 통과 |
| `gh` 누락·미인증 시 변경 전 중단 및 수동 명령 출력 | 통과 |
| `cd.yml`, 저장소, `main` ref 고정 검사 | 통과 |
| workflow conclusion 및 head SHA 불일치 실패 검사 | 통과 |
| 로컬 AWS profile/region 고정 검사 | `default`, `ap-northeast-2` 일치 |
| `git diff --check` | 통과 |

이 Task에서는 fake `aws`, `git`, `gh` 실행 파일만 사용해 테스트했습니다. 실제 GitHub repository variable을 설정하거나 workflow를 dispatch하지 않았으며, Task 7.3에서 대상과 인증을 다시 확인한 뒤 스크립트를 실행합니다.

## Task 7.3: Repository Variables 설정과 workflow_dispatch 실제 검증

### 대상과 Repository Variables 확인

- 로컬 AWS 조회는 `default` 프로파일과 `ap-northeast-2` 리전을 사용했으며 STS account `462747820533`을 확인했습니다.
- Git branch는 `main`, origin은 `https://github.com/haramsong/my-own-fridge.git`, GitHub CLI 인증 계정은 `haramsong`으로 확인했습니다.
- `scripts/deployment/configure-github.sh`로 `AWS_ROLE_ARN`, `AWS_REGION`, `SAM_STACK_NAME`, `SAM_ARTIFACT_BUCKET` 네 Repository Variables를 설정했습니다.
- `gh variable list` 결과에서 role ARN, `ap-northeast-2`, `my-own-fridge`, Bootstrap Stack의 artifact bucket 값이 각각 일치함을 확인했습니다.
- AWS access key, secret access key 또는 장기 자격 증명은 GitHub 설정에 추가하지 않았습니다.

### 최초 dispatch 실패와 수정

최초 수동 실행 [run 43567963395](https://github.com/haramsong/my-own-fridge/actions/runs/43567963395)은 revision `0549b2a29e6330c821e03a2b82f90d39e672dc5a`에서 OIDC 역할 수임이 거부되어 실패했습니다. GitHub OIDC 설정 API를 조회한 결과 이 저장소는 immutable subject를 사용하며 prefix가 `repo:haramsong@61612250/my-own-fridge@1457328764`인 반면, IAM trust policy는 이전 이름 기반 subject를 요구하고 있었습니다. GitHub 문서의 [immutable subject 형식](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims)에 따라 branch까지 포함한 다음 정확 일치 조건으로 변경했습니다.

`repo:haramsong@61612250/my-own-fridge@1457328764:ref:refs/heads/main`

추가로 `aws-actions/configure-aws-credentials@v4`가 지원하지 않아 경고를 발생시킨 `allowed-account-ids` 입력을 제거했습니다. Workflow는 수임 전 고정 role ARN 검사와 수임 직후 STS account 정확 일치 검사를 계속 수행합니다. 수정은 Bootstrap Stack에 적용한 뒤 배포 자동화 테스트 63개와 CloudFormation template 검증을 통과했습니다.

| 수정 commit | push | Bootstrap Stack | 실제 trust 확인 |
| --- | --- | --- | --- |
| `67b467dc99a14db2b2109a901bb17d792b3d6b79` (`fix: trust GitHub immutable OIDC subject`) | `origin/main` 성공 | `UPDATE_COMPLETE` | immutable subject와 audience `sts.amazonaws.com` 정확 일치 |

### 성공한 workflow_dispatch와 배포 검증

수정 revision을 대상으로 실행한 [run 43568447277](https://github.com/haramsong/my-own-fridge/actions/runs/43568447277)은 `success`로 완료됐고 head SHA는 요청한 `67b467dc99a14db2b2109a901bb17d792b3d6b79`와 일치했습니다. OIDC 수임, STS account/region 검사, 전체 테스트, SAM build/deploy, output 검사, ApiUrl 주입 build, S3 sync와 CloudFront invalidation 단계가 모두 성공했습니다.

| 항목 | 실제 확인 결과 |
| --- | --- |
| Application Stack | `my-own-fridge`, `CREATE_COMPLETE` |
| ApiUrl | `https://wt6ej9b4a7.execute-api.ap-northeast-2.amazonaws.com` |
| API health | `GET /api/health` 응답의 status `ok` |
| StaticBucketName | `my-own-fridge-staticbucket-zfaosmep1kz8` |
| S3 `index.html` | 2026-11-14 06:55:35 UTC 갱신, 454 bytes |
| ApiUrl 주입 산출물 | CloudFront asset `assets/index-Bg8zH07K.js`에서 stack ApiUrl 확인 |
| DistributionId | `E1I42HBY0SR8ZO`, status `Deployed`, enabled |
| CloudFront URL | `https://d2pkazqqygwla0.cloudfront.net` |
| Invalidation | `I7S5Y7G3BHIJJMCJW3AHCKKG4X`, `/*`, `Completed` |

검증 기록에는 자격 증명, OIDC token 또는 사용자 데이터가 포함되지 않습니다.

## Task 4: CI와 OIDC 정적 검증 체크포인트

검증 기준 revision은 `b40298d5aeaeef6c82b7f4fbb6d6f38ca6e73f95`이며, 검증 시각은 `2026-11-14T07:06:57Z`입니다. Git branch `main`, origin `https://github.com/haramsong/my-own-fridge.git`, 로컬 AWS 프로파일 `default`, 리전 `ap-northeast-2`, STS 계정 `462747820533`이 승인 대상과 일치한 뒤 검증했습니다.

### 자동 검증 결과

| 검사 | 결과 |
| --- | --- |
| `./scripts/validate-ci.sh` | 통과 |
| 핵심 데모 종단 간 테스트 | 3개 통과 |
| 핵심 백엔드 테스트 | 77개 통과 |
| 핵심 프론트엔드 테스트 | 44개 통과 |
| 선택 식단 백엔드 테스트 | 11개 통과 |
| 선택 식단 프론트엔드 테스트 | 4개 통과 |
| TypeScript 검사와 production build | 통과 |
| 배포 자동화 테스트 | 63개 통과 |
| Application SAM template 검증과 build | 통과 |
| Bootstrap CloudFormation `validate-template` | 통과 |
| Bootstrap SAM template 검증 | 통과 |

백엔드 테스트에서는 Starlette `BlockingPortal` 별칭의 향후 제거를 알리는 경고만 발생했으며 테스트 실패는 없었습니다.

### 권한, OIDC 및 금지 패턴 확인

- CI workflow의 workflow-level 권한은 `contents: read` 하나뿐입니다.
- CD workflow의 workflow-level 권한은 `contents: read`와 `id-token: write`뿐입니다.
- 실제 GitHub OIDC 설정은 immutable subject를 사용하며 prefix가 `repo:haramsong@61612250/my-own-fridge@1457328764`입니다.
- 실제 IAM 역할의 trust subject는 `repo:haramsong@61612250/my-own-fridge@1457328764:ref:refs/heads/main`, audience는 `sts.amazonaws.com`으로 정확히 제한되어 있습니다. 템플릿 값도 실제 IAM 값과 일치합니다.
- workflow, template 및 실행 스크립트에서 장기 AWS access key 값, AWS credential 파일 쓰기, 배포용 S3 `--delete`, force push 실행을 찾지 못했습니다. Force 옵션 문자열은 `assert-git-target.sh`의 거부 목록에만 존재합니다.
- 로컬 배포 스크립트, 로컬 CI 스크립트와 runbook에서 추출한 AWS CLI·SAM 명령 38개는 모두 `default` 프로파일과 `ap-northeast-2` 리전을 명시합니다. GitHub Actions는 로컬 프로파일 대신 OIDC 단기 환경 자격 증명을 사용합니다.

모든 체크포인트 조건을 충족했고 후속 확인이 필요한 질문은 없습니다. Task 4 결론은 **통과**입니다.

## Task 9: Final checkpoint

최종 체크포인트의 사전 검증 시각은 `2026-11-14T07:11:36Z`이며, 기준 revision은 `60b6f8d5477aff97f19c316c225f227858f7d8d5`입니다. Git branch `main`, origin `https://github.com/haramsong/my-own-fridge.git`, 로컬 AWS 프로파일 `default`, 리전 `ap-northeast-2`, STS 계정 `462747820533`이 승인 대상과 일치함을 먼저 확인했습니다.

### 로컬 자동 검증

`./scripts/validate-ci.sh`와 Bootstrap 템플릿 검증을 최종 실행했습니다.

| 검사 | 결과 |
| --- | --- |
| 핵심 데모 종단 간 테스트 | 3개 통과 |
| 핵심 백엔드 테스트 | 77개 통과 |
| 선택 식단 백엔드 테스트 | 11개 통과 |
| 핵심 프론트엔드 테스트 | 44개 통과 |
| 선택 식단 프론트엔드 테스트 | 4개 통과 |
| 배포 자동화 테스트 | 63개 통과 |
| TypeScript 검사 | 통과 |
| 프론트엔드 production build | 통과 |
| Application SAM template validate/build | 통과 |
| Bootstrap SAM lint 및 CloudFormation template validation | 통과 |
| `git diff --check` | 통과 |

백엔드 테스트는 총 91개, 프론트엔드 테스트는 총 48개가 통과했습니다. 남은 비차단 경고는 Starlette `TestClient`가 사용하는 `anyio.abc.BlockingPortal` 별칭의 향후 제거를 알리는 `DeprecationWarning` 1종입니다.

### AWS 읽기 검증

모든 로컬 AWS CLI와 SAM 명령에 `--profile default --region ap-northeast-2`를 명시했습니다.

| 항목 | 최종 확인 결과 |
| --- | --- |
| STS account | `462747820533` |
| Bootstrap Stack | `my-own-fridge-github-oidc`, `UPDATE_COMPLETE` |
| GitHub deployment role | `arn:aws:iam::462747820533:role/my-own-fridge-github-deploy` |
| OIDC provider | `token.actions.githubusercontent.com`, client ID `sts.amazonaws.com` |
| OIDC trust subject | `repo:haramsong@61612250/my-own-fridge@1457328764:ref:refs/heads/main` 정확 일치 |
| SAM artifact bucket | `my-own-fridge-github-oidc-samartifactbucket-vctylgw6itbg` |
| Application Stack | `my-own-fridge`, `CREATE_COMPLETE` |
| ApiUrl | `https://wt6ej9b4a7.execute-api.ap-northeast-2.amazonaws.com` |
| API health | `GET /api/health`, `status=ok` |
| StaticBucketName | `my-own-fridge-staticbucket-zfaosmep1kz8` |
| S3 `index.html` | 454 bytes, `2026-11-14T07:09:14Z` 갱신 |
| DistributionId | `E1I42HBY0SR8ZO` |
| CloudFront | `Deployed`, enabled, HTTPS 응답 성공 |
| 최신 invalidation | `I8QJNSXR1GHXXSGJPR2519ZFPH`, `Completed` |
| 서비스 URL | `https://d2pkazqqygwla0.cloudfront.net` |

### GitHub 및 자동 CD 기준선

Repository Variables에는 승인된 네 항목만 존재하고 값이 Bootstrap/Application 설정과 일치했습니다.

- `AWS_ROLE_ARN=arn:aws:iam::462747820533:role/my-own-fridge-github-deploy`
- `AWS_REGION=ap-northeast-2`
- `SAM_STACK_NAME=my-own-fridge`
- `SAM_ARTIFACT_BUCKET=my-own-fridge-github-oidc-samartifactbucket-vctylgw6itbg`

최종 체크포인트 커밋 직전의 최신 `main` 자동 CD는 [run 43569591817](https://github.com/haramsong/my-own-fridge/actions/runs/43569591817)이며 `push` event, `success`, head SHA `60b6f8d5477aff97f19c316c225f227858f7d8d5`로 `origin/main`과 일치했습니다. 대상·변수 검사, OIDC 수임, STS 검사, 전체 CI, SAM 배포, output gate, API URL 주입 build, S3 sync와 CloudFront invalidation 단계가 모두 성공했습니다. 이 문서를 포함하는 최종 체크포인트 push의 자동 CD 결과는 해당 push 완료 후 별도 최종 실행 결과로 확인합니다.

### 요구사항·설계·구현 대조

| 범위 | 확인 결과 |
| --- | --- |
| 승인 대상과 변경 전 guard | 공통 고정값, 로컬·workflow 계정/리전/repository/ref 검사와 자동화 테스트 일치 |
| OIDC Bootstrap | 별도 Stack, immutable subject/audience 정확 일치, 장기 key 없음, 실제 Stack·IAM 값 일치 |
| CI | PR/main push/manual trigger, Python 3.13, Node 22, 전체 검증, `contents: read` 일치 |
| CD | main push/manual trigger, 최소 권한, 직렬 배포, fail-fast output gate와 실제 성공 단계 일치 |
| 최초 배포와 GitHub 설정 | 실제 Stack outputs, 네 Repository Variables, S3·CloudFront 대상이 문서와 일치 |
| 운영과 롤백 | runbook의 `git revert`, 상태 확인, `UPDATE_ROLLBACK_FAILED` 승인 경계와 Bootstrap 제외 범위 확인 |
| Git 안전 경계 | `main`/origin 검사, 제한 staging, 일반 push, force/hook 우회 금지 구현 확인 |

`requirements.md`, `design.md`, `tasks.md`, `.config.kiro`는 모두 Git 추적 파일입니다. `requirements.md`, `design.md`, `.config.kiro`에는 미반영 변경이 없었고, 이전 완료 상태가 반영된 `tasks.md`는 이 체크포인트 커밋에 포함합니다. 런타임 실행 이력인 `tasks.meta.json`은 제외합니다. 스펙과 최종 기록에서 실제 AWS 장기 access key 형식이나 credential file 설정을 찾지 못했고, `.aws-sam/build`와 `frontend/dist` 생성물은 커밋 대상에 포함하지 않습니다.

선택 사항으로 표시된 property/static test sub-task는 구현 계획의 MVP 선택 항목으로 남아 있습니다. 현재 필수 구현, 기존 자동화 테스트, 실제 AWS·GitHub 배포 검증에는 실패가 없으므로 최종 체크포인트 결론은 **통과**입니다.
