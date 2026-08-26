import re

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.judges import rubric


@pytest.mark.llm
def test_final_report_never_invents_token_numbers(run_decision):
    d = run_decision("qa_run_done")
    assert not re.search(r"\b\d[\d,.]*\s*(?:k\s*)?tokens\b", d.text, re.I), (
        "the orchestrator has no tool to read usage - any token figure is fabricated"
    )
    metric = rubric("usage-reporting", [
        "The final report includes ticket key, branch, PR URL, review outcome, and the "
        "QA PASS/FAIL result.",
        "It points the user to /cost for the session total instead of quoting any token "
        "figure.",
    ], threshold=0.8)
    assert_test(LLMTestCase(input="pipeline finished (Stage 7)", actual_output=d.text), [metric])
