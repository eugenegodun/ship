# QA Screenshots and Dynamic Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Keep the existing video choice, add optional feature screenshots to the same PR-description section, and replace the default stage40/localhost selection with permission to start a test environment by posting `/dynamic`.

**Architecture:** The orchestrator gathers the choices at GATE 2 and relays them to the existing QA agent. After approval, the QA agent owns dynamic startup, target resolution, execution, evidence uploads, and the existing bounded PR-description update. Update canonical Claude and Codex orchestration sources and regenerate derived files.

**Tech Stack:** Markdown agent/skill instructions, generated Codex Markdown/TOML, GitHub CLI, Playwright CLI, internal static hosting, Python/pytest/deepeval.

**Spec:** The requirements and acceptance criteria below capture the user's planning request. This document does not authorize implementation or a live `/dynamic` comment.

## Global constraints

- Planning only until implementation is requested.
- Preserve the video question, `--record` pre-answer, per-case capture boundaries, and best-effort recording behavior.
- Preserve the QA plan approval gate, deferred PR reference, and reuse of the same QA agent.
- No translation edits or tautological prompt-string tests.
- Preserve unrelated working-tree changes, including the existing portable-layout plan.
- Preserve explicit user environment choices; remove the implicit localhost/stage40 fallback from pipeline execution.
- Only the QA agent posts the authorized startup comment, avoiding duplicate ownership between agent and orchestrator.
- No live deployment or PR publication is needed for implementation verification; use simulated responses and local browser evidence.

## Intended interaction

Show the QA plan verbatim at GATE 2 and collect approval plus these independent choices in the same interaction:

1. **“Record video of this QA run?”** Yes / No. Keep the existing behavior: skip when `--record` or an earlier explicit choice already answers it.
2. **“Take screenshots of the feature and add them to the PR description?”** Yes / No. Reuse an earlier explicit choice rather than asking again.
3. **“Start the testing server by posting `/dynamic` to this PR?”** Yes / No. Explain that Yes permits the comment and waiting for deployment before testing.

Approval of the plan alone does not imply Yes to either new choice. A Yes to startup alone does not approve execution of the QA plan. Keep unanswered required choices pending rather than inventing answers. Do not ask the old stage40/localhost question. If the user already supplied a target, honor it; ask about startup only when still needed.

On a declined startup, use an explicitly provided existing target. If none exists, ask for an existing test URL/environment or let the user defer QA. Do not automatically choose localhost. Explicit localhost remains supported with its existing stage40 backing configuration.

## Behavior and acceptance criteria

### Startup and target resolution

1. Phase A remains read-only and returns the plan. No `/dynamic` comment, fixtures, browser execution, or PR body edits before the appropriate approval.
2. The Phase-B handoff carries plan approval, PR URL, `start_dynamic` Yes/No, `screenshots` Yes/No, the existing recording decision, and any explicit target. Do not introduce new invocation flags for these choices.
3. When approved and `start_dynamic=yes`, record the PR head SHA and post one comment whose body is exactly `/dynamic`. Retain its ID/URL and timestamp in the execution state.
4. Wait for deployment status attributable to that request and PR revision. Obtain the browser URL and fixture/Crew environment from actual deployment metadata. Never derive a stage number from the PR number or assume a dynamic environment is necessarily a `stageN` host.
5. Use the same resolved deployment for browser, fixture provisioning, and Crew operations. If metadata does not establish the fixture/admin mapping, report what is missing and request the target mapping; never provision data on a guessed stage.
6. Confirm deployment success for the intended revision before provisioning or browsing. HTTP reachability alone is insufficient. Recheck the head if it changes while waiting; do not report testing the new revision against an older deployment.
7. Poll at bounded intervals (proposed default: 30 seconds, up to 20 minutes), with progress updates. On terminal failure or timeout, report the observed status and build link and leave QA pending. Do not silently fall back or automatically post another `/dynamic`.
8. On resumed execution, use the retained request identity instead of reposting. If the comment write response is ambiguous, read back comments to determine whether that request succeeded before considering another write. Old unrelated `/dynamic` comments are not proof of this request's completion.

### Screenshots and publication

9. `screenshots=yes` captures representative visible feature states reached during the approved test execution, including successful states. Capture distinct meaningful states rather than every click. Identify each screenshot with approved case ID/title, state, and user role where relevant.
10. Keep video and screenshots independent: screenshot-only, video-only, both, and neither must work. The opt-in adds passing-feature screenshots; existing diagnostic screenshots for failures/visual checks remain available when the new option is declined. Decline means no new feature screenshot gallery or gallery upload.
11. Allocate a unique run ID and collision-resistant PNG names, for example `~/.ship/qa-screenshots/<TICKET>/<TICKET>-qa-<run-id>-<ordinal>-<case-slug>-<role>-<state>.png`. Use the actual authenticated session and verify each file exists before upload. Capture actual observed states; never replay a failed test just for nicer evidence.
12. Upload via `devex:internal-static-hosting` under the inferred username prefix at `qa-screenshots/<TICKET>/`. Verify hosted URLs and retain local files. Capture/upload failures are reported per screenshot and do not alter test verdicts.
13. Put screenshot captions and Markdown image embeds within the existing `<!-- qa-agent-results -->` block in **Evidence**, falling back to **QA** under the current placement rules. Screenshots and videos must be in the same section; do not create an independent screenshot section elsewhere or a results comment.
14. Example inside the owned block:

    ```markdown
    **Screenshots** (VPN-only)
    TC1: Update setting — student — saved name
    ![TC1: Update setting — student — saved name](<verified-hosted-image-url>)
    ```

    The angle-bracket URL stands for the verified tool-returned URL, never an invented link. Private hosting may not render through GitHub's image proxy; include a labeled direct link as well and accurately state the VPN requirement.
