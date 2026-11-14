from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from app.dependencies import inventory_partition_key
from app.models import InternalInventoryItem, StorageLocation

INVENTORY_SORT_KEY = "INVENTORY"


class InventoryConflictError(Exception):
    """재고 버전이 예상 버전과 다를 때 발생합니다."""


class InventoryStorageError(Exception):
    """재고 저장소 접근이 실패했을 때 발생합니다."""


@dataclass(frozen=True)
class InventoryDocument:
    version: int
    items: list[InternalInventoryItem]


class InventoryRepository(Protocol):
    def get(self, device_id: UUID) -> InventoryDocument: ...

    def replace(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
    ) -> InventoryDocument: ...


class DynamoInventoryRepository:
    """기기별 전체 재고 문서를 DynamoDB에서 조건부 교체합니다."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def get(self, device_id: UUID) -> InventoryDocument:
        try:
            response = self._table.get_item(
                Key={
                    "pk": inventory_partition_key(device_id),
                    "sk": INVENTORY_SORT_KEY,
                },
                ConsistentRead=True,
            )
        except Exception as error:
            raise InventoryStorageError from error

        stored = response.get("Item")
        if stored is None:
            return InventoryDocument(version=0, items=[])
        try:
            return InventoryDocument(
                version=int(stored["version"]),
                items=[self._deserialize_item(item) for item in stored.get("items", [])],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise InventoryStorageError from error

    def replace(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
    ) -> InventoryDocument:
        next_document = InventoryDocument(version=expected_version + 1, items=items)
        stored_item = {
            "pk": inventory_partition_key(device_id),
            "sk": INVENTORY_SORT_KEY,
            "version": next_document.version,
            "items": [self._serialize_item(item) for item in items],
        }
        try:
            self._table.put_item(
                Item=stored_item,
                ConditionExpression="attribute_not_exists(pk) OR #version = :expected",
                ExpressionAttributeNames={"#version": "version"},
                ExpressionAttributeValues={":expected": expected_version},
            )
        except Exception as error:
            error_code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                raise InventoryConflictError from error
            raise InventoryStorageError from error
        return next_document

    @staticmethod
    def _serialize_item(item: InternalInventoryItem) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "name": item.name,
            "quantityHalfUnits": item.quantity_half_units,
            "storageLocation": item.storage_location.value,
            "expirationDate": item.expiration_date.isoformat(),
            "expirationEstimated": item.expiration_estimated,
        }

    @staticmethod
    def _deserialize_item(item: dict[str, Any]) -> InternalInventoryItem:
        return InternalInventoryItem(
            id=UUID(item["id"]),
            name=item["name"],
            quantity_half_units=int(item["quantityHalfUnits"]),
            storage_location=StorageLocation(item["storageLocation"]),
            expiration_date=date.fromisoformat(item["expirationDate"]),
            expiration_estimated=bool(item["expirationEstimated"]),
        )


def create_dynamo_inventory_repository(table_name: str) -> DynamoInventoryRepository:
    """Lambda 런타임의 boto3 리소스로 DynamoDB 저장소를 생성합니다."""
    import boto3

    table = boto3.resource("dynamodb").Table(table_name)
    return DynamoInventoryRepository(table)
