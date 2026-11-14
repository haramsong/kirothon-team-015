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
