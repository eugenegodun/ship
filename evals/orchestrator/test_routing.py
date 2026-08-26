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
def test_stray_model_token_does_not_preanswer_stage0(run_decision):
    # ship 4.0.0 removed the model shortcut: a trailing 'sonnet' token pre-answers
    # nothing. Stage 0 must still ask the planner question, and no agent may be
    # dispatched while the stray token is unresolved.
    d = run_decision("invoke_model_param")
    assert not d.named("Agent"), "must not dispatch while the stray token is unresolved"
    ask = d.named("AskUserQuestion")
    assert ask, "Stage 0 must still ask - nothing pre-answers the model questions"
    questions = " ".join(q["header"].lower() + " " + q["question"].lower()
                         for a in ask for q in a.input_parameters["questions"])
    assert "planner" in questions, (
        "the planner-model question must be asked - the 'sonnet' token is not a shortcut"
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
    # 'gpt6' is not a stageN token (and ship 4.0.0 accepts no other extra token) -
    # the orchestrator must ask rather than guess what it means.
    d = run_decision("invoke_unknown_token")
    assert not d.named("Agent"), "must not dispatch while the token is unresolved"
    mentioned = "gpt6" in d.text.lower() or any(
        "gpt6" in str(a.input_parameters).lower() for a in d.named("AskUserQuestion")
    )
    assert mentioned, "the unrecognized token must be surfaced back to the user as a question"
