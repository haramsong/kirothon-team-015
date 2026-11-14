from copy import deepcopy
from datetime import date
from uuid import UUID

import pytest

from app.errors import AppError
from app.gateways.bedrock import BedrockGatewayError, BedrockTimeoutError
from app.models import (
    InternalInventoryItem,
    MealIngredientDto,
    MealRecommendationDto,
    StorageLocation,
)
from app.repositories.dynamodb_inventory import InventoryDocument
from app.services.recommendation import RecommendationService

DEVICE_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
ONION_ID = UUID("223e4567-e89b-42d3-a456-426614174000")
TOFU_ID = UUID("323e4567-e89b-42d3-a456-426614174000")
EXPIRED_ID = UUID("423e4567-e89b-42d3-a456-426614174000")


class MemoryRepository:
    def __init__(self, items: list[InternalInventoryItem]) -> None:
        self.document = InventoryDocument(3, items)

    def get(self, _device_id: UUID) -> InventoryDocument:
        return deepcopy(self.document)


class SequenceGateway:
    def __init__(
        self,
        recommendations: list[dict] | None = None,
        recipes: list[dict] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.recommendations = recommendations or []
        self.recipes = recipes or []
        self.error = error
        self.recommendation_calls: list[dict] = []
        self.recipe_calls: list[dict] = []

    def emit_recommendation(self, **kwargs: object) -> dict:
        self.recommendation_calls.append(kwargs)
        if self.error:
            raise self.error
        return self.recommendations.pop(0)

    def emit_recipe(self, **kwargs: object) -> dict:
        self.recipe_calls.append(kwargs)
        if self.error:
            raise self.error
        return self.recipes.pop(0)


def item(
    item_id: UUID,
    name: str,
    expiration_date: date,
    half_units: int = 4,
) -> InternalInventoryItem:
    return InternalInventoryItem(
        id=item_id,
        name=name,
        quantity_half_units=half_units,
        storage_location=StorageLocation.REFRIGERATED,
        expiration_date=expiration_date,
        expiration_estimated=True,
    )


def valid_recommendation(
    menu_name: str = "두부 양파 볶음",
    item_id: UUID = ONION_ID,
    use_half_units: int = 2,
    seasonings: list[str] | None = None,
) -> dict:
    return {
        "menu_name": menu_name,
        "ingredients": [
            {"item_id": str(item_id), "use_half_units": use_half_units}
        ],
        "seasonings": seasonings or ["간장"],
    }


def test_recommendation_excludes_expired_and_prioritizes_earliest_expiring_item() -> None:
    repository = MemoryRepository(
        [
            item(EXPIRED_ID, "상한 우유", date(2026, 4, 9)),
            item(TOFU_ID, "두부", date(2026, 4, 12)),
            item(ONION_ID, "양파", date(2026, 4, 11), half_units=3),
        ]
    )
    gateway = SequenceGateway([valid_recommendation(use_half_units=3)])
    service = RecommendationService(repository, gateway, clock=lambda: 1.0)

    result = service.recommend(
        DEVICE_ID, date(2026, 4, 10), deadline=20.0
    )

    assert result.menu_name == "두부 양파 볶음"
    assert result.ingredients == [
        MealIngredientDto(item_id=ONION_ID, name="양파", quantity=1.5)
    ]
    call = gateway.recommendation_calls[0]
    assert call["priority_item_id"] == str(ONION_ID)
    assert {entry["item_id"] for entry in call["inventory_context"]} == {
        str(ONION_ID),
        str(TOFU_ID),
    }


def test_recommendation_without_expiring_items_uses_earliest_nonexpired_item() -> None:
    repository = MemoryRepository(
        [
            item(TOFU_ID, "두부", date(2026, 4, 20)),
            item(ONION_ID, "양파", date(2026, 4, 15)),
        ]
    )
    gateway = SequenceGateway([valid_recommendation()])
    service = RecommendationService(repository, gateway, clock=lambda: 1.0)

    service.recommend(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert gateway.recommendation_calls[0]["priority_item_id"] == str(ONION_ID)


def test_same_excluded_menu_is_corrected_once_and_new_menu_is_accepted() -> None:
    repository = MemoryRepository(
        [item(ONION_ID, "양파", date(2026, 4, 11))]
    )
    gateway = SequenceGateway(
        [
            valid_recommendation(menu_name="양파 볶음"),
            valid_recommendation(menu_name="양파 덮밥"),
        ]
    )
    service = RecommendationService(repository, gateway, clock=lambda: 1.0)

    result = service.recommend(
        DEVICE_ID,
        date(2026, 4, 10),
        deadline=20.0,
        excluded_menu_name="양파 볶음",
    )

    assert result.menu_name == "양파 덮밥"
    assert gateway.recommendation_calls[0]["correction"] is None
    assert "직전 메뉴" in gateway.recommendation_calls[1]["correction"]


@pytest.mark.parametrize(
    "invalid_output",
    [
        valid_recommendation(item_id=TOFU_ID),
        valid_recommendation(use_half_units=5),
        valid_recommendation(seasonings=["굴소스"]),
    ],
)
def test_invalid_inventory_id_quantity_or_seasoning_is_rejected(
    invalid_output: dict,
) -> None:
    repository = MemoryRepository(
        [item(ONION_ID, "양파", date(2026, 4, 11), half_units=4)]
    )
    gateway = SequenceGateway([invalid_output])
    service = RecommendationService(repository, gateway, clock=lambda: 13.0)

    with pytest.raises(AppError) as caught:
        service.recommend(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert caught.value.status_code == 502
    assert caught.value.code == "INVALID_MODEL_OUTPUT"
    assert len(gateway.recommendation_calls) == 1


def test_recipe_accepts_only_recommendation_items_and_basic_seasonings() -> None:
    recommendation = MealRecommendationDto(
        id=UUID("523e4567-e89b-42d3-a456-426614174000"),
        menu_name="양파 볶음",
        ingredients=[
            MealIngredientDto(item_id=ONION_ID, name="양파", quantity=1)
        ],
        seasonings=["간장"],
    )
    gateway = SequenceGateway(
        recipes=[
            {"ingredient_names": ["양파", "버터"], "steps": ["잘못된 단계"]},
            {
                "ingredient_names": ["양파", "간장"],
                "steps": ["양파를 썰어요.", "간장과 볶아요."],
            },
        ]
    )
    service = RecommendationService(MemoryRepository([]), gateway, clock=lambda: 1.0)

    result = service.create_recipe(recommendation, deadline=20.0)

    assert result.steps == ["양파를 썰어요.", "간장과 볶아요."]
    assert len(gateway.recipe_calls) == 2
    assert "버터" in gateway.recipe_calls[1]["correction"]


def test_no_usable_inventory_returns_conflict_without_bedrock_call() -> None:
    repository = MemoryRepository(
        [item(EXPIRED_ID, "상한 우유", date(2026, 4, 9))]
    )
    gateway = SequenceGateway()
    service = RecommendationService(repository, gateway)

    with pytest.raises(AppError) as caught:
        service.recommend(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert caught.value.status_code == 409
    assert caught.value.code == "NO_USABLE_ITEMS"
    assert gateway.recommendation_calls == []


@pytest.mark.parametrize(
    ("gateway_error", "expected_status", "expected_code"),
    [
        (BedrockTimeoutError("timeout"), 504, "LLM_TIMEOUT"),
        (BedrockGatewayError("failed"), 502, "GENERATION_FAILED"),
    ],
)
def test_gateway_errors_are_mapped_for_recommendations(
    gateway_error: Exception, expected_status: int, expected_code: str
) -> None:
    repository = MemoryRepository(
        [item(ONION_ID, "양파", date(2026, 4, 11))]
    )
    service = RecommendationService(
        repository,
        SequenceGateway(error=gateway_error),
        clock=lambda: 1.0,
    )

    with pytest.raises(AppError) as caught:
        service.recommend(DEVICE_ID, date(2026, 4, 10), deadline=20.0)

    assert caught.value.status_code == expected_status
    assert caught.value.code == expected_code
    assert caught.value.retryable is True
