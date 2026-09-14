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


SETTINGS_PLAN = (
    "TC1: Update setting. Preconditions: log in as student, navigate to settings. "
    "Steps: enter a valid display name and save. Expected: saved name is visible.\n"
    "TC2: Reject invalid name. Preconditions: reset the name, navigate away and back "
    "to settings. Steps: clear the name and save. Expected: validation error is visible."
)


@pytest.mark.llm
@pytest.mark.parametrize("plan,decision,observation,criteria", [
    pytest.param(SETTINGS_PLAN, "Record the QA run.", "", [
        "Login and navigation to settings happen before video-start for TC1.",
        "There are two distinct recording files, one per case. TC1 video-stop happens "
        "before resetting the name or navigating for TC2; TC2 video-start follows its setup.",
        "Each clip includes the tested actions and visible outcome, with the approved "
        "case ID/title as its chapter and in the proposed results recording label.",
    ], id="case-boundaries"),
    pytest.param(
        "TC1: Open billing. Preconditions: logged in on settings. Steps: click Billing. "
        "Expected: billing page opens and shows the current plan.",
        "Record the QA run.", "", [
            "Login and setup precede video-start, but clicking Billing and verifying "
            "the destination occur while recording; video-stop follows the outcome.",
        ], id="tested-navigation"),
    pytest.param(
        "TC1: Receive message. Preconditions: tutor and student logged in to separate "
        "sessions on the same lesson page. Steps: tutor sends hello; student reads it. "
        "Expected: hello appears for both users.",
        "Record the QA run.", "", [
            "Both participants are prepared before capture. Recording commands target "
            "explicit separate sessions and distinct case/role filenames.",
            "Both sessions start capture before the tutor sends hello and stop after "
            "the tested outcome; proposed recording links identify case and role.",
        ], id="multi-user"),
    pytest.param(SETTINGS_PLAN, "Record the QA run.",
        "TC1 has just failed: the saved name is not visible. Recording was started, "
        "but video-stop returned an error and no finalized file is confirmed. "
        "The browser is still usable. Describe your remaining actions.", [
            "The agent preserves the actual assertion failure and attempts recording "
            "cleanup without rerunning TC1 just to obtain a video.",
            "It does not claim an unverified file is finalized or uploaded. If capture "
            "cannot be stopped, it discontinues recording in that session, reports the "
            "limitation, and continues remaining QA where browser state permits.",
        ], id="stop-failure"),
    pytest.param(SETTINGS_PLAN, "Record the QA run.",
        "Both cases passed and both case videos finalized successfully. Upload of TC1 "
        "succeeded and its URL was verified. Upload of TC2 failed. Describe the report "
        "and remaining actions, using placeholders for unavailable paths and URLs.", [
            "The report preserves both passing verdicts and labels each recording by "
            "case and role, using the verified URL for TC1 and a local fallback for TC2.",
            "The upload failure does not trigger rerunning test cases, deleting local "
            "files, or claiming a successful TC2 upload.",
        ], id="upload-failure"),
    pytest.param(SETTINGS_PLAN, "The user declined recording.", "", [
        "The execution does not start or stop video capture or upload videos. "
        "Mentioning that recording is disabled is allowed.",
    ], id="recording-declined"),
])
def test_recording_execution(plan, decision, observation, criteria):
    resume = (
        "Resuming Phase B for LEX-2101. The user approved the plan below and authorized "
        "fixtures, browser execution, and posting results on "
        "https://github.com/preply/edu-frontend/pull/99999. Target stage34. "
        f"{decision}\nApproved plan:\n{plan}\n{observation}\n"
        "There is no tool access here. Do not claim to execute anything. Give the "
        "ordered execution steps and concrete CLI commands you would use, including "
        "recording, cleanup, and result reporting when applicable."
    )
    out = ask([{"role": "user", "content": resume}])
    assert_test(
        LLMTestCase(input=resume, actual_output=out),
        [rubric("qa-recording-execution", criteria, threshold=0.9)],
    )
