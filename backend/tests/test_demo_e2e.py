from collections import deque
from copy import deepcopy
from datetime import date
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.gateways.bedrock import BedrockTimeoutError
from app.main import create_app
from app.models import InternalInventoryItem
from app.repositories.dynamodb_inventory import (
    DeductionRecord,
    DeductionTransactionConflictError,
    InventoryConflictError,
    InventoryDocument,
)

DEVICE_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
DEDUCTION_ID = UUID("323e4567-e89b-42d3-a456-426614174000")
HEADERS = {"X-Device-Id": str(DEVICE_ID)}
TODAY = "2026-04-10"
JPEG = b"\xff\xd8\xffprocessed-image"
MEAL_SEQUENCE = (
    (1, "점심"),
    (1, "저녁"),
    (2, "점심"),
    (2, "저녁"),
    (3, "점심"),
    (3, "저녁"),
)


class InMemoryDynamoAdapter:
    """실제 DynamoDB와 같은 버전 조건과 차감 원자성을 제공하는 테스트 더블입니다."""

    def __init__(self) -> None:
        self.documents: dict[UUID, InventoryDocument] = {}
        self.deductions: dict[tuple[UUID, UUID], DeductionRecord] = {}
        self.transaction_calls = 0

    def get(self, device_id: UUID) -> InventoryDocument:
        return deepcopy(self.documents.get(device_id, InventoryDocument(0, [])))

    def replace(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
    ) -> InventoryDocument:
        current = self.documents.get(device_id, InventoryDocument(0, []))
        if current.version != expected_version:
            raise InventoryConflictError
        saved = InventoryDocument(expected_version + 1, deepcopy(items))
        self.documents[device_id] = saved
        return deepcopy(saved)

    def get_deduction(
        self, device_id: UUID, request_id: UUID
    ) -> DeductionRecord | None:
        return deepcopy(self.deductions.get((device_id, request_id)))

    def transact_deduction(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
        record: DeductionRecord,
    ) -> InventoryDocument:
        current = self.documents.get(device_id, InventoryDocument(0, []))
        key = (device_id, record.request_id)
        if current.version != expected_version or key in self.deductions:
            raise DeductionTransactionConflictError

        saved = InventoryDocument(expected_version + 1, deepcopy(items))
        self.documents[device_id] = saved
        self.deductions[key] = deepcopy(record)
        self.transaction_calls += 1
        return deepcopy(saved)


class ScenarioBedrockAdapter:
    """호출 순서별 성공·시간 초과를 결정적으로 반환하는 Bedrock 테스트 더블입니다."""

    def __init__(self, recognition_results: list[dict | Exception]) -> None:
        self.recognition_results = deque(recognition_results)
        self.recommendation_results: deque[dict | Exception] = deque()
        self.recognition_calls = 0
        self.recommendation_calls = 0
        self.recipe_calls = 0
        self.meal_plan_calls = 0

    @staticmethod
    def _next(results: deque[dict | Exception]) -> dict:
        result = results.popleft()
        if isinstance(result, Exception):
            raise result
        return result

    def emit_recognition(self, **_kwargs: Any) -> dict:
        self.recognition_calls += 1
        return self._next(self.recognition_results)

    def emit_recommendation(self, **kwargs: Any) -> dict:
        self.recommendation_calls += 1
        if self.recommendation_results:
            result = self._next(self.recommendation_results)
            if "ingredients" in result:
                return result
        return {
            "menu_name": "양파 덮밥",
            "ingredients": [
                {
                    "item_id": kwargs["priority_item_id"],
                    "use_half_units": 2,
                }
            ],
            "seasonings": ["간장"],
        }

    def emit_recipe(self, **_kwargs: Any) -> dict:
        self.recipe_calls += 1
        return {
            "ingredient_names": ["양파", "간장"],
            "steps": ["양파를 썰어요.", "간장과 함께 볶아요."],
        }

    def emit_meal_plan(self, **kwargs: Any) -> dict:
        self.meal_plan_calls += 1
        item_id = kwargs["inventory_context"][0]["item_id"]
        return {
            "meals": [
                {
                    "day": day,
                    "slot": slot,
                    "menu_name": f"양파 활용 요리 {index}",
                    "ingredients": [
                        {"item_id": item_id, "use_half_units": 1}
                    ],
                    "seasonings": ["간장"],
                }
                for index, (day, slot) in enumerate(MEAL_SEQUENCE, start=1)
            ]
        }


