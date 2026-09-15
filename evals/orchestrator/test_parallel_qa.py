import json
from pathlib import Path

import pytest

from ship_evals.plan_display import assert_plan_displayed_verbatim


def assert_queued_plan_displayed(window, fixture_name):
    fixture = Path(__file__).parent / "fixtures" / "transcripts" / f"{fixture_name}.json"
    messages = json.loads(fixture.read_text())["messages"]
    plans = [
        block["content"].split("] ", 1)[1].split(": ", 1)[1].split(" Awaiting approval", 1)[0]
        for message in messages if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_result"
        and block.get("content", "").startswith("[agent_id: qa-01] Phase-A test plan")
    ]
    assert len(plans) == 1, "fixture must contain exactly one queued QA plan"
    try:
        assert_plan_displayed_verbatim(plans[0], window.text, window.calls)
    except AssertionError as error:
        raise AssertionError(str(error) + " " + window.diagnostics()) from error


@pytest.mark.llm
def test_first_verified_tree_launches_background_qa(run_decision):
    d = run_decision("impl_verified")
    qa = d.dispatches("qa-agent")
    assert qa, "first verified tree must launch qa-agent Phase A"
    assert qa[0].input_parameters.get("run_in_background") is True
    brief = qa[0].input_parameters["prompt"]
    assert "PR" in brief and ("does not exist" in brief or "deferred" in brief.lower()), (
        "the deferred-PR instruction must be in the brief"
    )
    assert "stage" in brief.lower(), (
        "the deferred-stage instruction must be in the brief - the target stage is "
        "unknowable before the PR's /dynamic environment exists"
    )


@pytest.mark.llm
def test_missing_worktree_is_chased_before_review(run_decision):
    d = run_decision("impl_missing_worktree")
    assert not d.dispatches("reviewer-agent"), "reviewer needs worktree+branch first"
    sends = d.named("SendMessage")
    assert sends and "impl-01" in sends[0].input_parameters.get("agent_id", "")
    assert "worktree" in sends[0].input_parameters["message"].lower()


@pytest.mark.llm
def test_gate2_surfaces_queued_plan_without_new_qa_agent(run_window):
    # Allow bookkeeping before the plan, then inspect prose and approval questions.
    w = run_window("pr_created_qa_ready")
    assert not w.dispatches("qa-agent"), "never dispatch a second qa-agent at Stage 5"
    assert_queued_plan_displayed(w, "pr_created_qa_ready")
    assert not w.named("SendMessage"), "Phase B starts only after GATE 2 approval"


@pytest.mark.llm
def test_gate2_asks_recording_question_when_no_record_flag(run_window):
    # ship 4.1.0: without --record, the "Record video of this QA run?" question is
    # asked via AskUserQuestion as part of the same GATE 2 stop.
    d = run_window("pr_created_qa_ready")
    asked = " ".join(
        q["header"].lower() + " " + q["question"].lower()
        for a in d.named("AskUserQuestion") for q in a.input_parameters["questions"]
    )
    assert "record" in asked or "video" in asked, (
        "GATE 2 must settle the recording decision alongside the plan surface " + d.diagnostics()
    )
    assert not d.named("SendMessage") and not d.named("Agent"), (
        "no execution or new QA agent before approval " + d.diagnostics()
    )


@pytest.mark.llm
def test_record_flag_preanswers_gate2_recording_question(run_window):
    # /ship LEX-1398 --record: recording is already decided - the question must NOT
    # be re-asked at GATE 2. The complete plan must still be visible before approval.
    w = run_window("pr_created_qa_ready_record_flag")
    for a in w.named("AskUserQuestion"):
        for q in a.input_parameters["questions"]:
            text = (q["header"] + " " + q["question"]).lower()
            assert "record" not in text and "video" not in text, (
                "--record pre-answers the recording question - it must not be re-asked"
            )
    assert_queued_plan_displayed(w, "pr_created_qa_ready_record_flag")
    assert not w.dispatches("qa-agent") and not w.named("SendMessage")


@pytest.mark.llm
def test_gate2_approval_resume_carries_verdict_stage_pr_and_recording(run_decision):
    # ship 4.0.0/4.1.0: the stage arrives at GATE 2 in the user's approval ("approved,
    # run it on stage34"), the recording decision was settled at the same gate stop
    # (answered Yes in this fixture), and both must be relayed in the Phase-B resume
    # alongside the PR URL.
    d = run_decision("qa_plan_approved")
    sends = d.named("SendMessage")
    assert sends and "qa-01" in sends[0].input_parameters.get("agent_id", "")
    msg = sends[0].input_parameters["message"]
    assert "approv" in msg.lower(), "the resume must carry the user's verdict"
    assert "stage34" in msg, "the stage named in the GATE 2 approval must be relayed"
    assert "pull/4321" in msg, "the PR URL is the deferred-PR handoff"
    assert "record" in msg.lower(), (
        "the recording decision (Yes at GATE 2) must travel in the Phase-B resume"
    )
