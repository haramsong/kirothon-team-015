import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.dependencies import require_device_id
from app.gateways.bedrock import BedrockGateway
from app.main import success_response
from app.models import MealPlanRequest
from app.repositories.dynamodb_inventory import InventoryRepository
from app.routes.inventory import get_inventory_repository
from app.routes.recognition import get_bedrock_gateway
from app.services.meal_plan import MealPlanService

router = APIRouter(prefix="/api", tags=["meal-plan"])


def get_meal_plan_service(
    repository: Annotated[InventoryRepository, Depends(get_inventory_repository)],
    gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
) -> MealPlanService:
    return MealPlanService(repository, gateway)


@router.post("/meal-plans")
def create_meal_plan(
    body: MealPlanRequest,
    request: Request,
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[MealPlanService, Depends(get_meal_plan_service)],
) -> JSONResponse:
    result = service.create(
        device_id=device_id,
        client_date=body.client_date,
        deadline=getattr(request.state, "deadline", time.monotonic() + 27),
    )
    return success_response(request, result)
