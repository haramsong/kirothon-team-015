# 나만의 냉장고 Figma 인계

## 파일

- Figma: https://www.figma.com/design/E4LmR5L4WsyD8Knn7zZl6X/Untitled?node-id=0-1
- File key: `E4LmR5L4WsyD8Knn7zZl6X`
- 기준 기기 폭: `480px`
- 콘텐츠 폭: `448px` (좌우 여백 16px)
- 사용 폰트: `Pretendard`
- 작성 범위: `00 Reference`, `01 Foundations`, `02 Components`, `03 Design`
- 제외 범위: `04 Screen Spec`, `05 Prototype`

## 페이지 node ID

| 페이지 | node ID | 주요 보드 |
| --- | --- | --- |
| 00 Reference | `0:1` | Reference Board `11:140` |
| 01 Foundations | `11:2` | Foundations Board `11:59` |
| 02 Components | `11:3` | Component Library `13:2` |
| 03 Design | `11:4` | Demo Flow · Mobile 480 `20:2` |

## Foundations

- 색상 변수(variable): 31개
  - Stone 기반 중립색
  - Emerald 행동·성공색
  - Amber 임박색
  - Red 오류·삭제색
- 크기 변수(variable): 15개
  - 간격: 4, 8, 12, 16, 20, 24, 32, 40px
  - 반경: 8, 12, 16, 24px
  - 최소 터치 영역: 44px
  - 모바일 폭: 480px
  - 콘텐츠 폭: 448px
- 텍스트 스타일(text style): 10개
  - 12, 14, 16, 18, 20, 24px
  - Regular, Medium, Bold
- 그림자 스타일(effect style): `Shadow/Sm`, `Shadow/Lg`
- 색상 채움·테두리·텍스트에 로컬 변수를 연결했다.
- 모든 작성 텍스트에 Pretendard 로컬 텍스트 스타일을 연결했다.

## 공통 컴포넌트

| 컴포넌트 | node ID | 용도 |
| --- | --- | --- |
| Button | `13:17` | Primary, Dark, Secondary, Ghost, Danger, Disabled |
| Badge | `13:28` | Expiring, Estimated, Expired, Success, Storage |
| Input/Field | `13:29` | 레이블이 유지되는 입력 필드 |
| Card/Inventory | `13:33` | 수량·보관 위치·D-day·예상 소비기한 |
| Upload/SingleImage | `13:44` | 영수증·주문내역 단일 업로드 |
| Feedback/Toast | `13:48` | 저장·차감 성공 피드백 |
| SpecMarker | `13:51` | 화면 흐름 번호와 화면명 |
| SpecCard | `13:55` | 목적·상태·차별점 메모 |

## 화면 컴포넌트 세트

| ID | 화면명 | Screen/<ID> component set node ID | 상태별 node ID | 기기 크기 |
| --- | --- | --- | --- | --- |
| INV-01 | 냉장고 목록 | `14:125` | Default `14:4`, Empty `14:51`, Loading `14:69`, Error `14:80`, Success `14:92` | 480×960 |
| REG-02 | 재료 등록 | `15:118` | Upload `15:6`, Loading `15:18`, Results `15:29`, Empty `15:62`, Error `15:74`, Saving `15:90` | 480×1040 |
| EDIT-03 | 품목 편집 | `16:95` | Default `16:9`, Error `16:37`, Saving `16:67` | 480×960 |
| REC-04 | 한 끼 추천·레시피 | `17:149` | LoadingMenu `17:9`, LoadingRecipe `17:22`, Default `17:57`, ErrorMenu `17:104`, ErrorRecipe `17:118`, Empty `17:135` | 480×1120 |
| DED-05 | 차감 확인 | `18:167` | Default `18:18`, Loading `18:60`, Empty `18:102`, Error `18:123` | 480×1000 |
| PLAN-06 | 3일 식단 | `19:124` | Loading `19:9`, Default `19:28`, Empty `19:98`, Error `19:111` | 480×1280 |

