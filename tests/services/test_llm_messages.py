from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from military_video_gen.services.llm_service import LLMService


class StructuredAnswer(BaseModel):
    answer: str


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeClient:
    def __init__(self, content: str) -> None:
        self.base_url = "http://test"
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


@pytest.mark.asyncio
async def test_structured_call_preserves_system_and_user_roles(monkeypatch) -> None:
    service = LLMService({})
    client = FakeClient('{"answer": "ok"}')
    monkeypatch.setattr(service, "_create_client", lambda **_: client)
    monkeypatch.setattr(service, "_get_config_value", lambda *args: "test-model")

    result = await service.generate_structured(
        messages=[
            {"role": "system", "content": "Use only supplied evidence."},
            {"role": "user", "content": "Extract a claim."},
        ],
        response_type=StructuredAnswer,
    )

    sent = client.chat.completions.calls[0]["messages"]
    assert [message["role"] for message in sent] == ["system", "user"]
    assert sent[0]["content"] == "Use only supplied evidence."
    assert sent[1]["content"].startswith("Extract a claim.")
    assert result == StructuredAnswer(answer="ok")


@pytest.mark.asyncio
async def test_legacy_prompt_call_still_sends_one_user_message(monkeypatch) -> None:
    service = LLMService({})
    client = FakeClient("legacy response")
    monkeypatch.setattr(service, "_create_client", lambda **_: client)
    monkeypatch.setattr(service, "_get_config_value", lambda *args: "test-model")

    result = await service(prompt="legacy prompt")

    assert result == "legacy response"
    assert client.chat.completions.calls[0]["messages"] == [
        {"role": "user", "content": "legacy prompt"}
    ]
