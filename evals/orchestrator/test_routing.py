import pytest


@pytest.mark.llm
def test_plain_invoke_runs_stage0_before_any_dispatch(run_decision):
    d = run_decision("invoke_plain")
    ask = d.named("AskUserQuestion")
    assert ask, f"expected Stage-0 AskUserQuestion, got tools={[c.name for c in d.calls]}"
    questions = ask[0].input_parameters["questions"]
    headers = " ".join(q["header"].lower() + " " + q["question"].lower() for q in questions)
    assert "planner" in headers and "reviewer" in headers
    labels = {o["label"] for q in questions for o in q["options"]}
    assert {"claude-fable-5", "claude-opus-5[1m]", "claude-sonnet-5"} <= labels
    assert not d.named("Agent"), "no agent may be dispatched before Stage 0 is answered"


@pytest.mark.llm
def test_model_param_preanswers_planner_question(run_decision):
    d = run_decision("invoke_model_param")
    for ask in d.named("AskUserQuestion"):
        for q in ask.input_parameters["questions"]:
            assert "planner" not in (q["header"] + q["question"]).lower(), (
                "model param 'sonnet' pre-answers the planner question - it must not be asked"
            )


@pytest.mark.llm
def test_spec_flag_reaches_spec_agent_not_planner(run_decision):
    d = run_decision("invoke_spec_flag")
    # Stage 0 still runs first; whichever agent is dispatched first must never be
    # the planner while --spec is set and no spec exists yet.
    assert not d.dispatches("task-planner-agent"), (
        "--spec means spec-agent precedes task-planner-agent"
    )


@pytest.mark.llm
def test_missing_ticket_asks_instead_of_guessing(run_decision):
    d = run_decision("invoke_no_ticket")
    assert not d.named("Agent"), "must not dispatch anything without a ticket"
    asked = bool(d.named("AskUserQuestion")) or "ticket" in d.text.lower()
    assert asked, "must ask the user for the ticket key"


@pytest.mark.llm
def test_unknown_token_asks_instead_of_guessing(run_decision):
    # 'gpt6' is neither a stageN token nor fable/opus/sonnet - the orchestrator must
    # ask rather than guess what it means.
    d = run_decision("invoke_unknown_token")
    assert not d.named("Agent"), "must not dispatch while the token is unresolved"
    mentioned = "gpt6" in d.text.lower() or any(
        "gpt6" in str(a.input_parameters).lower() for a in d.named("AskUserQuestion")
    )
    assert mentioned, "the unrecognized token must be surfaced back to the user as a question"
