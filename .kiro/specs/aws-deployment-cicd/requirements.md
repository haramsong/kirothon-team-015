# Requirements Document

## Introduction

이 문서는 GitHub 저장소 `haramsong/my-own-fridge`의 `main` 브랜치에 대해 GitHub Actions 기반 지속적 통합(Continuous Integration, CI)과 지속적 배포(Continuous Deployment, CD)를 구축하는 요구사항을 정의합니다. CD는 장기 AWS 액세스 키 대신 GitHub OpenID Connect(OIDC)로 AWS 계정 `462747820533`의 배포 역할을 수임하고, `ap-northeast-2`에 AWS SAM 애플리케이션과 React 정적 사이트를 배포합니다.

로컬 부트스트랩과 최초 배포는 AWS CLI `default` 프로파일을 사용합니다. 배포 자동화는 현재 `template.yaml`의 서버리스 구조를 유지하며, 기존 `refrigerator-management-mvp` 스펙은 변경하지 않습니다. 실제 배포는 계정, 리전, 저장소 또는 브랜치가 승인된 값과 다르면 변경 전에 중단해야 합니다.

## Glossary

- **Deployment_Automation**: 이 문서가 정의하는 OIDC 부트스트랩, CI, CD, 검증 및 운영 절차 전체
- **Source_Repository**: GitHub 저장소 `haramsong/my-own-fridge`
- **Deployment_Branch**: Source_Repository의 `main` 브랜치
- **Expected_AWS_Account**: AWS 계정 ID `462747820533`
- **Deployment_Region**: AWS 리전 `ap-northeast-2`
- **Local_AWS_Profile**: 로컬 AWS CLI와 SAM 명령에 사용하는 `default` 프로파일
- **Bootstrap_Stack**: GitHub OIDC 공급자, GitHub_Deployment_Role 및 SAM 배포 아티팩트 버킷을 애플리케이션 스택과 분리해 관리하는 CloudFormation 스택
- **Application_Stack**: 루트 `template.yaml`로 관리하는 나만의 냉장고 애플리케이션 CloudFormation 스택
- **GitHub_OIDC_Provider**: `https://token.actions.githubusercontent.com`을 발급자로, `sts.amazonaws.com`을 audience로 사용하는 AWS IAM OIDC 공급자
- **GitHub_Deployment_Role**: GitHub OIDC 토큰으로 수임하여 Application_Stack과 정적 프론트엔드를 배포하는 IAM 역할
- **Bootstrap_Template**: Bootstrap_Stack을 정의하는 별도 CloudFormation 템플릿
- **Bootstrap_Script**: 로컬 신원 검증 후 Bootstrap_Template을 검증하고 배포하는 비대화형 셸 스크립트
- **CI_Workflow**: pull request, Deployment_Branch push 또는 수동 실행에서 자동 검증을 수행하는 GitHub Actions workflow
- **CD_Workflow**: Deployment_Branch push 또는 수동 실행에서 AWS와 프론트엔드를 순서대로 배포하는 GitHub Actions workflow
- **Repository_Variables**: Source_Repository Actions에 저장하는 비밀이 아닌 배포 설정값
- **Role_ARN**: Bootstrap_Stack이 출력하는 GitHub_Deployment_Role ARN
- **ArtifactBucketName**: Bootstrap_Stack이 출력하는 SAM 패키지 전용 S3 버킷 이름
- **ApiUrl**: Application_Stack 출력의 HTTP API 기본 URL
- **StaticBucketName**: Application_Stack 출력의 프론트엔드 S3 버킷 이름
- **DistributionId**: Application_Stack 출력의 CloudFront 배포 ID
- **Deployment_Identity_Check**: AWS 계정, 리전, GitHub 저장소 및 Git ref를 승인된 값과 비교하는 변경 전 검증
- **Local_Validation**: 외부 서비스 변경 없이 템플릿, 스크립트 및 workflow 구문과 명령 연결을 검사하는 자동 검증
- **Workflow_Dispatch_Validation**: `gh` CLI로 CD_Workflow를 수동 실행하고 완료 결과와 배포 출력을 확인하는 검증
- **Independent_Commit**: 한 leaf task에서 변경한 파일과 검증 결과만 담는 Git commit
- **Rollback_Procedure**: 애플리케이션과 프론트엔드를 이전의 검증된 Git revision으로 복원하는 운영 절차

