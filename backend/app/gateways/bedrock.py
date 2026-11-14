import json
import logging
import math
import time
from collections.abc import Callable
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ConnectTimeoutError, ReadTimeoutError

RECOGNITION_TOOL_NAME = "emit_recognition"
RECOMMENDATION_TOOL_NAME = "emit_recommendation"
RECIPE_TOOL_NAME = "emit_recipe"
MEAL_PLAN_TOOL_NAME = "emit_meal_plan"

logger = logging.getLogger(__name__)

# "반드시 포함"을 메뉴 이름에 재료명을 붙이라는 뜻으로 받아들여 "계란 계란말이" 같은 이름이 나오지 않게 한다.
# 재고 목록 뒤, 프롬프트 끝에 붙여야 효과가 있었다(중간에 넣으면 같은 메뉴가 반복됐다).
MENU_NAME_RULE = (
    " 반드시 포함해야 하는 품목은 ingredients에 넣으세요. menu_name은 실제 요리 이름만 쓰고, "
    "재료 이름을 앞에 덧붙이거나 같은 단어를 반복하지 마세요(좋은 예: 계란말이, 대파계란국, 양파볶음 / "
    "나쁜 예: 계란 계란말이, 계란계란국). 여러 끼니를 만들 때는 메뉴 이름이 서로 겹치지 않게 하세요."
)

# Bedrock strict tool use는 JSON Schema 일부만 지원한다. minLength, maxLength, minimum, maxItems,
# 1보다 큰 minItems를 넣으면 ValidationException으로 요청 자체가 거절된다.
# 길이, 개수, 최솟값 제약은 응답을 받은 뒤 서비스의 Pydantic 모델로 검증한다.
# https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html
RECOGNITION_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "purchase_date": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity_half_units": {"type": "integer"},
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

RECOMMENDATION_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "menu_name": {"type": "string"},
        "ingredients": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "use_half_units": {"type": "integer"},
                },
                "required": ["item_id", "use_half_units"],
                "additionalProperties": False,
            },
        },
        "seasonings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["menu_name", "ingredients", "seasonings"],
    "additionalProperties": False,
}

RECIPE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ingredient_names": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
    },
    "required": ["ingredient_names", "steps"],
    "additionalProperties": False,
}

