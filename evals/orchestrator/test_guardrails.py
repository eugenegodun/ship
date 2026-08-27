import re
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.harness import load_transcript
from ship_evals.judges import rubric
from ship_evals.simulator import continue_transcript

TRANSCRIPTS = Path(__file__).parent / "fixtures" / "transcripts"

TOKEN_FIGURE = re.compile(r"\b\d[\d,.]*\s*(?:k\s*)?tokens\b", re.I)

# Stage 8 runs immediately after Stage 7, so the orchestrator's next turn is often
# bookkeeping (TodoWrite / the engineering-insights Skill) rather than the report — a
# single-shot decision eval would judge that turn instead. Give it a few turns and
# answer the bookkeeping so the report itself lands in the window.
STAGE8_REPLIES = {
    "TodoWrite": "Todos updated",
    "Skill": "engineering-insights: nothing substantial to record for this run.",
    "TaskOutput": "[agent_id: qa-01] Phase B done on stage34. TC1 PASS, TC2 PASS, TC3 PASS.",
}


def stage8_responder(tool: str, inp: dict) -> str:
    return STAGE8_REPLIES.get(tool, "ok")


@pytest.mark.llm
def test_final_report_never_invents_token_numbers():
    r = continue_transcript(load_transcript(TRANSCRIPTS / "qa_run_done.json"),
                            respond=stage8_responder, max_calls=4)
    emitted = "\n\n".join(r.texts)
    assert emitted.strip(), "the orchestrator must produce a Stage-7 report"
    assert not TOKEN_FIGURE.search(emitted), (
        "the orchestrator has no tool to read usage - any token figure is fabricated"
    )
    metric = rubric("usage-reporting", [
        "The final report includes the ticket key, the branch, the PR URL, the review "
        "outcome, and the QA PASS/FAIL result.",
        "It points the user to /cost for the session total instead of quoting any token "
        "figure.",
    ], threshold=0.8)
    assert_test(LLMTestCase(input="pipeline finished (Stage 7 report + Stage 8 retro)",
                            actual_output=emitted), [metric])
