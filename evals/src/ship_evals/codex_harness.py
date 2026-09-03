"""OpenAI chat-completions driver for the Codex-dialect orchestrator evals."""
import json
import os

from deepeval.test_case import ToolCall
from openai import OpenAI

from .artifacts import load_skill
from .config import MAX_TOKENS, PLUGIN_DIR

CODEX_MODEL = os.environ.get("EVAL_CODEX_MODEL", "gpt-4.1")
REFERENCE = PLUGIN_DIR / "skills" / "ship" / "references" / "codex-dispatch.md"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def load_codex_system() -> str:
    """What a Codex runtime effectively reads: SKILL.md body + the dispatch reference it points at."""
    return load_skill("ship") + "\n\n" + REFERENCE.read_text()


def call_codex_model(system: str, messages: list[dict], tools: list[dict], model: str = CODEX_MODEL):
    # max_completion_tokens (not max_tokens): accepted by every current model, including the
    # reasoning models a user may set via EVAL_CODEX_MODEL, which reject max_tokens.
    return _get_client().chat.completions.create(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": system}, *messages],
        tools=tools,
    )


def codex_tool_calls(response) -> list[ToolCall]:
    message = response.choices[0].message
    return [ToolCall(name=tc.function.name, input_parameters=json.loads(tc.function.arguments or "{}"))
            for tc in (message.tool_calls or [])]


def codex_output_text(response) -> str:
    return response.choices[0].message.content or ""
