from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_success_envelope_and_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == {"status": "ok"}
    assert UUID(payload["requestId"]).version == 4
    assert response.headers["X-Request-Id"] == payload["requestId"]
