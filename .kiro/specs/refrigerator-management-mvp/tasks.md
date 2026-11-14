# Implementation Plan: 나만의 냉장고 MVP

## Overview

승인된 요구사항과 설계를 React/Vite/TypeScript 프론트엔드, Python 3.13/FastAPI 백엔드, AWS SAM 인프라로 구현합니다. 인프라 뼈대를 먼저 만들되 실제 AWS 배포는 이 작업 목록에 포함하지 않으며, 로컬 Vite+uvicorn 자동 검증과 `sam validate`/`sam build`를 완료한 뒤에만 별도 배포 단계로 넘어갈 수 있게 구성합니다.

핵심 실행 경로는 `영수증 등록 → 재고 목록 → 한 끼 추천 → 레시피 → 차감 확인 → 원자 차감`입니다. 온라인 주문내역 검증과 3일 식단은 핵심 경로가 자동 테스트를 통과한 뒤 진행합니다.

### 시간 예산

| 실행 순서 | 구현 단위 | 필수·선택 작업 합계 |
| --- | --- | ---: |
| 1 | SAM 뼈대, 프로젝트 기반, 기기 ID | 40분 |
| 2 | 공통 모델, DynamoDB 저장소, 재고 API | 40분 |
| 3 | SPA 셸, 냉장고 목록, 품목 편집 | 45분 |
| 4 | 이미지 전처리, 영수증 인식, 확인 등록 | 55분 |
| 5 | 한 끼 추천과 조리 단계 | 40분 |
| 6 | 차감 확인, 원자 차감, 멱등성 | 45분 |
| 7 | 온라인 주문내역 검증 | 15분 |
| 8 | 3일 식단과 잔여 수량 | 30분 |
| 9 | 로컬 종단 간 검증과 SAM 로컬 검증 | 35분 |
| **합계** |  | **345분** |

`*`가 붙은 테스트 작업까지 모두 수행해도 345분이며, 15분은 장애 대응 여유로 남깁니다. 일정이 밀리면 부가 통합 테스트, 식단 끼니 완료 연동, 3일 식단 순서로 선택 작업을 생략합니다. 핵심 경로의 구현, 원자 차감 검증, 로컬 자동 검증은 생략하지 않습니다.

## Tasks

- [x] 1. 인프라 뼈대와 공통 실행 기반을 만든다. (40분, 필수)
  - [x] 1.1 SAM 템플릿과 프론트엔드·백엔드 프로젝트 뼈대를 생성한다. (20분, 필수)
    - `template.yaml`에 비공개 S3, OAC, CloudFront, HTTP API, 단일 Python 3.13 Lambda, `PAY_PER_REQUEST` DynamoDB와 최소 IAM 권한을 정의한다.
    - CloudFront 403/404의 `/index.html` 200 fallback, 두 CORS origin, Lambda 29초 timeout, `TABLE_NAME`, `MODEL_ID`, `APP_ENV`, `CORS_ORIGINS`를 구성한다.
    - `frontend/`에 Vite, React, TypeScript, Tailwind CSS, Vitest, React Testing Library, fast-check를 구성하고 `backend/`에 FastAPI, Mangum, pytest, Hypothesis를 구성한다.
    - 모든 AWS/SAM 스크립트에 `--profile default --region ap-northeast-2`를 명시하되 배포 명령은 자동 실행하지 않는다.
    - _Requirements: 10.1, 10.2, 11.1~11.12, 12.1~12.5_

  - [x] 1.2 기기 식별, 공통 API 계약과 백엔드 요청 경계를 구현한다. (12분, 필수)
    - `DeviceProvider`, UUID v4 localStorage 저장 확인, 저장 실패 차단 화면과 `apiClient`의 `X-Device-Id` 자동 주입을 구현한다.
    - FastAPI 공통 dependency에서 UUID v4 헤더를 검증하고 성공·오류 envelope, request ID, CORS와 안전한 오류 매핑을 구현한다.
    - 프론트엔드 DTO와 `ApiError`, 백엔드 Pydantic 모델, `quantity ↔ halfUnits` 경계 타입을 정의한다.
    - _Requirements: 1.1~1.7, 10.4, 10.7, 11.1~11.3, 11.9~11.10_

  - [ ]* 1.3 fast-check로 기기 식별과 요청 라우팅 property test를 작성한다. (4분, 선택)
    - **Property 1: 기기 식별과 요청 라우팅**
    - UUID 생성·저장·헤더 재사용과 서로 다른 기기의 저장소 key 분리를 최소 100회 검증한다.
    - **Validates: Requirements 1.1, 1.3, 1.5**

  - [ ]* 1.4 Hypothesis로 유효하지 않은 기기 헤더의 무부작용 property test를 작성한다. (4분, 선택)
    - **Property 2: 유효하지 않은 기기 헤더의 무부작용**
    - 누락·빈 값·UUID v4가 아닌 헤더에서 변경 API가 400을 반환하고 repository write가 0회인지 최소 100회 검증한다.
    - **Validates: Requirements 1.6, 1.7**

