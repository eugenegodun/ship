# QA Case Recordings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record actual QA test execution, excluding setup and navigation between cases, to produce shorter, clearly identified evidence videos.

**Architecture:** Change the QA agent's recording instructions to start and stop a separate clip around each approved test case. Keep the existing Playwright CLI, upload mechanism, and opt-in recording decision. Generate the Codex role from the canonical Markdown agent.

**Tech Stack:** Markdown agent instructions, generated TOML, Playwright CLI, Python/pytest/deepeval.

**Spec:** The behavior and acceptance criteria below capture the investigation and the user's request to plan this improvement.

## Global Constraints

- Planning only until the user authorizes implementation.
- Recording remains opt-in and best-effort; recording/upload failures do not change test verdicts or trigger rerunning a test.
- Preserve approved case IDs and titles in reports and chapter cards.
- Keep independent browser sessions for concurrent users and use explicit session targeting for recording commands.
- Keep the existing approval gates and stage resolution.
- Do not edit translation files or add tests that merely assert prompt wording.

## Behavior and acceptance criteria

1. Provision accounts, enable flags, log in, locate elements, and navigate to the case's starting state before starting capture. Treat preconditions separately from the steps being tested.
2. Immediately before the first actual test step, start a new recording, enable action annotations, and show the approved case ID/title as a chapter card. Record navigation/login if those are actual tested steps.
3. Capture steps through the observable result, including failure evidence. Stop in a cleanup/finally path before resetting state, preparing the next case, lengthy diagnosis, uploads, or reporting. Do not discard a failed case's clip.
4. For two cases separated by reset/navigation, produce two clips with the preparation interval excluded. A blocked case whose test steps never start does not need a clip.
5. Use one run identifier and collision-resistant names within `~/.ship/qa-recordings/<TICKET>/`: `<TICKET>-qa-<run-id>-<case-slug>-<role>.webm`. Allocate unique case slugs even when sanitized titles collide; retain the exact original title in the report. Include an attempt suffix only for an independently justified retry.
6. For multi-user cases, prepare all participants first; start recording each participating session before the tested cross-user action and stop each after the outcome. Keep case/role mapping for each clip.
7. Upload completed clips using the existing static-hosting skill. Under the verdict, use one labeled line per clip: `🎥 QA recording: <case id/title> (<role>) — <hosted URL>`. If upload fails, retain the case/role label and local file path. Keep identical recording lines in the PR comment and final response.
8. If start fails, continue the case unrecorded and report the failure. If stop fails, attempt cleanup of capture without rerunning the case; do not claim the file is finalized or uploaded unless verified. If capture cannot be stopped safely, discontinue further recording in that session and report the limitation. Continue QA where browser state permits.

No video concatenation, trimming dependency, or new CLI option is needed. Pausing/resuming the same output file is not assumed. This change removes setup and transitions; it does not promise to remove agent thinking time within a case. Scripted execution to reduce that time is a separate improvement.

## Task 1: Define regression coverage and update the agent contract

**Files:**
- Modify `evals/agents/qa/test_qa_agent.py`.
- Modify `plugins/ship/agents/qa-agent.md`.
- Generate `plugins/ship/codex-agents/ship-qa-agent.toml`.

**Interfaces:** Consume the existing Phase-B approval and recording decision. Produce case/role-labeled clips and the existing results table plus recording links.

- [x] Add parametrized model-backed cases using the existing `ask`, `rubric`, and `LLMTestCase` pattern. Supply a fixed approved plan rather than generating Phase A each time. Request exact ordered CLI execution steps with no tool access; do not tell the model the desired recording boundaries in the input.

  Fixtures and judge criteria:

  | Scenario | Input | Required observable behavior |
  |---|---|---|
  | Two cases | Approved TC1 updates a setting; TC2 validates an invalid value; login and reset/navigation are preconditions; recording requested | Login/navigation precede capture; two unique output files; each stop precedes reset/navigation; each clip contains its outcome and exact case label |
  | Navigation is tested | Approved case tests a link and destination; recording requested | Capture starts before clicking the link and includes the resulting navigation |
  | Concurrent users | Approved tutor/student interaction, distinct sessions, recording requested | Setup precedes capture; explicit session targets and distinct case/role files; both relevant sessions record the cross-user action |
  | Failures | Execution reports an assertion failure, then recording-stop or upload failure | Retain available failure evidence, attempt capture cleanup, report only verified files/URLs, do not rerun the test for recording, continue remaining QA where possible |
  | Recording declined | Same approved plan, recording explicitly declined | No video start/stop or video upload actions |

