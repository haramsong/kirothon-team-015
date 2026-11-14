# Requirements Document

## Introduction

이 문서는 1인 가구 사용자가 영수증 사진 또는 온라인 주문내역 캡처로 식재료를 등록하고, 소비기한이 가까운 재료로 메뉴를 추천받아 요리한 뒤 실제 사용량을 재고에서 차감하는 냉장고 관리 MVP의 전체 범위를 정의합니다. 대표 데모 흐름은 `등록 → 추천 → 요리 → 재고 차감`이며, 보조 데모 흐름은 3일 식단 생성과 식단 끼니의 재사용입니다.

MVP는 1인 개발자가 6시간 안에 구현하고 녹화 데모를 완주하는 것을 목표로 합니다. 구현 우선순위는 데모 흐름의 종단 간 동작, 요리 후 재고 차감, 온라인 주문내역 인식, 3일 식단 순서입니다.

회원가입, 로그인, 여러 사용자 간 공유, 푸시 알림, 바코드 스캔, 영양 정보, 칼로리 계산, 장보기 목록 및 쇼핑몰 연동은 MVP 범위에서 제외합니다.

## Glossary

- **Refrigerator_Management_MVP**: 이 문서에서 명세하는 1인 가구 냉장고 관리 서비스 전체
- **Client_App**: React, Vite, TypeScript, Tailwind CSS로 구현하는 비서버 렌더링 단일 페이지 애플리케이션
- **API_Service**: Python 3.13, FastAPI, Mangum으로 구현하고 AWS Lambda에서 실행하는 백엔드 API
- **Recognition_Service**: Amazon Bedrock의 비전 기능을 이용해 Shopping_Image를 Recognition_Result로 변환하는 구성 요소
- **Inventory_Service**: Device_ID별 냉장고 재고의 조회, 저장, 수정, 삭제를 담당하는 구성 요소
- **Recommendation_Service**: 현재 재고를 바탕으로 한 끼 메뉴와 Recipe_Steps를 생성하는 구성 요소
- **Deduction_Service**: 사용자가 확인한 요리 사용량을 재고에서 원자적으로 차감하는 구성 요소
- **Meal_Plan_Service**: 현재 재고를 바탕으로 Meal_Plan과 예상 잔여 수량을 생성하는 구성 요소
- **Infrastructure_Stack**: AWS SAM 템플릿으로 정의하는 S3, CloudFront, API Gateway HTTP API, Lambda, DynamoDB 및 IAM 리소스 집합
- **MVP_Plan**: 6시간 1인 개발 제약, 작업별 분 단위 배정 및 구현 우선순위를 기록하는 구현 계획
- **Demo_Build**: 핵심 데모 시나리오를 실행할 수 있는 배포 또는 로컬 빌드
- **Device_ID**: 로그인 없이 브라우저 단위 데이터를 구분하기 위해 최초 접속 시 생성하는 UUID v4 값
- **Valid_Device_ID**: 소문자 또는 대문자 16진수로 표현한 `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx` 형식이며 `y`의 첫 글자가 8, 9, a, b 중 하나인 Device_ID
- **X_Device_ID_Header**: API 요청에 Device_ID를 전달하는 `X-Device-Id` HTTP 헤더
- **Supported_Image_File**: JPEG, PNG 또는 WebP 형식의 이미지 파일 한 장
- **Shopping_Image**: 단일 입력 동작으로 선택한 영수증 사진 또는 온라인 주문내역 캡처 한 장
- **Processed_Image**: Shopping_Image의 방향과 가로세로 비율을 유지하고 긴 변을 1568픽셀 이하로 축소한 3.75MB 이하 JPEG 이미지
- **Recognition_Result**: 구매일과 0개 이상의 Inventory_Item 후보로 구성되며 영수증과 온라인 주문내역에 공통으로 사용하는 인식 결과
- **Inventory_Item**: 품목명, 0.5개 배수 수량, Storage_Location, 소비기한 및 소비기한 예상 여부를 가진 재고 항목
- **Storage_Location**: `냉장`, `냉동`, `실온` 중 하나인 보관 위치
- **Estimated_Expiration_Date**: 구매일, 품목 및 Storage_Location별 일반 보관 기간으로 산출하고 화면에 `예상`으로 표시하는 소비기한
- **Basic_Seasonings**: 재고 보유 여부와 관계없이 사용할 수 있고 등록 및 차감 대상에서 제외하는 소금, 설탕, 간장, 식용유, 후추, 참기름, 식초, 고춧가루
- **Half_Unit_Rounding**: kg, g 또는 L 수량을 품목별 일반 판매 단위로 나눈 값을 가장 가까운 0.5개로 반올림하고 정확한 중간값은 큰 쪽 0.5개로 정하는 변환 규칙
- **Calendar_Date_Difference**: 사용자 기기의 현지 달력 날짜를 기준으로 소비기한 날짜에서 현재 날짜를 뺀 정수 일수
- **Expiring_Item**: Calendar_Date_Difference가 0 이상 3 이하인 Inventory_Item
- **Expired_Item**: Calendar_Date_Difference가 0보다 작은 Inventory_Item
- **Meal_Recommendation**: 한 끼 1인분의 메뉴 이름과 Inventory_Item별 예상 사용량
- **Recipe_Steps**: Meal_Recommendation의 재료와 Basic_Seasonings만 사용하는 번호 순서의 조리 단계
- **Deduction_Draft**: 차감 전에 사용자가 품목 포함 여부와 0.5개 배수 사용량을 수정하는 확인 데이터
- **Deduction_Preview**: 품목명, 현재 수량, 사용 수량 및 차감 후 수량을 표시한 정보
- **Deduction_Request_ID**: 같은 차감 확정 요청의 중복 적용을 막기 위해 Client_App이 생성하는 요청별 고유 식별자
- **Meal_Plan**: 3일 동안 하루 점심과 저녁으로 구성된 정확히 6개 Meal_Recommendation의 순서 있는 집합
- **Completed_Meal**: 재고 차감이 성공한 Meal_Plan의 끼니
- **LLM_Request**: Recognition_Service, Recommendation_Service 또는 Meal_Plan_Service가 Amazon Bedrock에 보내는 생성 요청
- **Atomic_Update**: 한 요청에 포함된 모든 변경을 함께 적용하거나 어떤 변경도 적용하지 않는 저장 방식
- **Session_Lifetime**: Client_App을 새로고침하기 전까지 유지되는 브라우저 실행 기간
- **D_Day_Label**: Calendar_Date_Difference에 따라 미래 날짜를 `D-n`, 당일을 `D-day`, 지난 날짜를 `지남`으로 표시하는 형식
- **Last_Successful_Inventory**: Client_App이 가장 최근에 성공적으로 조회하거나 변경한 뒤 표시한 재고 상태

