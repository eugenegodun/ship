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
    assert ask, "must ask - nothing pre-answers the model questions and the token is stray"
    # Either shape is compliant: asking Stage 0's questions directly (the token pre-answers
    # nothing), or first questioning what the stray 'sonnet' token meant.
    asked_text = " ".join(
        q["header"].lower() + " " + q["question"].lower()
        for a in ask for q in a.input_parameters["questions"]
    )
    assert "planner" in asked_text or "sonnet" in asked_text, (
        "must either ask the Stage-0 planner question or question the stray 'sonnet' "
        "token - silently adopting it as a shortcut is the failure"
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
def test_missing_ticket_asks_instead_of_guessing(run_window):
    # The ask can be an AskUserQuestion or prose, and prose may follow a bookkeeping
    # turn - so observe the window, not one turn (see conftest.Window).
    w = run_window("invoke_no_ticket")
    assert not w.named("Agent"), "must not dispatch anything without a ticket"
    asked = bool(w.named("AskUserQuestion")) or "ticket" in w.text.lower()
    assert asked, "must ask the user for the ticket key " + w.diagnostics()


@pytest.mark.llm
def test_unknown_token_asks_instead_of_guessing(run_window):
    # 'gpt6' is not a stageN token (and ship 4.0.0 accepts no other extra token) -
    # the orchestrator must ask rather than guess what it means. Prose-bearing assertion,
    # so observe the window rather than one turn (see conftest.Window).
    w = run_window("invoke_unknown_token")
    assert not w.named("Agent"), "must not dispatch while the token is unresolved"
    mentioned = "gpt6" in w.text.lower() or any(
        "gpt6" in str(a.input_parameters).lower() for a in w.named("AskUserQuestion")
    )
    assert mentioned, (
        "the unrecognized token must be surfaced back to the user as a question "
        + w.diagnostics()
    )