- [x] 2. 재고 도메인, DynamoDB 저장소와 재고 API를 구현한다. (40분, 필수)
  - [x] 2.1 재고 순수 로직, 저장소와 CRUD endpoint를 연결한다. (20분, 필수)
    - `backend/app/logic`에 반 개 단위 변환, 실제 ISO 날짜 검증, 소비기한 추정, 동일 이름 병합과 재고 정렬 함수를 구현한다.
    - `DynamoInventoryRepository`에 `DEVICE#<uuid>/INVENTORY` 문서 조회와 version 조건부 전체 교체를 구현하고 최대 200개 품목 제한을 적용한다.
    - 재고 조회, batch 등록, 품목 수정·0개 삭제·명시적 삭제 endpoint를 구현하며 실패 시 원본 문서가 유지되게 한다.
    - _Requirements: 3.4~3.8, 4.8~4.13, 5.1, 5.8~5.10, 11.4, 12.2~12.3_

  - [ ]* 2.2 Hypothesis로 반 개 단위 변환 property test를 작성한다. (4분, 선택)
    - **Property 5: 반 개 단위 변환**
    - 양의 측정량과 판매 단위에서 최근접 0.5개 및 정확한 중간값의 큰 쪽 반올림을 최소 100회 검증한다.
    - **Validates: Requirements 3.4**

  - [ ]* 2.3 Hypothesis로 소비기한 추정 property test를 작성한다. (4분, 선택)
    - **Property 7: 소비기한 추정**
    - 감지 구매일 우선, 요청일 fallback, 보관 기간 덧셈과 `expirationEstimated=true`를 최소 100회 검증한다.
    - **Validates: Requirements 3.5, 3.6, 3.7, 3.8**

  - [ ]* 2.4 Hypothesis로 동일 이름 병합 보존 property test를 작성한다. (4분, 선택)
    - **Property 9: 동일 이름 병합 보존**
    - 이름별 수량 합계, 가장 이른 소비기한, 같은 날짜의 예상 여부 논리 AND와 이름 유일성을 최소 100회 검증한다.
    - **Validates: Requirements 4.9, 4.10, 4.11, 4.12**

  - [ ]* 2.5 Hypothesis로 수정 입력 검증 property test를 작성한다. (4분, 선택)
    - **Property 10: 수정 입력 검증**
    - 이름, storage location, 실제 ISO 날짜와 halfUnits 범위가 모두 유효할 때만 저장·차감 command가 생성되는지 최소 100회 검증한다.
    - **Validates: Requirements 4.5, 4.6, 5.7, 7.3, 9.4, 9.5, 9.6**

  - [ ]* 2.6 FastAPI와 가짜 repository로 재고 API 통합 테스트를 작성한다. (4분, 선택)
    - 기기별 격리, batch 병합, version 충돌, 저장 실패 rollback, 수량 0 삭제와 빈 목록 응답을 검증한다.
    - _Requirements: 1.5~1.7, 4.8~4.14, 5.8~5.14_

