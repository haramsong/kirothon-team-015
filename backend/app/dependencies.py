from typing import Annotated
from uuid import UUID

from fastapi import Header

from app.errors import AppError


DeviceIdHeader = Annotated[str | None, Header(alias="X-Device-Id")]


def require_device_id(x_device_id: DeviceIdHeader = None) -> UUID:
    """필수 기기 헤더가 RFC 4122 UUID v4인지 검증합니다."""
    if not x_device_id or not x_device_id.strip():
        raise AppError(
            status_code=400,
            code="INVALID_DEVICE_ID",
            message="기기 식별자가 필요해요.",
        )

    try:
        device_id = UUID(x_device_id)
    except (ValueError, AttributeError) as error:
        raise AppError(
            status_code=400,
            code="INVALID_DEVICE_ID",
            message="기기 식별자 형식이 올바르지 않아요.",
        ) from error

    if device_id.version != 4 or str(device_id).lower() != x_device_id.lower():
        raise AppError(
            status_code=400,
            code="INVALID_DEVICE_ID",
            message="기기 식별자 형식이 올바르지 않아요.",
        )

    return device_id


def inventory_partition_key(device_id: UUID) -> str:
    return f"DEVICE#{device_id}"