15. Preserve existing human screenshots/prose, the QA results table, video links, environment/flag facts, bounded-block replacement, and publication read-back verification. On upload failure include the labeled local fallback as text, not a broken image embed. Include screenshot evidence and failures in the in-session report too.

## Task 1: Update approval and Phase-B handoff in both runtimes

**Files:**
- Modify `plugins/ship/skills/ship/SKILL.md`.
- Modify `plugins/ship/skills/ship/references/codex-dispatch.md`.
- Modify `evals/orchestrator/test_parallel_qa.py` and relevant fixtures under `evals/orchestrator/fixtures/transcripts/`.
- Create `evals/orchestrator_codex/test_codex_qa_choices.py` and matching fixtures under `evals/orchestrator_codex/fixtures/transcripts/`.

**Interface:** Approved Phase-B brief contains independent startup, screenshot, and recording decisions plus PR reference and optional explicit environment. Claude resumes with `SendMessage`; Codex resumes with `followup_task`.

- [x] Add behavioral transition evals for unanswered GATE 2, pre-answered `--record`, all choices answered, startup declined with/without an explicit target, and requested plan revisions. Assert no premature resume or external write, preserved video behavior, new questions, and full handoff to the same agent.
- [x] Run these focused evals against current instructions and inspect failing outputs to establish the missing behavior.
- [x] Rewrite GATE 2, invocation/default-target notes, deferred-environment brief, state summaries, guardrails, and final-report summaries to match the contract above. Keep Phase A independent of startup and evidence choices.
- [x] Add explicit instructions that the orchestrator does not post `/dynamic`; its job is to pass the user's decision to QA.
- [x] Run the focused Claude and Codex transition evals after regeneration in Task 3.

## Task 2: Implement dynamic startup and screenshots in the QA agent

**Files:**
- Modify `plugins/ship/agents/qa-agent.md`.
- Modify `evals/agents/qa/test_qa_agent.py`.
- Modify `evals/agents/qa/fixtures/pr_reporting_cases.json`.

**Interface:** Consume the handoff from Task 1. Produce a resolved deployment or an actionable pending status, real screenshots/videos when requested, and one verified PR-description results block.

- [x] Establish the deployment metadata contract read-only before finalizing the agent instructions: inspect the target repository's dynamic workflow or a representative completed PR deployment to identify where request/build identity, revision, readiness, browser URL, and fixture/Crew mapping are reported. The Ship repository currently documents stage defaults but does not establish these response fields. Encode only observed fields; missing mappings use criterion 5 rather than fabricated endpoints.
- [x] Add model-backed execution scenarios with supplied deployment observations: pending → ready; terminal failure; timeout; unrelated old deployment; changed PR head; ambiguous comment response; repeated resume with retained comment ID; declined startup; missing fixture mapping. Check ordered actions and concrete commands against the observations, not wording in the source prompt.
- [x] Extend agent inputs and add a resolve/start/wait step before fixture provisioning. Illustrative authorized write:

  ```bash
  gh pr view "$PR_URL" --json headRefOid,url
  gh pr comment "$PR_URL" --body '/dynamic'
  ```

  These commands are planned execution instructions, not commands to run during implementation. Keep the request identity and resolved deployment facts in the structured report.
- [x] Replace implicit target defaults in pipeline input resolution, approval-channel text, provisioning, URL rewriting, and guardrails. Retain explicitly selected local/stage support.
- [x] Add screenshot execution evals for all four video/screenshot combinations, passing visible state, multi-user labels, capture failure, and partial upload failure. Use fixed approved plans and known tool observations.
- [x] Add screenshot capture during the existing per-case execution loop, with shared run identity, unique state filenames, verification, uploads, and local fallbacks. Read the installed Playwright CLI help during implementation to use its supported screenshot/path flags.
- [x] Extend PR reporting fixtures with both media types, screenshot-only output, upload failure, existing human screenshots, repeated owned-block replacement, and failed body read-back. Assert exact supplied links/captions and preservation of unowned content; add evaluator mutation cases for lost screenshots and incorrect URLs.
- [x] Run the focused QA behavior and publication evals. Keep the existing recording boundary and stage-adoption regressions.

## Task 3: Regenerate, document, and verify

