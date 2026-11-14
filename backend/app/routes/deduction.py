from datetime import date
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.dependencies import require_device_id
from app.logic.deduction import DeductionLine
from app.main import success_response
from app.models import DeductionRequest
from app.repositories.dynamodb_inventory import DeductionRepository, InventoryRepository
from app.routes.inventory import get_inventory_repository
from app.services.deduction import DeductionService

router = APIRouter(prefix="/api/deductions", tags=["deduction"])


def get_deduction_service(
    repository: Annotated[InventoryRepository, Depends(get_inventory_repository)],
) -> DeductionService:
    return DeductionService(cast(DeductionRepository, repository))


@router.post("")
def deduct_inventory(
    body: DeductionRequest,
    request: Request,
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[DeductionService, Depends(get_deduction_service)],
    today: Annotated[date | None, Query()] = None,
) -> JSONResponse:
    result = service.deduct(
        device_id,
        body.deduction_request_id,
        [
            DeductionLine(
                item_id=item.item_id,
                use_half_units=item.use_half_units(),
            )
            for item in body.items
        ],
        today or date.today(),
    )
    return success_response(request, result)
