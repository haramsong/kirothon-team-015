import math
import time
from collections.abc import Callable
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ConnectTimeoutError, ReadTimeoutError

RECOGNITION_TOOL_NAME = "emit_recognition"
RECOGNITION_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "purchase_date": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "maxItems": 200,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 80},
                    "quantity_half_units": {"type": "integer", "minimum": 1},
                    "storage_location": {
                        "type": "string",
                        "enum": ["냉장", "냉동", "실온"],
                    },
                    "detected_expiration_date": {"type": ["string", "null"]},
                    "is_food": {"type": "boolean"},
                    "is_basic_seasoning": {"type": "boolean"},
                },
                "required": [
                    "name",
                    "quantity_half_units",
                    "storage_location",
                    "detected_expiration_date",
                    "is_food",
                    "is_basic_seasoning",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["purchase_date", "items"],
    "additionalProperties": False,
}


class BedrockRuntimeClient(Protocol):
    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


class BedrockGatewayError(Exception):
    """Bedrock 호출 또는 응답 추출 실패입니다."""


class BedrockTimeoutError(BedrockGatewayError):
    """Bedrock 호출 시간이 요청 기한을 초과했습니다."""


class BedrockInvalidOutputError(BedrockGatewayError):
    """응답에 강제한 도구 입력이 없습니다."""


ClientFactory = Callable[[Config], BedrockRuntimeClient]


class BedrockGateway:
    def __init__(
        self,
        model_id: str,
        client: BedrockRuntimeClient | None = None,
        client_factory: ClientFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model_id = model_id
        self._client = client
        self._client_factory = client_factory or self._default_client_factory
        self._clock = clock

    def emit_recognition(
        self,
        image_bytes: bytes,
        deadline: float,
        correction: str | None = None,
    ) -> dict[str, Any]:
        """이미지에서 strict 도구 입력을 생성하고 원시 입력을 반환합니다."""
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise BedrockTimeoutError("인식 요청 기한이 지났습니다.")

        prompt = (
            "이 이미지는 마트 영수증 또는 온라인 주문내역입니다. 식품만 추출하고 "
            "수량은 0.5개를 1로 하는 quantity_half_units 정수로 변환하세요. "
            "소금, 설탕, 간장, 식용유, 후추, 참기름, 식초, 고춧가루는 기본 양념으로 표시하세요. "
            "이미지에 구매일이나 소비기한이 명시되지 않았다면 null을 사용하세요."
        )
        if correction:
            prompt += f"\n이전 결과를 다음 이유로 사용할 수 없습니다. 스키마와 의미를 고쳐 다시 생성하세요: {correction}"

        client = self._client or self._client_factory(self._timeout_config(remaining))
        try:
            response = client.converse(
                modelId=self._model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt},
                            {"image": {"format": "jpeg", "source": {"bytes": image_bytes}}},
                        ],
                    }
                ],
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": RECOGNITION_TOOL_NAME,
                                "description": "장보기 이미지에서 식재료 정보를 추출합니다.",
                                "strict": True,
                                "inputSchema": {"json": RECOGNITION_TOOL_SCHEMA},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": RECOGNITION_TOOL_NAME}},
                },
                inferenceConfig={"maxTokens": 3000, "temperature": 0},
            )
        except (ReadTimeoutError, ConnectTimeoutError, TimeoutError) as error:
            raise BedrockTimeoutError("Bedrock 응답 시간이 초과되었습니다.") from error
        except (ClientError, BotoCoreError) as error:
            raise BedrockGatewayError("Bedrock 호출에 실패했습니다.") from error

        if self._clock() >= deadline:
            raise BedrockTimeoutError("인식 요청 기한을 초과했습니다.")
        return self._extract_tool_input(response)

    @staticmethod
    def _extract_tool_input(response: dict[str, Any]) -> dict[str, Any]:
        try:
            content = response["output"]["message"]["content"]
        except (KeyError, TypeError) as error:
            raise BedrockInvalidOutputError("Bedrock 응답에 메시지가 없습니다.") from error

        for block in content:
            tool_use = block.get("toolUse") if isinstance(block, dict) else None
            if (
                isinstance(tool_use, dict)
                and tool_use.get("name") == RECOGNITION_TOOL_NAME
                and isinstance(tool_use.get("input"), dict)
            ):
                return tool_use["input"]
        raise BedrockInvalidOutputError("emit_recognition 도구 입력이 없습니다.")

    @staticmethod
    def _timeout_config(remaining: float) -> Config:
        read_timeout = max(1, min(22, math.floor(remaining)))
        return Config(
            connect_timeout=2,
            read_timeout=read_timeout,
            retries={"max_attempts": 0, "mode": "standard"},
        )

    @staticmethod
    def _default_client_factory(config: Config) -> BedrockRuntimeClient:
        return boto3.client("bedrock-runtime", config=config)
