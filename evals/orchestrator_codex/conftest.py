from pathlib import Path

import pytest

from ship_evals.codex_harness import call_codex_model, codex_output_text, codex_tool_calls, load_codex_system
from ship_evals.codex_tools import CODEX_ORCHESTRATOR_TOOLS
from ship_evals.harness import load_transcript

TRANSCRIPTS = Path(__file__).parent / "fixtures" / "transcripts"
SYSTEM = load_codex_system()


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