## 03 Design 흐름

`03 Design`은 위 화면 컴포넌트와 `SpecMarker`, `SpecCard`의 인스턴스(instance)로 조립했다.

| 순서 | 화면 | Design instance node ID | 연결된 상태 |
| ---: | --- | --- | --- |
| 01 | 빈 냉장고 | `20:13` | INV-01 / Empty |
| 02 | 통합 업로드 | `20:40` | REG-02 / Upload |
| 03 | 인식 결과 | `20:64` | REG-02 / Results |
| 04 | 품목 수정 | `20:106` | EDIT-03 / Default |
| 05 | 임박 재고 | `20:143` | INV-01 / Default |
| 06 | 한 끼 추천 | `20:199` | REC-04 / Default |
| 07 | 차감 확인 | `20:255` | DED-05 / Default |
| 08 | 차감 성공 | `20:306` | INV-01 / Success |
| 09 | 3일 식단 | `20:350` | PLAN-06 / Default |

## 차별점 표시 위치

- 차별점 1, 요리 후 재고 자동 차감
  - REC-04의 `요리했어요`
  - DED-05의 `양파 8개 → 7개`
  - INV-01 Success의 양파 7개와 차감 토스트
- 차별점 2, 영수증·온라인 주문내역 통합 인식
  - REG-02 Upload의 `영수증 사진 또는 주문내역 캡처 올리기`
  - 입력 종류를 고르는 별도 단계가 없다.
- 차별점 3, 대용량 재료를 끝까지 쓰는 3일 식단
  - PLAN-06 상단의 `양파 8개 → 0개`
  - 1일차 점심부터 3일차 저녁까지 6개 끼니

## 근거로 사용한 소스

| 경로 | 반영한 사실 |
| --- | --- |
| `.kiro/steering/product.md` | 차별점 우선순위, 수량 0.5개, 소비기한 용어, 차감 확인, 3일 식단 |
| `.kiro/steering/tech.md` | React SPA, 모바일 우선, 이미지 1568px, Lambda 29초, 두 단계 생성 |
| `.kiro/steering/plan.md` | S1~S4, M1~M2, 다섯 단계 데모 흐름, 화면 문구와 모든 상태 |
| `docs/mvp-implementation-log.md` | 등록·추천·차감·3일 식단 구현 완료 상태와 실제 복구 흐름 |
| `docs/task-4.2-bedrock-recognition.md` | JPEG 제한, 인식 오류 코드, 소비기한 추정, 0.5개 정규화 |
| `frontend/src/styles.css` | Pretendard, Stone 50 배경 |
| `frontend/src/features/inventory/InventoryPage.tsx` | 재고 카드, D-day, 예상·임박·지남, 추천 진입 |
| `frontend/src/features/registration/RegistrationPage.tsx` | 단일 업로드, 이미지 미리보기, 결과 수정·저장, 오류 복구 |
| `frontend/src/features/inventory/ItemModal.tsx` | 품목명·수량·보관 위치·소비기한 편집 |
| `frontend/src/features/recipe/RecipePage.tsx` | 메뉴와 조리 순서의 두 단계 로딩, 요리했어요 |
| `frontend/src/features/deduction/DeductionModal.tsx` | 실제 사용량 수정, 전후 수량, 원자 차감 재시도 |
| `frontend/src/features/meal-plan/MealPlanPage.tsx` | 6개 끼니, 생성 시점 재고 기준, 완료 상태 |

## 코드·기획·Figma 차이

