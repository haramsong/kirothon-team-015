import json
from datetime import date
from pathlib import Path

import pytest

from app.errors import AppError
from app.gateways.bedrock import BedrockGateway, BedrockGatewayError, BedrockTimeoutError
from app.models import RecognitionResultDto
from app.services.recognition import (
    MAX_IMAGE_BYTES,
    RecognitionService,
    normalize_order_item_name,
    validate_jpeg,
)

JPEG = b"\xff\xd8\xffimage"
FIXTURES = Path(__file__).parent / "fixtures"


class SequenceGateway:
    def __init__(self, outputs: list[dict]) -> None:
        self.outputs = outputs
        self.calls: list[dict] = []

    def emit_recognition(
        self, image_bytes: bytes, deadline: float, correction: str | None = None
    ) -> dict:
        self.calls.append(
            {"image_bytes": image_bytes, "deadline": deadline, "correction": correction}
        )
        return self.outputs.pop(0)


def raw_item(
    name: str,
    *,
    half_units: int = 2,
    storage: str = "실온",
    expiration: str | None = None,
    is_food: bool = True,
    is_seasoning: bool = False,
) -> dict:
    return {
        "name": name,
        "quantity_half_units": half_units,
        "storage_location": storage,
        "detected_expiration_date": expiration,
        "is_food": is_food,
        "is_basic_seasoning": is_seasoning,
    }


def test_recognition_normalizes_half_units_filters_and_estimates_dates() -> None:
    gateway = SequenceGateway(
        [
            {
                "purchase_date": "2026-04-01",
                "items": [
                    raw_item(" 양파 ", half_units=3),
                    raw_item("세제", is_food=False),
                    raw_item("소금"),
                    raw_item("후추", is_seasoning=True),
                    raw_item("두부", storage="냉장", expiration="2026-04-09"),
                ],
            }
        ]
    )
    service = RecognitionService(gateway, clock=lambda: 1.0)

    result = service.recognize(JPEG, "image/jpeg", date(2026, 4, 2), deadline=20.0)

    assert result.purchase_date == date(2026, 4, 1)
    assert result.purchase_date_source == "detected"
    assert [(item.name, item.quantity) for item in result.items] == [
        ("양파", 1.5),
        ("두부", 1.0),
    ]
    assert result.items[0].expiration_date == date(2026, 4, 15)
    assert result.items[0].expiration_estimated is True
    assert result.items[1].expiration_date == date(2026, 4, 9)
    assert result.items[1].expiration_estimated is False


def test_missing_purchase_date_uses_request_date_and_empty_items_is_success() -> None:
    gateway = SequenceGateway([{"purchase_date": None, "items": []}])
    service = RecognitionService(gateway, clock=lambda: 1.0)

    result = service.recognize(JPEG, "image/jpeg", date(2026, 4, 2), deadline=20.0)

    assert result.purchase_date == date(2026, 4, 2)
    assert result.purchase_date_source == "request_date"
    assert result.items == []


def test_invalid_model_output_is_corrected_once_when_eight_seconds_remain() -> None:
    gateway = SequenceGateway(
        [
            {"purchase_date": None, "items": [raw_item("양파", half_units=0)]},
            {"purchase_date": None, "items": [raw_item("양파", half_units=2)]},
        ]
    )
    service = RecognitionService(gateway, clock=lambda: 1.0)

    result = service.recognize(JPEG, "image/jpeg", date(2026, 4, 2), deadline=20.0)

    assert result.items[0].quantity == 1
    assert len(gateway.calls) == 2
    assert gateway.calls[0]["correction"] is None
    assert "quantity_half_units" in gateway.calls[1]["correction"]


@pytest.mark.parametrize(
    ("content_type", "image_bytes"),
    [
        ("image/png", JPEG),
        ("image/jpeg", b"not-jpeg"),
        ("image/jpeg", b"\xff\xd8\xff" + b"x" * (MAX_IMAGE_BYTES - 2)),
    ],
)
def test_invalid_image_is_rejected_before_bedrock(
    content_type: str, image_bytes: bytes
) -> None:
    gateway = SequenceGateway([])
    service = RecognitionService(gateway, clock=lambda: 1.0)

    with pytest.raises(AppError) as caught:
        service.recognize(
            image_bytes, content_type, date(2026, 4, 2), deadline=20.0
        )

    assert caught.value.status_code == 400
    assert caught.value.code == "INVALID_IMAGE"
    assert gateway.calls == []


