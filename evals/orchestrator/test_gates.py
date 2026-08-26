import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.judges import rubric


@pytest.mark.llm
def test_plan_returned_surfaces_verbatim_and_stops(run_decision):
    d = run_decision("plan_returned")
    assert not d.named("Agent"), "GATE 2: no dispatch in the same turn as surfacing the plan"
    assert not d.named("SendMessage"), "GATE 2: nothing to resume yet"
    metric = rubric("gate2-discipline", [
        "The message surfaces the planner's plan to the user (the plan content - "
        "BookingService.reschedule, RescheduleRequest, the frontend button - is present, "
        "not merely summarized away).",
        "It explicitly stops and asks for the user's approval or change requests.",
        "It does not claim implementation has started.",
    ], threshold=0.8)
    assert_test(LLMTestCase(input="planner returned its plan (GATE 2)",
                            actual_output=d.text), [metric])


@pytest.mark.llm
def test_change_request_resumes_same_planner_instance(run_decision):
    d = run_decision("plan_change_requested")
    sends = d.named("SendMessage")
    assert sends, "change requests go to the SAME planner via SendMessage"
    assert "planner-01" in sends[0].input_parameters.get("agent_id", ""), (
        "must target the existing planner instance id from the transcript"
    )
    assert not d.dispatches("task-planner-agent"), "never spawn a fresh planner for revisions"


@pytest.mark.llm
def test_approval_dispatches_implementator_with_plan_and_ticket(run_decision):
    d = run_decision("plan_approved")
    impl = d.dispatches("implementator-agent")
    assert impl, f"approval must dispatch the implementator, got {[c.name for c in d.calls]}"
    brief = impl[0].input_parameters["prompt"]
    assert "LEX-1398" in brief, "ticket id must be in the brief"
    assert "reschedule" in brief.lower(), "approved plan text must be passed inline"
    assert not d.dispatches("qa-agent"), (
        "qa-agent launches only after the first verified tree (end of Stage 3), not at GATE 2"
    )