- Figma 냉장고 화면에는 기획서의 `소비기한 임박 3개 · 지남 1개` 요약을 넣었다. 현재 `InventoryPage.tsx`에는 이 요약이 없다.
- Figma 품목 수정과 차감 확인에는 0.5개 단위 스테퍼(stepper)를 표시했다. 현재 구현은 숫자 입력(input)을 사용한다.
- Figma 등록 결과에는 `구매일 4/7 기준으로 소비기한을 예상했어요`를 표시했다. 현재 `RegistrationPage.tsx`는 구매일 안내를 렌더링하지 않는다.
- Figma 3일 식단은 제품 요구대로 `현재 → 3일 뒤`를 크게 표시한다. 현재 코드는 `현재 · 사용 · 3일 뒤`를 한 줄로 표시한다.
- Figma는 기획 용어 `식단 다시 짜기`를 사용한다. 현재 코드는 `식단 다시 만들기`를 사용한다.
- Figma의 `양파 8개 → 0개`는 제품 문서의 대표 예시다. 실제 데모에서 한 끼 차감 후 식단을 생성하면 `양파 7개 → 0개`가 자연스럽다.

## 접근성·구현 제약

- 모든 버튼과 입력의 터치 영역을 최소 44×44px로 구현한다.
- 키보드 포커스는 Emerald 600 계열의 2px 이상 외곽선으로 표시한다.
- 오류 문구는 필드 레이블과 `aria-describedby`로 연결한다.
- D-day는 색상만 쓰지 않고 `D-2`, `임박`, `지남` 텍스트를 함께 표시한다.
- 모달은 `role="dialog"`, `aria-modal="true"`, 제목 연결, 포커스 가두기와 닫힌 뒤 포커스 복귀가 필요하다.
- LLM 요청 중 중복 제출을 막고, 실패 시 같은 이미지·입력·차감 초안을 보존한다.
- 업로드 전에 브라우저에서 긴 변 1568px 이하 JPEG로 줄인다.
- 메뉴 추천과 조리 순서는 Lambda 29초 제한 때문에 두 요청으로 유지한다.

## DECISIONS

| ID | 결정할 내용 | 추천안 |
| --- | --- | --- |
| D-01 | 현재 숫자 입력을 Figma의 −/+ 스테퍼로 바꿀지 | 데모에서 수정 장면이 잘 보이도록 차감 확인만 스테퍼를 우선 적용한다. 품목 편집은 시간이 부족하면 숫자 입력을 유지한다. |
| D-02 | 3일 식단 데모 수량을 `8개 → 0개`와 `7개 → 0개` 중 무엇으로 고정할지 | 실제 흐름의 일관성을 위해 녹화에서는 한 끼 차감 후 `7개 → 0개`를 사용한다. 발표 설명과 제품 문서에서는 대표 예시 `8개 → 0개`를 유지한다. |
| D-03 | 기획 문구와 현재 코드 문구를 어느 쪽으로 통일할지 | 차별점 문구는 Figma·기획 기준으로 맞추고, 기능 의미가 같은 일반 버튼 문구는 현재 코드를 유지해 수정 범위를 줄인다. |

## Planner 직접 작업 결과: 04 Screen Spec · 05 Prototype

### 페이지

| 페이지 | node ID | 구성 |
| --- | --- | --- |
| 04 Screen Spec | `23:328` | 개요, 화면별 명세 보드 7개, 상태 variant, 화면·상태 hyperlink |
| 05 Prototype | `23:329` | 정상 흐름 3개, 주요 오류 복구 흐름 1개 |

- Screen Spec Overview: `23:330`
- `00 Reference`부터 `05 Prototype`까지 필수 페이지가 모두 존재한다.

### 04 Screen Spec 보드

| 화면 ID | 보드 | board node ID | 사용한 03 Design instance | hyperlink가 있는 텍스트 수 |
| --- | --- | --- | --- | ---: |
| INV-01 | 냉장고 목록 | `24:2` | `20:143` | 8 |
| REG-02 | 통합 업로드 | `24:282` | `20:40` | 8 |
| REG-02 | 인식 결과 | `24:487` | `20:64` | 6 |
| EDIT-03 | 품목 편집 | `24:702` | `20:106` | 5 |
| REC-04 | 한 끼 추천·레시피 | `24:901` | `20:199` | 10 |
| DED-05 | 차감 확인 | `24:1209` | `20:255` | 6 |
| PLAN-06 | 3일 식단 | `24:1510` | `20:350` | 7 |

