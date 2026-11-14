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
            version=2,
            items=[
                InternalInventoryItem(
                    id=UUID(ITEM_ID),
                    name="양파",
                    quantity_half_units=4,
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
        self.recommendation_calls: list[dict] = []
        self.recipe_calls: list[dict] = []

    def emit_recommendation(self, **kwargs: object) -> dict:
        self.recommendation_calls.append(kwargs)
        return {
            "menu_name": "양파 덮밥",
            "ingredients": [{"item_id": ITEM_ID, "use_half_units": 2}],
            "seasonings": ["간장"],
        }

    def emit_recipe(self, **kwargs: object) -> dict:
        self.recipe_calls.append(kwargs)
        return {
            "ingredient_names": ["양파", "간장"],
            "steps": ["양파를 썰어요.", "간장과 함께 볶아요."],
        }


def test_recommendation_and_recipe_endpoints_use_common_contract() -> None:
    gateway = RecordingGateway()
    client = TestClient(
        create_app(
            inventory_repository=MemoryRepository(),
            bedrock_gateway=gateway,
        )
    )

    recommendation_response = client.post(
        "/api/recommendations",
        headers=HEADERS,
        json={"clientDate": "2026-04-10", "excludedMenuName": "양파국"},
    )

    assert recommendation_response.status_code == 200
    recommendation = recommendation_response.json()["data"]
    assert recommendation["menuName"] == "양파 덮밥"
    assert recommendation["ingredients"] == [
        {"itemId": ITEM_ID, "name": "양파", "quantity": 1.0}
    ]
    assert recommendation["seasonings"] == ["간장"]
    assert recommendation_response.json()["requestId"]
    assert gateway.recommendation_calls[0]["excluded_menu_name"] == "양파국"

    recipe_response = client.post(
        "/api/recipes",
        headers=HEADERS,
        json={"recommendation": recommendation},
    )

    assert recipe_response.status_code == 200
    assert recipe_response.json()["data"] == {
        "steps": ["양파를 썰어요.", "간장과 함께 볶아요."]
    }
    assert recipe_response.json()["requestId"]
    assert len(gateway.recipe_calls) == 1


def test_recommendation_endpoint_rejects_invalid_date_before_bedrock() -> None:
    gateway = RecordingGateway()
    client = TestClient(
        create_app(
            inventory_repository=MemoryRepository(),
            bedrock_gateway=gateway,
        )
    )

    response = client.post(
        "/api/recommendations",
        headers=HEADERS,
        json={"clientDate": "2026-02-30"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert gateway.recommendation_calls == []
