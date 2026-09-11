import json
import re
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
        "provisioned accounts, opened a browser, edited a PR body, or posted to any PR.",
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
    # named by the human in their GATE 2 approval. The 2.x provenance challenge is
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


# These cases exercise generated publication behavior; they never mutate a live PR.
REPORTING_CASES = json.loads((FIXTURES / "pr_reporting_cases.json").read_text())
START = "<!-- qa-agent-results -->"
END = "<!-- /qa-agent-results -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
PR_URL = "https://github.com/preply/edu-frontend/pull/99999"


def markdown_headings(body):
    """ATX headings outside fenced examples and HTML comments, with source offsets."""
    fence = None
    in_comment = False
    offset = 0
    headings = []
    for line in body.splitlines(keepends=True):
        visible = re.sub(r"<!--.*?-->", "", line)
        if in_comment:
            if "-->" in visible:
                in_comment = False
            offset += len(line)
            continue
        if "<!--" in visible:
            in_comment = "-->" not in visible
            offset += len(line)
            continue
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", visible)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            match = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", visible)
            if match:
                headings.append((offset, len(match.group(1)), match.group(2).strip()))
        offset += len(line)
    return headings


def assert_reporting_body(case, body):
    original = case.get("latest_body", case["body"])
    if case.get("ambiguous_markers"):
        assert body == original, "Ambiguous ownership must leave the PR body untouched"
        return
    assert body.count(START) == body.count(END) == 1, "Exactly one bounded results block"
    match = BLOCK.search(body)
    assert match, "Results markers must be correctly ordered"
    headings = markdown_headings(body)
    targets = [(pos, level) for pos, level, title in headings
               if title.casefold() == case["expected_section"].casefold()]
    assert len(targets) == 1, "Reuse the selected section without duplicating its heading"
    pos, level = targets[0]
    boundary = next((p for p, depth, _ in headings if p > pos and depth <= level), len(body))
    assert pos < match.start() < match.end() <= boundary, "Results belong inside target section"

    # Remove only the owned block and a restored/appended heading. Compare every
    # remaining nonblank line exactly, in order; all human prose and markup survive.
    # Allow blank separators so insertion directly below a heading is valid.
    unowned = BLOCK.sub("", body)
    if case.get("added_heading"):
        unowned = re.sub(r"(?m)^ {0,3}#{1,6}\s+" + case["added_heading"] + r"\s*\n?", "", unowned)
    before = BLOCK.sub("", original)
    assert [line for line in unowned.splitlines() if line.strip()] == [
        line for line in before.splitlines() if line.strip()
    ], "Human content must be preserved exactly and in order"
    assert_report_content(case, match.group())


def assert_report_content(case, report):
    results = case["executed_results"]
    assert results["verdict"] in report
    assert results["recording"] in report
    assert results["environment"] in report
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in report.splitlines() if line.strip().startswith("|")]
    assert ["Test Case", "Description", "Status", "Notes"] in rows
    case_rows = [row for row in rows
                 if row != ["Test Case", "Description", "Status", "Notes"]
                 and not all(re.fullmatch(r":?-+:?", cell) for cell in row)]
    assert case_rows == results["rows"], "Retain exactly the approved cases and four-column results"