- [x] 3. SPA 셸, 냉장고 목록과 품목 편집을 구현한다. (45분, 필수)
  - [x] 3.1 라우팅, 재고 상태와 냉장고 목록 화면을 구현한다. (18분, 필수)
    - `/`, `/register`, `/recipe`, `/meal-plan` 라우트와 `InventoryProvider`, `ToastProvider`, 성공 응답에서만 교체되는 `lastSuccessfulInventory`를 구현한다.
    - 소비기한 정렬, D-day·임박·지남·예상 표시, 빈 상태, loading/error/retry 상태와 추천·식단 비활성화를 구현한다.
    - 320~767px 전체 폭과 768px 이상 `max-width: 480px`인 한 열 레이아웃을 적용한다.
    - _Requirements: 5.1~5.6, 5.11~5.13, 10.1~10.2, 10.6~10.8_

  - [x] 3.2 재사용 가능한 품목 편집 모달과 직접 편집 흐름을 구현한다. (12분, 필수)
    - 등록 초안과 저장 재고에서 함께 쓰는 `ItemModal`을 만들고 이름, 0.5개 단위 수량, 보관 위치, 소비기한 수정·삭제를 연결한다.
    - 소비기한 수정 시 `expirationEstimated=false`, 입력 오류 시 저장 비활성화, 요청 중 중복 방지와 실패 시 입력 보존을 구현한다.
    - _Requirements: 4.2~4.7, 5.7~5.10, 5.14, 9.1, 9.4~9.6_

  - [ ]* 3.3 fast-check로 정렬과 날짜 표시 property test를 작성한다. (4분, 선택)
    - **Property 11: 정렬과 날짜 표시**
    - 지난 품목 우선 정렬, 그룹별 날짜 비감소, `지남`·`D-day`·`D-n`·`임박` 판정을 최소 100회 검증한다.
    - **Validates: Requirements 5.1, 5.2, 5.5, 5.6**

  - [ ]* 3.4 fast-check로 실패 시 상태 보존 property test를 작성한다. (4분, 선택)
    - **Property 12: 실패 시 상태 보존**
    - 조회·저장·편집·삭제와 LLM 작업 실패 reducer가 마지막 성공 재고와 재시도 입력을 바꾸지 않는지 최소 100회 검증한다.
    - **Validates: Requirements 5.13, 5.14, 6.11, 6.13, 7.16, 10.4, 10.8, 13.12**

  - [ ]* 3.5 냉장고 목록과 품목 편집 component test를 작성한다. (7분, 선택)
    - 빈 목록, 임박·지남·예상 배지, 320/767/768px class, 수정·삭제 성공/실패, 모든 표시 문구에 `유통기한`이 없는지 검증한다.
    - _Requirements: 4.1~4.7, 5.2~5.14, 10.1~10.2, 10.5~10.8_

- [x] 4. 이미지 전처리, 영수증 인식과 확인 등록을 구현한다. (55분, 필수)
  - [x] 4.1 브라우저 이미지 전처리와 재료 등록 화면을 구현한다. (14분, 필수)
    - JPEG/PNG/WebP 한 장을 받아 EXIF 방향과 종횡비를 유지하고 긴 변 1568px 이하, 3.75MB 이하 JPEG로 변환하는 `processImage`를 구현한다.
    - 단일 업로드 문구, 원본·처리 이미지 보존, 처리/전송 중 재선택 방지, 같은 이미지 재시도·다른 이미지·직접 입력을 구현한다.
    - 인식 결과의 수정·추가·삭제, 빈 결과, 저장 확인, batch 저장 실패 시 초안 보존을 연결한다.
    - _Requirements: 2.1~2.9, 3.15, 4.1~4.8, 4.14, 9.1, 9.8, 10.3~10.5, 13.2, 13.12_

  - [x] 4.2 Bedrock gateway와 영수증 인식 service를 구현한다. (20분, 필수)
    - Converse API의 `emit_recognition` strict tool schema, 강제 tool 선택, deadline·timeout·1회 교정과 Pydantic 의미 검증을 구현한다.
    - JPEG MIME·magic bytes·3,932,160바이트 경계를 Bedrock 호출 전에 검증한다.
    - 비식품·기본 양념 제거, 구매일 fallback, shelf-life 사전, 수량 halfUnits 정규화와 빈 성공/실패 응답 구분을 구현한다.
    - _Requirements: 3.1~3.14, 11.5~11.6, 11.9, 12.4_

  - [ ]* 4.3 fast-check로 이미지 기하 보존 property test를 작성한다. (3분, 선택)
    - **Property 3: 이미지 기하 보존**
    - 임의의 양의 너비·높이에서 긴 변 제한과 종횡비·방향 보존을 최소 100회 검증한다.
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 4.4 fast-check로 지원하지 않는 이미지의 무요청 property test를 작성한다. (3분, 선택)
    - **Property 4: 지원하지 않는 이미지의 무요청 처리**
    - JPEG/PNG/WebP가 아닌 MIME에서 인식 API 호출이 0회이고 지정 오류가 생성되는지 최소 100회 검증한다.
    - **Validates: Requirements 2.6**

  - [ ]* 4.5 Hypothesis로 인식 결과 정규화 property test를 작성한다. (4분, 선택)
    - **Property 6: 인식 결과 정규화**
    - 유효한 tool output이 필수 필드와 양의 halfUnits를 가지며 비식품과 기본 양념을 제거하는지 최소 100회 검증한다.
    - **Validates: Requirements 3.3, 3.9**

  - [ ]* 4.6 Hypothesis로 서버 이미지 경계 property test를 작성한다. (4분, 선택)
    - **Property 8: 서버 이미지 경계**
    - 임의 바이트열과 크기에서 JPEG signature와 크기 조건을 모두 만족할 때만 Bedrock mock이 호출되는지 최소 100회 검증한다.
    - **Validates: Requirements 3.10, 3.11**

  - [ ]* 4.7 인식부터 batch 등록까지 자동 통합 테스트를 작성한다. (7분, 선택)
    - Stubbed Bedrock으로 영수증 성공·빈 결과·무효 결과·timeout, 수정된 예상 소비기한, 같은 이름 병합과 저장 재시도를 검증한다.
    - _Requirements: 2.5~2.9, 3.1~3.15, 4.1~4.14, 13.2, 13.12_

