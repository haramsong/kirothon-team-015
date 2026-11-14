import hashlib
from datetime import date
from uuid import UUID

import pytest

from app.logic.deduction import DeductionLine, apply_deduction, canonical_payload_hash
from app.models import InternalInventoryItem, StorageLocation

ONION_ID = UUID("223e4567-e89b-42d3-a456-426614174000")
CARROT_ID = UUID("323e4567-e89b-42d3-a456-426614174000")


def item(item_id: UUID, name: str, half_units: int) -> InternalInventoryItem:
    return InternalInventoryItem(
        id=item_id,
        name=name,
        quantity_half_units=half_units,
        storage_location=StorageLocation.REFRIGERATED,
        expiration_date=date(2026, 4, 12),
        expiration_estimated=True,
    )


def test_canonical_payload_hash_sorts_item_ids_and_uses_half_units() -> None:
    lines = [
        DeductionLine(CARROT_ID, 1),
        DeductionLine(ONION_ID, 2),
    ]
    canonical = (
        '[{"itemId":"223e4567-e89b-42d3-a456-426614174000","useHalfUnits":2},'
        '{"itemId":"323e4567-e89b-42d3-a456-426614174000","useHalfUnits":1}]'
    )

    assert canonical_payload_hash(lines) == hashlib.sha256(canonical.encode()).hexdigest()
    assert canonical_payload_hash(lines) == canonical_payload_hash(list(reversed(lines)))


def test_apply_deduction_reduces_once_and_removes_zero_quantity_items() -> None:
    inventory = [item(ONION_ID, "양파", 4), item(CARROT_ID, "당근", 1)]

    updated, removed = apply_deduction(
        inventory,
        [DeductionLine(ONION_ID, 2), DeductionLine(CARROT_ID, 1)],
    )

    assert [(stored.name, stored.quantity_half_units) for stored in updated] == [
        ("양파", 2)
    ]
    assert removed == ["당근"]
    assert [stored.quantity_half_units for stored in inventory] == [4, 1]


@pytest.mark.parametrize(
    "lines",
    [
        [],
        [DeductionLine(UUID("423e4567-e89b-42d3-a456-426614174000"), 1)],
        [DeductionLine(ONION_ID, 5)],
        [DeductionLine(ONION_ID, 0)],
        [DeductionLine(ONION_ID, 1), DeductionLine(ONION_ID, 1)],
    ],
)
def test_apply_deduction_rejects_invalid_requests_without_mutating_inventory(
    lines: list[DeductionLine],
) -> None:
    inventory = [item(ONION_ID, "양파", 4)]

    with pytest.raises(ValueError):
        apply_deduction(inventory, lines)

    assert inventory[0].quantity_half_units == 4
