"""OpenAI chat-completions driver for the Codex-dialect orchestrator evals."""
import json
import os
from dataclasses import dataclass, field
from typing import Callable

from deepeval.test_case import ToolCall
from openai import OpenAI

from .artifacts import load_skill
from .codex_tools import CODEX_ORCHESTRATOR_TOOLS
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


@dataclass
class CodexToolEvent:
    name: str
    input: dict


@dataclass
class CodexSimResult:
    events: list[CodexToolEvent] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    stop_reason: str = "max_calls"


def continue_codex_transcript(messages: list[dict], respond: Callable[[str, dict], str],
                              max_calls: int = 40) -> CodexSimResult:
    """Multi-turn driver for the Codex dialect, analogous to ship_evals.simulator.continue_transcript.

    Resumes from an existing OpenAI chat-completions transcript, answering every tool call via
    respond(tool_name, input) until a turn comes back with no tool calls (Codex tier has no
    multi-turn user-reply/gate-approval concept in these tests, so that's always the stop) or
    max_calls is exhausted.
    """
    system = load_codex_system()
    tools = CODEX_ORCHESTRATOR_TOOLS
    messages = list(messages)
    result = CodexSimResult()

    for _ in range(max_calls):
        resp = call_codex_model(system=system, messages=messages, tools=tools)
        message = resp.choices[0].message
        tool_calls_raw = message.tool_calls or []

        assistant_message = {"role": "assistant", "content": message.content}
        if tool_calls_raw:
            assistant_message["tool_calls"] = [
                {"id": tc.id, "type": tc.type,
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls_raw
            ]
        messages.append(assistant_message)

        if not tool_calls_raw:
            result.texts.append(message.content or "")
            result.stop_reason = "no_tool_calls"
            return result

        for tc in tool_calls_raw:
            name = tc.function.name
            tool_input = json.loads(tc.function.arguments or "{}")
            result.events.append(CodexToolEvent(name, tool_input))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": respond(name, tool_input)})

    return result
