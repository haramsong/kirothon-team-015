# 나만의 냉장고

혼자 사는 직장인과 대학생이 장 본 재료를 잊고 버리는 불편을, 영수증·주문내역 캡처 한 장으로 등록하고 "요리했어요" 한 번으로 쓴 재료가 빠지는 냉장고 재고 관리로 줄입니다.

**Demo:** (제출 전 추가: 배포 주소 또는 데모 영상 링크)

---

## 1. 문제 정의

### 대상 사용자

혼자 사는 직장인과 대학생 (1인 가구)

### 문제 상황

- **누가**: 혼자 사는 직장인과 대학생이
- **어떤 상황에서**: 양파 1.5kg망이나 대파 한 단처럼 혼자 먹기에 큰 단위로 장을 보고, 퇴근이나 수업 뒤에 남은 재료로 무엇을 만들지 떠올릴 여유가 없을 때
- **무엇이 불편한지**: 냉장고에 무엇이 남았는지 잊어버려 재료를 소비기한이 지나도록 두었다가 버리고, 결국 배달 음식을 시킨다.

### 기존 방식과 한계

냉장고 관리 앱([프리지](https://apps.apple.com/us/app/%ED%94%84%EB%A6%AC%EC%A7%80-%EC%86%8C%EB%B9%84%EA%B8%B0%ED%95%9C-%EC%9C%A0%ED%86%B5%EA%B8%B0%ED%95%9C-%EA%B4%80%EB%A6%AC/id6760248261), [냉장고 지킴이](https://apps.apple.com/sa/app/%EB%83%89%EC%9E%A5%EA%B3%A0-%EC%A7%80%ED%82%B4%EC%9D%B4/id6785734844), [킵](https://apps.apple.com/it/app/%ED%82%B5-keep/id6796238043) 등)은 영수증 스캔으로 재료를 **넣는 일**을 쉽게 만들었습니다. 그래도 세 가지 한계가 남습니다.

1. **다 먹은 재료를 빼는 일은 사용자가 직접 해야 합니다.** 아무도 지우지 않으니 목록이 금방 실제 냉장고와 달라집니다. 틀린 목록으로 추천받은 메뉴는 만들 수 없고, 사용자는 앱을 믿지 못해 쓰지 않게 됩니다.
2. **온라인 장보기에는 종이 영수증이 없습니다.** 쿠팡이나 컬리로 장을 보면 영수증 스캔을 쓸 수 없어 직접 입력해야 합니다.
3. **한 끼 추천만으로는 대용량 재료가 남습니다.** 양파 1.5kg망은 한 끼로 다 쓸 수 없어 남은 재료가 다시 방치됩니다.

### 근거

- 2024년 1인 가구는 804만 5천 가구로 전체 가구의 36.1%이며, 그중 약 60%가 취업 상태입니다 (국가데이터처 「2025 통계로 보는 1인가구」, [매일경제 보도](https://www.mk.co.kr/jp/economy/11487655)).
- 국내 앱스토어에 영수증 인식과 AI 레시피 추천을 묶은 냉장고 관리 앱이 여러 개 출시되어 있습니다(위 링크). 재료 낭비를 줄이려는 수요가 있다는 뜻입니다. 하지만 이 앱들의 스토어 설명에서 "요리 후 재고 자동 차감"이나 "온라인 주문내역 인식"은 찾지 못했습니다.

### 목표

등록, 추천, 요리, 차감을 하나의 흐름으로 묶어 **재고 목록이 실제 냉장고와 계속 맞도록** 합니다. 목록이 맞아야 소비기한이 임박한 재료로 실제로 만들 수 있는 메뉴를 추천받을 수 있고, 재료를 끝까지 쓸 수 있습니다.

```
장보기 → 등록 (영수증·주문내역 인식) → 추천 (임박 재료 우선) → 요리 → 차감 ("요리했어요")
   ↑                                                                        │
   └──────────────────────── 실제 냉장고와 맞는 재고 목록 ←─────────────────┘
```

---

## 2. 핵심 기능

| 기능 | 해결하는 불편 | 코드 위치 |
| --- | --- | --- |
| 장보기 인식: 영수증 사진과 온라인 주문내역 캡처를 같은 버튼 하나로 올리면 Bedrock(Claude Haiku 4.5)이 품목명, 수량(개), 보관 위치, 예상 소비기한을 추출합니다. 비식품과 기본 양념 8종은 뺍니다 | 등록이 번거롭다, 온라인 장보기에는 영수증이 없다 | `frontend/src/features/registration/`, `backend/app/services/recognition.py`, `backend/app/gateways/bedrock.py` |
| 이미지 전처리: 브라우저에서 EXIF 방향을 반영하고 긴 변 1568px 이하 JPEG로 줄입니다 | 휴대폰 사진이 Lambda·Bedrock 크기 제한을 넘는다 | `frontend/src/features/registration/imageProcessor.ts` |
| 등록 확인: 인식 결과를 수정, 삭제, 추가한 뒤 저장합니다. 이미 있는 같은 이름의 품목은 합칩니다 | LLM 추정값이 틀릴 수 있다 | `frontend/src/features/inventory/ItemModal.tsx`, `backend/app/logic/inventory.py`, `backend/app/routes/inventory.py` |
| 냉장고 목록: 남은 일수(D-day) 순으로 정렬하고 D-3 이내 재료를 강조합니다. 품목과 수량은 언제든 고칠 수 있습니다 | 무엇이 곧 상하는지 모른다 | `frontend/src/features/inventory/InventoryPage.tsx`, `frontend/src/logic/date.ts` |
| 한 끼 추천과 레시피: 임박 재료를 우선으로 메뉴를 추천하고, 조리 단계는 따로 생성합니다 | 남은 재료로 무엇을 만들지 고민할 여유가 없다 | `frontend/src/features/recipe/RecipePage.tsx`, `backend/app/services/recommendation.py` |
| 요리 후 자동 차감: "요리했어요"를 누르면 "양파 8개 → 7개"처럼 바뀌는 수량을 보여주고, 사용자가 확인하면 재고에서 뺍니다. 0개가 되면 목록에서 지웁니다 | 먹은 재료를 지우지 않아 목록이 틀어진다 | `frontend/src/features/deduction/DeductionModal.tsx`, `backend/app/services/deduction.py`, `backend/app/logic/deduction.py` |
| 3일 식단: 임박 재료를 3일 동안 점심·저녁 6끼로 다 쓰는 식단을 짜고, 재료별로 지금 수량과 3일 뒤 남는 수량을 보여줍니다. 끼니마다 같은 레시피·차감 흐름을 씁니다 | 대용량 재료가 한 끼로 다 안 쓰여 남는다 | `frontend/src/features/meal-plan/`, `frontend/src/logic/mealPlan.ts`, `backend/app/services/meal_plan.py` |
| 인프라: S3 + CloudFront 정적 SPA, API Gateway HTTP API + Lambda(FastAPI + Mangum), DynamoDB, Bedrock | 서버를 상시 띄우지 않고 쓴 만큼만 비용을 낸다 | `template.yaml` |

## 3. 사용 시나리오

1. 마트 영수증 사진을 올립니다. 인식된 품목(예: 양파 8개, 예상 소비기한 D-5)을 확인하고 틀린 수량을 고친 뒤 저장합니다.
2. 쿠팡 주문내역 캡처를 같은 버튼으로 올립니다. 같은 방식으로 확인하고 저장하면 이미 있는 품목은 수량이 합쳐집니다.
3. 냉장고 목록에서 D-3 이내 재료가 강조된 것을 확인하고 "한 끼 추천"을 누릅니다.
4. 추천 메뉴의 사용 재료와 조리 단계를 보고 요리합니다. "요리했어요"를 누르면 "양파 8개 → 7개"처럼 바뀌는 수량이 보이고, 필요하면 사용량을 고친 뒤 차감합니다. 냉장고 목록에 바뀐 수량이 바로 반영됩니다.
5. "3일 식단"을 누르면 6끼 메뉴와 재료별 "양파 7개 → 0개" 같은 3일 뒤 남는 수량이 나옵니다. 끼니를 요리할 때마다 4번과 같은 방식으로 차감합니다.

## 4. 기대 효과

화면 조작 횟수 기준으로 비교했습니다. 직접 입력 방식은 품목마다 품목명, 수량, 보관 위치, 소비기한을 입력하는 일반적인 재고 앱의 수동 입력을 기준으로 했습니다.

| 작업 | 직접 입력 방식 | 나만의 냉장고 |
| --- | --- | --- |
| 15개 품목 영수증 등록 | 입력 60회 (15개 × 4항목) | 사진 업로드 1회 + 틀린 항목만 수정 + 저장 1회 |
| 재료 3개를 쓴 요리 후 재고 정리 | 품목 찾기 3회 + 수량 수정·저장 3회 | "요리했어요" 1회 + 확인 후 차감 1회 |
| 3일 치 메뉴 정하기 | 끼니마다 6번 고민 | 식단 생성 1회로 6끼와 재료별 남는 수량 확인 |

## 5. 차별점

| 기능 | 프리지 | 냉장고 지킴이 | 킵 | 나만의 냉장고 |
| --- | --- | --- | --- | --- |
| 영수증 사진 인식 | O | O | O | O |
| 남은 재료 기반 AI 메뉴 추천 | 설명에 없음 | O | O | O |
| 온라인 주문내역 캡처 인식 | 설명에 없음 | 설명에 없음 | 설명에 없음 | **O** |
| 요리 후 재고 자동 차감 | 설명에 없음 | 설명에 없음 | 설명에 없음 | **O** |
| 재료를 다 쓰는 여러 끼 식단 | 설명에 없음 | 설명에 없음 | 설명에 없음 | **O** |

O는 앱스토어 설명에 해당 기능이 적혀 있다는 뜻입니다. "설명에 없음"은 기능이 없다고 확인한 것은 아닙니다.

1. **요리하면 재고가 알아서 줄어듭니다 (대표 차별점).** 레시피의 사용 재료와 수량이 재고와 같은 단위(개, 0.5개 단위)로 나오므로, "요리했어요" 한 번으로 차감할 수 있습니다. 차감은 사용자가 확인한 뒤에만 적용하고, 같은 요청이 두 번 들어와도 한 번만 반영합니다(DynamoDB 트랜잭션과 요청 ID).
2. **종이 영수증이 없어도 사진 한 장으로 등록합니다.** 영수증 사진과 주문내역 캡처를 같은 버튼 하나로 받고, 주문내역의 옵션·중량·묶음 표기(예: "양파 1.5kg 1망")도 일반 품목명과 개수로 바꿉니다.
3. **대용량 재료를 끝까지 쓰는 3일 식단을 짭니다.** 한 끼 추천이 아니라 임박 재료를 3일 안에 다 쓰도록 6끼를 짜고, 재료별로 남는 수량을 보여줍니다.

---

## 6. 설치와 실행

### 준비물

- Node.js 22 (`.nvmrc`), Python 3.13
- AWS 배포 시: AWS CLI, AWS SAM CLI, Amazon Bedrock에서 Claude Haiku 4.5(`global.anthropic.claude-haiku-4-5-20251001-v1:0`)를 호출할 수 있는 계정

```bash
# 1. 의존성 설치
python3.13 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
npm --prefix frontend ci

# 2. 로컬 실행 (AWS 없이 동작: 메모리 저장소와 고정된 테스트용 인식·추천 응답 사용)
APP_ENV=test CORS_ORIGINS=http://localhost:5173 \
  backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000

# 다른 터미널에서
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev
# 브라우저에서 http://localhost:5173 접속
```

실제 Bedrock 인식과 DynamoDB 저장을 쓰려면 AWS에 배포합니다.

```bash
# 3. AWS 배포 (ap-northeast-2)
sam build --profile default --region ap-northeast-2
sam deploy --guided --profile default --region ap-northeast-2

# 스택 출력의 ApiUrl로 프론트엔드를 빌드해 StaticBucketName 버킷에 올리고 CloudFront 캐시를 비웁니다
VITE_API_BASE_URL=<ApiUrl> npm --prefix frontend run build
aws s3 sync frontend/dist s3://<StaticBucketName> --profile default --region ap-northeast-2
aws cloudfront create-invalidation --distribution-id <DistributionId> --paths '/*' --profile default
# 접속 주소: 스택 출력의 WebUrl
```

`main` 브랜치 push 시 GitHub Actions CI(`.github/workflows/ci.yml`)가 테스트와 빌드를 검증합니다. GitHub OIDC 기반 CD(`.github/workflows/cd.yml`, `scripts/deployment/`)도 포함되어 있습니다.

## 7. 테스트

```bash
# 백엔드·프론트엔드 테스트, 핵심 데모 종단 간 테스트, TypeScript 검사, 프로덕션 빌드
./scripts/verify-all.sh

# 위 검증 + Vite·uvicorn 로컬 smoke 테스트 + sam validate/build
./scripts/verify-local.sh
```

`verify-all.sh` 실행 결과 (모두 통과):

| 단계 | 결과 |
| --- | --- |
| 핵심 데모 종단 간 테스트 (영수증 업로드 → 수정 → 저장 → 추천 → 레시피 → 차감 → 목록 반영) | 통과 |
| 백엔드 테스트 (pytest) | 77개 + 식단 11개 |
| 프론트엔드 테스트 (Vitest) | 44개 + 식단 4개 |
| TypeScript 검사, Vite 프로덕션 빌드 | 통과 |

테스트는 실제 AWS를 호출하지 않습니다. DynamoDB와 Bedrock은 메모리 어댑터와 시나리오별 고정 응답으로 대체합니다.

---

## 팀

- **팀 번호:** team-015
- **팀명:** 깜자조와

| 이름 | 역할 |
| --- | --- |
| 송하람 | 기획, 디자인, 프론트엔드, 백엔드, 인프라 |