## Requirements

### Requirement 1: 배포 대상 고정과 변경 전 안전 검사

**User Story:** 운영자로서, 승인된 계정과 저장소만 배포 대상으로 사용하고 싶습니다. 그래야 잘못된 환경에 리소스를 만들거나 변경하지 않습니다.

#### Acceptance Criteria

1. THE Deployment_Automation SHALL Expected_AWS_Account, Deployment_Region, Source_Repository 및 Deployment_Branch를 단일 설정 집합으로 정의한다.
2. WHEN 로컬 AWS 변경 명령을 실행하기 전에, THE Bootstrap_Script SHALL `aws sts get-caller-identity --profile default --region ap-northeast-2`로 확인한 계정 ID를 Expected_AWS_Account와 비교한다.
3. IF 로컬 AWS 계정 ID가 Expected_AWS_Account와 다르면, THEN THE Bootstrap_Script SHALL CloudFormation 또는 SAM 변경 명령을 실행하지 않고 0이 아닌 종료 코드를 반환한다.
4. WHEN CD_Workflow가 AWS 변경 단계에 진입하기 전에, THE CD_Workflow SHALL OIDC로 확인한 AWS 계정 ID와 실행 리전을 Expected_AWS_Account 및 Deployment_Region과 비교한다.
5. IF CD_Workflow의 AWS 계정 또는 리전이 승인된 값과 다르면, THEN THE CD_Workflow SHALL CloudFormation, SAM, S3 또는 CloudFront 변경 명령을 실행하지 않고 실패한다.
6. WHEN CD_Workflow가 실행되면, THE CD_Workflow SHALL 실행 저장소가 Source_Repository이고 실행 ref가 `refs/heads/main`인지 확인한다.
7. IF CD_Workflow의 실행 저장소 또는 ref가 승인된 값과 다르면, THEN THE CD_Workflow SHALL AWS 변경 명령을 실행하지 않고 실패한다.
8. THE Deployment_Automation SHALL 기존 `refrigerator-management-mvp` 스펙 파일을 수정 대상에서 제외한다.

### Requirement 2: GitHub OIDC 부트스트랩

**User Story:** 운영자로서, 장기 AWS 키 없이 GitHub Actions가 배포 역할을 수임하게 하고 싶습니다. 그래야 저장소에 AWS 비밀키를 저장하지 않고 배포할 수 있습니다.

#### Acceptance Criteria

1. THE Bootstrap_Template SHALL GitHub_OIDC_Provider, GitHub_Deployment_Role 및 SAM 패키지 전용 S3 버킷을 Bootstrap_Stack에 정의한다.
2. THE Bootstrap_Template SHALL GitHub_OIDC_Provider의 URL을 `https://token.actions.githubusercontent.com`으로, client ID를 `sts.amazonaws.com`으로 정의한다.
3. THE GitHub_Deployment_Role SHALL `sts:AssumeRoleWithWebIdentity` 신뢰 주체를 GitHub_OIDC_Provider로 제한한다.
4. THE GitHub_Deployment_Role SHALL OIDC audience 조건을 `sts.amazonaws.com`과 정확히 일치시킨다.
5. THE GitHub_Deployment_Role SHALL OIDC subject 조건을 GitHub가 Source_Repository에 부여한 immutable owner·repository ID와 Deployment_Branch를 포함하는 `repo:haramsong@61612250/my-own-fridge@1457328764:ref:refs/heads/main`과 정확히 일치시킨다.
6. THE GitHub_Deployment_Role SHALL Application_Stack 배포, Lambda 아티팩트 업로드, 프론트엔드 업로드 및 CloudFront 무효화에 필요한 작업으로 권한을 제한한다.
7. THE Bootstrap_Template SHALL GitHub_Deployment_Role의 Role_ARN과 SAM 패키지 전용 버킷의 ArtifactBucketName을 stack output으로 제공한다.
8. WHEN Bootstrap_Script가 실행되면, THE Bootstrap_Script SHALL Deployment_Identity_Check를 통과한 뒤 Bootstrap_Template 검증과 Bootstrap_Stack 배포를 순서대로 수행한다.
9. IF Bootstrap_Template 검증 또는 Bootstrap_Stack 배포가 실패하면, THEN THE Bootstrap_Script SHALL 후속 AWS 변경 명령을 실행하지 않고 0이 아닌 종료 코드를 반환한다.
10. WHEN Bootstrap_Stack 배포가 완료되면, THE Bootstrap_Script SHALL CloudFormation output에서 Role_ARN과 ArtifactBucketName을 조회하고 각 값의 형식을 검증한다.
11. THE Local_Validation SHALL Bootstrap_Template의 OIDC URL, audience, subject, 역할 권한 및 Role_ARN output을 자동 검사한다.
12. THE Bootstrap_Template SHALL 장기 AWS 액세스 키 또는 비밀 액세스 키를 포함하지 않는다.

