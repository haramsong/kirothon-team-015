from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from boto3.dynamodb.types import TypeSerializer

from app.dependencies import inventory_partition_key
from app.models import InternalInventoryItem, StorageLocation

INVENTORY_SORT_KEY = "INVENTORY"


class InventoryConflictError(Exception):
    """재고 버전이 예상 버전과 다를 때 발생합니다."""


class InventoryStorageError(Exception):
    """재고 저장소 접근이 실패했을 때 발생합니다."""


class DeductionTransactionConflictError(Exception):
    """차감 트랜잭션의 조건부 쓰기가 경합으로 취소될 때 발생합니다."""


@dataclass(frozen=True)
class InventoryDocument:
    version: int
    items: list[InternalInventoryItem]


@dataclass(frozen=True)
class DeductionRecord:
    request_id: UUID
    payload_hash: str
    deducted_count: int
    removed_names: list[str]
    result_version: int
    created_at: str


class InventoryRepository(Protocol):
    def get(self, device_id: UUID) -> InventoryDocument: ...

    def replace(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
    ) -> InventoryDocument: ...


class DeductionRepository(InventoryRepository, Protocol):
    def get_deduction(
        self, device_id: UUID, request_id: UUID
    ) -> DeductionRecord | None: ...

    def transact_deduction(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
        record: DeductionRecord,
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

    def get_deduction(
        self, device_id: UUID, request_id: UUID
    ) -> DeductionRecord | None:
        try:
            response = self._table.get_item(
                Key={
                    "pk": inventory_partition_key(device_id),
                    "sk": f"DEDUCTION#{request_id}",
                },
                ConsistentRead=True,
            )
        except Exception as error:
            raise InventoryStorageError from error

        stored = response.get("Item")
        if stored is None:
            return None
        try:
            return DeductionRecord(
                request_id=request_id,
                payload_hash=stored["payloadHash"],
                deducted_count=int(stored["deductedCount"]),
                removed_names=list(stored.get("removedNames", [])),
                result_version=int(stored["resultVersion"]),
                created_at=stored["createdAt"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise InventoryStorageError from error

    def transact_deduction(
        self,
        device_id: UUID,
        expected_version: int,
        items: list[InternalInventoryItem],
        record: DeductionRecord,
    ) -> InventoryDocument:
        next_document = InventoryDocument(version=expected_version + 1, items=items)
        partition_key = inventory_partition_key(device_id)
        inventory_item = {
            "pk": partition_key,
            "sk": INVENTORY_SORT_KEY,
            "version": next_document.version,
            "items": [self._serialize_item(item) for item in items],
        }
        deduction_item = {
            "pk": partition_key,
            "sk": f"DEDUCTION#{record.request_id}",
            "payloadHash": record.payload_hash,
            "deductedCount": record.deducted_count,
            "removedNames": record.removed_names,
            "resultVersion": record.result_version,
            "createdAt": record.created_at,
        }
        serializer = TypeSerializer()

        try:
            self._table.meta.client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self._table.name,
                            "Item": self._serialize_document(inventory_item, serializer),
                            "ConditionExpression": (
                                "attribute_not_exists(pk) OR #version = :expected"
                            ),
                            "ExpressionAttributeNames": {"#version": "version"},
                            "ExpressionAttributeValues": {
                                ":expected": serializer.serialize(expected_version)
                            },
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._table.name,
                            "Item": self._serialize_document(deduction_item, serializer),
                            "ConditionExpression": "attribute_not_exists(pk)",
                        }
                    },
                ]
            )
        except Exception as error:
            error_code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if error_code in {
                "ConditionalCheckFailedException",
                "TransactionCanceledException",
            }:
                raise DeductionTransactionConflictError from error
            raise InventoryStorageError from error
        return next_document

    @staticmethod
    def _serialize_document(
        document: dict[str, Any], serializer: TypeSerializer
    ) -> dict[str, Any]:
        return {key: serializer.serialize(value) for key, value in document.items()}

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
