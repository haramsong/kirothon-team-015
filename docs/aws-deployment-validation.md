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
