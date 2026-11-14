from app.gateways.bedrock import (
    RECOGNITION_TOOL_NAME,
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