def receipt_result() -> dict:
    return {
        "purchase_date": "2026-04-09",
        "items": [
            {
                "name": "양파",
                "quantity_half_units": 16,
                "storage_location": "실온",
                "detected_expiration_date": "2026-04-12",
                "is_food": True,
                "is_basic_seasoning": False,
            }
        ],
    }


def order_result() -> dict:
    return {
        "purchase_date": "2026-04-06",
        "items": [
            {
                "name": "[옵션: 중] 국내산 양파 1.5kg x 2망",
                "quantity_half_units": 32,
                "storage_location": "실온",
                "detected_expiration_date": "2026-04-12",
                "is_food": True,
                "is_basic_seasoning": False,
            }
        ],
    }


def create_client(
    gateway: ScenarioBedrockAdapter,
) -> tuple[TestClient, InMemoryDynamoAdapter]:
    repository = InMemoryDynamoAdapter()
    client = TestClient(
        create_app(inventory_repository=repository, bedrock_gateway=gateway),
        raise_server_exceptions=False,
    )
    return client, repository


def recognize(client: TestClient) -> dict:
    response = client.post(
        "/api/recognitions",
        files={"image": ("shopping.jpg", JPEG, "image/jpeg")},
        headers=HEADERS,
    )
    assert response.status_code == 200
    return response.json()["data"]


def save_recognition(client: TestClient, recognition: dict) -> dict:
    response = client.post(
        f"/api/inventory/items:batch?today={TODAY}",
        headers=HEADERS,
        json={"expectedVersion": 0, "items": recognition["items"]},
    )
    assert response.status_code == 200
    return response.json()["data"]["inventory"]