## Requirements

### Requirement 1: 기기 기반 사용자 구분

**User Story:** 1인 가구 사용자로서, 로그인 없이 현재 브라우저에서 개인 냉장고를 사용하고 싶습니다. 그래야 가입 절차 없이 데모 흐름을 시작할 수 있습니다.

#### Acceptance Criteria

1. WHEN 저장된 Device_ID가 없는 브라우저에서 Client_App이 최초 실행되면, THE Client_App SHALL Valid_Device_ID를 생성한다.
2. WHEN Client_App이 Valid_Device_ID를 생성하면, THE Client_App SHALL Valid_Device_ID를 localStorage에 저장한다.
3. WHILE Valid_Device_ID가 localStorage에 저장되어 있으면, THE Client_App SHALL 모든 API 요청에 Valid_Device_ID와 같은 값의 X_Device_ID_Header를 포함한다.
4. IF Client_App이 Device_ID를 localStorage에 저장하지 못하면, THEN THE Client_App SHALL API 요청을 전송하지 않고 기기 식별자 저장 실패를 표시한다.
5. WHEN Valid_Device_ID가 포함된 재고 요청을 수신하면, THE API_Service SHALL 해당 Device_ID의 데이터만 조회하거나 변경한다.
6. IF X_Device_ID_Header가 누락되거나 빈 값이면, THEN THE API_Service SHALL 재고 데이터를 변경하지 않고 HTTP 400 응답을 반환한다.
7. IF X_Device_ID_Header가 Valid_Device_ID 형식과 일치하지 않으면, THEN THE API_Service SHALL 재고 데이터를 변경하지 않고 HTTP 400 응답을 반환한다.

### Requirement 2: 장보기 이미지 입력과 전처리

**User Story:** 1인 가구 사용자로서, 영수증 사진과 온라인 주문내역 캡처를 같은 방법으로 올리고 싶습니다. 그래야 구매 경로와 관계없이 식재료를 등록할 수 있습니다.

#### Acceptance Criteria

1. THE Client_App SHALL `영수증 사진 또는 주문내역 캡처 올리기`라는 단일 입력 동작으로 Supported_Image_File 한 장을 받는다.
2. WHEN 사용자가 Supported_Image_File을 선택하면, THE Client_App SHALL 원본 방향과 가로세로 비율을 유지한 Processed_Image를 생성한다.
3. WHEN Processed_Image를 생성하면, THE Client_App SHALL Processed_Image의 긴 변을 1568픽셀 이하로 제한한다.
4. WHEN Processed_Image를 생성하면, THE Client_App SHALL Processed_Image를 3.75MB 이하의 JPEG 형식으로 변환한다.
5. WHEN Processed_Image 생성이 완료되면, THE Client_App SHALL 한 번의 인식 요청에 Processed_Image 한 장을 전송한다.
6. IF 사용자가 Supported_Image_File이 아닌 파일을 선택하면, THEN THE Client_App SHALL 인식 요청을 전송하지 않고 `사진 파일만 올릴 수 있어요`를 표시한다.
7. IF Processed_Image 생성에 실패하면, THEN THE Client_App SHALL 선택한 Shopping_Image를 유지하고 전처리 재시도 동작을 제공한다.
8. IF 인식 요청 전송에 실패하면, THEN THE Client_App SHALL Processed_Image를 유지하고 같은 이미지 인식 재시도 동작을 제공한다.
9. WHILE Processed_Image 생성 또는 인식 요청이 진행 중이면, THE Client_App SHALL 파일 재선택과 추가 인식 요청 동작을 비활성화한다.

