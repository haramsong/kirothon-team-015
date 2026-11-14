import time
from collections.abc import Callable
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.constants import BASIC_SEASONINGS
from app.errors import AppError
from app.gateways.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockInvalidOutputError,
    BedrockTimeoutError,
)
from app.models import (
    InternalInventoryItem,
    MealPlanDto,
    MealPlanMealDto,
)
from app.repositories.dynamodb_inventory import InventoryRepository, InventoryStorageError
from app.services.recommendation import (
    ModelSemanticError,
    RecommendationToolIngredient,
    RecommendationToolOutput,
    correction_reason,
    select_priority_item,
    validate_recommendation,
)

MEAL_SEQUENCE: tuple[tuple[int, Literal["점심", "저녁"]], ...] = (
    (1, "점심"),
    (1, "저녁"),
    (2, "점심"),
    (2, "저녁"),
    (3, "점심"),
    (3, "저녁"),
)


class MealPlanToolMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1, le=3)
    slot: Literal["점심", "저녁"]
    menu_name: str = Field(min_length=1, max_length=80)
    ingredients: list[RecommendationToolIngredient] = Field(max_length=200)
    seasonings: list[str]

    @field_validator("menu_name")
    @classmethod
    def clean_menu_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("메뉴 이름은 비어 있을 수 없습니다.")
        return cleaned


class MealPlanToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meals: list[MealPlanToolMeal] = Field(min_length=6, max_length=6)


