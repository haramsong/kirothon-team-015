import time
from collections.abc import Callable
from datetime import date
from typing import Any
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
    MealIngredientDto,
    MealRecommendationDto,
    RecipeDto,
)
from app.repositories.dynamodb_inventory import InventoryRepository, InventoryStorageError


class RecommendationToolIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    use_half_units: int = Field(ge=1)


class RecommendationToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    menu_name: str = Field(min_length=1, max_length=80)
    ingredients: list[RecommendationToolIngredient] = Field(min_length=1, max_length=200)
    seasonings: list[str]

    @field_validator("menu_name")
    @classmethod
    def clean_menu_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("메뉴 이름은 비어 있을 수 없습니다.")
        return cleaned


class RecipeToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_names: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=1, max_length=8)

    @field_validator("ingredient_names", "steps")
    @classmethod
    def clean_text_list(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split()) for value in values]
        if any(not value for value in cleaned):
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return cleaned


class ModelSemanticError(ValueError):
    """도구 스키마는 맞지만 업무 불변식을 위반한 결과입니다."""


class RecommendationService:
    def __init__(
        self,
        repository: InventoryRepository,
        gateway: BedrockGateway,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._clock = clock

    def recommend(
        self,
        device_id: UUID,
        client_date: date,
        deadline: float,
        excluded_menu_name: str | None = None,
    ) -> MealRecommendationDto:
        usable_items = self._usable_inventory(device_id, client_date)
        priority_item = select_priority_item(usable_items, client_date)
        context = [
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
                raw_output = self._gateway.emit_recommendation(
                    inventory_context=context,
                    priority_item_id=str(priority_item.id),
                    deadline=deadline,
                    excluded_menu_name=excluded_menu_name,
                    correction=correction,
                )
                output = RecommendationToolOutput.model_validate(raw_output)
                return validate_recommendation(
                    output,
                    usable_items,
                    priority_item.id,
                    excluded_menu_name,
                )
            except BedrockTimeoutError as error:
                raise _timeout_error("메뉴 추천") from error
            except BedrockGatewayError as error:
                if not isinstance(error, BedrockInvalidOutputError):
                    raise _generation_error("메뉴를 추천하지 못했어요.") from error
                validation_error: Exception = error
            except (ValidationError, ModelSemanticError) as error:
                validation_error = error

            if attempt == 0 and deadline - self._clock() >= 8:
                correction = correction_reason(validation_error)
                continue
            raise _invalid_output_error("추천 결과를 확인할 수 없어요.") from validation_error

        raise AssertionError("추천 교정 횟수를 초과했습니다.")

    def create_recipe(
        self,
        recommendation: MealRecommendationDto,
        deadline: float,
    ) -> RecipeDto:
        context = recommendation.model_dump(mode="json", by_alias=True)
        allowed_names = {
            ingredient.name for ingredient in recommendation.ingredients
        } | BASIC_SEASONINGS

        correction: str | None = None
        for attempt in range(2):
            try:
                raw_output = self._gateway.emit_recipe(
                    recommendation_context=context,
                    deadline=deadline,
                    correction=correction,
                )
                output = RecipeToolOutput.model_validate(raw_output)
                invalid_names = sorted(set(output.ingredient_names) - allowed_names)
                if invalid_names:
                    raise ModelSemanticError(
                        "허용되지 않은 조리 재료: " + ", ".join(invalid_names[:8])
                    )
                return RecipeDto(steps=output.steps)
            except BedrockTimeoutError as error:
                raise _timeout_error("조리 순서 생성") from error
            except BedrockGatewayError as error:
                if not isinstance(error, BedrockInvalidOutputError):
                    raise _generation_error("조리 순서를 만들지 못했어요.") from error
                validation_error = error
            except (ValidationError, ModelSemanticError) as error:
                validation_error = error

            if attempt == 0 and deadline - self._clock() >= 8:
                correction = correction_reason(validation_error)
                continue
            raise _invalid_output_error("조리 순서를 확인할 수 없어요.") from validation_error

        raise AssertionError("조리 순서 교정 횟수를 초과했습니다.")

    def _usable_inventory(
        self, device_id: UUID, client_date: date
    ) -> list[InternalInventoryItem]:
        try:
            document = self._repository.get(device_id)
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "재고를 불러오지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

        usable_items = [
            item.model_copy(deep=True)
            for item in document.items
            if item.expiration_date >= client_date
        ]
        if not usable_items:
            raise AppError(
                409,
                "NO_USABLE_ITEMS",
                "추천에 사용할 수 있는 재료가 없어요.",
            )
        return sorted(usable_items, key=_item_sort_key)


def select_priority_item(
    usable_items: list[InternalInventoryItem], client_date: date
) -> InternalInventoryItem:
    """임박 재료를 우선하고, 없으면 가장 이른 비만료 재료를 선택합니다."""
    expiring_items = [
        item
        for item in usable_items
        if 0 <= (item.expiration_date - client_date).days <= 3
    ]
    candidates = expiring_items or usable_items
    if not candidates:
        raise ValueError("사용 가능한 재료가 필요합니다.")
    return min(candidates, key=_item_sort_key)


def validate_recommendation(
    output: RecommendationToolOutput,
    usable_items: list[InternalInventoryItem],
    priority_item_id: UUID,
    excluded_menu_name: str | None,
) -> MealRecommendationDto:
    """추천 도구 결과가 현재 비만료 재고와 수량 범위를 지키는지 검증합니다."""
    if excluded_menu_name and output.menu_name == excluded_menu_name:
        raise ModelSemanticError("직전 메뉴와 다른 메뉴 이름이 필요합니다.")

    inventory_by_id = {item.id: item for item in usable_items}
    seen_ids: set[UUID] = set()
    ingredients: list[MealIngredientDto] = []
    for ingredient in output.ingredients:
        item = inventory_by_id.get(ingredient.item_id)
        if item is None:
            raise ModelSemanticError(f"재고에 없는 품목 ID: {ingredient.item_id}")
        if ingredient.item_id in seen_ids:
            raise ModelSemanticError(f"중복 품목 ID: {ingredient.item_id}")
        if ingredient.use_half_units > item.quantity_half_units:
            raise ModelSemanticError(f"재고 수량을 초과한 품목 ID: {ingredient.item_id}")
        seen_ids.add(ingredient.item_id)
        ingredients.append(
            MealIngredientDto(
                item_id=item.id,
                name=item.name,
                quantity=ingredient.use_half_units / 2,
            )
        )

    if priority_item_id not in seen_ids:
        raise ModelSemanticError("우선 소비 품목이 추천에 포함되지 않았습니다.")

    seasonings = [" ".join(name.split()) for name in output.seasonings]
    invalid_seasonings = sorted(
        {name for name in seasonings if name not in BASIC_SEASONINGS}
    )
    if invalid_seasonings:
        raise ModelSemanticError(
            "허용되지 않은 기본 양념: " + ", ".join(invalid_seasonings[:8])
        )
    if len(seasonings) != len(set(seasonings)):
        raise ModelSemanticError("기본 양념은 중복될 수 없습니다.")

    return MealRecommendationDto(
        id=uuid4(),
        menu_name=output.menu_name,
        ingredients=ingredients,
        seasonings=seasonings,
    )


def correction_reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        fields = sorted(
            {".".join(str(part) for part in item["loc"]) for item in error.errors()}
        )
        return "유효하지 않은 필드: " + ", ".join(fields[:8])
    return str(error) or "도구 입력이 없거나 형식이 잘못됨"


def _item_sort_key(item: InternalInventoryItem) -> tuple[date, str, str]:
    return item.expiration_date, item.name, str(item.id)


def _timeout_error(operation: str) -> AppError:
    return AppError(
        504,
        "LLM_TIMEOUT",
        f"{operation} 시간이 초과되었어요. 다시 시도해 주세요.",
        True,
    )


def _generation_error(message: str) -> AppError:
    return AppError(502, "GENERATION_FAILED", message + " 다시 시도해 주세요.", True)


def _invalid_output_error(message: str) -> AppError:
    return AppError(502, "INVALID_MODEL_OUTPUT", message + " 다시 시도해 주세요.", True)
