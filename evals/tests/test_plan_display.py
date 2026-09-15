from types import SimpleNamespace

import pytest

from ship_evals.plan_display import assert_plan_displayed_verbatim

PLAN = "TC1 happy-path reschedule. TC2 lesson <12h hides action. Flag exp_v1 required."


def question_call(text, name="AskUserQuestion"):
    return SimpleNamespace(name=name, input_parameters={"questions": [{"question": text}]})


@pytest.mark.parametrize("channel", ["prose", "question"])
def test_complete_plan_in_either_visible_channel(channel):
    text = "Plan:\n" + PLAN.replace(". ", ".\n\n") + "\nApprove?"
    assert_plan_displayed_verbatim(
        PLAN, text if channel == "prose" else "",
        [question_call(text)] if channel == "question" else [],
    )


@pytest.mark.parametrize("text", ["", "TC1 happy-path reschedule.", PLAN.replace("hides action", "hides the action")])
@pytest.mark.parametrize("channel", ["prose", "question"])
def test_missing_truncated_or_paraphrased_plan_fails(text, channel):
    with pytest.raises(AssertionError, match="complete queued plan"):
        assert_plan_displayed_verbatim(
            PLAN, text if channel == "prose" else "",
            [question_call(text)] if channel == "question" else [],
        )


def test_plan_in_other_tool_does_not_count_as_displayed():
    with pytest.raises(AssertionError, match="complete queued plan"):
        assert_plan_displayed_verbatim(PLAN, "", [question_call(PLAN, "SendMessage")])


@pytest.mark.parametrize("fixture_name", ["pr_created_qa_ready", "pr_created_qa_ready_record_flag"])
def test_real_fixture_excludes_agent_metadata_from_expected_plan(fixture_name):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "orchestrator" / "test_parallel_qa.py"
    spec = importlib.util.spec_from_file_location("parallel_qa_assertions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = (
        "TC1 happy-path reschedule (preconditions, steps, expected), "
        "TC2 lesson <12h hides action, TC3 third reschedule hidden. "
        "Flag exp_lesson_reschedule_v1 required."
    )
    window = SimpleNamespace(text=plan, calls=[], diagnostics=lambda: "fixture regression")
    module.assert_queued_plan_displayed(window, fixture_name)
    window.text = "TC1 happy-path reschedule"
    with pytest.raises(AssertionError, match="complete queued plan"):
        module.assert_queued_plan_displayed(window, fixture_name)
