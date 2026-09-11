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
    assert_report_facts(case, report)
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in report.splitlines() if line.strip().startswith("|")]
    assert ["Test Case", "Description", "Status", "Notes"] in rows
    case_rows = [row for row in rows
                 if row != ["Test Case", "Description", "Status", "Notes"]
                 and not all(re.fullmatch(r":?-+:?", cell) for cell in row)]
    assert case_rows == results["rows"], "Retain exactly the approved cases and four-column results"


def report_urls(report):
    return [url.rstrip(".,;") for url in re.findall(r"https?://[^\s<>\[\]()`]+", report)]


def assert_report_facts(case, report):
    """Check stable facts; the rubric judges meaning and contradictions in prose."""
    facts = case["report_facts"]
    plain = report.replace("`", "").replace("**", "")
    assert re.search(r"\b" + re.escape(facts["stage"]) + r"\b", plain)
    assert re.search(r"\b" + re.escape(facts["flag"]) + r"\b", plain)
    # Require both state facts without prescribing sentence order. The semantic
    # rubric owns attribution/direction; reject only an explicit reversed transition
    # here, not harmless forms such as 'enabled for QA (originally off)'.
    off, on = r"(?:off|disabled|false)", r"(?:on|enabled|true)"
    assert re.search(r"\b" + off + r"\b", plain, re.I), "Retain the original off state"
    assert re.search(r"\b" + on + r"\b", plain, re.I), "Retain the tested on state"
    assert not re.search(r"\b" + on + r"\s*(?:to|→|->)\s*" + off + r"\b", plain, re.I), \
        "Do not reverse the supplied flag transition"
    status = facts["recording_status"]
    if status == "hosted":
        assert facts["recording_url"] in report_urls(report), "Retain the exact hosted recording URL"
        assert re.search(r"\bVPN\b", report, re.I), "Retain the recording's VPN access limitation"
    elif status == "upload_failed":
        assert facts["recording_path"] in re.findall(r"/[^\s<>\[\]()`]+", report)
        assert re.search(r"upload.{0,100}(?:fail|error)|(?:fail|error).{0,100}upload", plain, re.I | re.S)
    else:
        assert status == "capture_failed"
        assert facts["recording_command"] in plain
        assert re.search(r"exit(?:ed)?(?:\s+(?:code|status))?\s*[:=]?\s*"
                         + str(facts["recording_exit_code"]) + r"\b", plain, re.I)
        assert re.search(r"fail|error", plain, re.I)
        assert re.search(r"unrecorded|without (?:a )?recording", plain, re.I)


def assert_description_link(case, report):
    urls = [url.rstrip(".,;") for url in report_urls(report)]
    links = [url for url in urls if url == PR_URL or url.startswith(PR_URL + "#")]
    assert links, "Link to the PR description; its section anchor is optional"
    for link in links:
        if "#" in link:
            assert link.split("#", 1)[1] == case["expected_section"].lower(), \
                "An included anchor must identify the selected results section"


