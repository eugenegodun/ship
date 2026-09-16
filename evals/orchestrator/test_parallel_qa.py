import json
import re
from pathlib import Path

import pytest
from ship_evals.plan_display import assert_plan_displayed_verbatim
from ship_evals.qa_assertions import has_execution_authorization, parse_labeled_choice


def asked_questions(window):
    return [q for call in window.named("AskUserQuestion")
            for q in call.input_parameters["questions"]]


def question_text(question):
    return (question["header"] + " " + question["question"]).lower()


def assert_choice(message, labels, expected):
    assert parse_labeled_choice(message, labels) is expected, message


def assert_no_execution_authorization(message):
    assert not has_execution_authorization(message), message


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
        # The current gate contract requires prose before the question pauses execution.
        assert_plan_displayed_verbatim(plans[0], window.text, [])
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
    assert "target" in brief.lower() or "environment" in brief.lower(), (
        "the deferred-target instruction must be in the brief"
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
    # Allow bookkeeping before the complete plan is shown in prose before the gate.
    w = run_window("pr_created_qa_ready")
    assert not w.dispatches("qa-agent"), "never dispatch a second qa-agent at Stage 5"
    assert_queued_plan_displayed(w, "pr_created_qa_ready")
    assert not w.named("SendMessage"), "Phase B starts only after GATE 2 approval"


@pytest.mark.llm
def test_gate2_asks_recording_question_when_no_record_flag(run_window):
    # ship 4.1.0: without --record, the "Record video of this QA run?" question is
    # asked via AskUserQuestion as part of the same GATE 2 stop.
    d = run_window("pr_created_qa_ready")
    asked = " ".join(question_text(q) for q in asked_questions(d))
    assert "record" in asked or "video" in asked
    assert "screenshot" in asked
    assert "/dynamic" in asked or ("start" in asked and "server" in asked), (
        "GATE 2 must settle three independent choices alongside the plan " + d.diagnostics())
    assert not d.named("SendMessage") and not d.named("Agent"), (
        "no execution or new QA agent before approval " + d.diagnostics()
    )


@pytest.mark.llm
def test_record_flag_preanswers_gate2_recording_question(run_window):
    # /ship LEX-1398 --record: recording is already decided - the question must NOT
    # be re-asked at GATE 2. The complete plan must still be visible before approval.
    w = run_window("pr_created_qa_ready_record_flag")
    asked = " ".join(question_text(q) for q in asked_questions(w))
    assert "record" not in asked and "video" not in asked, (
        "--record pre-answers the recording question - it must not be re-asked")
    assert "screenshot" in asked
    assert "/dynamic" in asked or ("start" in asked and "server" in asked)
    assert_queued_plan_displayed(w, "pr_created_qa_ready_record_flag")
    assert not w.dispatches("qa-agent") and not w.named("SendMessage")


@pytest.mark.llm
def test_gate2_approval_resume_carries_all_choices_and_pr(run_decision):
    d = run_decision("qa_plan_approved")
    sends = d.named("SendMessage")
    assert sends and "qa-01" in sends[0].input_parameters.get("agent_id", "")
    msg = sends[0].input_parameters["message"]
    assert "approv" in msg.lower(), "the resume must carry the user's verdict"
    assert "pull/4321" in msg, "the PR URL is the deferred-PR handoff"
    lowered = msg.lower()
    assert_choice(lowered, ("recording", "record video"), True)
    assert_choice(lowered, ("screenshots", "screenshot"), True)
    assert_choice(lowered, ("start_dynamic", "start dynamic", "dynamic comment"), True)


@pytest.mark.llm
def test_declined_startup_with_explicit_target_resumes_same_qa(run_decision):
    d = run_decision("qa_start_declined_with_target")
    sends = d.named("SendMessage")
    assert sends and sends[0].input_parameters.get("agent_id") == "qa-01"
    msg = sends[0].input_parameters["message"].lower()
    assert "stage34" in msg
    assert_choice(msg, ("start_dynamic", "start dynamic", "dynamic comment"), False)
    assert not d.named("Agent")


@pytest.mark.llm
def test_declined_startup_without_target_stays_pending(run_window):
    w = run_window("qa_start_declined_without_target")
    assert not w.named("SendMessage") and not w.dispatches("qa-agent"), w.diagnostics()
    prompt = " ".join(question_text(q) for q in asked_questions(w))
    observed = w.text + " " + prompt
    assert re.search(r"(existing|test).{0,30}(url|environment|target)|defer", observed,
                     re.I | re.S), w.diagnostics()


@pytest.mark.llm
def test_requested_qa_plan_revision_resumes_same_agent_without_execution(run_decision):
    d = run_decision("qa_plan_revision_requested")
    sends = d.named("SendMessage")
    assert sends and sends[0].input_parameters.get("agent_id") == "qa-01"
    msg = sends[0].input_parameters["message"].lower()
    assert "keyboard" in msg and ("revis" in msg or "plan" in msg)
    assert_no_execution_authorization(msg)
    assert not d.named("Agent")