### Requirement 3: 영수증 및 온라인 주문내역 인식

**User Story:** 1인 가구 사용자로서, 장보기 이미지에서 등록할 식재료 정보를 자동으로 얻고 싶습니다. 그래야 품목을 하나씩 입력하지 않아도 됩니다.

#### Acceptance Criteria

1. WHEN 영수증 사진을 수신하면, THE Recognition_Service SHALL Recognition_Result 스키마에 맞는 결과를 생성한다.
2. WHEN 온라인 주문내역 캡처를 수신하면, THE Recognition_Service SHALL 영수증 사진과 동일한 Recognition_Result 스키마에 맞는 결과를 생성한다.
3. WHEN 식재료를 인식하면, THE Recognition_Service SHALL 각 Inventory_Item에 품목명, 0.5개 배수 수량, Storage_Location, 소비기한 및 소비기한 예상 여부를 제공한다.
4. WHEN kg, g 또는 L 단위 수량을 인식하면, THE Recognition_Service SHALL 품목별 일반 판매 단위를 기준으로 Half_Unit_Rounding을 적용한다.
5. WHEN 소비기한을 추정하면, THE Recognition_Service SHALL 인식한 품목과 Storage_Location에 해당하는 일반 보관 기간을 구매일에 더한다.
6. WHEN 구매일을 인식하면, THE Recognition_Service SHALL 인식한 구매일을 소비기한 추정 기준일로 사용한다.
7. IF 구매일을 인식하지 못하면, THEN THE Recognition_Service SHALL API_Service가 요청을 받은 날짜를 소비기한 추정 기준일로 사용한다.
8. WHEN Estimated_Expiration_Date를 생성하면, THE Recognition_Service SHALL 소비기한 예상 여부를 `true`로 설정한다.
9. WHEN 비식품 또는 Basic_Seasonings를 인식하면, THE Recognition_Service SHALL 해당 항목을 Recognition_Result의 Inventory_Item 목록에서 제외한다.
10. WHEN API_Service가 인식 요청을 수신하면, THE API_Service SHALL 입력이 JPEG 형식이고 3.75MB 이하인지 검증한다.
11. IF 입력이 JPEG 형식이 아니거나 3.75MB를 초과하면, THEN THE API_Service SHALL LLM_Request를 전송하지 않고 HTTP 400 응답을 반환한다.
12. WHEN 식재료를 인식하지 못했지만 Recognition_Result 생성에 성공하면, THE Recognition_Service SHALL 빈 Inventory_Item 목록과 성공 상태를 반환한다.
13. IF LLM_Request가 29초 안에 완료되지 않으면, THEN THE API_Service SHALL 시간 초과로 식별할 수 있는 오류 응답을 29초 안에 반환한다.
14. IF Recognition_Result 생성이 실패하면, THEN THE API_Service SHALL 빈 인식 결과와 구분되는 인식 실패 오류 응답을 반환한다.
15. IF API_Service가 시간 초과 또는 인식 실패 오류를 반환하면, THEN THE Client_App SHALL 같은 Shopping_Image 재시도, 다른 이미지 선택 및 직접 입력 동작을 제공한다.

### Requirement 4: 인식 결과 확인과 재고 등록

**User Story:** 1인 가구 사용자로서, AI가 추정한 등록 정보를 저장 전에 고치고 싶습니다. 그래야 실제로 구매한 재료와 냉장고 재고를 맞출 수 있습니다.

#### Acceptance Criteria

1. WHEN Recognition_Result가 표시되면, THE Client_App SHALL 각 Inventory_Item의 품목명, 수량, Storage_Location, 소비기한 및 소비기한 예상 여부를 표시한다.
2. WHILE Recognition_Result를 확인하는 중이면, THE Client_App SHALL 각 Inventory_Item의 품목명, 수량, Storage_Location 및 소비기한을 수정할 수 있게 한다.
3. WHILE Recognition_Result를 확인하는 중이면, THE Client_App SHALL Inventory_Item을 추가하거나 삭제할 수 있게 한다.
4. WHEN 사용자가 Estimated_Expiration_Date를 수정하면, THE Client_App SHALL 해당 소비기한 예상 여부를 `false`로 변경한다.
5. IF Inventory_Item 수량이 0.5개 미만이거나 0.5개 배수가 아니면, THEN THE Client_App SHALL 해당 수량 오류를 표시하고 재고 저장 동작을 비활성화한다.
6. IF Inventory_Item의 품목명, Storage_Location 또는 소비기한이 비어 있으면, THEN THE Client_App SHALL 해당 필드 오류를 표시하고 재고 저장 동작을 비활성화한다.
7. IF Recognition_Result의 Inventory_Item이 0개이면, THEN THE Client_App SHALL 재고 저장 동작을 비활성화하고 품목 추가 동작을 제공한다.
8. WHEN 사용자가 1개 이상의 유효한 Inventory_Item 저장을 확정하면, THE Inventory_Service SHALL 확인된 Inventory_Item 목록을 해당 Device_ID의 재고에 Atomic_Update로 저장한다.
9. WHEN 저장할 품목명과 기존 품목명이 정확히 일치하면, THE Inventory_Service SHALL 두 Inventory_Item을 한 항목으로 병합한다.
10. WHEN 같은 이름의 Inventory_Item을 병합하면, THE Inventory_Service SHALL 두 수량의 합계를 병합된 Inventory_Item 수량으로 저장한다.
11. WHEN 같은 이름이며 소비기한이 서로 다른 Inventory_Item을 병합하면, THE Inventory_Service SHALL 이른 소비기한과 이른 소비기한에 대응하는 예상 여부를 저장한다.
12. WHEN 같은 이름이며 소비기한이 같은 Inventory_Item을 병합하면, THE Inventory_Service SHALL 두 예상 여부 중 하나라도 `false`이면 병합된 예상 여부를 `false`로 저장한다.
13. IF 재고 저장에 실패하면, THEN THE Inventory_Service SHALL 저장 요청 전 재고를 유지한다.
14. IF 재고 저장에 실패하면, THEN THE Client_App SHALL 수정된 Recognition_Result를 유지하고 저장 재시도 동작을 제공한다.

