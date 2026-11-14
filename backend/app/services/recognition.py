import re
import time
from datetime import date
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.constants import BASIC_SEASONINGS
from app.errors import AppError
from app.gateways.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockInvalidOutputError,
    BedrockTimeoutError,
)
from app.logic.date_rules import estimate_expiration_date
from app.models import InventoryItemDto, RecognitionResultDto, StorageLocation

MAX_IMAGE_BYTES = 3_932_160
JPEG_CONTENT_TYPE = "image/jpeg"
DEFAULT_SHELF_LIFE_DAYS = {
    StorageLocation.REFRIGERATED: 5,
    StorageLocation.FROZEN: 30,
    StorageLocation.ROOM_TEMPERATURE: 7,
}
SHELF_LIFE_DAYS: dict[str, dict[StorageLocation, int]] = {
    "양파": {
        StorageLocation.REFRIGERATED: 14,
        StorageLocation.FROZEN: 30,
        StorageLocation.ROOM_TEMPERATURE: 14,
    },
    "대파": {
        StorageLocation.REFRIGERATED: 10,
        StorageLocation.FROZEN: 30,
        StorageLocation.ROOM_TEMPERATURE: 3,
    },
    "우유": {
        StorageLocation.REFRIGERATED: 7,
        StorageLocation.FROZEN: 30,
        StorageLocation.ROOM_TEMPERATURE: 1,
    },
    "달걀": {
        StorageLocation.REFRIGERATED: 21,
        StorageLocation.FROZEN: 30,
        StorageLocation.ROOM_TEMPERATURE: 7,
    },
    "두부": {
        StorageLocation.REFRIGERATED: 5,
        StorageLocation.FROZEN: 30,
        StorageLocation.ROOM_TEMPERATURE: 1,
    },
    "돼지고기": {
        StorageLocation.REFRIGERATED: 3,
        StorageLocation.FROZEN: 90,
        StorageLocation.ROOM_TEMPERATURE: 1,
    },
    "닭고기": {
        StorageLocation.REFRIGERATED: 2,
        StorageLocation.FROZEN: 90,
        StorageLocation.ROOM_TEMPERATURE: 1,
    },
}

OPTION_PATTERN = re.compile(r"[\[(](?:옵션|선택)\s*[:：]?[^\])]*[\])]")
MULTIPLIER_PATTERN = re.compile(
    r"(?:[xX×]\s*\d+(?:\.\d+)?\s*(?:개|입|구|팩|봉|망|묶음)?)"
)
PACKAGE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:kg|g|ml|l|개입|입|구|팩|봉|망|묶음)",
    re.IGNORECASE,
)
PRODUCT_DESCRIPTORS = re.compile(
    r"(?<!\S)(?:국내산|국산|친환경|유기농|무농약|냉장|냉동|대용량|산지직송)(?!\S)"
)
SEPARATOR_PATTERN = re.compile(r"\s*[-_/|,·]+\s*")


def normalize_order_item_name(name: str) -> str:
    """주문 상품의 옵션·중량·묶음 표기를 제거해 일반 품목명으로 만듭니다."""
    original = " ".join(name.split())
    normalized = OPTION_PATTERN.sub(" ", original)
    normalized = MULTIPLIER_PATTERN.sub(" ", normalized)
    normalized = PACKAGE_PATTERN.sub(" ", normalized)
    normalized = PRODUCT_DESCRIPTORS.sub(" ", normalized)
    normalized = SEPARATOR_PATTERN.sub(" ", normalized)
    normalized = " ".join(normalized.split()).strip(" -_/|,·")
    return normalized or original


class RecognitionToolItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    quantity_half_units: int = Field(ge=1)
    storage_location: StorageLocation
    detected_expiration_date: date | None
    is_food: bool
    is_basic_seasoning: bool

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("품목명은 비어 있을 수 없습니다.")
        return cleaned


class RecognitionToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_date: date | None
    items: list[RecognitionToolItem] = Field(max_length=200)


