from app.gateways.bedrock import (
    MEAL_PLAN_TOOL_NAME,
    RECIPE_TOOL_NAME,
    RECOGNITION_TOOL_NAME,
    RECOMMENDATION_TOOL_NAME,
    BedrockGateway,
    BedrockInvalidOutputError,
)


class RecordingClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def converse(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return self.response


def tool_response(tool_input: dict) -> dict:
    return {
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "name": RECOGNITION_TOOL_NAME,
                            "toolUseId": "tool-1",
                            "input": tool_input,
                        }
                    }
                ]
            }
        }
    }


def test_emit_recognition_forces_strict_tool_and_returns_its_input() -> None:
    expected = {"purchase_date": None, "items": []}
    client = RecordingClient(tool_response(expected))
    gateway = BedrockGateway("test-model", client=client, clock=lambda: 10.0)

    actual = gateway.emit_recognition(b"\xff\xd8\xffdata", deadline=20.0)

    assert actual == expected
    call = client.calls[0]
    assert call["modelId"] == "test-model"
    tool_config = call["toolConfig"]
    tool_spec = tool_config["tools"][0]["toolSpec"]
    assert tool_spec["name"] == RECOGNITION_TOOL_NAME
    assert tool_spec["strict"] is True
    assert tool_spec["inputSchema"]["json"]["additionalProperties"] is False
    assert (
        tool_spec["inputSchema"]["json"]["properties"]["items"]["items"]
        ["additionalProperties"]
        is False
    )
    assert tool_config["toolChoice"] == {
        "tool": {"name": RECOGNITION_TOOL_NAME}
    }
    assert call["messages"][0]["content"][1]["image"]["format"] == "jpeg"
    prompt = call["messages"][0]["content"][0]["text"]
    assert "마트 영수증 또는 온라인 주문내역" in prompt
    assert "옵션 수량과 묶음 수량" in prompt
    assert "kg, g, L, mL" in prompt


def test_emit_recognition_rejects_response_without_forced_tool() -> None:
    client = RecordingClient(
        {"output": {"message": {"content": [{"text": "일반 텍스트"}]}}}
    )
    gateway = BedrockGateway("test-model", client=client, clock=lambda: 10.0)

    try:
        gateway.emit_recognition(b"\xff\xd8\xffdata", deadline=20.0)
    except BedrockInvalidOutputError:
        pass
    else:
        raise AssertionError("도구 입력이 없으면 예외가 필요합니다.")


def named_tool_response(tool_name: str, tool_input: dict) -> dict:
    return {
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "name": tool_name,
                            "toolUseId": "tool-2",
                            "input": tool_input,
                        }
                    }
                ]
            }
        }
    }


def test_emit_recommendation_forces_its_strict_tool_and_inventory_prompt() -> None:
    expected = {
        "menu_name": "양파 볶음",
        "ingredients": [{"item_id": "item-1", "use_half_units": 2}],
        "seasonings": ["간장"],
    }
    client = RecordingClient(named_tool_response(RECOMMENDATION_TOOL_NAME, expected))
    gateway = BedrockGateway("test-model", client=client, clock=lambda: 10.0)

    actual = gateway.emit_recommendation(
        inventory_context=[
            {
                "item_id": "item-1",
                "name": "양파",
                "quantity_half_units": 4,
                "expiration_date": "2026-04-12",
            }
        ],
        priority_item_id="item-1",
        excluded_menu_name="양파국",
        deadline=20.0,
    )

    assert actual == expected
    call = client.calls[0]
    tool_spec = call["toolConfig"]["tools"][0]["toolSpec"]
    assert tool_spec["name"] == RECOMMENDATION_TOOL_NAME
    assert tool_spec["strict"] is True
    assert tool_spec["inputSchema"]["json"]["additionalProperties"] is False
    assert (
        tool_spec["inputSchema"]["json"]["properties"]["ingredients"]["items"]
        ["additionalProperties"]
        is False
    )
    assert call["toolConfig"]["toolChoice"] == {
        "tool": {"name": RECOMMENDATION_TOOL_NAME}
    }
    prompt = call["messages"][0]["content"][0]["text"]
    assert "item-1" in prompt
    assert "양파국" in prompt


def test_emit_recipe_forces_separate_strict_tool() -> None:
    expected = {
        "ingredient_names": ["양파", "간장"],
        "steps": ["양파를 볶아요."],
    }
    client = RecordingClient(named_tool_response(RECIPE_TOOL_NAME, expected))
    gateway = BedrockGateway("test-model", client=client, clock=lambda: 10.0)

    actual = gateway.emit_recipe(
        recommendation_context={
            "menuName": "양파 볶음",
            "ingredients": [{"name": "양파", "quantity": 1}],
            "seasonings": ["간장"],
        },
        deadline=20.0,
    )

    assert actual == expected
    call = client.calls[0]
    tool_spec = call["toolConfig"]["tools"][0]["toolSpec"]
    assert tool_spec["name"] == RECIPE_TOOL_NAME
    assert tool_spec["strict"] is True
    assert tool_spec["inputSchema"]["json"]["additionalProperties"] is False
    assert call["toolConfig"]["toolChoice"] == {
        "tool": {"name": RECIPE_TOOL_NAME}
    }


def test_emit_meal_plan_forces_strict_six_meal_tool() -> None:
    expected = {
        "meals": [
            {
                "day": day,
                "slot": slot,
                "menu_name": f"양파 요리 {index}",
                "ingredients": [{"item_id": "item-1", "use_half_units": 1}],
                "seasonings": ["간장"],
            }
            for index, (day, slot) in enumerate(
                [
                    (1, "점심"),
                    (1, "저녁"),
                    (2, "점심"),
                    (2, "저녁"),
                    (3, "점심"),
                    (3, "저녁"),
                ],
                start=1,
            )
        ]
    }
    client = RecordingClient(named_tool_response(MEAL_PLAN_TOOL_NAME, expected))
    gateway = BedrockGateway("test-model", client=client, clock=lambda: 10.0)

    actual = gateway.emit_meal_plan(
        inventory_context=[
            {
                "item_id": "item-1",
                "name": "양파",
                "quantity_half_units": 6,
                "expiration_date": "2026-04-12",
            }
        ],
        client_date="2026-04-10",
        deadline=20.0,
    )

    assert actual == expected
    call = client.calls[0]
    tool_spec = call["toolConfig"]["tools"][0]["toolSpec"]
    schema = tool_spec["inputSchema"]["json"]
    assert tool_spec["name"] == MEAL_PLAN_TOOL_NAME
    assert tool_spec["strict"] is True
    assert schema["additionalProperties"] is False
    assert schema["properties"]["meals"]["minItems"] == 6
    assert schema["properties"]["meals"]["maxItems"] == 6
    assert schema["properties"]["meals"]["items"]["additionalProperties"] is False
    assert call["toolConfig"]["toolChoice"] == {
        "tool": {"name": MEAL_PLAN_TOOL_NAME}
    }
    prompt = call["messages"][0]["content"][0]["text"]
    assert "정확히 6개 끼니" in prompt
    assert "각 끼니 직전" in prompt
    assert "2026-04-10" in prompt