### Requirement 5: 냉장고 재고 조회와 직접 편집

**User Story:** 1인 가구 사용자로서, 현재 재고와 소비기한을 한눈에 확인하고 고치고 싶습니다. 그래야 화면의 재고를 실제 냉장고와 일치시킬 수 있습니다.

#### Acceptance Criteria

1. WHEN 냉장고 목록을 조회하면, THE Inventory_Service SHALL Expired_Item을 소비기한 오름차순으로 먼저 배치하고 나머지 Inventory_Item을 소비기한 오름차순으로 배치한다.
2. WHEN Inventory_Item을 표시하면, THE Client_App SHALL Calendar_Date_Difference로 D_Day_Label을 계산한다.
3. WHEN Inventory_Item을 표시하면, THE Client_App SHALL 품목명, 수량, Storage_Location, 소비기한 및 D_Day_Label을 표시한다.
4. WHEN 소비기한 예상 여부가 `true`인 Inventory_Item을 표시하면, THE Client_App SHALL 소비기한 옆에 `예상`을 표시한다.
5. WHEN Expiring_Item을 표시하면, THE Client_App SHALL `임박`을 표시한다.
6. WHEN Expired_Item을 표시하면, THE Client_App SHALL `지남`을 표시한다.
7. IF 편집한 Inventory_Item 수량이 0.5개 배수가 아니거나 품목명, Storage_Location 또는 소비기한이 유효하지 않으면, THEN THE Client_App SHALL 해당 오류를 표시하고 편집 확정 동작을 비활성화한다.
8. WHEN 사용자가 0.5개 이상의 유효한 Inventory_Item 편집을 확정하면, THE Inventory_Service SHALL 품목명, 수량, Storage_Location, 소비기한 및 소비기한 예상 여부를 저장한다.
9. WHEN 사용자가 Inventory_Item 수량 0개를 확정하면, THE Inventory_Service SHALL 해당 Inventory_Item을 재고에서 삭제한다.
10. WHEN 사용자가 Inventory_Item 삭제를 확정하면, THE Inventory_Service SHALL 해당 Device_ID의 재고에서 Inventory_Item을 삭제한다.
11. WHEN 해당 Device_ID의 Inventory_Item이 0개이면, THE Client_App SHALL 영수증 사진 또는 주문내역 캡처 등록을 안내하는 빈 상태를 표시한다.
12. WHILE 해당 Device_ID의 Inventory_Item이 0개이면, THE Client_App SHALL 한 끼 추천과 3일 식단 진입 동작을 비활성화한다.
13. IF 냉장고 목록 조회에 실패하면, THEN THE Client_App SHALL Last_Successful_Inventory를 유지하고 목록 조회 재시도 동작을 표시한다.
14. IF Inventory_Item 편집 또는 삭제에 실패하면, THEN THE Client_App SHALL Last_Successful_Inventory와 편집 입력값을 유지하고 실패한 동작의 재시도 수단을 표시한다.

### Requirement 6: 한 끼 메뉴 추천과 레시피

**User Story:** 1인 가구 사용자로서, 소비기한이 가까운 재료로 만들 한 끼 메뉴와 조리법을 받고 싶습니다. 그래야 남은 재료를 제때 사용할 수 있습니다.

#### Acceptance Criteria