- [x] 5. 한 끼 추천과 레시피 흐름을 구현한다. (40분, 필수)
  - [x] 5.1 추천·조리 단계 backend service와 endpoint를 구현한다. (12분, 필수)
    - 현지 `clientDate` 기준 가장 이른 임박 재료 또는 가장 이른 비만료 재료를 선택하고 `emit_recommendation` 결과를 의미 검증한다.
    - 현재 비만료 재고와 기본 양념만 허용하고 사용량을 1~현재 halfUnits로 제한하며 직전 메뉴 이름 제외를 적용한다.
    - `emit_recipe`를 별도 호출하고 재료 집합 제한, 1~8단계, deadline·timeout·교정과 오류 매핑을 구현한다.
    - _Requirements: 6.1~6.6, 6.8~6.13, 11.7, 11.9_

  - [x] 5.2 추천 모드의 레시피 화면과 두 단계 로딩을 구현한다. (10분, 필수)
    - 메뉴 추천 중 임박 재료 chip을 표시하고 메뉴·재료 응답 뒤 조리 단계를 별도 요청한다.
    - 조리 단계 loading/error 중에도 메뉴, 사용량·현재 재고와 `요리했어요`를 유지하고 추천·재시도 동작을 연결한다.
    - _Requirements: 6.7~6.13, 9.2, 9.10, 10.3~10.4, 13.4_

  - [ ]* 5.3 Hypothesis로 추천 우선 품목 property test를 작성한다. (4분, 선택)
    - **Property 13: 추천 우선 품목**
    - 임박 항목 우선과 임박 항목이 없을 때 가장 이른 비만료 항목 선택을 최소 100회 검증한다.
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 5.4 Hypothesis로 추천과 조리 단계 유효성 property test를 작성한다. (4분, 선택)
    - **Property 14: 추천과 조리 단계 유효성**
    - priority item 포함, 비만료 재고 최소 한 개, 사용량 범위와 허용 재료 집합을 최소 100회 검증한다.
    - **Validates: Requirements 6.3, 6.4, 6.5, 6.6, 6.9**

  - [ ]* 5.5 Hypothesis로 다른 메뉴 제외 property test를 작성한다. (3분, 선택)
    - **Property 15: 다른 메뉴 제외**
    - 직전 메뉴 이름과 같은 결과가 승인되지 않는지 최소 100회 검증한다.
    - **Validates: Requirements 6.12**

  - [ ]* 5.6 추천과 조리 단계 통합·component test를 작성한다. (7분, 선택)
    - 임박 우선, expired 제외, recipe 별도 호출, 단계 pending/실패 중 `요리했어요` 유지, 다른 메뉴와 timeout 재시도를 검증한다.
    - _Requirements: 6.1~6.13, 10.3~10.4, 13.4_

