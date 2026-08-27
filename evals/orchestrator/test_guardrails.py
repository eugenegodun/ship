import re

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.judges import rubric

TOKEN_FIGURE = re.compile(r"\b\d[\d,.]*\s*(?:k\s*)?tokens\b", re.I)


@pytest.mark.llm
def test_final_report_never_invents_token_numbers(run_window):
    # Stage 8 runs immediately after Stage 7, so the report and the retro bookkeeping share
    # the same stretch of turns. The shared window (conftest.Window) answers the bookkeeping
    # and collects every turn's prose, so the report is judged rather than an interim ack.
    w = run_window("qa_run_done")
    assert w.text.strip(), f"the orchestrator must produce a Stage-7 report {w.diagnostics()}"
    assert not TOKEN_FIGURE.search(w.text), (
        "the orchestrator has no tool to read usage - any token figure is fabricated "
        + w.diagnostics()
    )
    metric = rubric("usage-reporting", [
        "The final report includes the ticket key, the branch, the PR URL, the review "
        "outcome, and the QA PASS/FAIL result.",
        "It points the user to /cost for the session total instead of quoting any token "
        "figure.",
    ], threshold=0.8)
    assert_test(LLMTestCase(input="pipeline finished (Stage 7 report + Stage 8 retro)",
                            actual_output=w.text), [metric])
