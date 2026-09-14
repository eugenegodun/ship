# QA Results in the PR Description Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task after the user authorizes implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish Ship QA results in the PR description's `Evidence` section by default; when the applied PR template has no such section, reuse or create `QA`.

**Architecture:** Update the canonical QA agent's Phase-B reporting instructions, both orchestrator dialects, and behavioral evals. Keep this a prompt-contract change using existing GitHub CLI access; regenerate Codex artifacts from their sources.

**Tech Stack:** Markdown agent/skill definitions, GitHub CLI, Python pytest/DeepEval, existing Codex generation scripts.

**Spec:** The user's request in this task, with the concrete acceptance rules below.

## Acceptance rules and constraints

- Phase B publishes results to the PR description. It does not create a separate results comment by default. Explicit user instructions about destination take precedence.
- Read the latest PR body first. An existing `Evidence` heading wins, including when `QA` also exists. Match heading text case-insensitively and tolerate ordinary heading levels and surrounding whitespace; do not mistake prose, fenced examples, or HTML comments for headings.
- The current body normally contains the template applied at PR creation. If it lacks `Evidence`, inspect the template used for that PR (the pipeline currently uses `.github/pull_request_template.md` in the target repository). If that template contains `Evidence`, restore that heading and insert results there. Otherwise reuse an existing `QA` heading or append `## QA`.
- Do not choose an arbitrary alternate template when several exist. If the applied template cannot be established, use the current body as the available structure and fall back to `QA`; state that limitation in the final report only when relevant.
- Preserve existing prose, screenshots, checklists, template guidance, and other sections, including human-authored content inside `Evidence` or `QA`.
- Own only a bounded block delimited by `<!-- qa-agent-results -->` and `<!-- /qa-agent-results -->`. On reruns replace that block; do not duplicate results or headings. If an existing owned block is under `QA` and `Evidence` becomes available, move the block into `Evidence`, retaining surrounding human content.
- If markers are malformed or duplicated and ownership is ambiguous, do not delete guessed ranges. Return the results with a publication failure explanation rather than claiming success.
- Keep the existing verdict line, approved test-case IDs, four-column results table, recording links/fallbacks, and relevant flag/environment notes. The final response repeats the same results and links to the PR description, with a section anchor when unambiguous.
- No PR mutation during Phase A. Keep the existing QA approval gate, provisioning, execution, recording behavior, and browser cleanup requirements.
- Publication failure is separate from the test verdict: retain the results in-session, report the write failure, and do not silently fall back to a comment.

## Task 1: Update and exercise the QA publication contract

**Files:**
- Modify `plugins/ship/agents/qa-agent.md`.
- Modify `evals/agents/qa/test_qa_agent.py`.
- Create `evals/agents/qa/fixtures/pr_reporting_cases.json`.

**Interface:** Phase B still consumes the approved plan, PR reference, target stage, and recording decision. It returns the existing verdict/table plus a description link and an accurate publication status.

- [x] Add fixtures with complete PR bodies, applied template text, executed test outcomes, and expected target sections. Cover: existing Evidence; template Evidence missing from body; no Evidence with existing QA; neither section; empty body; both headings; a rerun with old marked results; human evidence surrounding the block; heading-like text in code/comments; and failed publication.
- [x] Add parametrized model-backed reporting tests using the existing `ask`, `LLMTestCase`, and `rubric` helpers. Supply an approved, completed QA run and ask for the exact proposed body and publication steps, without live GitHub access. Judge section selection, preservation of supplied human content, one owned block, accurate verdict/table/recording retention, and no default comment. Use exact string/count assertions for fixture content preservation and duplicate markers where output is structured. These test generated behavior, not whether instructions contain keywords.
- [ ] Run the new reporting tests against the current agent and confirm the default-comment cases fail for the intended reason.
- [x] Rewrite Phase-B steps 5–6 with the acceptance rules above. Include this publication sequence:

  ```text
  gh pr view <ref> --json body,url
  Read the applied target-repository PR template when needed.
  Build the merged body in a temporary UTF-8 file using a file-writing tool.
  Re-read the current body before editing; if it changed, reapply the merge to the latest body.
  gh pr edit <ref> --body-file <absolute-temp-file>
  gh pr view <ref> --json body,url
  Verify the owned results block and preserved surrounding content before reporting publication success.
  ```

  Do not interpolate result text into shell commands. Section boundaries end at the next heading of the same or higher level. This read/merge/write sequence reduces stale-body overwrites but is not an atomic compare-and-swap; do not promise concurrency protection it does not provide.
