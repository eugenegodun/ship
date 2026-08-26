import pytest


@pytest.mark.llm
def test_first_verified_tree_launches_background_qa(run_decision):
    d = run_decision("impl_verified")
    qa = d.dispatches("qa-agent")
    assert qa, "first verified tree must launch qa-agent Phase A"
    assert qa[0].input_parameters.get("run_in_background") is True
    brief = qa[0].input_parameters["prompt"]
    assert "/ship LEX-1398" in brief, "the user's invocation must be quoted verbatim"
    assert "PR" in brief and ("does not exist" in brief or "deferred" in brief.lower()), (
        "the deferred-PR instruction must be in the brief"
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
def test_gate3_approval_resume_carries_verbatim_quote_and_pr(run_decision):
    d = run_decision("qa_plan_approved")
    sends = d.named("SendMessage")
    assert sends and "qa-01" in sends[0].input_parameters.get("agent_id", "")
    msg = sends[0].input_parameters["message"]
    assert "approved, run it" in msg, "the user's approval must be quoted verbatim"
    assert "/ship LEX-1398" in msg, "the original invocation re-confirms provenance"
    assert "pull/4321" in msg, "the PR URL is the deferred-PR handoff"
