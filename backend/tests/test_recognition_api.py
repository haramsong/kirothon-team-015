from datetime import date

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.recognition import MAX_IMAGE_BYTES

DEVICE_ID = "123e4567-e89b-42d3-a456-426614174000"
HEADERS = {"X-Device-Id": DEVICE_ID}
JPEG = b"\xff\xd8\xffimage"


class RecordingGateway:
    def __init__(self, output: dict) -> None:
        self.output = output
        self.calls = 0

    def emit_recognition(
        self, image_bytes: bytes, deadline: float, correction: str | None = None
    ) -> dict:
        self.calls += 1
        return self.output


def test_recognition_endpoint_returns_common_success_envelope() -> None:
    gateway = RecordingGateway(
        {
            "purchase_date": "2026-04-01",
            "items": [
                {
                    "name": "양파",
                    "quantity_half_units": 3,
                    "storage_location": "실온",
                    "detected_expiration_date": None,
                    "is_food": True,
                    "is_basic_seasoning": False,
                }
            ],
        }
    )
    client = TestClient(create_app(bedrock_gateway=gateway))

    response = client.post(
        "/api/recognitions",
        files={"image": ("receipt.jpg", JPEG, "image/jpeg")},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["data"]["purchaseDate"] == "2026-04-01"
    assert response.json()["data"]["purchaseDateSource"] == "detected"
    assert response.json()["data"]["items"][0]["quantity"] == 1.5
    assert gateway.calls == 1


def test_recognition_endpoint_distinguishes_empty_success() -> None:
    gateway = RecordingGateway({"purchase_date": None, "items": []})
    client = TestClient(create_app(bedrock_gateway=gateway))

    response = client.post(
        "/api/recognitions",
        files={"image": ("receipt.jpg", JPEG, "image/jpeg")},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "purchaseDate": date.today().isoformat(),
        "purchaseDateSource": "request_date",
        "items": [],
    }


def test_invalid_jpeg_mime_magic_and_size_never_call_gateway() -> None:
    gateway = RecordingGateway({"purchase_date": None, "items": []})
    client = TestClient(create_app(bedrock_gateway=gateway))

    responses = [
        client.post(
            "/api/recognitions",
            files={"image": ("receipt.png", JPEG, "image/png")},
            headers=HEADERS,
        ),
        client.post(
            "/api/recognitions",
            files={"image": ("receipt.jpg", b"not-jpeg", "image/jpeg")},
            headers=HEADERS,
        ),
        client.post(
            "/api/recognitions",
            files={
                "image": (
                    "receipt.jpg",
                    b"\xff\xd8\xff" + b"x" * (MAX_IMAGE_BYTES - 2),
                    "image/jpeg",
                )
            },
            headers=HEADERS,
        ),
    ]

    assert [response.status_code for response in responses] == [400, 400, 400]
    assert all(response.json()["error"]["code"] == "INVALID_IMAGE" for response in responses)
    assert gateway.calls == 0
