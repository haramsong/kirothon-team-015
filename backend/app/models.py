from datetime import date
from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


DataT = TypeVar("DataT")
Quantity = Annotated[float, Field(ge=0.5, multiple_of=0.5)]
HalfUnits = Annotated[int, Field(ge=1)]


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class SuccessEnvelope(ApiModel, Generic[DataT]):
    data: DataT
    request_id: str


class ErrorBody(ApiModel):
    code: str
    message: str
    retryable: bool


class ErrorEnvelope(ApiModel):
    error: ErrorBody
    request_id: str


class StorageLocation(StrEnum):
    REFRIGERATED = "냉장"
    FROZEN = "냉동"
    ROOM_TEMPERATURE = "실온"


class InventoryItemDto(ApiModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=80)]
    quantity: Quantity
    storage_location: StorageLocation
    expiration_date: date
    expiration_estimated: bool


class InventoryDto(ApiModel):
    items: list[InventoryItemDto]
    version: Annotated[int, Field(ge=0)]


class RecognitionResultDto(ApiModel):
    purchase_date: date
    purchase_date_source: Literal["detected", "request_date"]
    items: list[InventoryItemDto]


class InternalInventoryItem(ApiModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=80)]
    quantity_half_units: HalfUnits
    storage_location: StorageLocation
    expiration_date: date
    expiration_estimated: bool


class InventoryItemCreate(ApiModel):
    id: UUID
    name: Annotated[str, Field(min_length=1, max_length=80)]
    quantity: Quantity
    storage_location: StorageLocation
    expiration_date: date
    expiration_estimated: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("품목명은 비어 있을 수 없습니다.")
        return value

    def to_internal(self) -> InternalInventoryItem:
        return InternalInventoryItem(
            id=self.id,
            name=self.name,
            quantity_half_units=quantity_to_half_units(self.quantity),
            storage_location=self.storage_location,
            expiration_date=self.expiration_date,
            expiration_estimated=self.expiration_estimated,
        )


class BatchInventoryRequest(ApiModel):
    expected_version: Annotated[int, Field(ge=0)]
    items: Annotated[list[InventoryItemCreate], Field(min_length=1, max_length=200)]


class InventoryItemUpdateRequest(ApiModel):
    expected_version: Annotated[int, Field(ge=0)]
    name: Annotated[str, Field(min_length=1, max_length=80)]
    quantity: Annotated[float, Field(ge=0, multiple_of=0.5)]
    storage_location: StorageLocation
    expiration_date: date
    expiration_estimated: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("품목명은 비어 있을 수 없습니다.")
        return value

    def quantity_half_units(self) -> int:
        if self.quantity == 0:
            raise ValueError("0개 수량은 삭제로 처리해야 합니다.")
        return quantity_to_half_units(self.quantity)


def quantity_to_half_units(quantity: Quantity) -> int:
    """검증된 외부 개수 수량을 내부 정수 반 개 단위로 바꿉니다."""
    return round(quantity * 2)


def half_units_to_quantity(half_units: HalfUnits) -> float:
    """검증된 내부 반 개 단위를 외부 개수 수량으로 바꿉니다."""
    return half_units / 2
