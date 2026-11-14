---
inclusion: always
---

# 기술 스택과 인프라

## AWS 계정
- 프로파일: `default` (계정 `462747820533`), 리전: `ap-northeast-2`
- 모든 AWS CLI와 SAM 명령에 `--profile default --region ap-northeast-2`를 명시한다.

## 아키텍처

```
브라우저 (React SPA)
  ├─ 정적 파일: CloudFront → S3 (비공개, OAC)
  └─ API 호출: API Gateway (HTTP API) → Lambda (Python, FastAPI + Mangum)
                                          ├─ DynamoDB (재고 저장)
                                          └─ Bedrock (Claude Haiku 4.5)
```

ECS나 EC2 대신 Lambda를 쓰는 이유:
- 요청이 하루 몇 번 몰리는 형태라 상시 서버가 필요 없고, 쓰지 않을 때 비용이 0이다.
- ECS는 VPC, ALB, ECR, 태스크 정의 설정이 필요하고 ALB 고정비가 생긴다.
- 장시간 작업, 웹소켓, 꾸준한 고트래픽이 생기면 그때 ECS로 옮긴다.

## 프론트엔드
- React + Vite + TypeScript + Tailwind CSS. SSR은 쓰지 않는다.
- 빌드 결과물을 S3에 올리고 CloudFront로 배포한다.
- SPA 라우팅: CloudFront에서 403/404 응답을 `/index.html`(200)로 돌려준다.
- 이미지는 업로드 전에 브라우저에서 긴 변 1568px 이하 JPEG로 줄인다. Lambda 동기 호출 페이로드 6MB, Bedrock 이미지 3.75MB 제한 때문이다.
- 사용자 구분: 로그인이 없으므로 처음 접속할 때 UUID를 만들어 localStorage에 저장하고, 모든 API 요청에 `X-Device-Id` 헤더로 보낸다. 인증 수단이 아니며, 실제 서비스 단계에서 Cognito로 바꾼다.

## 백엔드
- Python 3.13 Lambda 함수 하나에 FastAPI + Mangum으로 모든 API를 둔다.
- 로컬 개발은 uvicorn으로 실행한다.
- API Gateway HTTP API를 쓰고, CORS는 CloudFront 도메인과 `http://localhost:5173`을 허용한다.
- HTTP API 통합 타임아웃은 최대 30초다. Lambda 타임아웃은 29초로 두고, LLM 호출은 한 번에 끝나는 작은 단위로 나눈다.
  - 예: 3일 식단은 메뉴 이름과 사용 재료만 먼저 받고, 레시피 단계는 끼니를 열 때 따로 생성한다.

## Bedrock
- 모델: `global.anthropic.claude-haiku-4-5-20251001-v1:0` (글로벌 교차 리전 추론 프로파일)
  - 이 계정에서 호출 확인 완료. 짧은 프롬프트 응답 약 0.7초
  - `global.anthropic.claude-haiku-5-5`는 이 계정에서 AccessDenied
- Converse API를 쓰고, 응답 형식은 tool use로 JSON 스키마를 강제한다.
- Lambda 실행 역할에는 추론 프로파일 ARN과 foundation model ARN 모두에 `bedrock:InvokeModel`을 허용한다. 정확한 ARN 형식은 AWS 문서로 확인한다.

## 데이터
- DynamoDB 테이블 하나, PAY_PER_REQUEST
- 파티션 키는 디바이스 ID 기준으로 둔다. 세부 속성은 스펙의 design 문서에서 정의한다.

## IaC와 배포
- AWS SAM. `template.yaml` 하나에 S3, CloudFront, HTTP API, Lambda, DynamoDB, IAM을 정의한다.
- 인프라 뼈대는 개발 초반에 먼저 배포한다. CloudFront 생성에 몇 분이 걸리기 때문이다.
- 배포에 문제가 생기면 로컬 실행(Vite + uvicorn)으로 데모를 녹화한다.

## 레포 구조

```
frontend/      React SPA
backend/       Lambda (FastAPI)
template.yaml  SAM 템플릿
```

## 코드 규칙
- 코드 주석은 한국어로 쓴다. 변수명과 함수명은 영어로 쓴다.
- 비밀값을 코드에 넣지 않는다. AWS 접근은 IAM 역할로 한다.
