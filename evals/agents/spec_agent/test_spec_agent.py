from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.artifacts import load_agent
from ship_evals.harness import call_model, output_text
from ship_evals.judges import rubric

FIXTURES = Path(__file__).parent / "fixtures"
SYSTEM = load_agent("spec-agent")

BRIEF = (
    "Write the spec for the ticket below. The full ticket content is provided inline — "
    "do not try to fetch anything; there is no Jira access in this environment.\n\n"
    "--- TICKET ---\n{ticket}\n--- END TICKET ---"
)


def run_spec_agent(ticket_file: str) -> tuple[str, str]:
    prompt = BRIEF.format(ticket=(FIXTURES / ticket_file).read_text())
    resp = call_model(system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    return prompt, output_text(resp)


@pytest.mark.llm
def test_feature_ticket_yields_user_stories_and_ears_criteria():
    prompt, out = run_spec_agent("ticket_feature.md")
    metric = rubric("spec-quality", [
        "The output contains user stories in the form 'As a <role>, I want <capability>, "
        "so that <benefit>'.",
        "Acceptance criteria are written in EARS notation: lines shaped "
        "'WHEN <event/condition> THE SYSTEM SHALL <expected behavior>'.",
        "Every constraint from the ticket is covered by at least one criterion: the 12-hour "
        "cutoff, tutor confirmation flow, the at-most-twice limit, and both notification "
        "directions.",
        "Each criterion is falsifiable — it names an observable outcome, not a vague goal.",
        "Heavily penalize implementation detail (component names, endpoints, database "
        "columns, file paths): the spec must be WHAT/WHY only.",
    ])
    assert_test(LLMTestCase(input=prompt, actual_output=out), [metric])


@pytest.mark.llm
def test_refactor_ticket_yields_invariants_not_new_criteria():
    prompt, out = run_spec_agent("ticket_refactor.md")
    metric = rubric("refactor-invariants", [
        "The output contains an 'Invariants to preserve' section (or equivalently titled "
        "section about preserving behavior).",
        "Invariants are framed as 'THE SYSTEM SHALL CONTINUE TO <existing behavior>' — "
        "behavior preservation, not new requirements.",
        "The invariants cover invoice dates, proration math, receipt timezone handling, "
        "renewal-date display, and the 72-hour local-timezone reminder from the ticket.",
        "Heavily penalize invented new user-facing requirements — a refactor ticket has "
        "no new WHEN/SHALL behavior to specify.",
    ])
    assert_test(LLMTestCase(input=prompt, actual_output=out), [metric])
