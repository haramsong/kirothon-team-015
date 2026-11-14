from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models import (
    InternalInventoryItem,
    InventoryItemDto,
    StorageLocation,
    half_units_to_quantity,
    quantity_to_half_units,
)

ITEM_ID = UUID("123e4567-e89b-42d3-a456-426614174000")


def test_quantity_boundary_converts_between_quantity_and_half_units() -> None:
    assert quantity_to_half_units(1.5) == 3
    assert half_units_to_quantity(3) == 1.5


def test_inventory_dto_accepts_half_unit_quantity_and_serializes_camel_case() -> None:
    item = InventoryItemDto(
        id=ITEM_ID,
        name="양파",
        quantity=1.5,
        storage_location=StorageLocation.ROOM_TEMPERATURE,
        expiration_date=date(2026, 4, 12),
        expiration_estimated=True,
    )

    assert item.model_dump(mode="json", by_alias=True) == {
        "id": str(ITEM_ID),
        "name": "양파",
        "quantity": 1.5,
        "storageLocation": "실온",
        "expirationDate": "2026-04-12",
        "expirationEstimated": True,
    }


def test_inventory_dto_rejects_non_half_unit_quantity() -> None:
    with pytest.raises(ValidationError):
        InventoryItemDto(
            id=ITEM_ID,
            name="양파",
            quantity=1.25,
            storage_location=StorageLocation.ROOM_TEMPERATURE,
            expiration_date=date(2026, 4, 12),
            expiration_estimated=True,
        )


def test_internal_inventory_item_rejects_zero_half_units() -> None:
    with pytest.raises(ValidationError):
        InternalInventoryItem(
            id=ITEM_ID,
            name="양파",
            quantity_half_units=0,
            storage_location=StorageLocation.ROOM_TEMPERATURE,
            expiration_date=date(2026, 4, 12),
            expiration_estimated=True,
        )
