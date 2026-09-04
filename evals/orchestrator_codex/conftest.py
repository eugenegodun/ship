from pathlib import Path

import pytest
from deepeval.test_case import ToolCall

from ship_evals.codex_harness import (call_codex_model, codex_output_text, codex_tool_calls,
                                      continue_codex_transcript, load_codex_system)
from ship_evals.codex_tools import CODEX_ORCHESTRATOR_TOOLS
from ship_evals.harness import load_transcript

TRANSCRIPTS = Path(__file__).parent / "fixtures" / "transcripts"
SYSTEM = load_codex_system()

# Bookkeeping the Codex orchestrator is required to do (checklist + preflight re-confirmation),
# answered so it never consumes the observation window.
CODEX_BOOKKEEPING = {
    "update_plan": "Plan updated",
    "shell": ("unchanged  ship-git-agent.toml\nunchanged  ship-implementator-agent.toml\n"
              "unchanged  ship-qa-agent.toml\nunchanged  ship-reviewer-agent.toml\n"
              "unchanged  ship-spec-agent.toml\nunchanged  ship-task-planner-agent.toml\n(exit 0)"),
}


def codex_bookkeeping_responder(tool: str, inp: dict) -> str:
    return CODEX_BOOKKEEPING.get(tool, "ok")


class CodexDecision:
    """One assistant turn in the Codex dialect — assert on the NEXT TOOL CALL."""

    def __init__(self, response):
        self.calls = codex_tool_calls(response)
        self.text = codex_output_text(response)

    def named(self, tool_name: str):
        return [c for c in self.calls if c.name == tool_name]

    def spawns(self, agent_type: str):
        return [c for c in self.named("spawn_agent")
                if c.input_parameters.get("agent_type") == agent_type]

    def diagnostics(self) -> str:
        return f"[tools={[(c.name, c.input_parameters.get('agent_type') or c.input_parameters.get('target')) for c in self.calls]} text={self.text[:300]!r}]"


@pytest.fixture
def run_codex_decision():
    def _run(transcript_name: str) -> CodexDecision:
        messages = load_transcript(TRANSCRIPTS / f"{transcript_name}.json")
        return CodexDecision(call_codex_model(SYSTEM, messages, CODEX_ORCHESTRATOR_TOOLS))
    return _run


class CodexWindow:
    """Several turns, up to the Codex orchestrator's own stopping point — use for PROSE.

    A single turn is the wrong window for text: the model may spend a turn entirely on
    mandated bookkeeping (update_plan, the preflight re-check) and defer the actual
    spawn_agent/text to a further turn.
    """

    def __init__(self, result):
        self.result = result
        self.text = "\n\n".join(result.texts)
        self.calls = [ToolCall(name=e.name, input_parameters=e.input) for e in result.events]

    def named(self, tool_name: str):
        return [c for c in self.calls if c.name == tool_name]

    def spawns(self, agent_type: str):
        return [c for c in self.named("spawn_agent")
                if c.input_parameters.get("agent_type") == agent_type]

    def diagnostics(self) -> str:
        return (f"[turns_with_text={len(self.result.texts)} "
                f"stop={self.result.stop_reason} "
                f"tools={[c.name for c in self.calls]} "
                f"text={self.text[:400]!r}]")


@pytest.fixture
def run_codex_window():
    def _run(transcript_name: str, max_calls: int = 5) -> CodexWindow:
        messages = load_transcript(TRANSCRIPTS / f"{transcript_name}.json")
        return CodexWindow(continue_codex_transcript(messages, respond=codex_bookkeeping_responder,
                                                      max_calls=max_calls))
    return _run
