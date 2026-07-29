
import pytest
from openclaw_ultimate.runtime import AgentRuntime

class FakeModel:
    def chat(self, user_message: str, system_prompt: str | None = None) -> str:
        return f"echo:{user_message}"

def test_runtime() -> None:
    assert AgentRuntime(FakeModel()).respond("hello") == "echo:hello"

def test_empty_input() -> None:
    with pytest.raises(ValueError):
        AgentRuntime(FakeModel()).respond(" ")