- [x] 6. 차감 확인, 원자 차감과 멱등성을 구현한다. (45분, 필수)
  - [x] 6.1 차감 순수 함수와 DynamoDB 원자·멱등 service를 구현한다. (14분, 필수)
    - item ID순 canonical payload SHA-256, 재고 version 조건과 `DEDUCTION#<requestId>` 조건을 하나의 `TransactWriteItems`에 구현한다.
    - 동일 ID·동일 payload는 기존 결과를 반환하고 동일 ID·다른 payload는 409, 품목·수량 오류나 초과 차감은 write 전 오류로 처리한다.
    - 성공 시 수량을 정확히 한 번 줄이고 0인 품목을 제거하며 실패 시 전체 재고를 유지한다.
    - _Requirements: 7.9~7.12, 7.15~7.17, 9.7, 9.9_

  - [x] 6.2 차감 초안 모달과 성공 후 재고 반영을 구현한다. (11분, 필수)
    - 추천 재료 전체를 포함한 초안, 포함 해제, 0.5개 단위 수정, 현재 재고의 다른 품목 1개 추가와 실시간 전후 수량을 구현한다.
    - 재고 이하 입력만 허용하고 0개 제거 안내, 빈 선택 비활성화, 취소 무요청, 요청 중 중복 방지를 구현한다.
    - 전송 후 실패에는 수정 초안과 같은 Deduction_Request_ID를 유지하고 성공 시 최신 재고·차감 수·제거 품목 토스트를 표시한다.
    - _Requirements: 7.1~7.17, 9.2, 9.7, 9.9, 10.5~10.6, 13.4~13.5_

  - [ ]* 6.3 fast-check로 차감 초안과 요청 투영 property test를 작성한다. (3분, 선택)
    - **Property 16: 차감 초안과 요청 투영**
    - 최초 포함 상태와 확정 시 포함 품목·확정 수량·요청 ID만 전송되는지 최소 100회 검증한다.
    - **Validates: Requirements 7.1, 7.9, 9.7**

  - [ ]* 6.4 Hypothesis로 차감 산술과 제거 property test를 작성한다. (3분, 선택)
    - **Property 17: 차감 산술과 제거**
    - 유효 사용량에서 `현재-사용`, 0 제거, 양수 항목 단일 존속을 최소 100회 검증한다.
    - **Validates: Requirements 7.3, 7.5, 7.11**

  - [ ]* 6.5 Hypothesis 인메모리 원자 저장소로 차감 멱등성 property test를 작성한다. (5분, 선택)
    - **Property 18: 차감 멱등성**
    - 동일 ID·payload 반복 결과와 version 동일성, 다른 payload 충돌과 무변경을 최소 100회 검증한다.
    - **Validates: Requirements 7.10, 7.12, 7.15**

  - [ ]* 6.6 fast-check로 차감 전후 표시 property test를 작성한다. (3분, 선택)
    - **Property 23: 차감 전후 표시**
    - formatter가 `<품목명> <현재>개 → <차감 후>개` 순서와 0.5 단위 값을 손실 없이 포함하는지 최소 100회 검증한다.
    - **Validates: Requirements 7.6, 13.5**

  - [ ]* 6.7 원자 차감 API와 모달 통합 테스트를 작성한다. (6분, 선택)
    - DynamoDB stub으로 성공, 중복, payload 재사용, version 경합, 일부 오류 시 전체 rollback을 검증한다.
    - UI에서 전체 해제, 품목 추가, 취소, 실패 후 같은 ID 재시도와 `양파 8개 → 7개` 표시를 검증한다.
    - _Requirements: 7.1~7.17, 9.2, 9.7, 9.9, 13.4~13.5_

- [x] 7. 온라인 주문내역 인식 호환성을 검증하고 보완한다. (15분, 핵심 흐름 이후 필수)
  - [x] 7.1 주문내역 fixture와 인식 정규화 보완 코드를 추가한다. (10분, 필수)
    - 주문내역 캡처용 Bedrock 응답 fixture를 추가하고 영수증과 동일한 `RecognitionResultDto` 경로를 사용하게 한다.
    - 상품 옵션·묶음 수량·중량 표기를 일반 품목명과 halfUnits로 정규화하되 별도 업로드 유형 선택이나 별도 endpoint를 만들지 않는다.
    - _Requirements: 2.1, 3.2~3.9, 13.3, 13.8_

  - [ ]* 7.2 주문내역 등록 자동 통합 테스트를 작성한다. (5분, 선택)
    - 같은 업로드 동작, 주문 캡처 fixture 인식, 사용자 수정, batch 저장과 기존 동일 이름 병합까지 검증한다.
    - _Requirements: 2.1~2.5, 3.2~3.9, 4.1~4.14, 13.3_