### Requirement 3: 지속적 통합 workflow

**User Story:** 개발자로서, 배포 전에 백엔드, 프론트엔드와 SAM 템플릿을 자동 검증하고 싶습니다. 그래야 실패한 revision이 CD 단계로 넘어가지 않습니다.

#### Acceptance Criteria

1. WHEN Source_Repository의 pull request가 열리거나 갱신되면, THE CI_Workflow SHALL CI 검증을 실행한다.
2. WHEN Deployment_Branch에 push가 발생하면, THE CI_Workflow SHALL CI 검증을 실행한다.
3. WHEN 사용자가 CI_Workflow의 `workflow_dispatch`를 요청하면, THE CI_Workflow SHALL push와 같은 CI 검증을 실행한다.
4. THE CI_Workflow SHALL Python 3.13과 프로젝트가 고정한 Node.js 버전에서 실행한다.
5. THE CI_Workflow SHALL 백엔드 의존성과 프론트엔드 lockfile 의존성을 재현 가능한 명령으로 설치한다.
6. THE CI_Workflow SHALL 백엔드 테스트, 프론트엔드 테스트, TypeScript 검사, 프론트엔드 production build, `sam validate` 및 `sam build`를 수행한다.
7. IF CI 검증 단계가 하나라도 실패하면, THEN THE CI_Workflow SHALL 실패 상태로 종료한다.
8. THE CI_Workflow SHALL AWS 장기 자격 증명과 배포 권한 없이 실행한다.
9. THE Local_Validation SHALL CI_Workflow 구문, trigger, 권한, runtime 버전 및 프로젝트 검증 명령을 자동 검사한다.
10. WHEN 개발자가 로컬 CI 검증 스크립트를 실행하면, THE Local_Validation SHALL CI_Workflow와 같은 프로젝트 검증 명령을 비대화형으로 실행한다.

### Requirement 4: 지속적 배포 workflow

**User Story:** 운영자로서, main push와 수동 실행으로 백엔드와 프론트엔드를 정해진 순서대로 배포하고 싶습니다. 그래야 API URL이 반영된 단일 revision을 반복 가능하게 배포할 수 있습니다.

#### Acceptance Criteria

