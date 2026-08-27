import pytest

from ship_evals.simulator import run_pipeline

from .scenarios import Script


def dispatches(result, subagent_type):
    return [e for e in result.events
            if e.name == "Agent" and e.input.get("subagent_type") == subagent_type]


def sends_to(result, agent_fragment):
    return [e for e in result.events
            if e.name == "SendMessage" and agent_fragment in e.input.get("agent_id", "")]


@pytest.mark.e2e
@pytest.mark.llm
def test_happy_path_without_spec():
    script = Script(clean_review_round=1)
    r = run_pipeline("/ship LEX-1398", script,
                     user_replies=["Approved - proceed.", "approved, run it on stage34"])
    order = [e.input["subagent_type"] for e in r.events
             if e.name == "Agent" and "subagent_type" in e.input]
    assert order.index("task-planner-agent") < order.index("implementator-agent")
    assert order.index("implementator-agent") < order.index("reviewer-agent")
    assert not dispatches(r, "spec-agent"), "--spec was not passed"
    assert len(dispatches(r, "qa-agent")) == 1, "qa launched once, in the background"
    assert dispatches(r, "qa-agent")[0].input.get("run_in_background") is True
    phase_b = sends_to(r, "qa")
    assert phase_b, "GATE 3 approval must resume the qa instance"
    msg = phase_b[0].input["message"]
    assert "approv" in msg.lower(), "the resume must carry the user's verdict"
    assert "stage34" in msg, "the stage named in the GATE 3 approval must be relayed"
    assert "pull/4321" in msg
    assert len(r.texts) >= 3, "plan gate, qa gate, final report"


@pytest.mark.e2e
@pytest.mark.llm
def test_spec_path_feeds_spec_into_planner():
    script = Script(clean_review_round=1)
    r = run_pipeline("/ship LEX-1398 --spec", script,
                     user_replies=["Approved.", "Approved - proceed.", "approved, run it"])
    order = [e.input["subagent_type"] for e in r.events
             if e.name == "Agent" and "subagent_type" in e.input]
    assert order.index("spec-agent") < order.index("task-planner-agent")
    planner_brief = dispatches(r, "task-planner-agent")[0].input["prompt"]
    assert "SHALL" in planner_brief, "approved spec text flows into the planner brief"


@pytest.mark.e2e
@pytest.mark.llm
def test_fix_loop_cap_halts_without_commit():
    script = Script(clean_review_round=0)  # never clean
    r = run_pipeline("/ship LEX-1398", script, user_replies=["Approved - proceed."])
    assert len(dispatches(r, "reviewer-agent")) <= 3, "3-round cap"
    assert len(dispatches(r, "implementator-agent")) == 1, "fix rounds resume, never respawn"
    assert not dispatches(r, "claude"), "no git agent - never commit past the cap"
    assert sends_to(r, "impl"), "fix rounds go through SendMessage"


@pytest.mark.e2e
@pytest.mark.llm
def test_stage3_failure_stops_before_qa_launch():
    script = Script(impl_ok=False)
    r = run_pipeline("/ship LEX-1398", script, user_replies=["Approved - proceed."])
    assert not dispatches(r, "qa-agent"), "no verified tree -> qa never launched"
    assert not dispatches(r, "reviewer-agent")
    assert not dispatches(r, "claude")


@pytest.mark.e2e
@pytest.mark.llm
def test_critical_then_clean_escalates_to_opus_when_base_is_sonnet():
    class SonnetScript(Script):
        def __call__(self, tool, inp):
            if tool == "AskUserQuestion":
                asked = str(inp.get("questions", "")).lower()
                if "record" not in asked and "video" not in asked:
                    return ('{"Planner model": "claude-sonnet-5", '
                            '"Reviewer model": "claude-sonnet-5"}')
            return super().__call__(tool, inp)

    script = SonnetScript(clean_review_round=2)  # round 1 Critical, round 2 clean
    r = run_pipeline("/ship LEX-1398", script,
                     user_replies=["Approved - proceed.", "approved, run it"])
    rev = dispatches(r, "reviewer-agent")
    assert len(rev) == 2
    assert "sonnet" in rev[0].input.get("model", "")
    assert "opus" in rev[1].input.get("model", ""), (
        "a Critical finding on a non-opus base escalates the re-review round to opus"
    )