def assert_publication_result(case, structured):
    """A prepared write, a persisted body, and verified publication are distinct."""
    outcome = case["expected_publication"]
    proposed, saved = structured["proposed_body"], structured["saved_body"]
    original = case.get("latest_body", case["body"])
    assert structured["publication_status"] == ("success" if outcome == "success" else "failed")
    if outcome == "refused":
        assert proposed is None, "Ambiguous ownership must refuse the write before preparing a payload"
        assert saved == original, "Refusal must leave human content and ambiguous markers untouched"
    else:
        assert isinstance(proposed, str), "A write attempt needs its proposed payload even if denied"
        assert_reporting_body(case, proposed)
        if outcome == "success":
            assert saved == proposed, "Successful read-back must match the proposed merged body"
        elif outcome == "write_denied":
            assert saved == original, "A denied write did not publish the proposed results"
        elif outcome == "readback_mismatch":
            assert saved == case["readback_body"], "Report the supplied actual read-back, not the proposal"
        else:
            assert outcome == "readback_unknown"
            assert saved is None, "Failed read-back cannot establish the persisted body"
    final = structured["final_report"]
    assert_report_content(case, final)
    if outcome == "success":
        assert_description_link(case, final)
    elif outcome == "write_denied":
        assert re.search(r"\b403\b", final), "Retain the actual publication denial error"
    elif outcome == "readback_unknown":
        assert re.search(r"\b502\b", final), "Retain the actual read-back error"
    elif outcome == "readback_mismatch":
        assert re.search(r"read.?back|verif", final, re.I), "Explain the verification failure"


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
        "Return only JSON with keys proposed_body (the exact complete write payload, even "
        "when an attempted edit is denied; null only for refusal before a write), "
        "saved_body (the actual persisted body: the verified proposal on success, the "
        "unchanged latest body on write denial or pre-write refusal, readback_body when "
        "supplied, or null when read-back is unavailable), publication_steps (ordered array "
        "of actions/commands), publication_status (success or failed), final_report "
        "(exact report you return in-session). Report the simulated outcome accurately.\n\n"
        + json.dumps({key: case[key] for key in (
            "body", "applied_template", "latest_body", "template_context",
            "executed_results", "publication_outcome", "readback_body",
        ) if key in case}, ensure_ascii=False)
    )
    out = ask([{"role": "user", "content": prompt}])
    structured = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", out.strip()))
    assert_publication_result(case, structured)
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
        "recording and flag/environment facts, allowing equivalent wording. Both the proposed "
        "body (when a payload exists) and final report must accurately attribute the off-to-on transition to "
        "exp_lesson_reschedule_v1 on stage34, retain the recording URL/path or capture "
        "error and its exit code, and explain VPN access or recording/upload failure "
        "without contradicting those facts. It accurately separates publication "
        "failure from the failing QA test verdict, does not claim a failed write "
        "succeeded and does not fall back to comments. Successful reports link to the "
        "PR description (a base PR URL is sufficient; any included section anchor must "
        "match the selected section). Unknown applied templates are not guessed. The "
        "saved_body represents observed persisted state; proposed_body represents the "
        "attempted write. Failed or unverified publication is never claimed as success.",
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


CI_REGRESSIONS = json.loads((FIXTURES / "pr_reporting_ci_regressions.json").read_text())["cases"]


@pytest.mark.parametrize("regression", CI_REGRESSIONS, ids=lambda item: item["case_id"])
def test_ci_reporting_regressions(regression):
    case = next(case for case in REPORTING_CASES if case["id"] == regression["case_id"])
    if "report" in regression:
        assert_report_content(case, regression["report"])
        if regression["case_id"] in {"existing_evidence", "move_owned_block"}:
            assert_description_link(case, regression["report"])
    else:
        _, _, report = _sample_reporting_body()
        assert_publication_result(case, {
            "proposed_body": case["body"] + "\n" + report,
            "saved_body": regression["saved_body"],
            "publication_status": "failed",
            "final_report": report + "\nPublication failed: HTTP 403 Resource not accessible by integration.",
        })


@pytest.mark.parametrize("note", [
    "Environment: stage34; flag `exp_lesson_reschedule_v1` was flipped from **off** → **on**.",
    "Stage: stage34. Experiment exp_lesson_reschedule_v1 changed from disabled to enabled for QA.",
    "stage34; exp_lesson_reschedule_v1 initially off; enabled for the run.",
    "stage34; exp_lesson_reschedule_v1 enabled for QA (originally off).",
])
def test_reporting_accepts_equivalent_environment_facts(note):
    case, _, report = _sample_reporting_body()
    assert_report_content(case, report.replace(case["executed_results"]["environment"], note))