class RecognitionService:
    def __init__(
        self,
        gateway: BedrockGateway,
        clock: Any = time.monotonic,
    ) -> None:
        self._gateway = gateway
        self._clock = clock

    def recognize(
        self,
        image_bytes: bytes,
        content_type: str | None,
        request_date: date,
        deadline: float,
    ) -> RecognitionResultDto:
        validate_jpeg(image_bytes, content_type)

        correction: str | None = None
        for attempt in range(2):
            try:
                raw_output = self._gateway.emit_recognition(
                    image_bytes=image_bytes,
                    deadline=deadline,
                    correction=correction,
                )
                output = RecognitionToolOutput.model_validate(raw_output)
                return normalize_recognition(output, request_date)
            except BedrockTimeoutError as error:
                raise AppError(
                    504,
                    "LLM_TIMEOUT",
                    "이미지 인식 시간이 초과되었어요. 다시 시도해 주세요.",
                    True,
                ) from error
            except BedrockGatewayError as error:
                if not isinstance(error, BedrockInvalidOutputError):
                    raise AppError(
                        502,
                        "RECOGNITION_FAILED",
                        "이미지를 인식하지 못했어요. 다시 시도해 주세요.",
                        True,
                    ) from error
                validation_error: Exception = error
            except ValidationError as error:
                validation_error = error

            remaining = deadline - self._clock()
            if attempt == 0 and remaining >= 8:
                correction = _correction_reason(validation_error)
                continue
            raise AppError(
                502,
                "INVALID_MODEL_OUTPUT",
                "인식 결과를 확인할 수 없어요. 다시 시도해 주세요.",
                True,
            ) from validation_error

        raise AssertionError("인식 교정 횟수를 초과했습니다.")


def validate_jpeg(image_bytes: bytes, content_type: str | None) -> None:
    """Bedrock 호출 전에 JPEG MIME, signature와 실제 크기를 검증합니다."""
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type != JPEG_CONTENT_TYPE:
        raise AppError(400, "INVALID_IMAGE", "JPEG 사진만 인식할 수 있어요.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise AppError(400, "INVALID_IMAGE", "사진 크기는 3.75MB 이하여야 해요.")
    if len(image_bytes) < 3 or image_bytes[:3] != b"\xff\xd8\xff":
        raise AppError(400, "INVALID_IMAGE", "올바른 JPEG 사진이 아니에요.")


def normalize_recognition(
    output: RecognitionToolOutput, request_date: date
) -> RecognitionResultDto:
    """도구 결과를 필터링하고 소비기한을 채운 API 결과로 변환합니다."""
    purchase_date = output.purchase_date or request_date
    source = "detected" if output.purchase_date else "request_date"
    items: list[InventoryItemDto] = []

    for raw_item in output.items:
        normalized_name = normalize_order_item_name(raw_item.name)
        if (
            not raw_item.is_food
            or raw_item.is_basic_seasoning
            or normalized_name in BASIC_SEASONINGS
        ):
            continue

        if raw_item.detected_expiration_date is not None:
            expiration_date = raw_item.detected_expiration_date
            expiration_estimated = False
        else:
            days = SHELF_LIFE_DAYS.get(normalized_name, {}).get(
                raw_item.storage_location,
                DEFAULT_SHELF_LIFE_DAYS[raw_item.storage_location],
            )
            expiration_date, expiration_estimated = estimate_expiration_date(
                request_date=request_date,
                shelf_life_days=days,
                detected_purchase_date=output.purchase_date,
            )

        items.append(
            InventoryItemDto(
                id=uuid4(),
                name=normalized_name,
                quantity=raw_item.quantity_half_units / 2,
                storage_location=raw_item.storage_location,
                expiration_date=expiration_date,
                expiration_estimated=expiration_estimated,
            )
        )

    return RecognitionResultDto(
        purchase_date=purchase_date,
        purchase_date_source=source,
        items=items,
    )


def _correction_reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        return "유효하지 않은 필드: " + ", ".join(fields[:8])
    return "emit_recognition 도구 입력이 없거나 형식이 잘못됨"