def test_receipt_registration_recommendation_recipe_and_atomic_deduction_flow() -> None:
    gateway = ScenarioBedrockAdapter([receipt_result()])
    client, repository = create_client(gateway)

    recognized = recognize(client)
    assert recognized["items"][0]["quantity"] == 8

    # 사용자가 인식 결과의 수량과 소비기한 추정 여부를 저장 전에 수정합니다.
    edited = deepcopy(recognized)
    edited["items"][0]["quantity"] = 7.5
    edited["items"][0]["expirationDate"] = "2026-04-11"
    edited["items"][0]["expirationEstimated"] = False
    saved = save_recognition(client, edited)
    item_id = saved["items"][0]["id"]
    assert saved["items"][0]["quantity"] == 7.5

    listed = client.get(f"/api/inventory?today={TODAY}", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()["data"] == saved

    recommended = client.post(
        "/api/recommendations",
        headers=HEADERS,
        json={"clientDate": TODAY},
    )
    assert recommended.status_code == 200
    recommendation = recommended.json()["data"]
    assert recommendation["ingredients"] == [
        {"itemId": item_id, "name": "양파", "quantity": 1.0}
    ]

    recipe = client.post(
        "/api/recipes",
        headers=HEADERS,
        json={"recommendation": recommendation},
    )
    assert recipe.status_code == 200
    assert recipe.json()["data"]["steps"] == [
        "양파를 썰어요.",
        "간장과 함께 볶아요.",
    ]

    # 추천 재료가 기본 포함된 차감 초안을 사용자가 그대로 확정합니다.
    deduction_draft = {
        "deductionRequestId": str(DEDUCTION_ID),
        "items": [
            {
                "itemId": ingredient["itemId"],
                "quantity": ingredient["quantity"],
            }
            for ingredient in recommendation["ingredients"]
        ],
    }
    deducted = client.post(
        f"/api/deductions?today={TODAY}",
        headers=HEADERS,
        json=deduction_draft,
    )
    assert deducted.status_code == 200
    assert deducted.json()["data"]["inventory"]["items"][0]["quantity"] == 6.5
    assert repository.transaction_calls == 1

    refreshed = client.get(f"/api/inventory?today={TODAY}", headers=HEADERS)
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["version"] == 2
    assert refreshed.json()["data"]["items"][0]["quantity"] == 6.5


def test_same_deduction_id_is_replayed_without_a_second_atomic_write() -> None:
    gateway = ScenarioBedrockAdapter([receipt_result()])
    client, repository = create_client(gateway)
    saved = save_recognition(client, recognize(client))
    item_id = saved["items"][0]["id"]
    request = {
        "deductionRequestId": str(DEDUCTION_ID),
        "items": [{"itemId": item_id, "quantity": 1}],
    }

    first = client.post("/api/deductions", headers=HEADERS, json=request)
    retried = client.post("/api/deductions", headers=HEADERS, json=request)

    assert first.status_code == 200
    assert retried.status_code == 200
    assert retried.json()["data"] == first.json()["data"]
    assert repository.transaction_calls == 1
    assert repository.get(DEVICE_ID).version == 2


def test_recognition_and_recommendation_timeout_keep_input_for_retry() -> None:
    gateway = ScenarioBedrockAdapter(
        [BedrockTimeoutError("recognition timeout"), receipt_result()]
    )
    gateway.recommendation_results.append(BedrockTimeoutError("recommendation timeout"))
    client, repository = create_client(gateway)

    failed_recognition = client.post(
        "/api/recognitions",
        files={"image": ("receipt.jpg", JPEG, "image/jpeg")},
        headers=HEADERS,
    )
    assert failed_recognition.status_code == 504
    assert failed_recognition.json()["error"]["code"] == "LLM_TIMEOUT"
    assert repository.get(DEVICE_ID) == InventoryDocument(0, [])

    recognized = recognize(client)
    saved = save_recognition(client, recognized)
    assert saved["version"] == 1

    failed_recommendation = client.post(
        "/api/recommendations",
        headers=HEADERS,
        json={"clientDate": TODAY},
    )
    assert failed_recommendation.status_code == 504
    assert failed_recommendation.json()["error"]["code"] == "LLM_TIMEOUT"
    assert repository.get(DEVICE_ID).version == 1

    recovered = client.post(
        "/api/recommendations",
        headers=HEADERS,
        json={"clientDate": TODAY},
    )
    assert recovered.status_code == 200
    assert recovered.json()["data"]["menuName"] == "양파 덮밥"
    assert gateway.recognition_calls == 2
    assert gateway.recommendation_calls == 2


def test_order_history_uses_shared_registration_and_generates_six_meals() -> None:
    gateway = ScenarioBedrockAdapter([order_result()])
    client, repository = create_client(gateway)

    recognized = recognize(client)
    assert recognized["items"][0]["name"] == "양파"
    assert recognized["items"][0]["quantity"] == 16
    saved = save_recognition(client, recognized)

    meal_plan = client.post(
        "/api/meal-plans",
        headers=HEADERS,
        json={"clientDate": TODAY},
    )

    assert meal_plan.status_code == 200
    data = meal_plan.json()["data"]
    assert data["inventoryVersion"] == saved["version"] == 1
    assert [(meal["day"], meal["slot"]) for meal in data["meals"]] == list(
        MEAL_SEQUENCE
    )
    assert len(data["meals"]) == 6
    assert all(
        meal["recommendation"]["ingredients"][0]["name"] == "양파"
        for meal in data["meals"]
    )
    assert repository.get(DEVICE_ID).items[0].quantity_half_units == 32
    assert gateway.meal_plan_calls == 1
