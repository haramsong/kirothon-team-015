import json
import logging
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.errors import AppError
from app.models import ErrorBody, ErrorEnvelope, SuccessEnvelope

logger = logging.getLogger(__name__)


def request_id_for(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def success_response(request: Request, data: Any, status_code: int = 200) -> JSONResponse:
    envelope = SuccessEnvelope[Any](data=data, request_id=request_id_for(request))
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def error_response(request: Request, error: AppError) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
        ),
        request_id=request_id_for(request),
    )
    return JSONResponse(
        status_code=error.status_code,
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def create_app(
    inventory_repository: Any | None = None,
    bedrock_gateway: Any | None = None,
) -> FastAPI:
    application = FastAPI(
        title="나만의 냉장고 API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    settings = get_settings()
    application.state.inventory_repository = inventory_repository
    application.state.inventory_table_name = settings.table_name
    application.state.bedrock_gateway = bedrock_gateway
    application.state.model_id = settings.model_id
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Device-Id"],
    )

    @application.middleware("http")
    async def request_boundary(request: Request, call_next: Any) -> Any:
        request.state.request_id = str(uuid4())
        started_at = time.monotonic()
        request.state.deadline = started_at + 27
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        logger.info(
            json.dumps(
                {
                    "requestId": request.state.request_id,
                    "route": request.url.path,
                    "durationMs": round((time.monotonic() - started_at) * 1000),
                    "status": response.status_code,
                },
                ensure_ascii=False,
            )
        )
        return response

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return error_response(request, error)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            request,
            AppError(
                status_code=400,
                code="VALIDATION_ERROR",
                message="요청 값을 확인해 주세요.",
            ),
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        if error.status_code == 404:
            mapped = AppError(404, "NOT_FOUND", "요청한 경로를 찾을 수 없어요.")
        elif error.status_code >= 500:
            mapped = AppError(
                500,
                "INTERNAL_ERROR",
                "요청을 처리하지 못했어요. 다시 시도해 주세요.",
                True,
            )
        else:
            mapped = AppError(
                error.status_code,
                "REQUEST_ERROR",
                "요청을 처리할 수 없어요.",
            )
        return error_response(request, mapped)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, _error: Exception
    ) -> JSONResponse:
        logger.exception(
            json.dumps(
                {
                    "requestId": request_id_for(request),
                    "route": request.url.path,
                    "code": "INTERNAL_ERROR",
                },
                ensure_ascii=False,
            )
        )
        return error_response(
            request,
            AppError(
                status_code=500,
                code="INTERNAL_ERROR",
                message="요청을 처리하지 못했어요. 다시 시도해 주세요.",
                retryable=True,
            ),
        )

    @application.get("/api/health", tags=["system"])
    def health(request: Request) -> JSONResponse:
        """애플리케이션 프로세스의 준비 상태를 반환합니다."""
        return success_response(request, {"status": "ok"})

    from app.routes.deduction import router as deduction_router
    from app.routes.inventory import router as inventory_router
    from app.routes.recognition import router as recognition_router
    from app.routes.recommendation import router as recommendation_router

    application.include_router(inventory_router)
    application.include_router(recognition_router)
    application.include_router(recommendation_router)
    application.include_router(deduction_router)
    return application


app = create_app()
