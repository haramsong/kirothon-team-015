from copy import deepcopy
from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import InternalInventoryItem, StorageLocation
from app.repositories.dynamodb_inventory import (
    DeductionRecord,
    DeductionTransactionConflictError,
    InventoryDocument,
)

DEVICE_ID = UUID("123e4567-e89b-42d3-a456-426614174000")
ITEM_ID = UUID("223e4567-e89b-42d3-a456-426614174000")
REQUEST_ID = UUID("323e4567-e89b-42d3-a456-426614174000")
HEADERS = {"X-Device-Id": str(DEVICE_ID)}


class MemoryDeductionRepository:
    def __init__(self) -> None:
        self.documents = {DEVICE_ID: InventoryDocument(0, [self._item()])}
        self.records: dict[tuple[UUID, UUID], DeductionRecord] = {}
        self.transaction_calls = 0
        self.force_conflict = False

    @staticmethod
    def _item() -> InternalInventoryItem:
        return InternalInventoryItem(
            id=ITEM_ID,
            name="양파",
            quantity_half_units=4,
            storage_location=StorageLocation.ROOM_TEMPERATURE,
            expiration_date=date(2026, 4, 12),
            expiration_estimated=True,
        )

    def get(self, device_id: UUID) -> InventoryDocument:
        return deepcopy(self.documents.get(device_id, InventoryDocument(0, [])))

    def replace(self, device_id, expected_version, items):
        raise AssertionError("차감은 일반 교체를 사용하면 안 됩니다.")

    def get_deduction(
        self, device_id: UUID, request_id: UUID
    ) -> DeductionRecord | None:
        return deepcopy(self.records.get((device_id, request_id)))

    def transact_deduction(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
        record: DeductionRecord,
    ) -> InventoryDocument:
        self.transaction_calls += 1
        current = self.documents[device_id]
        key = (device_id, record.request_id)
        if self.force_conflict or current.version != expected_version or key in self.records:
            raise DeductionTransactionConflictError
        saved = InventoryDocument(expected_version + 1, deepcopy(items))
        self.documents[device_id] = saved
        self.records[key] = deepcopy(record)
        return deepcopy(saved)


def client_with(repository: MemoryDeductionRepository) -> TestClient:
    return TestClient(
        create_app(inventory_repository=repository),
        raise_server_exceptions=False,
    )


def payload(quantity: float = 1) -> dict:
    return {
        "deductionRequestId": str(REQUEST_ID),
        "items": [{"itemId": str(ITEM_ID), "quantity": quantity}],
    }


def test_deduction_endpoint_applies_once_and_returns_existing_result_on_retry() -> None:
    repository = MemoryDeductionRepository()
    client = client_with(repository)

    first = client.post(
        "/api/deductions?today=2026-04-10", json=payload(), headers=HEADERS
    )
    retried = client.post(
        "/api/deductions?today=2026-04-10", json=payload(), headers=HEADERS
    )

    assert first.status_code == 200
    assert first.json()["data"] == {
        "inventory": {
            "items": [
                {
                    "id": str(ITEM_ID),
                    "name": "양파",
                    "quantity": 1.0,
                    "storageLocation": "실온",
                    "expirationDate": "2026-04-12",
                    "expirationEstimated": True,
                }
            ],
            "version": 1,
        },
        "deductedCount": 1,
        "removedNames": [],
    }
    assert retried.json()["data"] == first.json()["data"]
    assert repository.transaction_calls == 1
    assert repository.get(DEVICE_ID).items[0].quantity_half_units == 2


def test_reused_request_id_with_different_payload_returns_conflict_without_write() -> None:
    repository = MemoryDeductionRepository()
    client = client_with(repository)
    assert client.post("/api/deductions", json=payload(), headers=HEADERS).status_code == 200

    reused = client.post("/api/deductions", json=payload(0.5), headers=HEADERS)

    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert repository.transaction_calls == 1
    assert repository.get(DEVICE_ID).items[0].quantity_half_units == 2


def test_unknown_or_excessive_deduction_is_rejected_before_transaction() -> None:
    repository = MemoryDeductionRepository()
    client = client_with(repository)
    original = repository.get(DEVICE_ID)

    excessive = client.post("/api/deductions", json=payload(2.5), headers=HEADERS)
    unknown = client.post(
        "/api/deductions",
        json={
            "deductionRequestId": str(UUID("423e4567-e89b-42d3-a456-426614174000")),
            "items": [
                {
                    "itemId": "523e4567-e89b-42d3-a456-426614174000",
                    "quantity": 0.5,
                }
            ],
        },
        headers=HEADERS,
    )

    assert excessive.status_code == 400
    assert unknown.status_code == 400
    assert repository.transaction_calls == 0
    assert repository.get(DEVICE_ID) == original


def test_inventory_version_race_returns_conflict_without_partial_change() -> None:
    repository = MemoryDeductionRepository()
    repository.force_conflict = True
    client = client_with(repository)
    original = repository.get(DEVICE_ID)

    response = client.post("/api/deductions", json=payload(), headers=HEADERS)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVENTORY_CONFLICT"
    assert repository.get(DEVICE_ID) == original
    assert repository.records == {}