class MealPlanService:
    def __init__(
        self,
        repository: InventoryRepository,
        gateway: BedrockGateway,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._clock = clock

    def create(
        self,
        device_id: UUID,
        client_date: date,
        deadline: float,
    ) -> MealPlanDto:
        try:
            document = self._repository.get(device_id)
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "재고를 불러오지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

        usable_items = sorted(
            (
                item.model_copy(deep=True)
                for item in document.items
                if item.expiration_date >= client_date
            ),
            key=lambda item: (item.expiration_date, item.name, str(item.id)),
        )
        if not usable_items:
            raise AppError(
                409,
                "NO_USABLE_ITEMS",
                "식단에 사용할 수 있는 재료가 없어요.",
            )

        inventory_context = [
            {
                "item_id": str(item.id),
                "name": item.name,
                "quantity_half_units": item.quantity_half_units,
                "expiration_date": item.expiration_date.isoformat(),
            }
            for item in usable_items
        ]
        correction: str | None = None
        for attempt in range(2):
            try:
                raw_output = self._gateway.emit_meal_plan(
                    inventory_context=inventory_context,
                    client_date=client_date.isoformat(),
                    deadline=deadline,
                    correction=correction,
                )
                output = MealPlanToolOutput.model_validate(
                    _drop_invalid_raw_ingredients(raw_output)
                )
                return validate_meal_plan(
                    output,
                    usable_items,
                    document.version,
                    client_date,
                )
            except BedrockTimeoutError as error:
                raise AppError(
                    504,
                    "LLM_TIMEOUT",
                    "3일 식단 생성 시간이 초과되었어요. 다시 시도해 주세요.",
                    True,
                ) from error
            except BedrockGatewayError as error:
                if not isinstance(error, BedrockInvalidOutputError):
                    raise AppError(
                        502,
                        "GENERATION_FAILED",
                        "3일 식단을 만들지 못했어요. 다시 시도해 주세요.",
                        True,
                    ) from error
                validation_error: Exception = error
            except (ValidationError, ModelSemanticError) as error:
                validation_error = error

            if attempt == 0 and deadline - self._clock() >= 8:
                correction = correction_reason(validation_error)
                continue
            raise AppError(
                502,
                "INVALID_MODEL_OUTPUT",
                "3일 식단 결과를 확인할 수 없어요. 다시 시도해 주세요.",
                True,
            ) from validation_error

        raise AssertionError("식단 교정 횟수를 초과했습니다.")


def _drop_invalid_raw_ingredients(raw_output: object) -> object:
    """사용량이 1보다 작거나 ID가 UUID가 아닌 재료는 식단 전체를 거절하지 않고 뺀다."""
    if not isinstance(raw_output, dict) or not isinstance(raw_output.get("meals"), list):
        return raw_output
    meals = []
    for meal in raw_output["meals"]:
        if isinstance(meal, dict) and isinstance(meal.get("ingredients"), list):
            kept = []
            for ingredient in meal["ingredients"]:
                if not isinstance(ingredient, dict):
                    continue
                use = ingredient.get("use_half_units")
                try:
                    UUID(str(ingredient.get("item_id")))
                except ValueError:
                    continue
                if isinstance(use, int) and not isinstance(use, bool) and use >= 1:
                    kept.append(ingredient)
            meal = {**meal, "ingredients": kept}
        meals.append(meal)
    return {**raw_output, "meals": meals}


def validate_meal_plan(
    output: MealPlanToolOutput,
    usable_items: list[InternalInventoryItem],
    inventory_version: int,
    client_date: date,
) -> MealPlanDto:
    """각 끼니 직전 예상 잔여 재고를 기준으로 식단 전체를 검증합니다."""
    actual_sequence = tuple((meal.day, meal.slot) for meal in output.meals)
    if actual_sequence != MEAL_SEQUENCE:
        raise ModelSemanticError("끼니는 1일차 점심부터 3일차 저녁 순서여야 합니다.")

    remaining = {item.id: item.model_copy(deep=True) for item in usable_items}
    meals: list[MealPlanMealDto] = []
    for position, meal in enumerate(output.meals, start=1):
        remaining_items = list(remaining.values())
        if not remaining_items:
            raise ModelSemanticError(
                f"{position}번째 끼니 전에 사용 가능한 예상 잔여 재고가 없습니다."
            )
        priority_item = select_priority_item(remaining_items, client_date)
        # 모델은 6끼 동안 남은 재고를 정확히 따라가지 못한다. 규칙 하나를 어겼다고 식단 전체를
        # 거절하지 않고, 남은 재고에 맞게 사용량을 줄이거나 빼서 받는다. 재료가 하나도 남지 않으면
        # 그 끼니에는 우선 소비 품목을 넣는다.
        repaired: list[dict[str, object]] = []
        seen_ids: set[UUID] = set()
        for ingredient in meal.ingredients:
            current = remaining.get(ingredient.item_id)
            if current is None or ingredient.item_id in seen_ids:
                continue
            use_half_units = min(ingredient.use_half_units, current.quantity_half_units)
            if use_half_units < 1:
                continue
            seen_ids.add(ingredient.item_id)
            repaired.append({"item_id": ingredient.item_id, "use_half_units": use_half_units})
        if not repaired:
            repaired.append(
                {
                    "item_id": priority_item.id,
                    "use_half_units": min(2, priority_item.quantity_half_units),
                }
            )
        seasonings = list(
            dict.fromkeys(
                name
                for name in (" ".join(raw.split()) for raw in meal.seasonings)
                if name in BASIC_SEASONINGS
            )
        )
        recommendation_output = RecommendationToolOutput.model_validate(
            {
                "menu_name": meal.menu_name,
                "ingredients": repaired,
                "seasonings": seasonings,
            }
        )
        recommendation = validate_recommendation(
            recommendation_output,
            remaining_items,
            recommendation_output.ingredients[0].item_id,
            None,
        )
        for ingredient in recommendation_output.ingredients:
            current = remaining[ingredient.item_id]
            next_half_units = current.quantity_half_units - ingredient.use_half_units
            if next_half_units == 0:
                del remaining[ingredient.item_id]
            else:
                remaining[ingredient.item_id] = current.model_copy(
                    update={"quantity_half_units": next_half_units}
                )
        meals.append(
            MealPlanMealDto(
                id=uuid4(),
                day=meal.day,
                slot=meal.slot,
                recommendation=recommendation,
            )
        )

    return MealPlanDto(
        id=uuid4(),
        inventory_version=inventory_version,
        meals=meals,
    )
