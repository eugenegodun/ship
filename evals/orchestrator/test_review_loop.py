import pytest


@pytest.mark.llm
def test_critical_finding_resumes_same_implementator(run_decision):
    d = run_decision("review_critical_round1")
    sends = d.named("SendMessage")
    assert sends and "impl-01" in sends[0].input_parameters.get("agent_id", ""), (
        "fix rounds resume the SAME implementator instance"
    )
    assert "refund" in sends[0].input_parameters["message"].lower(), (
        "the findings must be handed to the implementator"
    )
    assert not d.dispatches("implementator-agent"), "never a fresh implementator per round"


@pytest.mark.llm
def test_fix_report_redispatches_reviewer_fresh(run_decision):
    d = run_decision("review_fix_reported")
    rev = d.dispatches("reviewer-agent")
    assert rev, "after a fix round the reviewer is re-dispatched fresh"
    brief = rev[0].input_parameters["prompt"]
    assert "/tmp/worktrees/LEX-1398" in brief and "LEX-1398" in brief, (
        "reviewer always gets worktree path + branch"
    )
    # Stage-0 reviewer base in this transcript is claude-opus-5[1m]; previous round was
    # Critical but the base is already opus -> stays on opus (no escalation needed).
    assert "opus" in rev[0].input_parameters.get("model", "")


@pytest.mark.llm
def test_cap_reached_halts_without_commit_and_keeps_qa_alive(run_decision):
    d = run_decision("review_cap_reached")
    assert not d.dispatches("claude"), "no git agent - never commit past the cap"
    assert not d.named("SendMessage") or all(
        "impl-01" not in s.input_parameters.get("agent_id", "") for s in d.named("SendMessage")
    ), "round cap is 3 - no fourth fix round"
    text = d.text.lower()
    assert "qa" in text and ("alive" in text or "plan" in text), (
        "halt summary must report the parallel qa instance state"
    )


@pytest.mark.llm
def test_clean_review_dispatches_haiku_git_agent(run_decision):
    d = run_decision("review_clean")
    git = d.dispatches("claude")
    assert git, "clean verdict exits the loop into Stage 5's git agent"
    assert "haiku" in git[0].input_parameters.get("model", "").lower()
    brief = git[0].input_parameters["prompt"]
    assert "/tmp/worktrees/LEX-1398" in brief and "LEX-1398" in brief
    assert "draft" in brief.lower()
    assert "co-author" in brief.lower(), "the no-co-author rule must be relayed"
