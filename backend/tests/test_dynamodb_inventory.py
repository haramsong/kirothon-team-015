from datetime import date
from uuid import UUID

import pytest

from app.models import InternalInventoryItem, StorageLocation
from app.repositories.dynamodb_inventory import (
    DynamoInventoryRepository,
    InventoryConflictError,
    InventoryStorageError,
)

DEVICE_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
ITEM_ID = UUID("223e4567-e89b-42d3-a456-426614174000")


class ConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeTable:
    def __init__(self) -> None:
        self.item = None
        self.fail_get = False
        self.fail_put = None
        self.last_get = None
        self.last_put = None

    def get_item(self, **kwargs):
        self.last_get = kwargs
        if self.fail_get:
            raise RuntimeError("get failed")
        return {} if self.item is None else {"Item": self.item}

    def put_item(self, **kwargs):
        self.last_put = kwargs
        if self.fail_put:
            raise self.fail_put
        self.item = kwargs["Item"]
        return {}


def sample_item() -> InternalInventoryItem:
    return InternalInventoryItem(
        id=ITEM_ID,
        name="양파",
        quantity_half_units=4,
        storage_location=StorageLocation.ROOM_TEMPERATURE,
        expiration_date=date(2026, 4, 12),
        expiration_estimated=True,
    )


def test_repository_uses_device_inventory_key_and_round_trips_document() -> None:
    table = FakeTable()
    repository = DynamoInventoryRepository(table)

    empty = repository.get(DEVICE_ID)
    saved = repository.replace(DEVICE_ID, empty.version, [sample_item()])
    loaded = repository.get(DEVICE_ID)

    assert empty.version == 0
    assert saved.version == 1
    assert loaded == saved
    assert table.last_get == {
        "Key": {"pk": f"DEVICE#{DEVICE_ID}", "sk": "INVENTORY"},
        "ConsistentRead": True,
    }
    assert table.last_put["ExpressionAttributeValues"] == {":expected": 0}


def test_repository_maps_conditional_and_storage_failures_without_returning_success() -> None:
    table = FakeTable()
    repository = DynamoInventoryRepository(table)
    table.fail_put = ConditionalFailure()
    with pytest.raises(InventoryConflictError):
        repository.replace(DEVICE_ID, 0, [sample_item()])

    table.fail_put = RuntimeError("put failed")
    with pytest.raises(InventoryStorageError):
        repository.replace(DEVICE_ID, 0, [sample_item()])

    table.fail_get = True
    with pytest.raises(InventoryStorageError):
        repository.get(DEVICE_ID)
