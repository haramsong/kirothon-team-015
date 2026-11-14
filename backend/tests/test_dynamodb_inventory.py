from datetime import date
from uuid import UUID

import pytest

from app.models import InternalInventoryItem, StorageLocation
from app.repositories.dynamodb_inventory import (
    DeductionRecord,
    DeductionTransactionConflictError,
    DynamoInventoryRepository,
    InventoryConflictError,
    InventoryStorageError,
)

DEVICE_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
ITEM_ID = UUID("223e4567-e89b-42d3-a456-426614174000")


class ConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class TransactionFailure(Exception):
    response = {"Error": {"Code": "TransactionCanceledException"}}


class FakeMeta:
    def __init__(self, client) -> None:
        self.client = client


class FakeTable:
    def __init__(self) -> None:
        self.name = "inventory-table"
        self.meta = FakeMeta(self)
        self.item = None
        self.fail_get = False
        self.fail_put = None
        self.fail_transact = None
        self.last_get = None
        self.last_put = None
        self.last_transact = None

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

    def transact_write_items(self, **kwargs):
        self.last_transact = kwargs
        if self.fail_transact:
            raise self.fail_transact
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


def test_repository_reads_deduction_record_with_device_scoped_key() -> None:
    request_id = UUID("323e4567-e89b-42d3-a456-426614174000")
    table = FakeTable()
    table.item = {
        "pk": f"DEVICE#{DEVICE_ID}",
        "sk": f"DEDUCTION#{request_id}",
        "payloadHash": "abc123",
        "deductedCount": 2,
        "removedNames": ["당근"],
        "resultVersion": 3,
        "createdAt": "2026-04-10T00:00:00Z",
    }
    repository = DynamoInventoryRepository(table)

    record = repository.get_deduction(DEVICE_ID, request_id)

    assert record == DeductionRecord(
        request_id=request_id,
        payload_hash="abc123",
        deducted_count=2,
        removed_names=["당근"],
        result_version=3,
        created_at="2026-04-10T00:00:00Z",
    )
    assert table.last_get == {
        "Key": {
            "pk": f"DEVICE#{DEVICE_ID}",
            "sk": f"DEDUCTION#{request_id}",
        },
        "ConsistentRead": True,
    }


def test_repository_transacts_inventory_version_and_unique_deduction_record() -> None:
    request_id = UUID("323e4567-e89b-42d3-a456-426614174000")
    table = FakeTable()
    repository = DynamoInventoryRepository(table)
    record = DeductionRecord(
        request_id=request_id,
        payload_hash="abc123",
        deducted_count=1,
        removed_names=[],
        result_version=2,
        created_at="2026-04-10T00:00:00Z",
    )

    saved = repository.transact_deduction(DEVICE_ID, 1, [sample_item()], record)

    inventory_put, deduction_put = [
        action["Put"] for action in table.last_transact["TransactItems"]
    ]
    assert saved.version == 2
    assert inventory_put["ConditionExpression"] == (
        "attribute_not_exists(pk) OR #version = :expected"
    )
    assert inventory_put["ExpressionAttributeValues"] == {":expected": 1}
    assert inventory_put["Item"]["sk"] == "INVENTORY"
    assert deduction_put["ConditionExpression"] == "attribute_not_exists(pk)"
    assert deduction_put["Item"]["sk"] == f"DEDUCTION#{request_id}"
    assert deduction_put["Item"]["payloadHash"] == "abc123"


def test_repository_maps_canceled_deduction_transaction_without_success() -> None:
    request_id = UUID("323e4567-e89b-42d3-a456-426614174000")
    table = FakeTable()
    table.fail_transact = TransactionFailure()
    repository = DynamoInventoryRepository(table)
    record = DeductionRecord(request_id, "abc123", 1, [], 1, "2026-04-10T00:00:00Z")

    with pytest.raises(DeductionTransactionConflictError):
        repository.transact_deduction(DEVICE_ID, 0, [sample_item()], record)
