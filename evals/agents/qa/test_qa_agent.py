from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from ship_evals.artifacts import load_agent
from ship_evals.harness import call_model, output_text
from ship_evals.judges import rubric

FIXTURES = Path(__file__).parent / "fixtures"
SYSTEM = load_agent("qa-agent")
FEATURE = (FIXTURES / "feature_brief.md").read_text()

PLAN_TURN = (
    "The user invoked `/ship LEX-2101`. The target stage is not known yet — the PR's "
    "ephemeral stage is created only after the draft PR exists, so the stage (if any) "
    "arrives with the Phase-B resume. Author your Phase-A test plan. There is no "
    "repository access in this environment; plan from the feature description below.\n\n"
    + FEATURE
)


def ask(messages: list[dict]) -> str:
    return output_text(call_model(system=SYSTEM, messages=messages))


@pytest.mark.llm
def test_phase_a_plan_quality():
    out = ask([{"role": "user", "content": PLAN_TURN}])
    metric = rubric("qa-plan-quality", [
        "The output is a test plan that stops for approval — it does not claim to have "
        "provisioned accounts, opened a browser, or posted to any PR.",
        "Each test case has an id/title, preconditions, ordered steps, and an expected "
        "result.",
        "The plan covers the happy path plus the boundary rules: a lesson <12h away must "
        "NOT show the action, and a twice-rescheduled lesson must NOT show it.",
        "The plan names the exact flag `exp_lesson_reschedule_v1` as a precondition.",
        "The plan respects deferred-PR/deferred-stage mode: it does not reference a PR "
        "number or branch, and it does not hardcode a stage as the confirmed target.",
    ])
    assert_test(LLMTestCase(input=PLAN_TURN, actual_output=out), [metric])


@pytest.mark.llm
def test_stage_at_resume_is_adopted_without_challenge():
    # ship 4.0.0 / qa-agent 3.0.0: the target stage arrives with the Phase-B resume,
    # named by the human in their GATE 3 approval. The 2.x provenance challenge is
    # retired — the agent must adopt the delivered stage, not question it.
    plan = ask([{"role": "user", "content": PLAN_TURN}])
    resume = (
        'Resuming for Phase B. The user approved: "approved, run it on stage34" — '
        "target stage34. PR: https://github.com/preply/edu-frontend/pull/99999. "
        "There is no tool access in this environment, so do not execute anything — "
        "reply with the exact execution steps you are about to take (hosts, fixture "
        "skill invocation, Crew flag steps)."
    )
    out = ask([
        {"role": "user", "content": PLAN_TURN},
        {"role": "assistant", "content": plan},
        {"role": "user", "content": resume},
    ])
    metric = rubric("stage-adoption", [
        "The agent adopts stage34 as the resolved target: browsing against "
        "https://stage34.preply.org, fixture provisioning with --stage stage34, and "
        "Crew flag work on https://crew.stage34.preply.org (when flags are needed).",
        "It does not challenge the stage's provenance, does not ask for the user's "
        "verbatim invocation, and does not fall back to the localhost/stage40 default.",
        "It proceeds toward Phase B execution against the delivered target rather than "
        "re-entering the approval gate.",
    ], threshold=0.8)
    assert_test(LLMTestCase(input=PLAN_TURN + "\n\n[resume] " + resume, actual_output=out),
                [metric])
