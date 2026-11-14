# AWS 배포 운영·롤백 Runbook

## 1. 목적과 승인 대상

이 문서는 `haramsong/my-own-fridge`의 GitHub OpenID Connect(OIDC) 부트스트랩, 최초 배포, 일상 배포, 검증, 장애 진단 및 롤백 절차를 설명합니다. 애플리케이션은 AWS SAM으로 배포하고, 프론트엔드는 Application Stack output이 가리키는 S3와 CloudFront에 배포합니다.

승인된 대상은 다음 값으로 고정합니다.

| 항목 | 승인값 |
| --- | --- |
| AWS 계정 | `462747820533` |
| AWS 리전 | `ap-northeast-2` |
| 로컬 AWS CLI 프로파일 | `default` |
| GitHub 저장소 | `haramsong/my-own-fridge` |
| 배포 브랜치·ref | `main` · `refs/heads/main` |
| Bootstrap Stack | `my-own-fridge-github-oidc` |
| Application Stack | `my-own-fridge` |
| GitHub 배포 역할 | `arn:aws:iam::462747820533:role/my-own-fridge-github-deploy` |
| OIDC audience | `sts.amazonaws.com` |
| OIDC immutable subject | `repo:haramsong@61612250/my-own-fridge@1457328764:ref:refs/heads/main` |

계정, 리전, 저장소 또는 브랜치 중 하나라도 승인값과 다르면 즉시 중단합니다. 불일치를 임시로 우회하거나 스크립트의 고정값을 바꿔서 배포하지 않습니다.

## 2. 자격 증명과 비밀값 원칙

- GitHub Actions는 OIDC로 `my-own-fridge-github-deploy` 역할을 수임합니다. AWS access key, secret access key 또는 session token을 GitHub Actions secret이나 variable에 저장하지 않습니다.
- Repository Variables에는 비밀이 아닌 `AWS_ROLE_ARN`, `AWS_REGION`, `SAM_STACK_NAME`, `SAM_ARTIFACT_BUCKET`만 저장합니다.
- AWS 자격 증명, OIDC token 및 사용자 데이터는 workflow, 명령 인자, `.env` 계열 파일, 문서, 로그, 커밋 또는 Git 이력에 기록하지 않습니다.
- 로컬 작업은 AWS CLI의 `default` 프로파일을 사용합니다. 프로파일의 credential 파일을 저장소로 복사하거나 workflow runner에 만들지 않습니다.
- 민감한 환경 변수를 출력할 수 있는 `set -x`, `env`, `printenv`를 배포 진단에 사용하지 않습니다. GitHub Actions 로그에도 token이나 credential을 붙여 넣지 않습니다.
- 자격 증명이 노출되었다고 의심되면 배포를 중단하고 해당 자격 증명을 폐기·교체한 뒤 Git 이력과 Actions 로그의 노출 범위를 별도 보안 절차로 확인합니다. 노출값을 단순히 새 커밋에서 삭제하는 것으로 끝내지 않습니다.

## 3. 모든 변경 전 사전 점검

저장소 루트에서 다음을 실행합니다.

```bash
./scripts/deployment/assert-git-target.sh assert

aws sts get-caller-identity \
  --query Account \
  --output text \
  --profile default \
  --region ap-northeast-2

aws configure get region \
  --profile default \
  --region ap-northeast-2

git branch --show-current
git remote get-url origin
```

결과가 각각 계정 `462747820533`, 리전 `ap-northeast-2`, 브랜치 `main`, 저장소 `haramsong/my-own-fridge`와 일치해야 합니다. Git remote는 스크립트가 동등한 HTTPS·SSH 형식을 정규화해 검사합니다. 하나라도 다르면 Bootstrap, SAM deploy, S3 sync, CloudFront invalidation, commit 및 push를 실행하지 않습니다.

로컬 검증은 AWS 리소스를 변경하지 않습니다.

```bash
./scripts/validate-ci.sh

sam validate \
  --template-file infra/github-oidc-bootstrap.yaml \
  --profile default \
  --region ap-northeast-2

sam validate \
  --template-file template.yaml \
  --profile default \
  --region ap-northeast-2
```

## 4. OIDC Bootstrap

### 4.1 실행 시점

Bootstrap은 최초 구성 또는 `infra/github-oidc-bootstrap.yaml`의 승인된 변경을 적용할 때만 실행합니다. 일상적인 애플리케이션 배포나 롤백에서는 실행하지 않습니다.

사전 점검과 로컬 검증을 통과한 뒤 실행합니다.

```bash
./scripts/deployment/bootstrap-oidc.sh
```