1. WHEN 사용자가 한 끼 추천을 요청하고 Expiring_Item이 있으면, THE Recommendation_Service SHALL Expiring_Item 중 소비기한이 가장 빠른 재료를 우선 사용하는 Meal_Recommendation 한 개를 생성한다.
2. IF Expiring_Item이 없으면, THEN THE Recommendation_Service SHALL Expired_Item이 아닌 Inventory_Item 중 소비기한이 가장 빠른 재료를 우선 사용하는 Meal_Recommendation 한 개를 생성한다.
3. WHEN Meal_Recommendation을 생성하면, THE Recommendation_Service SHALL 1인분 메뉴에 Inventory_Item을 최소 한 개 포함한다.
4. WHEN Meal_Recommendation을 생성하면, THE Recommendation_Service SHALL Expired_Item을 사용 재료에서 제외한다.
5. WHEN Meal_Recommendation을 생성하면, THE Recommendation_Service SHALL 현재 Inventory_Item과 Basic_Seasonings만 사용한다.
6. WHEN Meal_Recommendation을 생성하면, THE Recommendation_Service SHALL 각 Inventory_Item 예상 사용량을 0.5개 이상, 현재 수량 이하인 0.5개 배수로 반환한다.
7. WHEN Meal_Recommendation을 수신하면, THE Client_App SHALL 품목별 예상 사용량과 현재 재고 수량을 함께 표시한다.
8. WHEN Meal_Recommendation을 수신하면, THE Client_App SHALL Recipe_Steps를 별도 API 요청으로 조회한다.
9. WHEN Recipe_Steps를 생성하면, THE Recommendation_Service SHALL Meal_Recommendation의 Inventory_Item과 Basic_Seasonings만 Recipe_Steps의 재료로 사용한다.
10. WHILE Recipe_Steps를 조회하는 중이면, THE Client_App SHALL 메뉴 이름, 사용 재료 및 `요리했어요` 동작을 표시한다.
11. IF Recipe_Steps 조회에 실패하면, THEN THE Client_App SHALL Meal_Recommendation을 유지하고 Recipe_Steps 재시도 동작을 제공한다.
12. WHEN 사용자가 다른 메뉴 추천을 요청하면, THE Recommendation_Service SHALL 직전 Meal_Recommendation의 메뉴 이름과 다른 이름의 Meal_Recommendation을 생성한다.
13. IF Meal_Recommendation을 생성하지 못하면, THEN THE Client_App SHALL 현재 재고 화면 상태를 유지하고 추천 재시도 동작을 표시한다.

### Requirement 7: 요리 후 재고 차감

**User Story:** 1인 가구 사용자로서, 요리에 실제로 쓴 수량을 확인한 뒤 한 번에 차감하고 싶습니다. 그래야 재고 목록이 실제 냉장고와 계속 맞습니다.

#### Acceptance Criteria

1. WHEN 사용자가 `요리했어요`를 선택하면, THE Client_App SHALL Meal_Recommendation의 모든 Inventory_Item을 기본 포함한 Deduction_Draft를 생성한다.
2. WHILE Deduction_Draft를 확인하는 중이면, THE Client_App SHALL 각 품목의 포함 여부를 변경할 수 있게 한다.
3. WHILE Deduction_Draft를 확인하는 중이면, THE Client_App SHALL 각 포함 품목의 사용량을 0.5개 이상, 현재 재고 이하인 0.5개 배수로 수정할 수 있게 한다.
4. WHILE Deduction_Draft를 확인하는 중이면, THE Client_App SHALL 현재 재고의 다른 Inventory_Item을 사용량 1개로 추가할 수 있게 한다.
5. WHEN Deduction_Draft의 사용량이 변경되면, THE Client_App SHALL 차감 후 수량을 `현재 수량 - 사용량`으로 계산한다.
6. WHEN Deduction_Draft를 표시하면, THE Client_App SHALL 각 품목의 품목명, 현재 수량, 사용 수량 및 차감 후 수량을 Deduction_Preview로 표시한다.
7. WHEN 차감 후 수량이 0개이면, THE Client_App SHALL 해당 품목이 재고 목록에서 제거된다는 정보를 표시한다.
8. IF Deduction_Draft의 포함 품목이 0개이면, THEN THE Client_App SHALL 차감 확정 동작을 비활성화한다.
9. WHEN 사용자가 차감을 확정하면, THE Client_App SHALL Deduction_Request_ID와 포함 품목만 차감 요청에 전달한다.
10. WHEN 유효한 차감 요청을 수신하면, THE Deduction_Service SHALL 포함된 모든 품목의 사용량을 해당 Device_ID 재고에 Atomic_Update로 적용한다.
11. WHEN 차감 결과 수량이 0개이면, THE Deduction_Service SHALL 해당 Inventory_Item을 재고에서 삭제한다.
12. WHEN 같은 Deduction_Request_ID의 차감 요청을 두 번 이상 수신하면, THE Deduction_Service SHALL 해당 차감 요청을 최대 한 번만 재고에 적용한다.
13. WHILE 차감 확정 요청이 진행 중이면, THE Client_App SHALL 추가 차감 확정 동작을 비활성화한다.
14. WHEN 사용자가 Deduction_Draft를 취소하면, THE Client_App SHALL 차감 요청을 전송하지 않고 Meal_Recommendation을 유지한다.
15. IF 차감 요청이 실패하면, THEN THE Deduction_Service SHALL 요청 전 모든 재고 수량을 유지한다.
16. IF 차감 요청이 실패하면, THEN THE Client_App SHALL 수정된 Deduction_Draft를 유지하고 같은 Deduction_Request_ID를 사용하는 재시도 동작을 표시한다.
17. WHEN 한 끼 추천에서 차감이 완료되면, THE Client_App SHALL 갱신된 냉장고 목록과 차감 품목 수를 표시한다.