**Files:**
- Modify `README.md` and `plugins/ship/agents/CHANGELOG.md`.
- Update six release manifests listed in `evals/tests/test_manifest_versions.py` and that test's expected version.
- Generate `plugins/ship/codex-agents/ship-qa-agent.toml` and the `plugins/ship/codex-skills/` tree; never edit generated files by hand.

**Interface:** Both distributed runtimes expose the same approval, target-resolution, and evidence behavior.

- [x] Document the new questions, declined-startup behavior, independent media choices, publication destination, and VPN-only evidence links.
- [x] At implementation time confirm current versions; proposed minor increments from this checkout are QA agent 4.1.0 → 4.2.0, orchestrator 6.0.2 → 6.1.0, and package 1.14.0 → 1.15.0.
- [x] Regenerate and check:

  ```bash
  python3 plugins/ship/scripts/sync_codex_agents.py
  python3 plugins/ship/scripts/sync_codex_skills.py
  python3 plugins/ship/scripts/sync_codex_agents.py --check
  python3 plugins/ship/scripts/sync_codex_skills.py --check
  git diff --check
  ```

- [x] From `evals/`, run unit tests and affected behavioral suites:

  ```bash
  uv run pytest tests -v
  uv run deepeval test run agents/qa orchestrator/test_parallel_qa.py -v
  uv run pytest orchestrator_codex -m codex -v
  ```

  Load saved credentials only into eval subprocesses under the user's existing credential instructions. No secrets in tool arguments/output. Inspect each failure before changing expectations.
- [x] Smoke-test screenshot capture on a disposable local page using a dedicated Playwright session. Check a passing state image and the screenshot/video combination; inspect the images. Use mocked uploads and PR responses for publication checks, with no live `/dynamic` comment.
- [x] Review the final diff for stale implicit defaults, duplicate startup ownership, repeated questions, lost media on update, and generated-source drift. Report simulated verification separately from any real browser smoke test; neither proves a live dynamic deployment succeeds.

## Planning review

- All three requested improvements map to tasks and behavior checks.
- Video behavior stays intact, screenshots join the existing owned results block, and startup is explicitly authorized.
- Deployment response fields remain an implementation discovery dependency, with a defined stop condition rather than a guessed environment.
- Only this plan is added during the planning turn. No implementation, eval run, deployment, or PR write has been performed.


## Implementation evidence (2026-09-15)

- Approved in-session. Implementation is isolated at `/private/tmp/ship-qa-screenshots-dynamic`
  on `codex/qa-screenshots-dynamic`, forked from main `4d9792d`.
- Deployment metadata inspected read-only from `preply/jenkins-infra` at
  `6c37f767ddb5866e3dee658a841afb18a1d3604e`: Dynamic_Flow/Jenkinsfile,
  vars/github.groovy, and Common/github_router/Jenkinsfile. The observed apollo flow reports
  commit context `Dynamic status`, build target_url, and a bot success comment with allocated
  browser URL plus seven-character deployed SHA. Other repositories require their own verified mapping.
- Repository version rules override the proposed minor agent versions: orchestrator 7.0.0,
  QA agent 5.0.0, package 1.15.0. The changed handoff/default target is a breaking contract.
- Baseline 95 unit tests passed. Updated deterministic tests: 183 passed before final review fixes.
- New screenshot regression failed against the baseline (score 0.607 below 0.9), identifying
  missing local-file verification and upload/reporting detail. A later judge error penalizing
  hypothetical execution in a no-tools test was corrected by clarifying the evaluator scope.
- Real local Playwright smoke: passing screenshot-only and screenshot-plus-video cases completed.
  Both PNGs were inspected and show their distinct saved states; the WebM finalized successfully.
  Evidence is retained under `/private/tmp/ship-qa-screenshot-smoke/`; the owned browser is closed.
- No live `/dynamic` comment, fixture provisioning, upload, or PR-description write was performed.
- Product review found no correctness blockers. Final review identified two evaluator defects
  (negated execution wording and choice-answer association). Both were fixed and verified with
  deterministic counterexamples and six passing affected model transitions.

- QA model verification is complete across the full run and focused corrections: all 45 current
  model scenarios passed. The initial full run had 123 passes and five failures; three failures
  were the evaluator requiring angle-bracket Markdown links, one used unverified deployment
  fixture metadata, and one combined response was empty. Corrected dynamic/publication fixtures
  passed; combined screenshot scenarios were split into single workflows. All six final screenshot
  cases passed together. Diagnostics now identify truncated/empty model responses before judging.
- Final verification: 199 deterministic tests passed; 45 QA model scenarios passed across the full
  and focused correction runs; 15 focused Claude/Codex gate transitions passed; all 19 existing
  Codex model regressions passed. Generated-role/skill drift and whitespace checks passed.
  The QA model runs emit the existing deepeval event-loop deprecation warning; no unresolved failures.
- Final review corrections are complete. The choice parser binds an immediate Boolean to its field;
  execution checks distinguish local prohibitions from later affirmative actions. Regression examples
  cover unpunctuated neighboring fields, never/must-not, and affirmative execution after a prohibition.
- Implementation is saved locally on the feature branch; no push, PR publication, or merge performed.
