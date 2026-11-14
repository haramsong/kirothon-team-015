from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.testclient import TestClient

from app.dependencies import inventory_partition_key, require_device_id
from app.main import create_app, success_response

VALID_DEVICE_ID = "123e4567-e89b-42d3-a456-426614174000"


def protected_client() -> TestClient:
    application = create_app()

    @application.post("/api/protected")
    def protected(
        request: Request,
        device_id: Annotated[UUID, Depends(require_device_id)],
    ):
        return success_response(
            request,
            {"partitionKey": inventory_partition_key(device_id)},
        )

    return TestClient(application)


def test_valid_device_header_is_parsed_and_scopes_partition_key() -> None:
    response = protected_client().post(
        "/api/protected", headers={"X-Device-Id": VALID_DEVICE_ID}
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "partitionKey": f"DEVICE#{VALID_DEVICE_ID}"
    }


def test_missing_device_header_returns_safe_400_envelope() -> None:
    response = protected_client().post("/api/protected")

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "INVALID_DEVICE_ID",
        "message": "기기 식별자가 필요해요.",
        "retryable": False,
    }
    assert UUID(response.json()["requestId"]).version == 4


def test_non_v4_device_header_returns_safe_400_envelope() -> None:
    response = protected_client().post(
        "/api/protected",
        headers={"X-Device-Id": "123e4567-e89b-12d3-a456-426614174000"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DEVICE_ID"


def test_unknown_route_uses_common_error_envelope() -> None:
    response = TestClient(create_app()).get("/api/unknown")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": "요청한 경로를 찾을 수 없어요.",
        "retryable": False,
    }


def test_cors_preflight_allows_required_origin_and_headers() -> None:
    response = TestClient(create_app()).options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-Device-Id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_headers
    assert "x-device-id" in allowed_headers
