import json
from pathlib import Path

from anthropic import Anthropic
from deepeval.test_case import ToolCall

from .config import EVAL_MODEL, MAX_TOKENS

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def call_model(system: str, messages: list[dict], tools: list[dict] | None = None,
               model: str = EVAL_MODEL):
    return _get_client().messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        tools=tools or [],
    )


def tool_calls(response) -> list[ToolCall]:
    return [ToolCall(name=b.name, input_parameters=dict(b.input))
            for b in response.content if b.type == "tool_use"]


def output_text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


def load_transcript(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text())["messages"]