스크립트는 다음 순서로 동작합니다.

1. Git branch·origin과 로컬 AWS 계정·리전을 검사합니다.
2. 계정의 `token.actions.githubusercontent.com` OIDC provider가 0개인지 1개인지 확인합니다.
3. Bootstrap 템플릿을 검증합니다.
4. `my-own-fridge-github-oidc` Stack을 생성 또는 갱신합니다.
5. `GitHubDeploymentRoleArn`과 `SamArtifactBucketName` output 형식을 검증합니다.

같은 URL의 provider가 둘 이상 발견되거나 승인 계정 밖의 ARN이면 변경 전에 중단합니다. 기존 provider 한 개가 있으면 재사용합니다.

### 4.2 Bootstrap 결과 확인

```bash
aws cloudformation describe-stacks \
  --stack-name my-own-fridge-github-oidc \
  --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' \
  --output json \
  --profile default \
  --region ap-northeast-2

aws iam get-role \
  --role-name my-own-fridge-github-deploy \
  --query 'Role.AssumeRolePolicyDocument.Statement[0].Condition.StringEquals' \
  --output json \
  --profile default \
  --region ap-northeast-2

aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::462747820533:oidc-provider/token.actions.githubusercontent.com \
  --query '{Url:Url,ClientIDList:ClientIDList}' \
  --output json \
  --profile default \
  --region ap-northeast-2
```

Stack 상태가 `CREATE_COMPLETE` 또는 `UPDATE_COMPLETE`여야 합니다. 신뢰 정책의 audience와 subject가 이 문서 1절의 값과 정확히 일치해야 하며 wildcard가 없어야 합니다.

Bootstrap Stack, IAM 역할 및 OIDC provider는 애플리케이션보다 긴 수명주기를 갖습니다. 삭제나 신뢰·권한 변경은 일반 운영 및 롤백 범위가 아니며 별도 변경 승인과 영향 분석이 필요합니다.

## 5. 최초 Application Stack 및 프론트엔드 배포

Bootstrap 성공 후 한 번에 최초 배포하려면 다음 스크립트를 사용합니다.

```bash
./scripts/deployment/first-deploy.sh
```

Bootstrap이 이미 준비된 상태에서 Application Stack과 프론트엔드만 배포하려면 다음을 사용합니다.

```bash
./scripts/deployment/deploy-application.sh
```

`deploy-application.sh`는 대상 검사 후 다음을 직렬로 수행합니다.

1. Bootstrap Stack의 SAM artifact bucket output 확인
2. `sam build`와 `sam deploy`
3. Application Stack의 `ApiUrl`, `StaticBucketName`, `DistributionId` 확인
4. `VITE_API_BASE_URL=<ApiUrl>`로 프론트엔드 production build
5. `frontend/dist`를 output의 S3 bucket에 sync
6. output의 CloudFront distribution에서 `/*` invalidation 생성

세 output 중 하나라도 없거나 형식이 올바르지 않으면 프론트엔드 배포를 시작하지 않습니다. S3 sync에는 `--delete`를 사용하지 않습니다.

## 6. GitHub Repository Variables

Bootstrap output을 확인한 뒤 다음 스크립트로 네 변수를 설정하고 값까지 다시 검사합니다.

```bash
./scripts/deployment/configure-github.sh

gh variable list \
  --repo haramsong/my-own-fridge \
  --json name,value
```

| 변수 | 값 |
| --- | --- |
| `AWS_ROLE_ARN` | `arn:aws:iam::462747820533:role/my-own-fridge-github-deploy` |
| `AWS_REGION` | `ap-northeast-2` |
| `SAM_STACK_NAME` | `my-own-fridge` |
| `SAM_ARTIFACT_BUCKET` | Bootstrap Stack의 `SamArtifactBucketName` output |

`gh`가 없거나 `github.com` 인증이 없으면 스크립트는 GitHub 설정을 변경하지 않고 동일한 수동 `gh variable set` 명령을 표시합니다. 표시된 값은 Bootstrap output과 승인된 고정값을 다시 대조한 후 실행합니다. AWS key나 token은 Repository Variables 또는 Secrets에 추가하지 않습니다.

## 7. 자동·수동 CI/CD 운영

### 7.1 자동 배포

`main` push는 CI와 CD workflow를 시작합니다. CD는 다음 안전 경계를 적용합니다.