1. WHEN Deployment_Branch에 push가 발생하면, THE CD_Workflow SHALL 배포 작업을 실행한다.
2. WHEN 사용자가 Deployment_Branch를 대상으로 `workflow_dispatch`를 요청하면, THE CD_Workflow SHALL 배포 작업을 실행한다.
3. THE CD_Workflow SHALL workflow 권한을 `contents: read`와 `id-token: write`로 제한한다.
4. THE CD_Workflow SHALL Repository_Variables의 Role_ARN과 Deployment_Region을 사용해 GitHub_Deployment_Role을 OIDC로 수임한다.
5. WHEN GitHub_Deployment_Role 수임이 완료되면, THE CD_Workflow SHALL Deployment_Identity_Check를 수행한다.
6. WHEN Deployment_Identity_Check가 성공하면, THE CD_Workflow SHALL CI_Workflow와 같은 검증을 통과한 revision만 배포한다.
7. WHEN 검증이 성공하면, THE CD_Workflow SHALL `sam build` 후 Application_Stack에 `sam deploy`를 수행한다.
8. WHEN Application_Stack 배포가 성공하면, THE CD_Workflow SHALL CloudFormation에서 ApiUrl, StaticBucketName 및 DistributionId output을 조회한다.
9. IF ApiUrl, StaticBucketName 또는 DistributionId output이 없거나 빈 값이면, THEN THE CD_Workflow SHALL 프론트엔드 배포를 시작하지 않고 실패한다.
10. WHEN Application_Stack output 조회가 성공하면, THE CD_Workflow SHALL ApiUrl을 `VITE_API_BASE_URL`에 주입해 프론트엔드 production build를 생성한다.
11. WHEN 프론트엔드 production build가 성공하면, THE CD_Workflow SHALL build 산출물을 StaticBucketName에 동기화한다.
12. WHEN S3 동기화가 성공하면, THE CD_Workflow SHALL DistributionId의 `/*` 경로에 CloudFront invalidation을 생성한다.
13. IF SAM 배포, output 조회, 프론트엔드 build, S3 동기화 또는 CloudFront invalidation 단계가 실패하면, THEN THE CD_Workflow SHALL 뒤따르는 배포 단계를 실행하지 않고 실패한다.
14. THE CD_Workflow SHALL 같은 Deployment_Branch 배포가 동시에 실행될 때 진행 중인 배포를 취소하지 않고 한 번에 하나만 실행되도록 구성한다.
15. THE Local_Validation SHALL CD_Workflow의 trigger, 최소 workflow 권한, 단계 순서, output 검사 및 변경 전 중단 조건을 자동 검사한다.
16. THE CD_Workflow SHALL AWS 액세스 키와 AWS 비밀 액세스 키를 GitHub secret 또는 파일로 저장하지 않는다.

### Requirement 5: 최초 배포와 GitHub 저장소 설정

**User Story:** 운영자로서, 로컬 부트스트랩부터 GitHub 수동 배포까지 같은 대상과 산출물을 확인하고 싶습니다. 그래야 자동 CD를 활성화하기 전에 배포 경로를 검증할 수 있습니다.

#### Acceptance Criteria

1. WHEN 최초 배포를 시작하면, THE Deployment_Automation SHALL Deployment_Identity_Check, Bootstrap_Stack 배포, Application_Stack 최초 배포 순서로 수행한다.
2. WHEN Application_Stack 최초 배포를 수행하면, THE Deployment_Automation SHALL Local_AWS_Profile과 Deployment_Region을 명시한다.
3. WHEN Application_Stack 최초 배포가 성공하면, THE Deployment_Automation SHALL ApiUrl을 주입한 프론트엔드 build, StaticBucketName 대상 S3 동기화 및 DistributionId 대상 CloudFront invalidation을 순서대로 수행한다.
4. IF 최초 배포 중 계정, 리전 또는 stack output이 승인된 값과 다르면, THEN THE Deployment_Automation SHALL 후속 변경을 수행하지 않고 실패한다.
5. WHEN Bootstrap_Stack에서 Role_ARN과 ArtifactBucketName을 확인하면, THE Deployment_Automation SHALL Source_Repository의 Repository_Variables에 `AWS_ROLE_ARN`, `AWS_REGION`, `SAM_STACK_NAME`, `SAM_ARTIFACT_BUCKET`을 설정한다.
6. THE Repository_Variables SHALL `AWS_REGION=ap-northeast-2`, 승인된 Application_Stack 이름 및 Bootstrap_Stack이 출력한 ArtifactBucketName을 포함한다.
7. WHEN Repository_Variables를 설정하면, THE Deployment_Automation SHALL 가능하면 `gh variable set` 명령을 사용한다.
8. THE Deployment_Automation SHALL GitHub 저장소 설정에 AWS 액세스 키 또는 비밀 액세스 키를 저장하지 않는다.
9. WHEN Repository_Variables 설정을 완료하면, THE Deployment_Automation SHALL `gh variable list` 결과로 네 변수의 존재를 확인한다.
10. WHEN Workflow_Dispatch_Validation을 시작하면, THE Deployment_Automation SHALL Source_Repository와 Deployment_Branch를 명시해 CD_Workflow를 실행한다.
11. WHEN Workflow_Dispatch_Validation이 완료되면, THE Deployment_Automation SHALL workflow 결론이 성공이고 실행된 Git SHA가 요청한 Deployment_Branch revision과 일치하는지 확인한다.
12. IF `gh` CLI를 사용할 수 없거나 인증되지 않았으면, THEN THE Deployment_Automation SHALL GitHub 설정을 변경하지 않고 필요한 수동 명령을 표시한다.

