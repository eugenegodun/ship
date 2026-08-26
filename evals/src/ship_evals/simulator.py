"""Multi-turn orchestrator simulator: the harness plays tool executor with canned replies."""
from dataclasses import dataclass, field
from typing import Callable

from .artifacts import load_skill
from .harness import call_model, output_text
from .tools import ORCHESTRATOR_TOOLS


@dataclass
class ToolEvent:
    name: str
    input: dict


@dataclass
class SimResult:
    events: list[ToolEvent] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    stop_reason: str = "max_calls"


def run_pipeline(invocation: str, respond: Callable[[str, dict], str],
                 user_replies: list[str], max_calls: int = 40) -> SimResult:
    """Drive the ship orchestrator turn by turn.

    Every tool call is answered by respond(tool_name, input). Every turn that ends in
    plain text (a gate stop, halt, or final report) consumes the next entry of
    user_replies; when none remain, the run ends.
    """
    system = load_skill("ship")
    messages: list[dict] = [{"role": "user", "content": invocation}]
    result = SimResult()
    replies = list(user_replies)

    for _ in range(max_calls):
        resp = call_model(system=system, messages=messages, tools=ORCHESTRATOR_TOOLS)
        blocks = list(resp.content)
        tool_uses = [b for b in blocks if b.type == "tool_use"]
        messages.append({"role": "assistant",
                         "content": [b.model_dump() if hasattr(b, "model_dump") else {"type": b.type, "text": b.text} for b in blocks]})
        if not tool_uses:
            result.texts.append(output_text(resp))
            if not replies:
                result.stop_reason = "user_replies_exhausted"
                return result
            messages.append({"role": "user", "content": replies.pop(0)})
            continue
        tool_results = []
        for tu in tool_uses:
            result.events.append(ToolEvent(tu.name, dict(tu.input)))
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                 "content": respond(tu.name, dict(tu.input))})
        messages.append({"role": "user", "content": tool_results})
    return result