- 저장소 `haramsong/my-own-fridge`와 ref `refs/heads/main` 정확 일치
- Repository Variables의 존재와 승인값 확인
- OIDC 역할 수임 후 STS 계정 `462747820533`과 리전 `ap-northeast-2` 재확인
- 백엔드·프론트엔드 테스트, TypeScript 검사, production build, SAM 검증·build 성공 후에만 배포
- Application Stack 배포와 output gate 성공 후에만 S3·CloudFront 변경
- concurrency group으로 운영 배포를 한 번에 하나씩 실행하고 진행 중 실행을 취소하지 않음

자동 실행 상태와 배포 SHA를 확인합니다.

```bash
gh run list \
  --workflow cd.yml \
  --repo haramsong/my-own-fridge \
  --branch main \
  --limit 10

gh run view <RUN_ID> \
  --repo haramsong/my-own-fridge \
  --json conclusion,headSha,event,status,url
```

`conclusion=success`이고 `headSha`가 배포하려는 `origin/main` SHA와 같아야 합니다.

### 7.2 수동 workflow_dispatch

현재 `origin/main`을 다시 배포하고 완료 결과와 SHA를 함께 확인합니다.

```bash
EXPECTED_SHA="$(git ls-remote --exit-code origin refs/heads/main | cut -f1)"
./scripts/deployment/dispatch-cd.sh "${EXPECTED_SHA}"
```

직접 실행해야 하는 경우 다음과 같이 `main`을 명시합니다.

```bash
gh workflow run cd.yml \
  --repo haramsong/my-own-fridge \
  --ref main

gh run watch <RUN_ID> \
  --repo haramsong/my-own-fridge \
  --exit-status

gh run view <RUN_ID> \
  --repo haramsong/my-own-fridge \
  --json conclusion,headSha,url
```

GitHub의 `workflow_dispatch`는 임의의 과거 commit SHA를 직접 배포 대상으로 선택하지 않습니다. 이전 revision으로 롤백하려면 먼저 10절처럼 해당 revision의 내용을 `git revert`로 현재 `main`에 복원한 뒤 새 `main` SHA를 dispatch합니다.

## 8. 배포 후 확인

먼저 Application Stack output을 읽습니다.

```bash
API_URL="$(aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]" \
  --output text \
  --profile default \
  --region ap-northeast-2)"

STATIC_BUCKET="$(aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query "Stacks[0].Outputs[?OutputKey=='StaticBucketName'].OutputValue | [0]" \
  --output text \
  --profile default \
  --region ap-northeast-2)"

DISTRIBUTION_ID="$(aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue | [0]" \
  --output text \
  --profile default \
  --region ap-northeast-2)"
```

### 8.1 Stack과 API

```bash
aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query 'Stacks[0].{Status:StackStatus,Updated:LastUpdatedTime,Outputs:Outputs}' \
  --output json \
  --profile default \
  --region ap-northeast-2

curl --fail --silent --show-error "${API_URL%/}/api/health"
```

Stack은 정상 완료 상태여야 하고 health 응답의 `status`가 `ok`여야 합니다. 사용자 기기 ID, 재고 데이터 또는 요청 본문은 검증 로그에 남기지 않습니다.

### 8.2 S3 배포 revision

```bash
aws s3api head-object \
  --bucket "${STATIC_BUCKET}" \
  --key index.html \
  --query '{LastModified:LastModified,ETag:ETag,ContentLength:ContentLength}' \
  --output json \
  --profile default \
  --region ap-northeast-2

aws s3api list-objects-v2 \
  --bucket "${STATIC_BUCKET}" \
  --prefix assets/ \
  --query 'reverse(sort_by(Contents,&LastModified))[:5].[Key,LastModified,Size]' \
  --output table \
  --profile default \
  --region ap-northeast-2
```

S3 객체에는 Git SHA metadata를 별도로 쓰지 않습니다. 따라서 배포 revision은 성공한 CD run의 `headSha`, 순서대로 성공한 `프론트엔드 S3 동기화` 단계, `index.html`과 asset의 `LastModified`가 해당 run 시간대인지 함께 대조해 확인합니다. run URL, head SHA, 객체 갱신 시각과 ETag만 운영 기록에 남기고 객체 내용이나 사용자 데이터는 남기지 않습니다.

### 8.3 CloudFront와 invalidation

```bash
aws cloudfront get-distribution \
  --id "${DISTRIBUTION_ID}" \
  --query 'Distribution.{Status:Status,Enabled:DistributionConfig.Enabled,DomainName:DomainName}' \
  --output json \
  --profile default \
  --region ap-northeast-2

aws cloudfront list-invalidations \
  --distribution-id "${DISTRIBUTION_ID}" \
  --max-items 5 \
  --query 'InvalidationList.Items[].{Id:Id,Status:Status,CreateTime:CreateTime}' \
  --output table \
  --profile default \
  --region ap-northeast-2
```

