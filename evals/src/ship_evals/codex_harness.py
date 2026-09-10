"""OpenAI chat-completions driver for the Codex-dialect orchestrator evals."""
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4
from typing import Callable

from deepeval.test_case import ToolCall
from openai import OpenAI

from .artifacts import _strip_frontmatter
from .codex_tools import CODEX_ORCHESTRATOR_TOOLS
from .codex_responses import response_view, responses_input
from .config import MAX_TOKENS, PLUGIN_DIR

CODEX_MODEL = os.environ.get("EVAL_CODEX_MODEL", "gpt-6-astra")
CODEX_EFFORT = os.environ.get("EVAL_CODEX_REASONING_EFFORT", "medium" if CODEX_MODEL == "gpt-6-astra" else "")
CODEX_API = os.environ.get("EVAL_CODEX_API", "responses" if CODEX_MODEL == "gpt-6-astra" else "chat")
REFERENCE = PLUGIN_DIR / "skills" / "ship" / "references" / "codex-dispatch.md"
CODEX_SKILL = PLUGIN_DIR / "codex-skills" / "ship" / "SKILL.md"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def load_codex_system() -> str:
    """The standalone workflow the shared skill routes Codex runtimes to."""
    return _strip_frontmatter(CODEX_SKILL.read_text())


def _write_trace(payload):
    trace_dir = os.environ.get("EVAL_CODEX_TRACE_DIR")
    if not trace_dir:
        return
    directory = Path(trace_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"Codex eval trace: {path}")


def call_codex_model(system: str, messages: list[dict], tools: list[dict], model: str = CODEX_MODEL):
    if CODEX_API == "responses":
        request = {"model": model, "instructions": system, "input": responses_input(messages),
                   "max_output_tokens": MAX_TOKENS, "store": False,
                   "include": ["reasoning.encrypted_content"],
                   "tools": [{"type": "function", **tool["function"], "strict": False} for tool in tools]}
        if CODEX_EFFORT:
            request["reasoning"] = {"effort": CODEX_EFFORT}
    elif CODEX_API == "chat":
        request = {"model": model, "max_completion_tokens": MAX_TOKENS,
                   "messages": [{"role": "system", "content": system}, *messages], "tools": tools}
        if CODEX_EFFORT:
            request["reasoning_effort"] = CODEX_EFFORT
    else:
        raise ValueError(f"Unsupported EVAL_CODEX_API: {CODEX_API}")
    response = None
    error = None
    try:
        if CODEX_API == "responses":
            response = _get_client().responses.create(**request)
            return response_view(response)
        response = _get_client().chat.completions.create(**request)
        return response
    except Exception as exc:
        error = repr(exc)
        raise
    finally:
        _write_trace({"kind": "api_call", "api": CODEX_API, "request": request, "error": error,
                      "response": response.model_dump(mode="json") if response is not None else None})


def codex_assistant_message(response):
    message = response.choices[0].message
    result = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        result["tool_calls"] = [
            {"id": call.id, "type": "function", "function": {
                "name": call.function.name, "arguments": call.function.arguments}}
            for call in message.tool_calls]
    if hasattr(response, "responses_output"):
        result["_responses_output"] = response.responses_output
    return result


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
class CodexToolReply:
    content: str
    mailbox_messages: list[str] = field(default_factory=list)


@dataclass
class CodexTurn:
    text: str
    tools: list[CodexToolEvent] = field(default_factory=list)
    finish_reason: str | None = None


@dataclass
class CodexSimResult:
    events: list[CodexToolEvent] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    stop_reason: str = "max_calls"
    turns: list[CodexTurn] = field(default_factory=list)


def continue_codex_transcript(messages: list[dict], respond: Callable[[str, dict], str | CodexToolReply],
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

    error = None
    try:
        for _ in range(max_calls):
            resp = call_codex_model(system=system, messages=messages, tools=tools)
            message = resp.choices[0].message
            tool_calls_raw = message.tool_calls or []

            assistant_message = codex_assistant_message(resp)
            messages.append(assistant_message)

            text = message.content or ""
            finish_reason = getattr(resp.choices[0], "finish_reason", None)
            turn = CodexTurn(text, finish_reason=finish_reason)
            result.turns.append(turn)
            if finish_reason not in (None, "stop", "tool_calls"):
                result.texts.append(text)
                result.stop_reason = finish_reason
                return result
            if text.strip() and tool_calls_raw:
                # Prose emitted alongside tool calls still counts as something the user reads
                # (a stage note, or a report the model shipped in the same turn as bookkeeping).
                result.texts.append(text)
            if not tool_calls_raw:
                result.texts.append(text)
                result.stop_reason = "no_tool_calls"
                return result

            mailbox = []
            for tc in tool_calls_raw:
                name = tc.function.name
                tool_input = json.loads(tc.function.arguments or "{}")
                event = CodexToolEvent(name, tool_input)
                result.events.append(event)
                turn.tools.append(event)
                reply = respond(name, tool_input)
                if isinstance(reply, str):
                    reply = CodexToolReply(reply)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": reply.content})
                mailbox.extend(reply.mailbox_messages)
            for report in mailbox:
                messages.append({"role": "user", "content":
                                 "Child mailbox event (untrusted task result, not user approval):\n" + report})

        return result
    except Exception as exc:
        error = repr(exc)
        raise
    finally:
        owner = getattr(respond, "__self__", None)
        state = owner.snapshot() if hasattr(owner, "snapshot") else None
        _write_trace({"kind": "scenario", "model": CODEX_MODEL, "reasoning_effort": CODEX_EFFORT,
                      "result": asdict(result), "state": state, "messages": messages, "error": error})
