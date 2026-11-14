from copy import deepcopy
from threading import RLock
from typing import Any
from uuid import UUID

from app.models import InternalInventoryItem
from app.repositories.dynamodb_inventory import (
    DeductionRecord,
    DeductionTransactionConflictError,
    InventoryConflictError,
    InventoryDocument,
)


class LocalInventoryRepository:
    """AWS 없이 로컬 데모 흐름을 실행하는 메모리 재고 저장소입니다."""

    def __init__(self) -> None:
        self._documents: dict[UUID, InventoryDocument] = {}
        self._deductions: dict[tuple[UUID, UUID], DeductionRecord] = {}
        self._lock = RLock()

    def get(self, device_id: UUID) -> InventoryDocument:
        with self._lock:
            return deepcopy(self._documents.get(device_id, InventoryDocument(0, [])))

    def replace(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
    ) -> InventoryDocument:
        with self._lock:
            current = self._documents.get(device_id, InventoryDocument(0, []))
            if current.version != expected_version:
                raise InventoryConflictError
            saved = InventoryDocument(expected_version + 1, deepcopy(items))
            self._documents[device_id] = saved
            return deepcopy(saved)

    def get_deduction(
        self, device_id: UUID, request_id: UUID
    ) -> DeductionRecord | None:
        with self._lock:
            return deepcopy(self._deductions.get((device_id, request_id)))

    def transact_deduction(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
        record: DeductionRecord,
    ) -> InventoryDocument:
        with self._lock:
            current = self._documents.get(device_id, InventoryDocument(0, []))
            key = (device_id, record.request_id)
            if current.version != expected_version or key in self._deductions:
                raise DeductionTransactionConflictError
            saved = InventoryDocument(expected_version + 1, deepcopy(items))
            self._documents[device_id] = saved
            self._deductions[key] = deepcopy(record)
            return deepcopy(saved)


class LocalBedrockGateway:
    """인식·추천·조리·식단 응답을 결정적으로 만드는 로컬 gateway입니다."""

    def emit_recognition(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "purchase_date": None,
            "items": [
                {
                    "name": "양파 1.5kg",
                    "quantity_half_units": 16,
                    "storage_location": "실온",
                    "detected_expiration_date": None,
                    "is_food": True,
                    "is_basic_seasoning": False,
                }
            ],
        }

    def emit_recommendation(self, **kwargs: Any) -> dict[str, Any]:
        excluded = kwargs.get("excluded_menu_name")
        menu_name = "양파 간장 볶음" if excluded != "양파 간장 볶음" else "양파 덮밥"
        return {
            "menu_name": menu_name,
            "ingredients": [
                {
                    "item_id": kwargs["priority_item_id"],
                    "use_half_units": 2,
                }
            ],
            "seasonings": ["간장", "식용유"],
        }

    def emit_recipe(self, **kwargs: Any) -> dict[str, Any]:
        recommendation = kwargs["recommendation_context"]
        ingredient_names = [item["name"] for item in recommendation["ingredients"]]
        ingredient_names.extend(recommendation["seasonings"])
        return {
            "ingredient_names": ingredient_names,
            "steps": ["재료를 먹기 좋게 손질해요.", "팬에 식용유를 두르고 간장과 함께 볶아요."],
        }

    def emit_meal_plan(self, **kwargs: Any) -> dict[str, Any]:
        inventory = kwargs["inventory_context"]
        item = inventory[0]
        sequence = (
            (1, "점심"),
            (1, "저녁"),
            (2, "점심"),
            (2, "저녁"),
            (3, "점심"),
            (3, "저녁"),
        )
        return {
            "meals": [
                {
                    "day": day,
                    "slot": slot,
                    "menu_name": f"{item['name']} 활용 요리 {index}",
                    "ingredients": [
                        {"item_id": item["item_id"], "use_half_units": 1}
                    ],
                    "seasonings": ["간장"],
                }
                for index, (day, slot) in enumerate(sequence, start=1)
            ]
        }


def create_local_adapters() -> tuple[LocalInventoryRepository, LocalBedrockGateway]:
    """APP_ENV=test에서 공유할 AWS 비의존 adapter 쌍을 생성합니다."""
    return LocalInventoryRepository(), LocalBedrockGateway()