- [x] 8. 3일 식단과 끼니 재사용 흐름을 구현한다. (30분, 시간 부족 시 8.2·8.6·8.7부터 생략 가능)
  - [x] 8.1 3일 식단 backend 생성·검증 endpoint를 구현한다. (8분, 필수)
    - `emit_meal_plan` strict schema로 `(1,점심)`부터 `(3,저녁)`까지 정확히 6개 끼니를 생성한다.
    - 각 끼니 직전 예상 잔여량에서 가장 이른 임박 또는 비만료 재료를 우선하고 expired·재고 외 재료·초과 사용을 거부한다.
    - 사용 가능 재료 없음과 생성 실패를 구분하고 deadline·timeout·교정 규칙을 적용한다.
    - _Requirements: 8.1~8.5, 8.15~8.17, 11.8~11.9_

  - [x] 8.2 식단 화면, 잔여량 요약과 끼니 레시피·차감 재사용을 구현한다. (8분, 선택)
    - 생성 시점 snapshot으로 현재·사용 합계·3일 뒤 잔여·부족 수량과 정확히 6개 끼니 카드를 표시한다.
    - `MealPlanProvider`에 메모리 식단과 완료 끼니 ID를 유지하고 새로고침 초기화, 재생성, 식단 모드 RecipePage와 DeductionModal 복귀를 연결한다.
    - _Requirements: 8.6~8.17, 9.3, 9.10, 13.6, 13.9~13.10_

  - [ ]* 8.3 Hypothesis로 식단 구조와 재료 제한 property test를 작성한다. (3분, 선택)
    - **Property 19: 식단 구조와 재료 제한**
    - 6개 day/slot 순서와 모든 재료의 비만료 재고·기본 양념 집합 포함을 최소 100회 검증한다.
    - **Validates: Requirements 8.1, 8.4, 8.5**

  - [ ]* 8.4 Hypothesis로 식단 순차 우선 소비 property test를 작성한다. (3분, 선택)
    - **Property 20: 식단 순차 우선 소비**
    - 각 끼니 직전 잔여량 기준 임박 우선 및 가장 이른 비만료 fallback을 최소 100회 검증한다.
    - **Validates: Requirements 8.2, 8.3**

  - [ ]* 8.5 fast-check로 식단 잔여량과 부족량 property test를 작성한다. (2분, 선택)
    - **Property 21: 식단 잔여량과 부족량**
    - `max(0, stock-use)`, `max(0, use-stock)`과 두 값이 동시에 양수가 아님을 최소 100회 검증한다.
    - **Validates: Requirements 8.7, 8.8**

  - [ ]* 8.6 fast-check로 완료 끼니 전이 property test를 작성한다. (2분, 선택)
    - **Property 22: 완료 끼니 전이**
    - 차감 성공은 해당 끼니만 추가하고 실패·취소는 완료 집합을 바꾸지 않는지 최소 100회 검증한다.
    - **Validates: Requirements 8.10, 8.11**

  - [ ]* 8.7 식단 생성과 화면 왕복 통합 테스트를 작성한다. (4분, 선택)
    - 정확히 6개 끼니, 잔여·부족 표시, recipe 별도 요청, 차감 성공 한 끼만 완료, 실패·취소 무변경과 Provider remount 초기화를 검증한다.
    - _Requirements: 8.1~8.17, 9.3, 13.6_