- [x] Run the new recording evals against the current agent and inspect the output to establish that the boundary cases expose the existing early-start/session-wide behavior. Do not weaken rubrics to make them pass.
- [x] Rewrite the recording subsection and relevant input/description/guardrail/report wording to implement all eight acceptance criteria. Integrate start/stop inside the per-case loop rather than leaving a separate session-level instruction. Include this concrete command shape, substituting actual allocated names and session IDs:

  ```bash
  playwright-cli -s=student video-start ~/.ship/qa-recordings/LEX-2101/LEX-2101-qa-RUN-tc1-student.webm --size "1280x800"
  playwright-cli -s=student video-show-actions
  playwright-cli -s=student video-chapter "TC1: Update setting"
  # Execute TC1 and capture its observable outcome.
  playwright-cli -s=student video-stop
  ```

- [x] Regenerate the Codex role, then check drift:

  ```bash
  python3 plugins/ship/scripts/sync_codex_agents.py
  python3 plugins/ship/scripts/sync_codex_agents.py --check
  ```

- [x] Run focused agent evals from `evals/`: `uv run deepeval test run agents/qa -v`. Load saved API keys only into the subprocess environment as authorized by personal instructions; never print or embed secrets in commands.

## Task 2: Document, verify, and prepare the change for review

**Files:**
- Modify `README.md` recording description and QA section.
- Modify `plugins/ship/skills/ship/SKILL.md` session-recording summaries where needed for consistency.
- Modify `plugins/ship/agents/CHANGELOG.md`.
- Update release versions in the six manifests listed in `evals/tests/test_manifest_versions.py`, plus that test's expected version.

**Interfaces:** Preserve `--record` and the Phase-B recording-decision handoff. Document that results contain multiple labeled clips.

- [x] Describe per-case recording, excluded preconditions, retained test navigation, role labels, and local-file fallback in the README and orchestrator summaries.
- [x] Apply repository version conventions: QA agent 3.1.1 → 3.2.0 for the added workflow; package 1.10.2 → 1.11.0, subject to rechecking versions at implementation time. Wording-only orchestrator edits receive its patch bump. Record changes in the changelog and regenerate the role after final agent edits.
- [x] Run `uv run pytest tests -v` from `evals/` and the generation drift check from the repository root. Run affected recording decision-point evals if orchestrator text changes. Reuse successful focused QA eval results unless subsequent changes affect them.
- [x] Perform a local browser smoke check on a disposable page with a dedicated session: navigate before capture, record one interaction and outcome, stop, perform a visibly different reset while unrecorded, then start a second file in the same session and record another interaction. Close only the owned session. Inspect both saved clips to verify start/stop boundaries and sequential recordings preserve browser state. Do not provision a stage account or publish a PR comment for this smoke check.
- [x] Review the diff for contradictory session-wide recording instructions, correct generated output, complete labels, and unchanged opt-in semantics. Report eval outcomes and smoke-check evidence without claiming model-backed evals prove browser execution.

## Review checklist

- [x] All eight acceptance criteria map to the agent update and the stated verification scenarios.
- [x] No implementation relies on an unsupported pause/resume command or appending to the same video.
- [x] Capture covers the real failing/passing test attempt; no polished replay is substituted for evidence.
- [x] Setup/navigation exclusions do not remove actions that are themselves under test.
- [x] Existing unrelated working-tree files remain untouched.

## Execution evidence (2026-09-14)

- Implemented on `codex/qa-case-recordings`; unrelated portable-layout plan left untouched.
- Unit checks: 31 passed. Codex role drift check and `git diff --check` passed.
- The new case-boundary eval against the original HEAD agent failed as expected: the judge
  identified one recording spanning TC1 and TC2 (score 0.674, required 0.9).
- Local Playwright CLI smoke: two distinct WebM clips finalized in the same session;
  browser localStorage persisted and both test interactions reached their expected outcome.
  Decoded clips were checked frame-by-frame for the red setup/reset screen; none was detected.
  Final frames visually show each case's passing outcome. Videos and inspection artifacts are
  retained in `/tmp/ship-qa-video-smoke/`; owned browser sessions were closed.
- Initial model calls were blocked by invalid saved credentials. The user updated both keys;
  Anthropic and OpenAI authentication now succeeds. Updated-agent and handoff evals: 14 passed
  (8 QA agent cases, including 6 new recording cases; 6 pipeline checks). One existing deepeval
  event-loop deprecation warning; no test failures. Existing virtualenv Python/pytest was used
  directly because the sandbox blocked the uv cache; test processes ran with approved network/local
  socket access. Keys were loaded only into subprocesses and were never printed.
