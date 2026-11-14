from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.logic.date_rules import estimate_expiration_date, parse_iso_date
from app.logic.inventory import merge_inventory_items, sort_inventory_items
from app.logic.quantity import measurement_to_half_units
from app.models import InternalInventoryItem, StorageLocation


def item(
    item_id: str,
    name: str,
    quantity_half_units: int,
    expiration_date: date,
    expiration_estimated: bool = True,
) -> InternalInventoryItem:
    return InternalInventoryItem(
        id=UUID(item_id),
        name=name,
        quantity_half_units=quantity_half_units,
        storage_location=StorageLocation.ROOM_TEMPERATURE,
        expiration_date=expiration_date,
        expiration_estimated=expiration_estimated,
    )


def test_measurement_conversion_rounds_exact_midpoint_up_to_half_item() -> None:
    assert measurement_to_half_units(Decimal("1.25"), Decimal("1")) == 3


def test_iso_date_validation_and_expiration_estimation_use_detected_date_first() -> None:
    assert parse_iso_date("2026-04-30") == date(2026, 4, 30)
    with pytest.raises(ValueError):
        parse_iso_date("2026-02-30")
    assert estimate_expiration_date(date(2026, 4, 1), 5, date(2026, 4, 2)) == (
        date(2026, 4, 7),
        True,
    )


def test_merge_preserves_quantity_and_earliest_expiration_metadata() -> None:
    existing = item(
        "123e4567-e89b-42d3-a456-426614174000",
        "양파",
        4,
        date(2026, 4, 10),
        True,
    )
    incoming = item(
        "123e4567-e89b-42d3-a456-426614174001",
        "양파",
        3,
        date(2026, 4, 8),
        False,
    )

    merged = merge_inventory_items([existing], [incoming])

    assert len(merged) == 1
    assert merged[0].id == existing.id
    assert merged[0].quantity_half_units == 7
    assert merged[0].expiration_date == date(2026, 4, 8)
    assert merged[0].expiration_estimated is False


def test_sort_places_expired_items_first_then_orders_each_group_by_date() -> None:
    items = [
        item("123e4567-e89b-42d3-a456-426614174000", "미래", 2, date(2026, 4, 12)),
        item("123e4567-e89b-42d3-a456-426614174001", "과거2", 2, date(2026, 4, 9)),
        item("123e4567-e89b-42d3-a456-426614174002", "과거1", 2, date(2026, 4, 8)),
        item("123e4567-e89b-42d3-a456-426614174003", "오늘", 2, date(2026, 4, 10)),
    ]

    sorted_items = sort_inventory_items(items, date(2026, 4, 10))

    assert [entry.name for entry in sorted_items] == ["과거1", "과거2", "오늘", "미래"]