- [x] 9. 로컬 종단 간 자동 검증과 SAM 로컬 검증을 완료한다. (35분, 필수)
  - [x] 9.1 핵심 데모 경로의 자동 종단 간 테스트를 작성한다. (15분, 필수)
    - Bedrock과 DynamoDB adapter를 test double로 교체해 `영수증 업로드 → 수정 → 저장 → 목록 → 추천 → recipe → 차감 초안 → 원자 차감 → 갱신 목록`을 한 테스트로 검증한다.
    - 별도 시나리오에서 같은 차감 ID 재전송, 인식·추천 timeout 복구, 주문내역 등록과 6개 끼니 식단을 검증한다.
    - _Requirements: 13.2~13.6, 13.12_

  - [x] 9.2 Vite+uvicorn 로컬 자동 smoke 검증 스크립트를 구현한다. (8분, 필수)
    - 비대화형 스크립트가 uvicorn과 Vite를 임시 child process로 시작하고 API health, SPA index와 CORS를 검사한 뒤 성공·실패 모두에서 process를 종료하게 한다.
    - 실제 AWS credential 없이 local fake adapter를 선택하는 `APP_ENV=test` 경로를 사용하고 장시간 실행되는 dev server나 watch process를 남기지 않는다.
    - _Requirements: 11.1~11.3, 12.6, 13.2~13.4_

  - [x] 9.3 전체 자동 테스트와 프로덕션 빌드 검증 명령을 연결한다. (7분, 필수)
    - 단일 비대화형 명령에서 `pytest`, `vitest --run`, TypeScript 검사와 `npm --prefix frontend run build`를 실행하도록 스크립트를 작성하고 실패 코드를 보존한다.
    - 핵심 경로 테스트를 먼저 실행하고 선택 식단 테스트를 나중에 실행해 시간 부족 시 제외 범위가 분명하게 한다.
    - _Requirements: 11.1~11.3, 13.7~13.10_

  - [x] 9.4 SAM 템플릿 로컬 검증을 실행 가능하게 고정한다. (5분, 필수)
    - `sam validate --profile default --region ap-northeast-2`와 `sam build --profile default --region ap-northeast-2`를 로컬 검증 스크립트에 넣고 두 명령의 오류를 그대로 반환한다.
    - 로컬 Vite+uvicorn smoke와 전체 자동 테스트가 성공한 뒤에만 SAM 검증이 실행되게 순서를 고정하며 AWS 배포는 수행하지 않는다.
    - _Requirements: 12.5~12.8, 13.11_

- [-] 10. Checkpoint - 핵심 경로와 전체 시간 예산을 확인한다.
  - Ensure all tests pass, ask the user if questions arise.
  - 핵심 경로 구현과 로컬 자동 검증을 먼저 완료하고, 누적 시간이 330분을 넘으면 8.2, 8.6, 8.7과 기타 선택 통합 테스트를 생략해 360분 상한을 지킨다.

## Notes

- `*`가 붙은 sub-task는 선택 작업이며 시간 부족 시 생략할 수 있습니다. 필수 구현과 9장의 핵심 자동 검증은 생략하지 않습니다.
- 각 correctness property는 독립된 fast-check 또는 Hypothesis 테스트 한 개로 구현하고 최소 100개 사례를 실행합니다.
- 테스트 주석은 `Feature: refrigerator-management-mvp, Property {번호}: {속성 문장}` 형식을 사용합니다.
- 이 계획은 코드 작성과 자동 테스트, 로컬 빌드까지만 포함합니다. AWS 배포와 수동 데모 리허설은 coding task가 아니므로 포함하지 않습니다.
- AWS/SAM 명령은 항상 `--profile default --region ap-northeast-2`를 사용합니다.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "3.1"] },
    { "id": 4, "tasks": ["3.2"] },
    { "id": 5, "tasks": ["3.3", "3.4", "3.5", "4.1", "4.2"] },
    { "id": 6, "tasks": ["4.3", "4.4", "4.5", "4.6", "4.7"] },
    { "id": 7, "tasks": ["5.1"] },
    { "id": 8, "tasks": ["5.2"] },
    { "id": 9, "tasks": ["5.3", "5.4", "5.5", "5.6", "6.1"] },
    { "id": 10, "tasks": ["6.2"] },
    { "id": 11, "tasks": ["6.3", "6.4", "6.5", "6.6", "6.7"] },
    { "id": 12, "tasks": ["7.1"] },
    { "id": 13, "tasks": ["7.2"] },
    { "id": 14, "tasks": ["8.1"] },
    { "id": 15, "tasks": ["8.2"] },
    { "id": 16, "tasks": ["8.3", "8.4", "8.5", "8.6", "8.7"] },
    { "id": 17, "tasks": ["9.1"] },
    { "id": 18, "tasks": ["9.2"] },
    { "id": 19, "tasks": ["9.3"] },
    { "id": 20, "tasks": ["9.4"] }
  ]
}
```
