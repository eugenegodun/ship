import re
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.artifacts import load_agent
from ship_evals.harness import call_model, output_text
from ship_evals.judges import rubric

FIXTURES = Path(__file__).parent / "fixtures"
SYSTEM = load_agent("reviewer-agent")

BRIEF = (
    "Review the working-tree changes for ticket LEX-2103 (worktree: "
    "/tmp/worktrees/LEX-2103, branch LEX-2103). There is no shell access in this "
    "environment: the full uncommitted diff is inlined below, and the static checks "
    "already ran clean (lint: 0 errors, tsc: n/a, tests: 214 passed). Review the diff "
    "and return your findings and verdict.\n\n--- DIFF ---\n{diff}\n--- END DIFF ---"
)

VERDICT_RE = re.compile(r"Ready to commit\?\s*\**\s*\[?\s*(Yes|No|With fixes)\s*\]?", re.I)


@pytest.mark.llm
def test_reviewer_catches_seeded_bugs_and_emits_verdict_line():
    prompt = BRIEF.format(diff=(FIXTURES / "seeded_bugs.diff").read_text())
    resp = call_model(system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    out = output_text(resp)

    match = VERDICT_RE.search(out)
    assert match, f"missing 'Ready to commit?' verdict line in:\n{out[-800:]}"
    assert match.group(1).lower() in {"no", "with fixes"}, (
        "seeded Critical bug must block a clean 'Yes' verdict"
    )

    metric = rubric("review-findings", [
        "The findings are grouped under Critical, Important, and Minor severities.",
        "A Critical (or at minimum Important) finding flags that refund_lesson uses "
        "order.list_price instead of the actually paid amount (list price minus discount), "
        "overpaying refunds for discounted orders.",
        "A finding flags that the refund_lesson endpoint catches all exceptions and "
        "returns status ok, hiding failures from the caller.",
        "Each finding cites a file (and ideally line) from the diff.",
        "Penalize fabricated findings about code that is not in the diff.",
    ])
    assert_test(LLMTestCase(input=prompt, actual_output=out), [metric])
