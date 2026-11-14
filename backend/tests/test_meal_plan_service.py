from copy import deepcopy
from datetime import date
from uuid import UUID

import pytest

from app.errors import AppError
from app.gateways.bedrock import BedrockGatewayError, BedrockTimeoutError
from app.models import InternalInventoryItem, StorageLocation
from app.repositories.dynamodb_inventory import InventoryDocument
from app.services.meal_plan import MealPlanService

DEVICE_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
ONION_ID = UUID("223e4567-e89b-42d3-a456-426614174000")
TOFU_ID = UUID("323e4567-e89b-42d3-a456-426614174000")
EXPIRED_ID = UUID("423e4567-e89b-42d3-a456-426614174000")


class MemoryRepository:
    def __init__(self, items: list[InternalInventoryItem], version: int = 7) -> None:
        self.document = InventoryDocument(version, items)

    def get(self, _device_id: UUID) -> InventoryDocument:
        return deepcopy(self.document)


class SequenceGateway:
    def __init__(
        self,
        outputs: list[dict] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.outputs = outputs or []
        self.error = error
        self.calls: list[dict] = []

    def emit_meal_plan(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.outputs.pop(0)


def item(
    item_id: UUID,
    name: str,
    expiration_date: date,
    half_units: int,
) -> InternalInventoryItem:
    return InternalInventoryItem(
        id=item_id,
        name=name,
        quantity_half_units=half_units,
        storage_location=StorageLocation.REFRIGERATED,
        expiration_date=expiration_date,
        expiration_estimated=True,
    )


def meal(day: int, slot: str, item_id: UUID, menu_name: str) -> dict:
    return {
        "day": day,
        "slot": slot,
        "menu_name": menu_name,
        "ingredients": [{"item_id": str(item_id), "use_half_units": 1}],
        "seasonings": ["간장"],
    }


def valid_plan() -> dict:
    return {
        "meals": [
            meal(1, "점심", ONION_ID, "양파 점심 1"),
            meal(1, "저녁", ONION_ID, "양파 저녁 1"),
            meal(2, "점심", ONION_ID, "양파 점심 2"),
            meal(2, "저녁", TOFU_ID, "두부 저녁 2"),
            meal(3, "점심", TOFU_ID, "두부 점심 3"),
            meal(3, "저녁", TOFU_ID, "두부 저녁 3"),
        ]
    }


def usable_inventory() -> list[InternalInventoryItem]:
    return [
        item(EXPIRED_ID, "상한 우유", date(2026, 4, 9), 8),
        item(TOFU_ID, "두부", date(2026, 4, 14), 3),
        item(ONION_ID, "양파", date(2026, 4, 11), 3),
    ]


def test_meal_plan_builds_exact_sequence_from_projected_remaining_inventory() -> None:
    gateway = SequenceGateway([valid_plan()])
    service = MealPlanService(
        MemoryRepository(usable_inventory()), gateway, clock=lambda: 1.0
    )

    result = service.create(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert result.inventory_version == 7
    assert [(entry.day, entry.slot) for entry in result.meals] == [
        (1, "점심"),
        (1, "저녁"),
        (2, "점심"),
        (2, "저녁"),
        (3, "점심"),
        (3, "저녁"),
    ]
    assert [entry.recommendation.ingredients[0].name for entry in result.meals] == [
        "양파",
        "양파",
        "양파",
        "두부",
        "두부",
        "두부",
    ]
    context_ids = {entry["item_id"] for entry in gateway.calls[0]["inventory_context"]}
    assert context_ids == {str(ONION_ID), str(TOFU_ID)}


def test_wrong_sequence_is_corrected_once() -> None:
    wrong_order = valid_plan()
    wrong_order["meals"][0]["slot"] = "저녁"
    gateway = SequenceGateway([wrong_order, valid_plan()])
    service = MealPlanService(
        MemoryRepository(usable_inventory()), gateway, clock=lambda: 1.0
    )

    result = service.create(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert len(result.meals) == 6
    assert len(gateway.calls) == 2
    assert "1일차 점심" in gateway.calls[1]["correction"]


@pytest.mark.parametrize(
    "invalid_plan",
    [
        {
            "meals": [
                meal(1, "점심", TOFU_ID, "잘못된 우선 품목"),
                *valid_plan()["meals"][1:],
            ]
        },
        {
            "meals": [
                {
                    **valid_plan()["meals"][0],
                    "ingredients": [
                        {"item_id": str(ONION_ID), "use_half_units": 4}
                    ],
                },
                *valid_plan()["meals"][1:],
            ]
        },
        {
            "meals": [
                {
                    **valid_plan()["meals"][0],
                    "ingredients": [
                        {"item_id": str(EXPIRED_ID), "use_half_units": 1}
                    ],
                },
                *valid_plan()["meals"][1:],
            ]
        },
    ],
)
def test_priority_overuse_and_expired_inventory_are_rejected(
    invalid_plan: dict,
) -> None:
    gateway = SequenceGateway([invalid_plan])
    service = MealPlanService(
        MemoryRepository(usable_inventory()), gateway, clock=lambda: 13.0
    )

    with pytest.raises(AppError) as caught:
        service.create(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert caught.value.status_code == 502
    assert caught.value.code == "INVALID_MODEL_OUTPUT"
    assert len(gateway.calls) == 1


def test_no_usable_inventory_is_distinct_and_skips_bedrock() -> None:
    gateway = SequenceGateway()
    service = MealPlanService(
        MemoryRepository([item(EXPIRED_ID, "상한 우유", date(2026, 4, 9), 8)]),
        gateway,
    )

    with pytest.raises(AppError) as caught:
        service.create(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert caught.value.status_code == 409
    assert caught.value.code == "NO_USABLE_ITEMS"
    assert gateway.calls == []


@pytest.mark.parametrize(
    ("gateway_error", "expected_status", "expected_code"),
    [
        (BedrockTimeoutError("timeout"), 504, "LLM_TIMEOUT"),
        (BedrockGatewayError("failed"), 502, "GENERATION_FAILED"),
    ],
)
def test_gateway_errors_are_mapped_for_meal_plans(
    gateway_error: Exception, expected_status: int, expected_code: str
) -> None:
    service = MealPlanService(
        MemoryRepository(usable_inventory()),
        SequenceGateway(error=gateway_error),
        clock=lambda: 1.0,
    )

    with pytest.raises(AppError) as caught:
        service.create(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert caught.value.status_code == expected_status
    assert caught.value.code == expected_code
    assert caught.value.retryable is True