- 주 화면은 screenshot이 아니라 `03 Design`의 `Screen/<ID>` instance를 복제해 사용했다.
- 각 보드의 `SpecMarker`와 `SpecCard` 번호가 일치한다. 보드당 마커 수는 5개 이하이며, REC-04와 DED-05만 6개다.
- 화면 ID hyperlink 40개, 상태 variant hyperlink 32개, REG-02 인식 결과 하위 보드 hyperlink 1개를 연결했다.
- 화면 ID는 해당 화면 보드로 연결했다. 상태 이름은 같은 보드의 상태 instance로 연결했다.
- 연결하지 못한 항목: 없음.
- 개요에는 화면 목록, 대표 사용자 흐름, 현재 구현 API 매핑, 확인 필요·알려진 차이를 배치했다.

### 05 Prototype 흐름

| 흐름 | section node ID | 시작 frame node ID | frame 수 | reaction 수 | 주요 반응 |
| --- | --- | --- | ---: | ---: | --- |
| Flow A · 첫 등록 | `25:2` | `25:40` | 7 | 7 | navigate, 품목 편집 overlay, 저장 timeout |
| Flow B · 한 끼 추천과 자동 차감 | `25:275` | `25:325` | 8 | 8 | 추천·레시피 timeout, 차감 확인 overlay, 차감 후 식단 진입 |
| Flow C · 3일 식단 | `25:693` | `25:729` | 6 | 4 | 식단 timeout, 끼니 선택, 레시피 timeout, 차감 확인 overlay |
| Flow D · 주요 오류 복구 | `25:1023` | 아래 3개 | 9 | 6 | 인식·추천·차감 오류별 재시도와 복구 timeout |

오류 복구 시작점:

- 인식 오류 복구: `25:1042`
- 추천 오류 복구: `25:1106`
- 차감 오류 복구: `25:1216`

- 전체 prototype frame은 30개다.
- 전체 reaction은 25개다.
- `03 Design` 정상 상태 instance를 실제 기기 크기 frame 안에 넣었다. 로딩·오류 단계는 같은 `Screen/<ID>` component set의 variant instance를 사용했다.
- 화면 이동은 navigate, 품목 편집과 차감 확인은 overlay, overlay 내부 상태 변경은 swap, 서버 응답 단계는 timeout으로 표현했다.

### 검증 결과

- 필수 페이지 `00 Reference`부터 `05 Prototype`까지 존재한다.
- 04 Screen Spec의 7개 주 화면이 모두 `03 Design` 기반 instance다.
- 모든 보드에서 marker와 card 번호가 일치한다.
- 화면 ID와 상태 hyperlink의 미연결 항목은 없다.
- prototype reaction의 목적지 node가 모두 존재한다. 끊어진 목적지 링크는 0개다.
- 04·05에서 새로 만든 설명 텍스트 208개가 모두 `01 Foundations`의 로컬 text style에 연결되어 있다.
- 7개 화면 보드와 4개 prototype section을 `get_screenshot`으로 확인했다. DED-05 보드와 Flow B는 확대 screenshot으로 겹침과 잘림을 추가 확인했다.
- 반응 설정과 목적지 node는 구조를 다시 읽어 검증했다. Prototype을 직접 재생했다고 보지는 않는다. 사용자는 Present mode에서 시작점별 실제 클릭과 timeout 전환을 확인해야 한다.

### 남은 DECISIONS

- 기존 `D-01`부터 `D-03`까지는 미결정 상태를 유지한다.
- 녹화 전 Present mode에서 6개 시작점의 클릭 영역과 timeout 속도를 확인한다. 현재 timeout은 약 1.0~1.5초로 설정했다.
