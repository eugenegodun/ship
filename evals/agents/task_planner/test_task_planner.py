from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.artifacts import load_agent
from ship_evals.harness import call_model, output_text
from ship_evals.judges import rubric

FIXTURES = Path(__file__).parent / "fixtures"
SYSTEM = load_agent("task-planner-agent")

BRIEF = (
    "Ticket: LEX-2101. An approved spec is provided below — ground the plan in it instead "
    "of re-reading the ticket. A relevant excerpt of the existing code is also inlined; "
    "there is no repository or Jira access in this environment, so plan from what is "
    "given.\n\n--- APPROVED SPEC ---\n{spec}\n--- CODE: lessons/services/booking.py ---\n"
    "```python\n{code}\n```"
)


@pytest.mark.llm
def test_plan_is_grounded_and_writes_no_code():
    prompt = BRIEF.format(
        spec=(FIXTURES / "approved_spec.md").read_text(),
        code=(FIXTURES / "code_excerpt.py").read_text(),
    )
    resp = call_model(system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    out = output_text(resp)
    metric = rubric("plan-quality", [
        "The plan is grounded in the provided code excerpt: it references BookingService "
        "and builds the reschedule flow around the existing book/cancel/notifications "
        "structure rather than inventing an unrelated architecture.",
        "The plan is decomposed into ordered implementation tasks, each with a concrete "
        "deliverable and a testing step.",
        "The plan covers every acceptance criterion from the spec: the 12-hour visibility "
        "rule, tutor confirmation with the original lesson unchanged, and the "
        "twice-rescheduled limit.",
        "The plan lists the skills or conventions the implementer should use (a section "
        "naming skills is present).",
        "Heavily penalize full product-code implementations in the plan — snippets to "
        "illustrate an interface are fine, complete function bodies are not; the planner "
        "never writes product code.",
    ])
    assert_test(LLMTestCase(input=prompt, actual_output=out), [metric])