MEAL_PLAN_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "meals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day": {"type": "integer", "enum": [1, 2, 3]},
                    "slot": {"type": "string", "enum": ["점심", "저녁"]},
                    "menu_name": {
                        "type": "string",
                    },
                    "ingredients": RECOMMENDATION_TOOL_SCHEMA["properties"][
                        "ingredients"
                    ],
                    "seasonings": RECOMMENDATION_TOOL_SCHEMA["properties"][
                        "seasonings"
                    ],
                },
                "required": [
                    "day",
                    "slot",
                    "menu_name",
                    "ingredients",
                    "seasonings",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["meals"],
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
        prompt = (
            "이 이미지는 마트 영수증 또는 온라인 주문내역입니다. 두 이미지 유형을 같은 형식으로 처리하세요. "
            "식품만 추출하고 상품명에서는 브랜드, 원산지, 옵션, 중량, 묶음 표기를 제거해 일반 품목명만 반환하세요. "
            "옵션 수량과 묶음 수량을 모두 반영하고 kg, g, L, mL는 일반 판매 단위의 개수로 환산한 뒤 "
            "최종 수량을 0.5개를 1로 하는 quantity_half_units 정수로 변환하세요. "
            "예를 들어 양파 1.5kg 2망이 망당 약 8개라면 quantity_half_units는 32이고 name은 양파입니다. "
            "소금, 설탕, 간장, 식용유, 후추, 참기름, 식초, 고춧가루는 기본 양념으로 표시하세요. "
            "이미지에 구매일이나 소비기한이 명시되지 않았다면 null을 사용하세요."
        )
        if correction:
            prompt += self._correction_prompt(correction)

        return self._converse_with_tool(
            deadline=deadline,
            tool_name=RECOGNITION_TOOL_NAME,
            tool_description="장보기 이미지에서 식재료 정보를 추출합니다.",
            tool_schema=RECOGNITION_TOOL_SCHEMA,
            content=[
                {"text": prompt},
                {"image": {"format": "jpeg", "source": {"bytes": image_bytes}}},
            ],
            max_tokens=3000,
        )

    def emit_recommendation(
        self,
        inventory_context: list[dict[str, Any]],
        priority_item_id: str,
        deadline: float,
        excluded_menu_name: str | None = None,
        correction: str | None = None,
    ) -> dict[str, Any]:
        """사용 가능한 재고로 한 끼 추천 도구 입력을 생성합니다."""
        prompt = (
            "다음 재고만 사용해 1인분 메뉴 하나를 추천하세요. "
            "priority_item_id 품목을 반드시 포함하고 각 사용량은 0.5개를 1로 하는 "
            "use_half_units 정수로 반환하세요. 재고 수량을 넘기지 마세요. "
            "양념은 소금, 설탕, 간장, 식용유, 후추, 참기름, 식초, 고춧가루만 허용됩니다.\n"
            f"priority_item_id: {priority_item_id}\n"
            f"사용 가능한 재고: {json.dumps(inventory_context, ensure_ascii=False)}"
            f"{MENU_NAME_RULE}"
        )
        if excluded_menu_name:
            prompt += f"\n직전 메뉴와 다른 이름을 사용하세요. 직전 메뉴: {excluded_menu_name}"
        if correction:
            prompt += self._correction_prompt(correction)

        return self._converse_with_tool(
            deadline=deadline,
            tool_name=RECOMMENDATION_TOOL_NAME,
            tool_description="현재 재고로 만들 한 끼 메뉴와 예상 사용량을 생성합니다.",
            tool_schema=RECOMMENDATION_TOOL_SCHEMA,
            content=[{"text": prompt}],
            max_tokens=1800,
        )

    def emit_recipe(
        self,
        recommendation_context: dict[str, Any],
        deadline: float,
        correction: str | None = None,
    ) -> dict[str, Any]:
        """승인된 추천 메뉴의 조리 단계를 별도 도구 호출로 생성합니다."""
        prompt = (
            "다음 1인분 추천 메뉴의 조리 순서를 1~8단계로 작성하세요. "
            "ingredient_names에는 실제 조리 단계에서 언급한 재료 이름을 모두 넣으세요. "
            "추천 재료와 기본 양념(소금, 설탕, 간장, 식용유, 후추, 참기름, 식초, 고춧가루) "
            "외의 재료는 사용하지 마세요.\n"
            f"추천 메뉴: {json.dumps(recommendation_context, ensure_ascii=False)}"
        )
        if correction:
            prompt += self._correction_prompt(correction)

        return self._converse_with_tool(
            deadline=deadline,
            tool_name=RECIPE_TOOL_NAME,
            tool_description="추천 메뉴에 허용된 재료만 사용하는 조리 단계를 생성합니다.",
            tool_schema=RECIPE_TOOL_SCHEMA,
            content=[{"text": prompt}],
            max_tokens=1800,
        )

    def emit_meal_plan(
        self,
        inventory_context: list[dict[str, Any]],
        client_date: str,
        deadline: float,
        correction: str | None = None,
    ) -> dict[str, Any]:
        """현재 재고의 예상 잔여량을 순차 반영한 3일 식단을 생성합니다."""
        prompt = (
            "다음 재고만 사용해 3일 동안 매일 점심과 저녁, 정확히 6개 끼니를 "
            "(1,점심), (1,저녁), (2,점심), (2,저녁), (3,점심), (3,저녁) 순서로 생성하세요. "
            "각 끼니 직전까지 사용한 수량을 재고에서 빼고, 남은 재고 중 기준일로부터 0~3일 안에 "
            "소비기한이 오는 가장 이른 품목을 반드시 포함하세요. 그런 품목이 없으면 남은 품목 중 "
            "소비기한이 가장 이른 품목을 반드시 포함하세요. 전체 사용량은 최초 재고 수량을 넘길 수 없고, "
            "각 사용량은 0.5개를 1로 하는 use_half_units 정수입니다. 양념은 소금, 설탕, 간장, "
            "식용유, 후추, 참기름, 식초, 고춧가루만 허용됩니다.\n"
            f"기준일: {client_date}\n"
            f"사용 가능한 재고: {json.dumps(inventory_context, ensure_ascii=False)}"
            f"{MENU_NAME_RULE}"
        )
        if correction:
            prompt += self._correction_prompt(correction)

        return self._converse_with_tool(
            deadline=deadline,
            tool_name=MEAL_PLAN_TOOL_NAME,
            tool_description="현재 재고를 순서대로 소비하는 3일 6끼 식단을 생성합니다.",
            tool_schema=MEAL_PLAN_TOOL_SCHEMA,
            content=[{"text": prompt}],
            max_tokens=5000,
        )

    def _converse_with_tool(
        self,
        *,
        deadline: float,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any],
        content: list[dict[str, Any]],
        max_tokens: int,
    ) -> dict[str, Any]:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise BedrockTimeoutError("요청 기한이 지났습니다.")

        client = self._client or self._client_factory(self._timeout_config(remaining))
        try:
            response = client.converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": content}],
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": tool_name,
                                "description": tool_description,
                                "strict": True,
                                "inputSchema": {"json": tool_schema},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": tool_name}},
                },
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
            )
        except (ReadTimeoutError, ConnectTimeoutError, TimeoutError) as error:
            raise BedrockTimeoutError("Bedrock 응답 시간이 초과되었습니다.") from error
        except ClientError as error:
            # 원인이 응답에 드러나지 않으므로 Bedrock 오류 코드와 메시지를 로그로 남긴다.
            details = error.response.get("Error", {})
            logger.warning(
                "Bedrock %s 호출 실패: %s %s",
                tool_name,
                details.get("Code"),
                details.get("Message"),
            )
            raise BedrockGatewayError("Bedrock 호출에 실패했습니다.") from error
        except BotoCoreError as error:
            logger.warning("Bedrock %s 호출 실패: %s", tool_name, type(error).__name__)
            raise BedrockGatewayError("Bedrock 호출에 실패했습니다.") from error

        if self._clock() >= deadline:
            raise BedrockTimeoutError("요청 기한을 초과했습니다.")
        return self._extract_tool_input(response, tool_name)

    @staticmethod
    def _extract_tool_input(
        response: dict[str, Any], tool_name: str
    ) -> dict[str, Any]:
        try:
            content = response["output"]["message"]["content"]
        except (KeyError, TypeError) as error:
            raise BedrockInvalidOutputError("Bedrock 응답에 메시지가 없습니다.") from error

        for block in content:
            tool_use = block.get("toolUse") if isinstance(block, dict) else None
            if (
                isinstance(tool_use, dict)
                and tool_use.get("name") == tool_name
                and isinstance(tool_use.get("input"), dict)
            ):
                return tool_use["input"]
        raise BedrockInvalidOutputError(f"{tool_name} 도구 입력이 없습니다.")

    @staticmethod
    def _correction_prompt(correction: str) -> str:
        return (
            "\n이전 결과를 다음 이유로 사용할 수 없습니다. "
            f"스키마와 의미를 고쳐 다시 생성하세요: {correction}"
        )

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
