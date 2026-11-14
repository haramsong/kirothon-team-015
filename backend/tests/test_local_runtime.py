from uuid import UUID

from fastapi.testclient import TestClient

from app.config import get_settings
from app.local_adapters import LocalBedrockGateway, LocalInventoryRepository
from app.main import create_app

DEVICE_ID = "123e4567-e89b-42d3-a456-426614174000"


def test_app_env_test_selects_aws_free_local_adapters(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    try:
        application = create_app()
        client = TestClient(application)

        health = client.get("/api/health")
        inventory = client.get(
            "/api/inventory?today=2026-04-10",
            headers={"X-Device-Id": DEVICE_ID},
        )

        assert health.status_code == 200
        assert health.json()["data"] == {"status": "ok"}
        assert inventory.status_code == 200
        assert inventory.json()["data"] == {"version": 0, "items": []}
        assert isinstance(application.state.inventory_repository, LocalInventoryRepository)
        assert isinstance(application.state.bedrock_gateway, LocalBedrockGateway)
    finally:
        get_settings.cache_clear()


def test_local_repository_keeps_device_inventory_separate() -> None:
    repository = LocalInventoryRepository()
    first_device = UUID(DEVICE_ID)
    second_device = UUID("223e4567-e89b-42d3-a456-426614174000")

    saved = repository.replace(first_device, expected_version=0, items=[])

    assert saved.version == 1
    assert repository.get(first_device).version == 1
    assert repository.get(second_device).version == 0


def test_local_gateway_returns_deterministic_core_flow_outputs() -> None:
    gateway = LocalBedrockGateway()
    item_id = DEVICE_ID
    context = [
        {
            "item_id": item_id,
            "name": "양파",
            "quantity_half_units": 16,
            "expiration_date": "2026-04-12",
        }
    ]

    recognition = gateway.emit_recognition()
    recommendation = gateway.emit_recommendation(
        inventory_context=context,
        priority_item_id=item_id,
        excluded_menu_name=None,
    )
    recipe = gateway.emit_recipe(
        recommendation_context={
            "ingredients": [{"name": "양파"}],
            "seasonings": ["간장", "식용유"],
        }
    )
    meal_plan = gateway.emit_meal_plan(inventory_context=context)

    assert recognition["items"][0]["quantity_half_units"] == 16
    assert recommendation["ingredients"][0]["item_id"] == item_id
    assert recipe["ingredient_names"] == ["양파", "간장", "식용유"]
    assert [(meal["day"], meal["slot"]) for meal in meal_plan["meals"]] == [
        (1, "점심"),
        (1, "저녁"),
        (2, "점심"),
        (2, "저녁"),
        (3, "점심"),
        (3, "저녁"),
    ]
