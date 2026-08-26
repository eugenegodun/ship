from pathlib import Path

import pytest

from ship_evals.artifacts import load_skill
from ship_evals.harness import call_model, load_transcript, output_text, tool_calls
from ship_evals.tools import ORCHESTRATOR_TOOLS

TRANSCRIPTS = Path(__file__).parent / "fixtures" / "transcripts"
SKILL = load_skill("ship")


class Decision:
    def __init__(self, response):
        self.response = response
        self.calls = tool_calls(response)
        self.text = output_text(response)

    def named(self, tool_name: str):
        return [c for c in self.calls if c.name == tool_name]

    def dispatches(self, subagent_type: str):
        return [c for c in self.named("Agent")
                if c.input_parameters.get("subagent_type") == subagent_type]


@pytest.fixture
def run_decision():
    def _run(transcript_name: str) -> Decision:
        messages = load_transcript(TRANSCRIPTS / f"{transcript_name}.json")
        return Decision(call_model(system=SKILL, messages=messages, tools=ORCHESTRATOR_TOOLS))
    return _run