배포 상태가 `Deployed`, `Enabled=true`이고 해당 CD run이 생성한 invalidation이 `Completed`인지 확인합니다. distribution output의 `DomainName`에 HTTPS로 접속해 최신 화면도 확인합니다.

## 9. 실패 진단

### 9.1 GitHub Actions

```bash
gh run view <RUN_ID> \
  --repo haramsong/my-own-fridge \
  --log-failed

gh run view <RUN_ID> \
  --repo haramsong/my-own-fridge \
  --json conclusion,headSha,event,status,url
```

실패한 단계 뒤의 단계가 실행되지 않았는지 확인합니다. OIDC 수임 실패 시 Repository Variables, immutable subject, audience, 실행 저장소와 ref를 먼저 대조합니다. 장기 AWS key를 추가해서 우회하지 않습니다.

### 9.2 CloudFormation/SAM

```bash
aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query 'Stacks[0].{Status:StackStatus,Reason:StackStatusReason}' \
  --output json \
  --profile default \
  --region ap-northeast-2

aws cloudformation describe-stack-events \
  --stack-name my-own-fridge \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED` || ResourceStatus==`DELETE_FAILED`].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table \
  --profile default \
  --region ap-northeast-2
```

- SAM deploy 실패: Stack event의 최초 실패 리소스와 원인을 수정한 뒤 전체 CI를 다시 통과시킵니다.
- output 누락: S3 sync와 invalidation을 수동 실행하지 말고 `template.yaml`과 Stack 상태부터 복구합니다.
- 프론트엔드 build 실패: Application Stack은 유지합니다. 코드를 수정해 전체 배포를 다시 실행합니다.
- S3 sync 실패: bucket이 Application Stack output과 같은지, 역할 권한과 workflow run을 확인합니다. 임의 bucket으로 변경하지 않습니다.
- invalidation 실패: S3 업로드는 유지될 수 있습니다. 같은 distribution output을 재확인한 뒤 승인된 배포 workflow를 다시 실행합니다.

### 9.3 Bootstrap

```bash
aws cloudformation describe-stack-events \
  --stack-name my-own-fridge-github-oidc \
  --query 'StackEvents[0:20].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table \
  --profile default \
  --region ap-northeast-2
```

Bootstrap 장애는 Application Stack 롤백과 분리해 처리합니다. provider 중복, IAM trust 또는 artifact bucket 문제를 확인하되 Bootstrap Stack, IAM 역할, OIDC provider를 삭제해 재생성하는 방식으로 복구하지 않습니다.

## 10. 이전 검증 revision으로 롤백

### 10.1 롤백 revision 선정

`GOOD_SHA`는 CI와 CD가 성공했고 Stack/API/S3/CloudFront 검증 기록이 있는 revision이어야 합니다.

```bash
GOOD_SHA='<검증된-40자리-Git-SHA>'

gh run list \
  --workflow cd.yml \
  --repo haramsong/my-own-fridge \
  --branch main \
  --commit "${GOOD_SHA}" \
  --limit 10

gh run view <GOOD_RUN_ID> \
  --repo haramsong/my-own-fridge \
  --json conclusion,headSha,url
```

`conclusion=success`, `headSha=${GOOD_SHA}`를 확인합니다. 현재 대상도 3절의 사전 점검으로 다시 확인합니다.

### 10.2 Git 이력을 보존하는 revert

과거 SHA로 force push하거나 `main`을 강제로 이동하지 않습니다. 최신 `main` 위에 이후 commit들을 최신순으로 `git revert`하여 검증 revision의 내용을 복원합니다.

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git log --oneline "${GOOD_SHA}..HEAD"

while IFS= read -r commit_sha; do
  git revert --no-edit "${commit_sha}"
done < <(git rev-list "${GOOD_SHA}..HEAD")

./scripts/validate-ci.sh
git diff --check
git push origin main
```

충돌이 발생하면 배포와 push를 중단합니다. 파일을 검증 revision의 의도와 맞게 해결하고 `git add` 후 `git revert --continue`를 사용합니다. `--no-verify`, amend, force push 또는 강제 refspec은 사용하지 않습니다. 저장소 정책이 pull request를 요구하면 rollback branch를 push하고 CI를 통과한 pull request를 `main`에 병합합니다.

`main` push가 자동 CD를 시작합니다. 자동 run의 head SHA가 새 revert commit과 일치하고 성공했는지 확인합니다. 자동 실행이 누락됐거나 동일 revision의 통제된 재배포가 필요하면 현재 `origin/main` SHA로 수동 dispatch를 실행합니다.

