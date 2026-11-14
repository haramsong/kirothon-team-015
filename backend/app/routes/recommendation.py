import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.dependencies import require_device_id
from app.gateways.bedrock import BedrockGateway
from app.main import success_response
from app.models import RecommendationRequest, RecipeRequest
from app.repositories.dynamodb_inventory import InventoryRepository
from app.routes.inventory import get_inventory_repository
from app.routes.recognition import get_bedrock_gateway
from app.services.recommendation import RecommendationService

router = APIRouter(prefix="/api", tags=["recommendation"])


def get_recommendation_service(
    repository: Annotated[InventoryRepository, Depends(get_inventory_repository)],
    gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
) -> RecommendationService:
    return RecommendationService(repository, gateway)


@router.post("/recommendations")
def create_recommendation(
    body: RecommendationRequest,
    request: Request,
    device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> JSONResponse:
    result = service.recommend(
        device_id=device_id,
        client_date=body.client_date,
        excluded_menu_name=body.excluded_menu_name,
        deadline=getattr(request.state, "deadline", time.monotonic() + 27),
    )
    return success_response(request, result)


@router.post("/recipes")
def create_recipe(
    body: RecipeRequest,
    request: Request,
    _device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[RecommendationService, Depends(get_recommendation_service)],
) -> JSONResponse:
    result = service.create_recipe(
        recommendation=body.recommendation,
        deadline=getattr(request.state, "deadline", time.monotonic() + 27),
    )
    return success_response(request, result)