### Requirement 6: 운영과 롤백 문서

**User Story:** 운영자로서, 배포 확인과 실패 복구 절차를 저장소에서 찾고 싶습니다. 그래야 자동 배포 실패 또는 잘못된 revision을 일관된 순서로 복구할 수 있습니다.

#### Acceptance Criteria

1. THE Deployment_Automation SHALL `docs/` 아래에 부트스트랩, 최초 배포, 자동 배포, 검증 및 Rollback_Procedure를 설명하는 운영 문서를 제공한다.
2. THE Rollback_Procedure SHALL 이전의 검증된 Git revision을 `workflow_dispatch`로 재배포하는 절차를 제공한다.
3. THE Rollback_Procedure SHALL Application_Stack 상태, ApiUrl 응답, S3 배포 revision 및 CloudFront invalidation 상태를 확인하는 명령을 제공한다.
4. IF Application_Stack이 `UPDATE_ROLLBACK_FAILED` 상태이면, THEN THE Rollback_Procedure SHALL 추가 배포 전에 운영자 승인이 필요한 CloudFormation 복구 절차를 구분해 표시한다.
5. THE Rollback_Procedure SHALL Bootstrap_Stack 삭제, IAM 역할 변경 및 OIDC 공급자 삭제를 일반 애플리케이션 롤백 절차에서 제외한다.
6. THE 운영 문서 SHALL 모든 로컬 AWS CLI 및 SAM 예시에 `--profile default --region ap-northeast-2`를 포함한다.
7. THE 운영 문서 SHALL AWS 계정, 리전, 저장소를 확인하는 사전 점검과 불일치 시 중단 기준을 포함한다.
8. THE 운영 문서 SHALL 비밀값을 명령 인자, 환경 파일, workflow 또는 Git 이력에 저장하지 않는 절차를 포함한다.

### Requirement 7: 작업별 검증과 Git 이력

**User Story:** 개발자로서, CI/CD 변경을 작은 단위로 검증하고 공유하고 싶습니다. 그래야 각 변경을 독립적으로 검토하고 되돌릴 수 있습니다.

#### Acceptance Criteria

1. WHEN 한 구현 task의 코드 및 자동 검증이 완료되면, THE Deployment_Automation SHALL 해당 task 변경만 포함한 Independent_Commit을 생성한다.
2. WHEN Independent_Commit을 생성하기 전에, THE Deployment_Automation SHALL 현재 branch가 Deployment_Branch이고 remote `origin`이 Source_Repository인지 확인한다.
3. IF 현재 branch 또는 remote `origin`이 승인된 값과 다르면, THEN THE Deployment_Automation SHALL commit 또는 push를 수행하지 않고 실패한다.
4. WHEN Independent_Commit을 생성하면, THE Deployment_Automation SHALL 해당 commit을 `origin/main`에 push한다.
5. IF 작업 디렉터리에 해당 task와 무관한 변경이 있으면, THEN THE Deployment_Automation SHALL 무관한 변경을 stage하거나 commit하지 않는다.
6. IF Independent_Commit 생성 또는 `origin/main` push가 실패하면, THEN THE Deployment_Automation SHALL 실패를 기록하고 다음 task를 시작하지 않는다.
7. THE Deployment_Automation SHALL force push와 Git hook 우회를 사용하지 않는다.