```bash
ROLLBACK_SHA="$(git ls-remote --exit-code origin refs/heads/main | cut -f1)"
./scripts/deployment/dispatch-cd.sh "${ROLLBACK_SHA}"
```

완료 후 8절의 Stack, API, S3 revision 및 CloudFront invalidation 검사를 모두 수행합니다.

### 10.3 `UPDATE_ROLLBACK_FAILED` 승인 경계

Application Stack 상태가 `UPDATE_ROLLBACK_FAILED`이면 추가 `sam deploy`, S3 sync, CloudFront invalidation 또는 자동 CD 재시도를 중단합니다. 먼저 상태와 event를 수집합니다.

```bash
aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query 'Stacks[0].{Status:StackStatus,Reason:StackStatusReason}' \
  --output json \
  --profile default \
  --region ap-northeast-2

aws cloudformation describe-stack-events \
  --stack-name my-own-fridge \
  --query 'StackEvents[0:30].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table \
  --profile default \
  --region ap-northeast-2
```

`continue-update-rollback`은 CloudFormation 상태를 변경하는 수동 복구 작업입니다. 운영자가 실패 원인, 영향받는 리소스, 데이터 보존 여부를 검토하고 명시적으로 승인한 뒤에만 실행합니다.

```bash
aws cloudformation continue-update-rollback \
  --stack-name my-own-fridge \
  --profile default \
  --region ap-northeast-2

aws cloudformation wait stack-update-rollback-complete \
  --stack-name my-own-fridge \
  --profile default \
  --region ap-northeast-2

aws cloudformation describe-stacks \
  --stack-name my-own-fridge \
  --query 'Stacks[0].StackStatus' \
  --output text \
  --profile default \
  --region ap-northeast-2
```

리소스를 건너뛰는 `--resources-to-skip`은 Stack 템플릿과 실제 리소스를 불일치시킬 수 있으므로 별도의 운영자 승인, 대상 리소스 영향 분석 및 복구 계획 없이는 사용하지 않습니다. Stack이 `UPDATE_ROLLBACK_COMPLETE`가 된 뒤 원인을 수정하고 CI를 통과한 revision만 다시 배포합니다.

### 10.4 일반 롤백에서 금지하는 작업

일반 애플리케이션 롤백은 다음 작업을 포함하지 않습니다.

- `my-own-fridge-github-oidc` Bootstrap Stack 삭제
- `my-own-fridge-github-deploy` IAM 역할 삭제 또는 신뢰·권한 변경
- `token.actions.githubusercontent.com` OIDC provider 삭제
- SAM artifact bucket 삭제
- Application Stack, DynamoDB table 또는 정적 S3 bucket의 수동 삭제
- S3 sync의 `--delete`, Git force push, hook 우회

이 리소스들의 변경이나 삭제는 일반 롤백과 분리된 변경 계획, 데이터 보존 검토 및 운영자 승인이 필요합니다.

## 11. 확인된 운영 기준선

2026-11-14에 다음 비밀이 아닌 결과를 실제 배포와 `workflow_dispatch`에서 확인했습니다.

| 항목 | 확인값 |
| --- | --- |
| 성공한 CD run | `43568447277` |
| 배포 revision | `67b467dc99a14db2b2109a901bb17d792b3d6b79` |
| Application Stack | `my-own-fridge`, `CREATE_COMPLETE` |
| ApiUrl | `https://wt6ej9b4a7.execute-api.ap-northeast-2.amazonaws.com` |
| API health | `/api/health`의 `status=ok` |
| StaticBucketName | `my-own-fridge-staticbucket-zfaosmep1kz8` |
| DistributionId | `E1I42HBY0SR8ZO` |
| CloudFront URL | `https://d2pkazqqygwla0.cloudfront.net` |
| 확인한 invalidation | `I7S5Y7G3BHIJJMCJW3AHCKKG4X`, `Completed` |
| GitHub deployment role | `arn:aws:iam::462747820533:role/my-own-fridge-github-deploy` |
| SAM artifact bucket | `my-own-fridge-github-oidc-samartifactbucket-vctylgw6itbg` |
| OIDC provider | `arn:aws:iam::462747820533:oidc-provider/token.actions.githubusercontent.com` |

이 기준선은 장애 시 비교용이며 고정된 배포 대상 자체를 바꾸지 않습니다. AWS credential, OIDC token, 기기 ID 및 재고 데이터는 기록하지 않습니다.