def test_second_invalid_output_returns_distinct_model_error() -> None:
    invalid = {"purchase_date": "잘못된 날짜", "items": []}
    gateway = SequenceGateway([invalid, invalid])
    service = RecognitionService(gateway, clock=lambda: 1.0)

    with pytest.raises(AppError) as caught:
        service.recognize(JPEG, "image/jpeg", date(2026, 4, 2), deadline=20.0)

    assert caught.value.status_code == 502
    assert caught.value.code == "INVALID_MODEL_OUTPUT"
    assert len(gateway.calls) == 2


class ErrorGateway:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def emit_recognition(
        self, image_bytes: bytes, deadline: float, correction: str | None = None
    ) -> dict:
        self.calls += 1
        raise self.error


def test_exact_image_size_limit_is_accepted() -> None:
    image = b"\xff\xd8\xff" + b"x" * (MAX_IMAGE_BYTES - 3)

    validate_jpeg(image, "image/jpeg; charset=binary")


def test_invalid_output_is_not_retried_without_eight_seconds_remaining() -> None:
    gateway = SequenceGateway([{"purchase_date": "잘못된 날짜", "items": []}])
    service = RecognitionService(gateway, clock=lambda: 13.0)

    with pytest.raises(AppError) as caught:
        service.recognize(JPEG, "image/jpeg", date(2026, 4, 2), deadline=20.0)

    assert caught.value.code == "INVALID_MODEL_OUTPUT"
    assert len(gateway.calls) == 1


@pytest.mark.parametrize(
    ("gateway_error", "status_code", "code"),
    [
        (BedrockTimeoutError("timeout"), 504, "LLM_TIMEOUT"),
        (BedrockGatewayError("failed"), 502, "RECOGNITION_FAILED"),
    ],
)
def test_gateway_failures_are_mapped_to_distinct_api_errors(
    gateway_error: Exception, status_code: int, code: str
) -> None:
    gateway = ErrorGateway(gateway_error)
    service = RecognitionService(gateway, clock=lambda: 1.0)

    with pytest.raises(AppError) as caught:
        service.recognize(JPEG, "image/jpeg", date(2026, 4, 2), deadline=20.0)

    assert caught.value.status_code == status_code
    assert caught.value.code == code
    assert caught.value.retryable is True


@pytest.mark.parametrize(
    ("product_name", "expected"),
    [
        ("[옵션: 중] 국내산 양파 1.5kg x 2망", "양파"),
        ("친환경 두부 300g 3팩", "두부"),
        ("[선택: 1L] 우유 1L × 2팩", "우유"),
        ("대파", "대파"),
    ],
)
def test_order_item_name_removes_options_bundle_and_weight_labels(
    product_name: str, expected: str
) -> None:
    assert normalize_order_item_name(product_name) == expected


class FixtureBedrockClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def converse(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return self.response


def test_order_history_fixture_uses_shared_recognition_result_path() -> None:
    fixture = json.loads(
        (FIXTURES / "order_history_bedrock_response.json").read_text(encoding="utf-8")
    )
    client = FixtureBedrockClient(fixture)
    gateway = BedrockGateway("test-model", client=client, clock=lambda: 1.0)
    service = RecognitionService(gateway, clock=lambda: 1.0)

    result = service.recognize(
        JPEG,
        "image/jpeg",
        request_date=date(2026, 4, 7),
        deadline=20.0,
    )

    assert isinstance(result, RecognitionResultDto)
    assert result.purchase_date == date(2026, 4, 6)
    assert result.purchase_date_source == "detected"
    assert [(item.name, item.quantity) for item in result.items] == [
        ("양파", 16.0),
        ("두부", 3.0),
        ("우유", 2.0),
    ]
    assert result.items[0].expiration_date == date(2026, 4, 20)
    assert result.items[1].expiration_estimated is False
    assert result.items[2].expiration_date == date(2026, 4, 13)
    assert len(client.calls) == 1