### Requirement 8: 3일 식단 생성과 사용

**User Story:** 1인 가구 사용자로서, 대용량 재료를 여러 끼에 나누어 사용하는 3일 식단을 받고 싶습니다. 그래야 한 끼를 만든 뒤 남은 재료도 계획적으로 사용할 수 있습니다.

#### Acceptance Criteria

1. WHEN 사용자가 3일 식단을 요청하면, THE Meal_Plan_Service SHALL 3일 동안 매일 점심과 저녁으로 구성된 정확히 6개의 Meal_Recommendation을 순서대로 생성한다.
2. WHEN Expiring_Item이 있는 재고로 Meal_Plan을 생성하면, THE Meal_Plan_Service SHALL 각 끼니 직전의 예상 잔여 수량을 기준으로 소비기한이 가장 빠른 Expiring_Item의 잔여 수량을 우선 줄인다.
3. IF Expiring_Item이 없으면, THEN THE Meal_Plan_Service SHALL 각 끼니 직전의 예상 잔여 수량을 기준으로 Expired_Item이 아닌 Inventory_Item 중 소비기한이 가장 빠른 재료의 잔여 수량을 우선 줄인다.
4. WHEN Meal_Plan을 생성하면, THE Meal_Plan_Service SHALL Expired_Item을 모든 끼니의 사용 재료에서 제외한다.
5. WHEN Meal_Plan을 생성하면, THE Meal_Plan_Service SHALL 현재 Inventory_Item과 Basic_Seasonings만 사용한다.
6. WHEN Meal_Plan을 표시하면, THE Client_App SHALL 각 표시 대상 Inventory_Item의 현재 수량, 6개 끼니 사용량 합계 및 3일 뒤 예상 잔여 수량을 함께 표시한다.
7. WHEN 품목별 6개 끼니 사용량 합계가 현재 수량 이하이면, THE Client_App SHALL 3일 뒤 예상 잔여 수량을 `현재 수량 - 사용량 합계`로 표시한다.
8. IF 품목별 6개 끼니 사용량 합계가 현재 수량보다 크면, THEN THE Client_App SHALL 3일 뒤 예상 잔여 수량을 0개로 표시하고 `사용량 합계 - 현재 수량`을 부족 수량으로 표시한다.
9. WHEN 사용자가 Meal_Plan의 끼니를 선택하면, THE Client_App SHALL 해당 Meal_Recommendation의 Recipe_Steps를 별도 API 요청으로 조회한다.
10. WHEN Meal_Plan 끼니의 차감이 성공하면, THE Client_App SHALL 해당 끼니만 Completed_Meal로 표시한다.
11. IF Meal_Plan 끼니의 차감이 실패하거나 취소되면, THEN THE Client_App SHALL 해당 끼니를 완료되지 않은 상태로 유지한다.
12. WHEN Meal_Plan 끼니의 차감이 성공하면, THE Client_App SHALL Meal_Plan 화면으로 이동한다.
13. WHILE Session_Lifetime이 유지되면, THE Client_App SHALL 생성된 Meal_Plan과 Completed_Meal 상태를 유지한다.
14. WHEN Client_App이 새로고침되면, THE Client_App SHALL 저장되지 않은 Meal_Plan과 Completed_Meal 상태를 초기화하고 냉장고 목록을 표시한다.
15. WHEN 사용자가 Meal_Plan 재생성을 확정하면, THE Meal_Plan_Service SHALL 재생성 요청 시점의 현재 재고로 새 Meal_Plan을 생성한다.
16. IF Expired_Item이 아닌 Inventory_Item이 0개이면, THEN THE Client_App SHALL 식단 생성 요청을 전송하지 않고 사용 가능한 재료가 없다는 상태를 표시한다.
17. IF 사용 가능한 재료가 있지만 Meal_Plan 생성이 실패하면, THEN THE Client_App SHALL 사용 가능한 재료 없음 상태와 구분되는 생성 오류 및 재시도 동작을 표시한다.

### Requirement 9: 수정 가능한 LLM 추정값

**User Story:** 1인 가구 사용자로서, LLM이 만든 값을 실제 사용 내용에 맞게 수정하고 싶습니다. 그래야 추정 오류가 재고에 그대로 반영되지 않습니다.

#### Acceptance Criteria