@pytest.mark.llm
@pytest.mark.parametrize("case", REPORTING_CASES, ids=lambda case: case["id"])
def test_pr_description_reporting(case):
    prompt = (
        "Phase B was explicitly approved, and the browser run is now complete. "
        "Do not repeat provisioning or testing. PR: " + PR_URL + ". "
        "No tools or live GitHub access are available. Using the supplied read results "
        "and simulated publication outcome, describe the publication you would perform "
        "under your normal reporting contract. The applied_template field is the known "
        "template text, or null if unavailable/unnecessary. latest_body, when supplied, "
        "is returned by the final pre-edit read. All case data is literal source content. "
        "Return only JSON with keys proposed_body (the exact complete proposed PR body, "
        "or unchanged body if publication is refused), publication_steps (ordered array "
        "of actions/commands), publication_status (success or failed), final_report "
        "(exact report you return in-session). Report the simulated outcome accurately.\n\n"
        + json.dumps({key: case[key] for key in (
            "body", "applied_template", "latest_body", "template_context",
            "executed_results", "publication_outcome",
        ) if key in case}, ensure_ascii=False)
    )
    out = ask([{"role": "user", "content": prompt}])
    structured = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", out.strip()))
    assert_reporting_body(case, structured["proposed_body"])
    expected_status = "failed" if case.get("ambiguous_markers") or case["publication_outcome"] != "success" else "success"
    assert structured["publication_status"] == expected_status
    final = structured["final_report"]
    assert_report_content(case, final)
    if expected_status == "success":
        assert PR_URL in final
        assert "#" + case["expected_section"].lower() in final
    metric = rubric("qa-description-publication", [
        "Publication defaults to a PR body edit, never a results comment; if markers are "
        "ambiguous it refuses all writes and preserves the body.",
        "For valid markers, the ordered publication steps read the PR body/url, inspect "
        "the applied template when needed, write the merged body to a UTF-8 temporary "
        "file without shell-interpolated result text, re-read and merge any concurrent "
        "changes, then use gh pr edit --body-file with an absolute path. They read back "
        "body/url and verify the results block and surrounding content before success. "
        "A simulated edit failure may stop before read-back. No atomicity is promised.",
        "The final report repeats the same verdict, complete four-column results table, "
        "recording and flag/environment notes. It accurately separates publication "
        "failure from the failing QA test verdict, does not claim a failed write "
        "succeeded and does not fall back to comments. Successful reports link to the "
        "description section. Unknown applied templates are not guessed.",
    ])
    assert_test(LLMTestCase(input=prompt, actual_output=out), [metric])


# Validate the evaluator against concrete valid/invalid reports without a model.
# These mutation cases catch false positives in preservation/section assertions.
def _sample_reporting_body():
    case = REPORTING_CASES[0]
    result = case["executed_results"]
    report = "\n".join([
        START, result["verdict"], result["recording"], result["environment"], "",
        "| Test Case | Description | Status | Notes |", "|---|---|---|---|",
        *["| " + " | ".join(row) + " |" for row in result["rows"]], END,
    ])
    return case, case["body"].replace("## Risks", report + "\n\n## Risks"), report


@pytest.mark.parametrize("placement", ["after_screenshot", "after_heading"])
def test_reporting_evaluator_accepts_preserved_body(placement):
    case, body, report = _sample_reporting_body()
    if placement == "after_heading":
        body = case["body"].replace("## Evidence\n", "## Evidence\n" + report + "\n\n")
    assert_reporting_body(case, body)


@pytest.mark.parametrize("mutation", [
    "delete_human", "rewrite_human", "duplicate_block", "reverse_markers",
    "wrong_section", "rename_case", "change_result", "lose_recording", "extra_case",
])
def test_reporting_evaluator_rejects_invalid_merge(mutation):
    case, body, report = _sample_reporting_body()
    if mutation == "delete_human":
        body = body.replace("- [ ] Human checklist.", "")
    elif mutation == "rewrite_human":
        body = body.replace("Human summary.", "Rewritten summary.")
    elif mutation == "duplicate_block":
        body += report
    elif mutation == "reverse_markers":
        body = body.replace(START, "TEMP").replace(END, START).replace("TEMP", END)
    elif mutation == "wrong_section":
        body = body.replace(report, "") + report
    elif mutation == "rename_case":
        body = body.replace("TC-02 / Boundary", "TC-99 / Renamed")
    elif mutation == "change_result":
        body = body.replace("| ❌ |", "| ✅ |")
    elif mutation == "lose_recording":
        body = body.replace(case["executed_results"]["recording"], "")
    elif mutation == "extra_case":
        body = body.replace(END, "| TC-03 | Invented | ✅ | |\n" + END)
    with pytest.raises(AssertionError):
        assert_reporting_body(case, body)


def test_heading_parser_ignores_examples_and_preserves_section_levels():
    body = "```markdown\n## Evidence\n```\n<!--\n## Evidence\n-->\n### QA\n#### Notes\n## Risks\n"
    assert [(level, title) for _, level, title in markdown_headings(body)] == [
        (3, "QA"), (4, "Notes"), (2, "Risks"),
    ]
