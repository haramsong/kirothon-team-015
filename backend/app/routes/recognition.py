import time
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.dependencies import require_device_id
from app.gateways.bedrock import BedrockGateway
from app.main import success_response
from app.services.recognition import RecognitionService

router = APIRouter(prefix="/api/recognitions", tags=["recognition"])


def get_bedrock_gateway(request: Request) -> BedrockGateway:
    gateway = request.app.state.bedrock_gateway
    if gateway is None:
        gateway = BedrockGateway(request.app.state.model_id)
        request.app.state.bedrock_gateway = gateway
    return gateway


def get_recognition_service(
    gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
) -> RecognitionService:
    return RecognitionService(gateway)


@router.post("")
async def recognize_shopping_image(
    request: Request,
    image: Annotated[UploadFile, File()],
    _device_id: Annotated[UUID, Depends(require_device_id)],
    service: Annotated[RecognitionService, Depends(get_recognition_service)],
) -> JSONResponse:
    image_bytes = await image.read()
    result = service.recognize(
        image_bytes=image_bytes,
        content_type=image.content_type,
        request_date=date.today(),
        deadline=getattr(request.state, "deadline", time.monotonic() + 27),
    )
    return success_response(request, result)