@pytest.mark.parametrize("mutation", [
    "wrong_stage", "wrong_flag", "reversed_flag", "missing_original_state",
    "wrong_recording_url", "missing_vpn", "wrong_capture_exit", "lost_capture_error",
    "wrong_local_path", "lost_upload_error",
])
def test_reporting_rejects_incorrect_or_missing_facts(mutation):
    case, _, report = _sample_reporting_body()
    if mutation in {"wrong_capture_exit", "lost_capture_error"}:
        case = next(case for case in REPORTING_CASES if case["id"] == "recording_capture_failed")
        report = report.replace(REPORTING_CASES[0]["executed_results"]["recording"], case["executed_results"]["recording"])
    elif mutation in {"wrong_local_path", "lost_upload_error"}:
        case = next(case for case in REPORTING_CASES if case["id"] == "recording_upload_failed")
        report = report.replace(REPORTING_CASES[0]["executed_results"]["recording"], case["executed_results"]["recording"])
    replacements = {
        "wrong_stage": ("stage34", "stage40"),
        "wrong_flag": ("exp_lesson_reschedule_v1", "exp_unrelated_v1"),
        "reversed_flag": ("off to on", "on to off"),
        "missing_original_state": ("changed from off to on", "was on"),
        "wrong_recording_url": ("LEX-2101.webm", "LEX-9999.webm"),
        "missing_vpn": ("(VPN-only)", ""),
        "wrong_capture_exit": ("exited 1", "exited 2"),
        "lost_capture_error": ("capture failed: video-start exited 1", "capture succeeded"),
        "wrong_local_path": ("/tmp/LEX-2101-qa.webm", "/tmp/wrong.webm"),
        "lost_upload_error": ("upload failed", "upload succeeded"),
    }
    before, after = replacements[mutation]
    with pytest.raises(AssertionError):
        assert_report_content(case, report.replace(before, after))


@pytest.mark.parametrize("suffix", ["", "#evidence"])
def test_description_link_accepts_base_or_correct_section(suffix):
    assert_description_link(REPORTING_CASES[0], "[QA results](" + PR_URL + suffix + ")")


@pytest.mark.parametrize("url", [PR_URL + "#qa", PR_URL + "#issuecomment-123", PR_URL + "0", "https://example.com/#evidence"])
def test_description_link_rejects_wrong_destination(url):
    with pytest.raises(AssertionError):
        assert_description_link(REPORTING_CASES[0], "[QA results](" + url + ")")


def _publication_response(outcome):
    case = next(case for case in REPORTING_CASES if case["expected_publication"] == outcome)
    _, _, report = _sample_reporting_body()
    original = case.get("latest_body", case["body"])
    if outcome == "success":
        _, proposed, _ = _sample_reporting_body()
    elif outcome == "refused":
        proposed = None
    else:
        proposed = original + "\n" + report
    saved = proposed if outcome == "success" else original
    if outcome == "readback_unknown":
        saved = None
    explanation = {
        "success": "Published to " + PR_URL,
        "write_denied": "Publication failed: HTTP 403 Resource not accessible by integration.",
        "readback_mismatch": "Publication failed: read-back did not contain the submitted results.",
        "readback_unknown": "Publication verification failed: HTTP 502; saved body unknown.",
        "refused": "Publication refused: unmatched marker; body untouched.",
    }[outcome]
    return case, dict(proposed_body=proposed, saved_body=saved,
                     publication_status="success" if outcome == "success" else "failed",
                     final_report=report + "\n" + explanation)


@pytest.mark.parametrize("outcome", ["success", "write_denied", "refused", "readback_mismatch", "readback_unknown"])
def test_publication_evaluator_distinguishes_proposed_and_saved_body(outcome):
    case, response = _publication_response(outcome)
    assert_publication_result(case, response)


@pytest.mark.parametrize("outcome,mutation", [
    ("write_denied", "saved_proposal"), ("write_denied", "missing_proposal"),
    ("write_denied", "claimed_success"), ("write_denied", "missing_error"),
    ("refused", "prepared_write"), ("refused", "altered_saved_body"),
    ("readback_mismatch", "saved_proposal"), ("readback_mismatch", "claimed_success"),
    ("readback_unknown", "saved_proposal"), ("readback_unknown", "claimed_success"),
    ("success", "altered_saved_body"),
])
def test_publication_evaluator_rejects_unverified_or_false_persistence(outcome, mutation):
    case, response = _publication_response(outcome)
    if mutation == "saved_proposal":
        response["saved_body"] = response["proposed_body"]
    elif mutation == "missing_proposal":
        response["proposed_body"] = None
    elif mutation == "claimed_success":
        response["publication_status"] = "success"
    elif mutation == "missing_error":
        response["final_report"] = response["final_report"].replace("403", "500")
    elif mutation == "prepared_write":
        response["proposed_body"] = case["body"]
    elif mutation == "altered_saved_body":
        response["saved_body"] = "## Summary\nInvented saved content.\n"
    with pytest.raises(AssertionError):
        assert_publication_result(case, response)