- [x] Update the agent description, Phase-A restriction, flag notes, and guardrails that currently call the destination a comment. Phase A prohibits all PR writes, including body edits.
- [ ] Run the reporting evals and existing Phase-A/stage-adoption evals. Use mocked/supplied publication outcomes for write failures; never edit a real PR as an automated test.

## Task 2: Align orchestration, documentation, and generated artifacts

**Files:**
- Modify `plugins/ship/skills/ship/SKILL.md`.
- Modify `plugins/ship/skills/ship/references/codex-dispatch.md`.
- Modify `README.md` and `plugins/ship/agents/CHANGELOG.md`.
- Modify `evals/orchestrator/fixtures/transcripts/qa_plan_approved.json` and `qa_run_done.json`.
- Update the corresponding final-report assertions in `evals/orchestrator/test_guardrails.py` if they constrain result links.
- Regenerate `plugins/ship/codex-agents/ship-qa-agent.toml` and affected files under `plugins/ship/codex-skills/`.

**Interface:** Both Claude and Codex orchestration must accept the QA description link and relay it in the final pipeline report without expecting a results-comment URL.

- [x] Replace current QA-comment references in both orchestration sources and README, including recording copy. Preserve unrelated PR comments such as `/dynamic` and historical changelog entries.
- [x] Update the Phase-B resume/completion transcript and final-report regression to point to results in `Evidence` or `QA`; preserve stage, approval, recording, and token-accounting scenarios.
- [x] Record the reporting-output contract change in the changelog. Under the repository's current breaking-output version rule, plan `qa-agent` 4.0.0 and `ship` 6.0.0, update the compatibility floor and README, and bump all plugin/marketplace package versions together to the next available release version at implementation time.
- [x] Regenerate rather than editing generated Codex files:

  ```sh
  python3 plugins/ship/scripts/sync_codex_agents.py
  python3 plugins/ship/scripts/sync_codex_skills.py
  python3 plugins/ship/scripts/sync_codex_agents.py --check
  python3 plugins/ship/scripts/sync_codex_skills.py --check
  ```

- [ ] From `evals/`, run `uv run pytest tests/ -q` for deterministic sync/manifest regressions, then `uv run pytest agents/qa/test_qa_agent.py orchestrator/test_guardrails.py -q` for the changed behavioral contract. Load only necessary saved API keys into the eval subprocess environment using the user's credential instructions.
- [x] Review the final diff for contradictory comment defaults and confirm only intended generated files changed. Report eval outcomes and any unverified live-GitHub behavior.

## Completion criteria

The reporting cases select the requested section, preserve human PR content, update owned results on reruns, and retain the existing QA report format. Both orchestrators link to the description, generated artifacts pass drift checks, and a failed PR edit is reported honestly without changing the QA verdict.

## Scope of this planning turn

Only this plan is written. Agent instructions, tests, versions, installed plugins, and GitHub PRs are not modified during planning.


## Implementation status — 2026-09-11

Implemented in `/private/tmp/ship-qa-description` on `codex/qa-results-description`, based on
`codex/remove-ship-spec` at `f64a530`. Package version is 1.13.0; QA agent is 4.0.0 and Ship is 6.0.0.
Source instructions, orchestration, fixtures, versions, and generated Codex files are updated.
The QA reporting eval includes 18 synthetic scenarios and deterministic checks of the evaluator.

Model-backed red/green and orchestrator runs remain unverified. Neither prescribed saved API-key
file exists, and automatic approval review rejected sending repository prompts/fixtures to model
providers without more explicit authorization. User input was requested; no live PR was edited.

Local verification uses the existing eval Python environment with this worktree's `evals/src`
on `PYTHONPATH`. Pytest plugin autoload is disabled because an unrelated installed rerun plugin
attempts to bind a local socket, which the sandbox rejects. Generation drift checks and diff
whitespace checks pass. Final focused local suite: **90 passed, 21 skipped** (78 existing deterministic tests plus 12
reporting-evaluator tests; 20 QA model tests and one orchestrator model test skipped for missing
credentials). Read-only review and the scoped evaluator fix review found no blocking issues. No claim of live model behavior or live GitHub publication is made.
