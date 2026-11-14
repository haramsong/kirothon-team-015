from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.dependencies import require_device_id
from app.main import success_response
from app.models import (
    BatchInventoryRequest,
    InventoryItemUpdateRequest,
    InternalInventoryItem,
)
from app.repositories.dynamodb_inventory import (
    InventoryRepository,
    create_dynamo_inventory_repository,
)
from app.services.inventory import InventoryService

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def get_inventory_repository(request: Request) -> InventoryRepository:
    repository = request.app.state.inventory_repository
    if repository is None:
        repository = create_dynamo_inventory_repository(
            request.app.state.inventory_table_name
        )
        request.app.state.inventory_repository = repository
    return repository


def get_inventory_service(
    repository: Annotated[InventoryRepository, Depends(get_inventory_repository)],
) -> InventoryService:
    return InventoryService(repository)


@router.get("")
def get_inventory(
    request: Request,
    today: Annotated[date, Query()],
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> JSONResponse:
    return success_response(request, service.get_inventory(device_id, today))


@router.post("/items:batch")
def add_inventory_items(
    body: BatchInventoryRequest,
    request: Request,
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    today: Annotated[date | None, Query()] = None,
) -> JSONResponse:
    inventory, saved_count = service.add_items(
        device_id,
        body.expected_version,
        [item.to_internal() for item in body.items],
        today or date.today(),
    )
    return success_response(
        request,
        {"inventory": inventory.model_dump(mode="json", by_alias=True), "savedCount": saved_count},
    )


@router.put("/items/{item_id}")
def update_inventory_item(
    item_id: UUID,
    body: InventoryItemUpdateRequest,
    request: Request,
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    today: Annotated[date | None, Query()] = None,
) -> JSONResponse:
    internal = None
    if body.quantity > 0:
        internal = InternalInventoryItem(
            id=item_id,
            name=body.name,
            quantity_half_units=body.quantity_half_units(),
            storage_location=body.storage_location,
            expiration_date=body.expiration_date,
            expiration_estimated=body.expiration_estimated,
        )
    inventory = service.update_item(
        device_id, item_id, body.expected_version, internal, today or date.today()
    )
    return success_response(request, inventory)


@router.delete("/items/{item_id}")
def delete_inventory_item(
    item_id: UUID,
    request: Request,
    expected_version: Annotated[int, Query(alias="expectedVersion", ge=0)],
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    today: Annotated[date | None, Query()] = None,
) -> JSONResponse:
    inventory = service.delete_item(
        device_id, item_id, expected_version, today or date.today()
    )
    return success_response(request, inventory)