1. WHEN Recognition_Service가 Inventory_Item을 생성하면, THE Client_App SHALL 저장 전에 품목명, 수량, Storage_Location 및 소비기한의 수정 수단을 제공한다.
2. WHEN Recommendation_Service가 Meal_Recommendation을 생성하면, THE Client_App SHALL 차감 확정 전에 사용 품목의 포함 여부와 사용 수량의 수정 수단을 제공한다.
3. WHEN Meal_Plan_Service가 Meal_Plan을 생성하면, THE Client_App SHALL 각 끼니의 차감 확정 전에 사용 품목의 포함 여부와 사용 수량의 수정 수단을 제공한다.
4. IF 수정한 Inventory_Item 수량 또는 사용 수량이 0.5개 배수가 아니면, THEN THE Client_App SHALL 저장 또는 차감 요청을 전송하지 않고 수량 오류를 표시한다.
5. IF 수정한 Storage_Location이 냉장, 냉동, 실온 중 하나가 아니면, THEN THE Client_App SHALL 저장 요청을 전송하지 않고 보관 위치 오류를 표시한다.
6. IF 수정한 소비기한이 유효한 달력 날짜가 아니면, THEN THE Client_App SHALL 저장 요청을 전송하지 않고 소비기한 오류를 표시한다.
7. WHEN 사용자가 차감을 확정하면, THE Client_App SHALL 포함된 품목과 사용자가 확정한 사용 수량만 차감 요청에 전달한다.
8. WHEN 사용자가 Recognition_Result 저장을 취소하면, THE Client_App SHALL 재고 저장 요청을 전송하지 않는다.
9. WHEN 사용자가 Deduction_Draft를 취소하면, THE Client_App SHALL 저장된 재고를 변경하지 않는다.
10. WHEN 사용자가 다른 메뉴 추천 또는 Meal_Plan 재생성을 확정하면, THE Client_App SHALL 기존 LLM 생성 메뉴를 재고에 반영하지 않고 새 생성 요청을 전송한다.

### Requirement 10: 공통 화면 상태와 모바일 레이아웃

**User Story:** 1인 가구 사용자로서, 처리 상태와 실패 원인을 명확히 확인하고 싶습니다. 그래야 AI 요청이 지연되거나 실패해도 다음 행동을 선택할 수 있습니다.

#### Acceptance Criteria

1. WHILE 화면 너비가 320픽셀 이상 767픽셀 이하이면, THE Client_App SHALL 화면 너비에 맞는 한 열 레이아웃으로 핵심 화면을 표시한다.
2. WHILE 화면 너비가 768픽셀 이상이면, THE Client_App SHALL 최대 480픽셀 너비의 한 열 콘텐츠 영역을 화면 가운데에 배치한다.
3. WHILE LLM_Request가 진행 중이면, THE Client_App SHALL 인식, 메뉴 추천, 조리 순서 또는 식단 생성 중 해당 요청 작업명을 포함한 로딩 상태를 표시한다.
4. IF LLM_Request가 실패하거나 시간 초과되면, THEN THE Client_App SHALL 해당 요청 입력을 유지하고 실패한 작업의 재시도 동작을 표시한다.
5. WHILE 저장 또는 차감 요청이 진행 중이면, THE Client_App SHALL 같은 저장 또는 차감 요청을 시작하는 동작을 비활성화한다.
6. WHEN 재고 등록 또는 차감이 완료되면, THE Client_App SHALL 처리 결과를 토스트 메시지로 표시한다.
7. THE Client_App SHALL 모든 사용자 표시 문구에서 `유통기한` 대신 `소비기한`을 사용한다.
8. IF 재고 조회, 저장, 편집, 삭제 또는 차감이 실패하면, THEN THE Client_App SHALL Last_Successful_Inventory를 표시 상태로 유지한다.

### Requirement 11: 애플리케이션 기술 제약

**User Story:** 개발자로서, 정해진 서버리스 기술 스택으로 MVP를 구현하고 싶습니다. 그래야 제한된 시간과 비용 안에서 배포 가능한 결과를 만들 수 있습니다.

#### Acceptance Criteria

1. THE Client_App SHALL React, Vite, TypeScript 및 Tailwind CSS로 구현한 비서버 렌더링 SPA 빌드를 생성한다.
2. THE API_Service SHALL Python 3.13, FastAPI 및 Mangum으로 실행 가능한 Lambda 패키지를 생성한다.
3. THE API_Service SHALL 모든 백엔드 엔드포인트를 하나의 Lambda 함수로 제공한다.
4. THE Inventory_Service SHALL Device_ID를 파티션 기준으로 사용하는 단일 DynamoDB 테이블에 재고를 저장한다.
5. THE Recognition_Service SHALL Amazon Bedrock Converse API와 `global.anthropic.claude-haiku-4-5-20251001-v1:0` 추론 프로파일을 사용한다.
6. WHEN Bedrock 응답을 요청하면, THE Recognition_Service SHALL 도구 사용 방식의 JSON 스키마로 Recognition_Result 형식을 제한한다.
7. WHEN Bedrock 응답을 요청하면, THE Recommendation_Service SHALL 도구 사용 방식의 JSON 스키마로 Meal_Recommendation 또는 Recipe_Steps 형식을 제한한다.
8. WHEN Bedrock 응답을 요청하면, THE Meal_Plan_Service SHALL 도구 사용 방식의 JSON 스키마로 Meal_Plan 형식을 제한한다.
9. WHEN API_Service가 API 요청을 수신하면, THE API_Service SHALL 성공 또는 오류 응답을 29초 안에 반환한다.
10. WHEN CloudFront 배포 도메인 또는 `http://localhost:5173`에서 교차 출처 요청을 수신하면, THE API_Service SHALL `Content-Type`과 `X-Device-Id` 요청 헤더를 허용한다.
11. THE Client_App SHALL 프로덕션 정적 파일을 비공개 S3 버킷과 원본 액세스 제어가 적용된 CloudFront를 통해 제공한다.
12. WHEN CloudFront가 SPA 경로에 대해 403 또는 404 응답을 받으면, THE Infrastructure_Stack SHALL `/index.html`을 HTTP 200으로 반환하도록 구성한다.

