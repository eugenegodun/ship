from pathlib import Path

import pytest
from deepeval.test_case import ToolCall

from ship_evals.artifacts import load_skill
from ship_evals.harness import call_model, load_transcript, output_text, tool_calls
from ship_evals.simulator import continue_transcript
from ship_evals.tools import ORCHESTRATOR_TOOLS

TRANSCRIPTS = Path(__file__).parent / "fixtures" / "transcripts"
SKILL = load_skill("ship")

# Bookkeeping the orchestrator is *required* to do (SKILL.md mandates a TodoWrite stage
# table with every update), answered so it never consumes the observation window.
BOOKKEEPING = {
    "TodoWrite": "Todos updated",
    "Skill": "engineering-insights: nothing substantial to record for this run.",
    "TaskOutput": "[agent_id: qa-01] Phase-A plan ready (TC1, TC2, TC3); awaiting approval.",
}


def bookkeeping_responder(tool: str, inp: dict) -> str:
    return BOOKKEEPING.get(tool, "ok")


class Decision:
    """One assistant turn — use for assertions about the NEXT TOOL CALL."""

    def __init__(self, response):
        self.response = response
        self.calls = tool_calls(response)
        self.text = output_text(response)

    def named(self, tool_name: str):
        return [c for c in self.calls if c.name == tool_name]

    def dispatches(self, subagent_type: str):
        return [c for c in self.named("Agent")
                if c.input_parameters.get("subagent_type") == subagent_type]


class Window:
    """Several turns, up to the orchestrator's own stopping point — use for PROSE.

    A single turn is the wrong window for text. SKILL.md mandates TodoWrite stage-table
    bookkeeping, so a compliant orchestrator may spend its next turn entirely on tool
    calls and emit the prose a turn later. Asserting on one turn made three cases fail
    intermittently on an empty `d.text` (`assert 'TC1' in ''`).
    """

    def __init__(self, result):
        self.result = result
        self.text = "\n\n".join(result.texts)
        self.calls = [ToolCall(name=e.name, input_parameters=e.input) for e in result.events]

    def named(self, tool_name: str):
        return [c for c in self.calls if c.name == tool_name]

    def dispatches(self, subagent_type: str):
        return [c for c in self.named("Agent")
                if c.input_parameters.get("subagent_type") == subagent_type]

    def diagnostics(self) -> str:
        """Attach to every prose assertion — a bare failure is not debuggable."""
        return (f"[turns_with_text={len(self.result.texts)} "
                f"stop={self.result.stop_reason} "
                f"tools={[c.name for c in self.calls]} "
                f"text={self.text[:400]!r}]")


@pytest.fixture
def run_decision():
    def _run(transcript_name: str) -> Decision:
        messages = load_transcript(TRANSCRIPTS / f"{transcript_name}.json")
        return Decision(call_model(system=SKILL, messages=messages, tools=ORCHESTRATOR_TOOLS))
    return _run


@pytest.fixture
def run_window():
    def _run(transcript_name: str, max_calls: int = 5) -> Window:
        messages = load_transcript(TRANSCRIPTS / f"{transcript_name}.json")
        return Window(continue_transcript(messages, respond=bookkeeping_responder,
                                          max_calls=max_calls))
    return _run
