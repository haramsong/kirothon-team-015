from datetime import date
from uuid import UUID

from app.errors import AppError
from app.logic.inventory import MAX_INVENTORY_ITEMS, merge_inventory_items, sort_inventory_items
from app.models import InventoryItemDto, InventoryDto, InternalInventoryItem
from app.repositories.dynamodb_inventory import (
    InventoryConflictError,
    InventoryDocument,
    InventoryRepository,
    InventoryStorageError,
)


class InventoryService:
    def __init__(self, repository: InventoryRepository) -> None:
        self._repository = repository

    def get_inventory(self, device_id: UUID, today: date) -> InventoryDto:
        document = self._get(device_id)
        return self._to_dto(document, today)

    def add_items(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
        today: date,
    ) -> tuple[InventoryDto, int]:
        if not items:
            raise AppError(400, "VALIDATION_ERROR", "한 개 이상의 품목이 필요해요.")
        current = self._get(device_id)
        self._ensure_version(current, expected_version)
        try:
            merged = merge_inventory_items(current.items, items)
        except ValueError as error:
            raise AppError(400, "VALIDATION_ERROR", str(error)) from error
        saved = self._replace(device_id, expected_version, merged)
        return self._to_dto(saved, today), len(items)

    def update_item(
        self,
        device_id: UUID,
        item_id: UUID,
        expected_version: int,
        item: InternalInventoryItem | None,
        today: date,
    ) -> InventoryDto:
        current = self._get(device_id)
        self._ensure_version(current, expected_version)
        index = next(
            (i for i, current_item in enumerate(current.items) if current_item.id == item_id),
            None,
        )
        if index is None:
            raise AppError(404, "ITEM_NOT_FOUND", "재고 품목을 찾을 수 없어요.")

        updated = [current_item.model_copy(deep=True) for current_item in current.items]
        if item is None:
            updated.pop(index)
        else:
            duplicate_name = any(
                current_item.id != item_id and current_item.name == item.name
                for current_item in updated
            )
            if duplicate_name:
                raise AppError(400, "VALIDATION_ERROR", "같은 이름의 재고 품목이 이미 있어요.")
            updated[index] = item.model_copy(update={"id": item_id})
        saved = self._replace(device_id, expected_version, updated)
        return self._to_dto(saved, today)

    def delete_item(
        self, device_id: UUID, item_id: UUID, expected_version: int, today: date
    ) -> InventoryDto:
        return self.update_item(device_id, item_id, expected_version, None, today)

    def _get(self, device_id: UUID) -> InventoryDocument:
        try:
            return self._repository.get(device_id)
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "재고를 불러오지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

    def _replace(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
    ) -> InventoryDocument:
        if len(items) > MAX_INVENTORY_ITEMS:
            raise AppError(400, "VALIDATION_ERROR", "재고 품목은 최대 200개까지 저장할 수 있어요.")
        try:
            return self._repository.replace(device_id, expected_version, items)
        except InventoryConflictError as error:
            raise AppError(
                409,
                "INVENTORY_CONFLICT",
                "재고가 변경되었어요. 최신 목록을 확인해 주세요.",
                True,
            ) from error
        except InventoryStorageError as error:
            raise AppError(
                500,
                "STORAGE_ERROR",
                "재고를 저장하지 못했어요. 다시 시도해 주세요.",
                True,
            ) from error

    @staticmethod
    def _ensure_version(document: InventoryDocument, expected_version: int) -> None:
        if document.version != expected_version:
            raise AppError(
                409,
                "INVENTORY_CONFLICT",
                "재고가 변경되었어요. 최신 목록을 확인해 주세요.",
                True,
            )

    @staticmethod
    def _to_dto(document: InventoryDocument, today: date) -> InventoryDto:
        return InventoryDto(
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