### Requirement 12: AWS SAM 인프라와 실행 환경

**User Story:** 개발자로서, MVP에 필요한 AWS 리소스를 하나의 배포 정의로 관리하고 싶습니다. 그래야 배포 환경과 로컬 대체 환경을 반복해서 검증할 수 있습니다.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL S3, CloudFront, API Gateway HTTP API, Lambda, DynamoDB 및 IAM 리소스를 하나의 `template.yaml`에 정의한다.
2. THE Infrastructure_Stack SHALL DynamoDB 테이블을 `PAY_PER_REQUEST` 과금 방식으로 정의한다.
3. THE Infrastructure_Stack SHALL 생성한 DynamoDB 테이블에 재고 조회, 저장, 수정 및 삭제에 필요한 작업 권한만 Lambda 실행 역할에 부여한다.
4. THE Infrastructure_Stack SHALL 구성된 Bedrock 추론 프로파일과 기반 모델에 대한 `bedrock:InvokeModel` 권한만 Lambda 실행 역할에 부여한다.
5. WHEN AWS CLI 또는 SAM 명령을 실행하면, THE MVP_Plan SHALL 명령에 `--profile default --region ap-northeast-2`를 포함한다.
6. WHERE AWS 배포 환경을 사용할 수 없으면, THE Demo_Build SHALL Vite와 uvicorn을 이용한 로컬 실행으로 핵심 데모 흐름을 제공한다.
7. WHEN Infrastructure_Stack의 로컬 템플릿 검증을 수행하면, THE Infrastructure_Stack SHALL `sam validate`를 오류 없이 완료한다.
8. WHEN Infrastructure_Stack의 로컬 빌드를 수행하면, THE Infrastructure_Stack SHALL `sam build`를 오류 없이 완료한다.

### Requirement 13: 핵심 데모 흐름과 구현 우선순위

**User Story:** 개발자로서, 6시간 안에 차별점이 드러나는 안정적인 데모를 완성하고 싶습니다. 그래야 기능 수보다 사용자 가치와 종단 간 동작을 우선해 검증할 수 있습니다.

#### Acceptance Criteria

1. THE MVP_Plan SHALL 각 구현 작업에 분 단위 예상 시간을 배정하고 전체 합계를 360분 이하로 유지한다.
2. THE Demo_Build SHALL 영수증 사진 업로드, 인식 결과 수정, 재고 저장 및 냉장고 목록 확인의 연속 흐름을 제공한다.
3. THE Demo_Build SHALL 온라인 주문내역 캡처 업로드, 인식 결과 수정, 재고 저장 및 냉장고 목록 확인의 연속 흐름을 동일한 이미지 입력 동작으로 제공한다.
4. THE Demo_Build SHALL 임박 재료 확인, 한 끼 추천, Recipe_Steps 확인, `요리했어요`, Deduction_Preview 확인, 차감 확정 및 갱신된 재고 확인의 연속 흐름을 제공한다.
5. WHEN Deduction_Preview를 표시하면, THE Demo_Build SHALL 차감 전후 수량을 `<품목명> <차감 전 수량>개 → <차감 후 수량>개` 형식으로 표시한다.
6. THE Demo_Build SHALL 3일 식단 생성 후 재료별 현재 수량과 3일 뒤 예상 잔여 수량을 표시하는 흐름을 제공한다.
7. THE MVP_Plan SHALL 인프라 뼈대, 냉장고 목록, 영수증 인식과 등록, 한 끼 추천, 재고 차감을 최우선 구현 범위로 배정한다.
8. THE MVP_Plan SHALL 온라인 주문내역 인식 검증을 최우선 구현 범위 다음 순서로 배정한다.
9. THE MVP_Plan SHALL 3일 식단 생성과 잔여 수량 표시를 온라인 주문내역 인식 검증 다음 순서로 배정한다.
10. IF 360분 안에 전체 범위를 완료할 수 없으면, THEN THE MVP_Plan SHALL 부가 기능, 식단 끼니 완료 연동, 3일 식단 생성 순서로 구현 범위를 축소한다.
11. IF AWS 배포 검증 지연이 30분 이상이면, THEN THE MVP_Plan SHALL 로컬 Demo_Build 검증을 AWS 배포 검증보다 먼저 수행한다.
12. IF 영수증 사진 또는 온라인 주문내역 캡처 인식이 실패하면, THEN THE Demo_Build SHALL 인식 요청 전 재고를 유지하고 같은 이미지 재시도 동작을 제공한다.
