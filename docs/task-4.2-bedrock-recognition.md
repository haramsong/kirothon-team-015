# Task 4.2 구현 기록: Bedrock 영수증 인식

## 구현 범위

- `POST /api/recognitions` multipart JPEG 인식 endpoint
- Amazon Bedrock Converse API의 `emit_recognition` 강제 도구 선택
- `strict: true`와 모든 object의 `additionalProperties: false`를 적용한 JSON Schema
- 요청 시작 후 27초 애플리케이션 deadline, SDK 재시도 0회, 연결 2초·읽기 최대 22초 제한
- 첫 결과의 도구 입력 또는 Pydantic 검증 실패 시 남은 시간이 8초 이상일 때 한 번만 교정
- JPEG MIME, `FF D8 FF` magic bytes, 3,932,160바이트 이하 조건을 Bedrock 호출 전에 검증
- 구매일 감지값 우선 및 API 요청일 fallback
- 품목별 shelf-life 사전과 보관 위치별 기본 기간을 사용한 예상 소비기한 생성
- 비식품과 기본 양념 8종 제외
- Bedrock의 정수 `quantity_half_units`를 API의 0.5개 단위 `quantity`로 변환
- 유효한 빈 품목 목록은 성공 응답으로, 호출 실패·timeout·무효 모델 결과는 각각 구분된 오류로 반환

## 오류 계약

| 상황 | HTTP | 오류 코드 |
| --- | ---: | --- |
| JPEG MIME·signature·크기 오류 | 400 | `INVALID_IMAGE` |
| Bedrock 호출 실패 | 502 | `RECOGNITION_FAILED` |
| 두 번 모두 모델 결과 검증 실패 | 502 | `INVALID_MODEL_OUTPUT` |
| deadline 또는 SDK timeout | 504 | `LLM_TIMEOUT` |

## 주요 파일

- `backend/app/gateways/bedrock.py`: Converse 요청, strict tool schema, 강제 선택, timeout 및 도구 입력 추출
- `backend/app/services/recognition.py`: 이미지 검증, 교정 정책, Pydantic 검증, 필터링·날짜·수량 정규화
- `backend/app/routes/recognition.py`: 기존 성공 envelope와 기기 헤더 경계를 유지한 endpoint
- `backend/app/main.py`: gateway 주입, 모델 설정, 요청별 27초 deadline, router 등록
- `backend/app/config.py`: `MODEL_ID` 설정
- `backend/tests/test_bedrock_gateway.py`: tool schema와 강제 선택 단위 테스트
- `backend/tests/test_recognition_service.py`: 정규화, fallback, 교정, 경계와 오류 매핑 단위 테스트
- `backend/tests/test_recognition_api.py`: multipart endpoint 통합 테스트

## 검증 결과

2026-04-07 로컬 Python 3.13 가상환경에서 다음 명령을 실행했습니다.

```bash
cd backend
./.venv/bin/python -m pytest
./.venv/bin/python -m compileall -q app tests
git diff --check
```

결과는 `35 passed`이며 문법 검사와 diff whitespace 검사도 통과했습니다. Starlette TestClient 내부 `anyio.abc.BlockingPortal` deprecation warning 1건은 기존 의존성에서 발생하며 테스트 결과에는 영향이 없습니다.

## 참고

Strict tool use의 `strict` 위치와 Converse tool definition 형식은 [Amazon Bedrock structured outputs 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html#structured-output-strict-tool-examples)를 기준으로 구현했습니다.
