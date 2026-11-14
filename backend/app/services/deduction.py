from datetime import date, datetime, timezone
from uuid import UUID

from app.errors import AppError
from app.logic.deduction import DeductionLine, apply_deduction, canonical_payload_hash
from app.logic.inventory import sort_inventory_items
from app.models import DeductionResultDto, InventoryDto, InventoryItemDto
from app.repositories.dynamodb_inventory import (
    DeductionRecord,
    DeductionRepository,
    DeductionTransactionConflictError,
    InventoryDocument,
    InventoryStorageError,
)


class DeductionService:
    def __init__(self, repository: DeductionRepository) -> None:
        self._repository = repository

    def deduct(
        self,
        device_id: UUID,
        request_id: UUID,
        lines: list[DeductionLine],
        today: date,
    ) -> DeductionResultDto:
        payload_hash = canonical_payload_hash(lines)
        existing = self._get_record(device_id, request_id)
        if existing is not None:
            return self._existing_result(device_id, payload_hash, existing, today)

        current = self._get_inventory(device_id)
        try:
            updated_items, removed_names = apply_deduction(current.items, lines)
        except ValueError as error:
            raise AppError(400, "VALIDATION_ERROR", str(error)) from error

        record = DeductionRecord(
            request_id=request_id,
            payload_hash=payload_hash,
            deducted_count=len(lines),
            removed_names=removed_names,
            result_version=current.version + 1,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        try:
            saved = self._repository.transact_deduction(
                device_id,
                current.version,
                updated_items,
                record,
            )
        except DeductionTransactionConflictError:
            raced_record = self._get_record(device_id, request_id)
            if raced_record is not None:
                return self._existing_result(
                    device_id, payload_hash, raced_record, today
                )
            raise AppError(
                409,
                "INVENTORY_CONFLICT",
                "재고가 변경되었어요. 최신 목록을 확인해 주세요.",
                True,
            )
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "재고를 차감하지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

        return self._to_result(saved, record, today)

    def _existing_result(
        self,
        device_id: UUID,
        payload_hash: str,
        record: DeductionRecord,
        today: date,
    ) -> DeductionResultDto:
        if record.payload_hash != payload_hash:
            raise AppError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "이미 다른 차감 요청에 사용한 요청 ID예요.",
            )
        return self._to_result(self._get_inventory(device_id), record, today)

    def _get_inventory(self, device_id: UUID) -> InventoryDocument:
        try:
            return self._repository.get(device_id)
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "재고를 불러오지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

    def _get_record(
        self, device_id: UUID, request_id: UUID
    ) -> DeductionRecord | None:
        try:
            return self._repository.get_deduction(device_id, request_id)
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "차감 기록을 확인하지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

    @staticmethod
    def _to_result(
        document: InventoryDocument,
        record: DeductionRecord,
        today: date,
    ) -> DeductionResultDto:
        inventory = InventoryDto(
            version=document.version,
            items=[
                InventoryItemDto(
                    id=item.id,
                    name=item.name,
                    quantity=item.quantity_half_units / 2,
                    storage_location=item.storage_location,
                    expiration_date=item.expiration_date,
                    expiration_estimated=item.expiration_estimated,
                )
                for item in sort_inventory_items(document.items, today)
            ],
        )
        return DeductionResultDto(
            inventory=inventory,
            deducted_count=record.deducted_count,
            removed_names=record.removed_names,
        )
