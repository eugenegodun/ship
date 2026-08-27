import pytest


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
def test_gate3_surfaces_queued_plan_without_new_qa_agent(run_decision):
    d = run_decision("pr_created_qa_ready")
    assert not d.dispatches("qa-agent"), "never dispatch a second qa-agent at Stage 6"
    assert "TC1" in d.text, "the queued Phase-A plan is surfaced verbatim"
    assert not d.named("SendMessage"), "Phase B starts only after GATE 3 approval"


@pytest.mark.llm
def test_gate3_asks_recording_question_when_no_record_flag(run_decision):
    # ship 4.1.0: without --record, the "Record video of this QA run?" question is
    # asked via AskUserQuestion as part of the same GATE 3 stop.
    d = run_decision("pr_created_qa_ready")
    asked = " ".join(
        q["header"].lower() + " " + q["question"].lower()
        for a in d.named("AskUserQuestion") for q in a.input_parameters["questions"]
    )
    assert "record" in asked or "video" in asked, (
        "GATE 3 must settle the recording decision alongside the plan surface"
    )


@pytest.mark.llm
def test_record_flag_preanswers_gate3_recording_question(run_decision):
    # /ship LEX-1398 --record: recording is already decided - the question must NOT
    # be re-asked at GATE 3.
    d = run_decision("pr_created_qa_ready_record_flag")
    for a in d.named("AskUserQuestion"):
        for q in a.input_parameters["questions"]:
            text = (q["header"] + " " + q["question"]).lower()
            assert "record" not in text and "video" not in text, (
                "--record pre-answers the recording question - it must not be re-asked"
            )
    assert "TC1" in d.text, "the queued Phase-A plan is still surfaced verbatim"
    assert not d.dispatches("qa-agent") and not d.named("SendMessage")


@pytest.mark.llm
def test_gate3_approval_resume_carries_verdict_stage_pr_and_recording(run_decision):
    # ship 4.0.0/4.1.0: the stage arrives at GATE 3 in the user's approval ("approved,
    # run it on stage34"), the recording decision was settled at the same gate stop
    # (answered Yes in this fixture), and both must be relayed in the Phase-B resume
    # alongside the PR URL.
    d = run_decision("qa_plan_approved")
    sends = d.named("SendMessage")
    assert sends and "qa-01" in sends[0].input_parameters.get("agent_id", "")
    msg = sends[0].input_parameters["message"]
    assert "approv" in msg.lower(), "the resume must carry the user's verdict"
    assert "stage34" in msg, "the stage named in the GATE 3 approval must be relayed"
    assert "pull/4321" in msg, "the PR URL is the deferred-PR handoff"
    assert "record" in msg.lower(), (
        "the recording decision (Yes at GATE 3) must travel in the Phase-B resume"
    )
