from copy import deepcopy
from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import InternalInventoryItem, StorageLocation
from app.repositories.dynamodb_inventory import InventoryDocument, InventoryStorageError

DEVICE_ID = "123e4567-e89b-42d3-a456-426614174000"
ITEM_ID = "223e4567-e89b-42d3-a456-426614174000"
HEADERS = {"X-Device-Id": DEVICE_ID}
TODAY = "2026-04-10"


class MemoryRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, InventoryDocument] = {}
        self.fail_replace = False

    def get(self, device_id: UUID) -> InventoryDocument:
        return deepcopy(self.documents.get(device_id, InventoryDocument(0, [])))

    def replace(self, device_id: UUID, expected_version: int, items: list[InternalInventoryItem]) -> InventoryDocument:
        if self.fail_replace:
            raise InventoryStorageError
        current = self.documents.get(device_id, InventoryDocument(0, []))
        if current.version != expected_version:
            from app.repositories.dynamodb_inventory import InventoryConflictError
            raise InventoryConflictError
        saved = InventoryDocument(expected_version + 1, deepcopy(items))
        self.documents[device_id] = saved
        return deepcopy(saved)


def client_with(repository: MemoryRepository) -> TestClient:
    application = create_app(inventory_repository=repository)
    return TestClient(application, raise_server_exceptions=False)


def batch_payload(quantity: float = 2) -> dict:
    return {
        "expectedVersion": 0,
        "items": [
            {
                "id": ITEM_ID,
                "name": "양파",
                "quantity": quantity,
                "storageLocation": "실온",
                "expirationDate": "2026-04-12",
                "expirationEstimated": True,
            }
        ],
    }


def test_batch_create_get_merge_update_zero_delete_and_explicit_delete() -> None:
    repository = MemoryRepository()
    client = client_with(repository)

    created = client.post(
        f"/api/inventory/items:batch?today={TODAY}", json=batch_payload(), headers=HEADERS
    )
    assert created.status_code == 200
    assert created.json()["data"]["inventory"]["version"] == 1

    merge_body = batch_payload(1)
    merge_body["expectedVersion"] = 1
    merged = client.post(
        f"/api/inventory/items:batch?today={TODAY}", json=merge_body, headers=HEADERS
    )
    assert merged.status_code == 200
    assert merged.json()["data"]["inventory"]["items"][0]["quantity"] == 3

    updated = client.put(
        f"/api/inventory/items/{ITEM_ID}?today={TODAY}",
        headers=HEADERS,
        json={
            "expectedVersion": 2,
            "name": "양파",
            "quantity": 0,
            "storageLocation": "실온",
            "expirationDate": "2026-04-12",
            "expirationEstimated": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["items"] == []

    second_id = "323e4567-e89b-42d3-a456-426614174000"
    add_body = batch_payload()
    add_body["expectedVersion"] = 3
    add_body["items"][0]["id"] = second_id
    assert client.post(
        f"/api/inventory/items:batch?today={TODAY}", json=add_body, headers=HEADERS
    ).status_code == 200
    deleted = client.delete(
        f"/api/inventory/items/{second_id}?today={TODAY}&expectedVersion=4", headers=HEADERS
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["items"] == []


def test_version_conflict_and_storage_failure_do_not_change_original_document() -> None:
    repository = MemoryRepository()
    client = client_with(repository)
    assert client.post(
        f"/api/inventory/items:batch?today={TODAY}", json=batch_payload(), headers=HEADERS
    ).status_code == 200
    original = repository.get(UUID(DEVICE_ID))

    conflict = client.put(
        f"/api/inventory/items/{ITEM_ID}?today={TODAY}",
        headers=HEADERS,
        json={
            "expectedVersion": 0,
            "name": "양파",
            "quantity": 1,
            "storageLocation": "실온",
            "expirationDate": "2026-04-15",
            "expirationEstimated": False,
        },
    )
    assert conflict.status_code == 409
    assert repository.get(UUID(DEVICE_ID)) == original

    repository.fail_replace = True
    failed = client.delete(
        f"/api/inventory/items/{ITEM_ID}?today={TODAY}&expectedVersion=1", headers=HEADERS
    )
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "STORAGE_ERROR"
    assert repository.get(UUID(DEVICE_ID)) == original


def test_inventory_isolated_by_device_and_sorted_for_requested_date() -> None:
    repository = MemoryRepository()
    client = client_with(repository)
    assert client.post(
        f"/api/inventory/items:batch?today={TODAY}", json=batch_payload(), headers=HEADERS
    ).status_code == 200

    other_headers = {"X-Device-Id": "423e4567-e89b-42d3-a456-426614174000"}
    other = client.get(f"/api/inventory?today={TODAY}", headers=other_headers)
    assert other.status_code == 200
    assert other.json()["data"] == {"items": [], "version": 0}
