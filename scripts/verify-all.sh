#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PYTHON="${BACKEND_PYTHON:-${ROOT_DIR}/backend/.venv/bin/python}"
NPM_BIN="${NPM_BIN:-npm}"

run_phase() {
  local label="$1"
  shift

  echo
  echo "==> ${label}"
  set +e
  "$@"
  local status=$?
  set -e

  if (( status != 0 )); then
    echo "검증 실패 (${status}): ${label}" >&2
    exit "${status}"
  fi
}

if [[ ! -x "${BACKEND_PYTHON}" ]]; then
  echo "백엔드 Python 실행 파일이 없습니다: ${BACKEND_PYTHON}" >&2
  exit 1
fi
if [[ "${NPM_BIN}" == */* ]]; then
  if [[ ! -x "${NPM_BIN}" ]]; then
    echo "npm 실행 파일이 없습니다: ${NPM_BIN}" >&2
    exit 1
  fi
elif ! command -v "${NPM_BIN}" >/dev/null 2>&1; then
  echo "npm 실행 파일을 찾을 수 없습니다: ${NPM_BIN}" >&2
  exit 1
fi

# 녹화 데모의 등록 → 추천 → 레시피 → 원자 차감 경로를 가장 먼저 확인합니다.
run_phase "핵심 데모 종단 간 테스트" \
  "${BACKEND_PYTHON}" -m pytest \
  "${ROOT_DIR}/backend/tests/test_demo_e2e.py::test_receipt_registration_recommendation_recipe_and_atomic_deduction_flow" \
  "${ROOT_DIR}/backend/tests/test_demo_e2e.py::test_same_deduction_id_is_replayed_without_a_second_atomic_write" \
  "${ROOT_DIR}/backend/tests/test_demo_e2e.py::test_recognition_and_recommendation_timeout_keep_input_for_retry"

run_phase "핵심 백엔드 테스트" \
  "${BACKEND_PYTHON}" -m pytest "${ROOT_DIR}/backend/tests" \
  --ignore="${ROOT_DIR}/backend/tests/test_demo_e2e.py" \
  --ignore="${ROOT_DIR}/backend/tests/test_meal_plan_api.py" \
  --ignore="${ROOT_DIR}/backend/tests/test_meal_plan_service.py"

run_phase "핵심 프론트엔드 테스트" \
  "${NPM_BIN}" --prefix "${ROOT_DIR}/frontend" run test -- \
  src/api/client.test.ts \
  src/app/App.test.tsx \
  src/features/deduction/DeductionModal.test.tsx \
  src/features/device/DeviceProvider.test.tsx \
  src/features/inventory/InventoryPage.test.tsx \
  src/features/inventory/InventoryProvider.test.tsx \
  src/features/inventory/ItemModal.test.tsx \
  src/features/recipe/RecipePage.test.tsx \
  src/features/registration/RegistrationPage.test.tsx \
  src/features/registration/imageProcessor.test.ts \
  src/logic/date.test.ts

# 선택 식단 범위는 핵심 경로가 모두 통과한 뒤 별도 단계로 실행합니다.
run_phase "선택 식단 백엔드 테스트" \
  "${BACKEND_PYTHON}" -m pytest \
  "${ROOT_DIR}/backend/tests/test_meal_plan_api.py" \
  "${ROOT_DIR}/backend/tests/test_meal_plan_service.py" \
  "${ROOT_DIR}/backend/tests/test_demo_e2e.py::test_order_history_uses_shared_registration_and_generates_six_meals"

run_phase "선택 식단 프론트엔드 테스트" \
  "${NPM_BIN}" --prefix "${ROOT_DIR}/frontend" run test -- \
  src/features/meal-plan/MealPlanPage.test.tsx \
  src/features/meal-plan/MealPlanProvider.test.tsx \
  src/logic/mealPlan.test.ts

run_phase "TypeScript 검사" \
  "${NPM_BIN}" --prefix "${ROOT_DIR}/frontend" run typecheck

run_phase "프론트엔드 프로덕션 빌드" \
  "${NPM_BIN}" --prefix "${ROOT_DIR}/frontend" run build

echo
echo "전체 자동 테스트와 프로덕션 빌드 검증을 통과했습니다."
