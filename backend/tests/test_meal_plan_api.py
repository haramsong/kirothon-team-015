from copy import deepcopy
from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import InternalInventoryItem, StorageLocation
from app.repositories.dynamodb_inventory import InventoryDocument

DEVICE_ID = "123e4567-e89b-42d3-a456-426614174000"
ITEM_ID = "223e4567-e89b-42d3-a456-426614174000"
HEADERS = {"X-Device-Id": DEVICE_ID}


class MemoryRepository:
    def __init__(self) -> None:
        self.document = InventoryDocument(
            version=4,
            items=[
                InternalInventoryItem(
                    id=UUID(ITEM_ID),
                    name="양파",
                    quantity_half_units=6,
                    storage_location=StorageLocation.ROOM_TEMPERATURE,
                    expiration_date=date(2026, 4, 12),
                    expiration_estimated=True,
                )
            ],
        )

    def get(self, _device_id: UUID) -> InventoryDocument:
        return deepcopy(self.document)


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def emit_meal_plan(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        sequence = [
            (1, "점심"),
            (1, "저녁"),
            (2, "점심"),
            (2, "저녁"),
            (3, "점심"),
            (3, "저녁"),
        ]
        return {
            "meals": [
                {
                    "day": day,
                    "slot": slot,
                    "menu_name": f"양파 요리 {index}",
                    "ingredients": [
                        {"item_id": ITEM_ID, "use_half_units": 1}
                    ],
                    "seasonings": ["간장"],
                }
                for index, (day, slot) in enumerate(sequence, start=1)
            ]
        }


def test_meal_plan_endpoint_returns_common_contract() -> None:
    gateway = RecordingGateway()
    client = TestClient(
        create_app(
            inventory_repository=MemoryRepository(),
            bedrock_gateway=gateway,
        )
    )

    response = client.post(
        "/api/meal-plans",
        headers=HEADERS,
        json={"clientDate": "2026-04-10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requestId"]
    assert body["data"]["inventoryVersion"] == 4
    assert len(body["data"]["meals"]) == 6
    assert body["data"]["meals"][0]["day"] == 1
    assert body["data"]["meals"][0]["slot"] == "점심"
    assert body["data"]["meals"][-1]["day"] == 3
    assert body["data"]["meals"][-1]["slot"] == "저녁"
    assert body["data"]["meals"][0]["recommendation"]["ingredients"] == [
        {"itemId": ITEM_ID, "name": "양파", "quantity": 0.5}
    ]
    assert gateway.calls[0]["client_date"] == "2026-04-10"


def test_meal_plan_endpoint_rejects_invalid_date_before_bedrock() -> None:
    gateway = RecordingGateway()
    client = TestClient(
        create_app(
            inventory_repository=MemoryRepository(),
            bedrock_gateway=gateway,
        )
    )

    response = client.post(
        "/api/meal-plans",
        headers=HEADERS,
        json={"clientDate": "2026-02-30"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert gateway.calls == []
