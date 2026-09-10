# Ship Codex Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The user authorized Codex-only implementation on September 10; results and verification limits are recorded at the end.

**Goal:** Keep an authorized ship run advancing through asynchronous agent handoffs until a real approval gate, evidenced blocker, explicit user stop, or pipeline completion, with truthful progress reports.

**Architecture:** Keep the existing prompt-based orchestrator and Codex custom roles. Define the result-processing loop exclusively in the Codex dispatch reference, and strengthen the Codex implementer through a role-specific overlay composed by the Codex generator. Leave the shared skill and Claude agent sources byte-for-byte unchanged. This repository does not own the Codex scheduler: these changes improve model behavior and detect regressions, but cannot guarantee resumption after an app shutdown, runtime interruption, or a model ignoring the instructions.

**Tech Stack:** Markdown skill/agent sources, generated TOML roles, Python/pytest, existing OpenAI chat-completions eval driver.

**Spec:** Requirements and incident evidence below, derived from the September 10 investigation of “LEX-1724-survey.” No separate product spec is required.

## Global constraints and incident evidence

- Scope is **Codex only**, per the user's explicit September 10 correction. Do not modify `plugins/ship/skills/ship/SKILL.md`, any `plugins/ship/agents/*-agent.md`, the shared Codex `_preamble.md`, or the Claude eval harness/scenarios. Package metadata and release documentation may change across manifests because the repository uses one package version.
- Preserve all existing approval gates, the three-review-round cap, review-before-commit, deferred QA execution, and recording preferences.
- Preserve exact canonical child identities, one implementer/worktree per run, and one QA agent; reviewers remain fresh per round.
- Do not run product work, external writes, installation, or the original ticket as part of implementing these regressions. Simulate child tools in evals.
- Keep Codex-specific tool vocabulary in the dispatch reference, as the existing structural test requires.
- Do not modify translation catalogs or add tests that merely assert the new prose exists.
- At 11:02:39 Kyiv time the parent resumed the implementer; at 11:02:42 it finalized. The child returned incomplete work at 11:03:30; the next resume was at 11:21:08 after user input.
- At 11:52:52 the parent resumed fixes and finalized three seconds later. The child completed at 12:01:58; re-review started at 12:10:35 after user input.
- Normal task completion is recorded at these parent exits. The observed failure is premature finalization, not evidence of a runtime crash.

## Required behavior in Codex

| Observed condition | Required next action |
|---|---|
| Child was just spawned/resumed | Continue independent pipeline work or wait; do not finalize a progress report. |
| Wait times out; child still running | Keep waiting, with periodic truthful commentary; timeout is not completion or failure. |
| Another child produces a result | Route it by exact identity; retain queued QA plans while review/PR work continues. |
| Child completes with unfinished authorized work | Resume the same child with the specific remaining work, then wait. |
| Child completes with sufficient evidence for its stage | Immediately advance the corresponding pipeline stage. |
| Required handoff evidence is missing | Request it from the same child before advancing. |
| Child asks an internal question | Answer from available plan/context; ask the user only for genuinely missing decisions or authorization. |
| Same unfinished result repeats without progress | Send a diagnostic follow-up asking for the concrete failure and attempted recovery; if it still cannot progress, report an explicit stall and recovery decision, not a background-work claim. |
| Genuine external blocker or review cap | Explain the exact blocker, completed/remaining work, worktree/branch, QA state, and required user action; stop appropriately. |
| User asks for status while work is authorized | Answer in commentary and continue; only an explicit pause/cancel changes the execution scope. |
| Approval gate or completed pipeline | Emit the appropriate final report/question and stage table. |

## Task 1: Make asynchronous continuation observable in the eval harness

**Files:**
- Modify `evals/src/ship_evals/codex_harness.py`.
- Modify `evals/src/ship_evals/codex_tools.py` descriptions to match actual tool behavior.
- Modify `evals/tests/test_codex_harness.py`.
- Create `evals/src/ship_evals/codex_scenarios.py` and `evals/tests/test_codex_scenarios.py`.

**Interfaces:** Preserve existing string-returning responders and existing decision tests. Add `CodexToolReply(content: str, mailbox_messages: list[str])`; the responder may return either this object or a string. Add ordered assistant-turn records with text and tool calls to `CodexSimResult`, retaining existing fields. Add a scenario driver with role states, dispatched canonical identities, pending mailbox events, and an explicitly configured expected terminal condition.

- [ ] Write deterministic tests using mocked model responses for these traces:

```text
spawn -> final("working")                    => premature exit detected
resume -> final("fixes underway")            => premature exit detected
wait(timeout) -> wait -> completion -> next   => ordered continuation recorded
wait(activity summary) + mailbox result      => separate delivery preserved
ready QA plan + running reviewer             => QA queued, reviewer still pending
real gate -> final(question)                  => valid stop, no follow-up dispatched
max_calls exhausted                          => incomplete, never a passing scenario
```

- [ ] Run `cd evals && uv run pytest tests/test_codex_harness.py tests/test_codex_scenarios.py -v`; confirm new tests fail for the missing interfaces/behavior.
- [ ] Implement the reply normalization and ordered turn recording. Append every tool reply before injecting mailbox messages; keep valid OpenAI tool-call pairing when an assistant emits multiple tool calls. Represent mailbox messages as clearly identified untrusted child results in model-visible transcript messages, not invented user approvals.
- [ ] Implement scenario responses: spawns return only canonical identity, follow-ups activate an idle role, waits return activity/timeout summaries, and separately delivered child results change the scenario state. `list_agents` returns current states. Reject unexpected product shell commands instead of returning unconditional success.
- [ ] Stop the driver on text-only model responses exactly as today. The evaluator must classify premature termination as failure; never repair the model by automatically sending “continue” or injecting a new user turn after finalization.
- [ ] Add a negative control asserting that the exact incident trace is rejected even though dispatch was successful. Keep the stop oracle based on scenario state/expected gate, not the model's claim that it is done.
- [ ] Rerun the focused unit tests. Review the diff as an independently testable harness change.

## Task 2: Specify and test the orchestration loop

**Files:**
- Modify `plugins/ship/skills/ship/references/codex-dispatch.md`.
- Modify `evals/orchestrator_codex/conftest.py`.
- Create `evals/orchestrator_codex/test_codex_continuation.py`.
- Create scenario fixtures under `evals/orchestrator_codex/fixtures/transcripts/` for `impl_partial`, `impl_running`, `fixes_complete`, `qa_ready_review_running`, `impl_external_blocker`, and `status_during_implementation`.

**Interfaces:** New tests use Task 1's ordered trace and scenario state. Existing handoff fields and free-text reports remain accepted; no mandatory machine-readable status field is introduced.

- [ ] Add live-model regressions with explicit assertions for every Required behavior row. Reuse existing verified-tree/review fixtures where possible. Include planner and git dispatches so waiting is not implementation-only.
- [ ] Include a full synthetic post-approval chain: partial implementation -> resume -> verified tree -> concurrent QA/review -> important finding -> same implementer fixes -> fresh reviewer -> clean review -> git PR result -> QA gate. Assert ordered transitions and stop only at that gate, with no synthetic user nudges.
- [ ] Test valid termination separately: spec/plan/QA approval gates; diagnosed missing credentials; unresolved review cap; explicit user cancellation. Ensure these are not converted into automatic retries or accidental gate bypasses.
- [ ] Run `cd evals && uv run pytest orchestrator_codex/test_codex_continuation.py -m codex -v` against unchanged prompts and retain the observed baseline. Live model failures are probabilistic: do not claim a reproduction if a run passes; the deterministic incident trace remains the negative control.
- [ ] Add a Codex continuation section near the top of `codex-dispatch.md`: stage completion requires substantive evidence, interim progress belongs in commentary, remaining authorized work requires another transition, and only specified terminal conditions permit a final response. Clarify how Codex handles incomplete Stage 3 and Stage 4 fix results without treating them as outright failure. Preserve the existing pipeline contract and shared `SKILL.md`; this section supplies Codex lifecycle mechanics, not new stages or gates.
- [ ] Add the concrete Codex loop below the adapter tool mapping:

```text
dispatch/resume -> retain canonical identity -> process available mailbox
if independent stage work is ready: dispatch it
if required child is running: wait, then process mailbox again
if required child is idle with incomplete work: followup_task, then wait
if stage evidence is complete: advance immediately
if genuine gate/blocker/end: final with stage table and correct state
```

- [ ] Correct the misleading mailbox wording: completion delivery must not be treated as a promise that a finalized parent will be awakened. Explain that `wait_agent` reports activity, not necessarily the full child result. When a completion summary lacks its report, inspect agent state; do not redispatch a running child merely because a wait timed out.
- [ ] Use waits of at most 60 seconds to allow progress communication under the host instructions. Emit concise progress at meaningful changes and a brief truthful update at the host's required cadence. Do not equate a timeout with lack of agent progress. Respect higher-priority host constraints if they differ.
- [ ] Add a pre-final check: no unresolved authorized transition may remain unless the final explicitly explains a permitted gate, blocker, cancellation, or completion. A queued QA plan can remain during a documented review halt, per the existing contract.
- [ ] Rerun the complete Codex eval tier, including the existing five decision tests. Repeat the new live scenarios three times for baseline/fixed comparison with the selected model recorded; report failures and skips instead of masking them with retries.

## Task 3: Stop the Codex implementer from treating milestones as completion

**Files:**
- Create `plugins/ship/codex-agents/overlays/implementator-agent.md`.
- Modify `plugins/ship/scripts/sync_codex_agents.py` and `evals/tests/test_sync_codex_agents.py`.
- Regenerate `plugins/ship/codex-agents/ship-implementator-agent.toml` using the sync script.
- Create `evals/orchestrator_codex/test_codex_implementator_completion.py` with simulated-tool milestone and genuine-blocker fixtures. Load the generated role's `developer_instructions` with `tomllib` and use the OpenAI driver directly with role-appropriate shell tools; do not load the Claude-only agent body or the orchestrator system prompt for these tests.

**Interfaces:** Preserve the current final report fields and the shared agent source. Extend `render_role(name, description, body, preamble, cfg, overlay="")` with an optional overlay inserted between the preamble and unchanged agent body. `generate(plugin_dir)` reads `codex-agents/overlays/<agent>.md` when present, otherwise passes an empty string. The overlay explicitly scopes its completion rules to Codex and clarifies that milestone completion does not satisfy the shared workflow's final report step. Parent recovery remains necessary for old installed roles and imperfect compliance.

- [ ] Add generator unit tests before implementing overlay composition: missing overlay preserves exact prior output; an implementer overlay changes only that role; the original agent body remains the unchanged suffix; TOML quoting validation includes overlay content; `--check` detects an overlay edit until regeneration. Extend temporary-plugin fixtures to copy overlays when testing production parity, retaining a separate no-overlay fixture for backward compatibility.
- [ ] Run `cd evals && uv run pytest tests/test_sync_codex_agents.py -v`, observe the new failures, then implement the optional composition. Preserve existing generated headers for roles without an overlay; add an overlay provenance comment only to the implementer output. Update the generator docstring to describe the new input without changing Claude's source-of-truth contract.
- [ ] Add behavioral scenarios where one focused suite passes but requested integration verification remains: expect continued tool work, not a milestone final. Add a diagnosed credentials blocker case that expects an honest report and no success claim.
- [ ] Write the role-specific overlay: finish the assigned scope before reporting completion; send milestones as commentary; use a final for completed work or a concrete blocker/question requiring the orchestrator. Never imply that work continues after the child ends its turn. Do not edit workflow steps 6–7 in the shared agent source.
- [ ] Explicitly retain authorization boundaries: missing credentials do not authorize obtaining new credentials or bypassing controls. Distinguish local recoverable failures from external prerequisites using actual error evidence.
- [ ] Run `cd evals && uv run pytest orchestrator_codex/test_codex_implementator_completion.py -m codex -v` before/after against the generated role. Record missing API access as unverified, not passed. Regenerate after writing the overlay with `python3 plugins/ship/scripts/sync_codex_agents.py`, then run `python3 plugins/ship/scripts/sync_codex_agents.py --check`.
- [ ] Confirm only the implementer generated role changed; do not edit generated TOML by hand or broaden the shared preamble across unrelated roles.

## Task 4: Package, document, and verify the actual delivery path

**Files:**
- Update `plugins/ship/agents/CHANGELOG.md`, `README.md`, and `evals/README.md`.
- Update all six package manifests listed in `evals/tests/test_manifest_versions.py`.
- Update the package version expectation in `evals/tests/test_manifest_versions.py`. Leave the shared skill version expectation in `evals/tests/test_skill_codex_section.py` unchanged.

- [ ] Release package `1.11.0`, provided it remains the next available version at implementation time. Keep shared ship `4.2.1` and implementer `1.3.2` versions and compatibility text unchanged; document the Codex adapter/overlay changes under the package release. All manifests carry the same package version, but this does not change Claude behavior.
- [ ] Document the continuation behavior, new scenario coverage, and limits of prompt-based orchestration. Update eval counts from actual collection rather than estimating them.
- [ ] Document delivery: update the installed plugin, run the bundled role installer, check it with `--check`, and start a fresh Codex session to load the updated role. The investigated run invoked the local `~/.codex/skills/ship/SKILL.md` copy; verify the resolved skill and reference match the release, rather than assuming updating the marketplace cache updates that copy. Do not modify user installations as part of this code change.
- [ ] Run offline verification:

```sh
python3 plugins/ship/scripts/sync_codex_agents.py --check
cd evals && uv run pytest tests -v
```

- [ ] Run live verification when credentials are available:

```sh
cd evals && uv run pytest orchestrator_codex -m codex -v
```

- [ ] Verify against the implementation base that `plugins/ship/skills/ship/SKILL.md`, all shared `plugins/ship/agents/*-agent.md` sources, and the Claude eval harness/scenarios have no diff. Compare generated roles: only `ship-implementator-agent.toml` may change. Existing offline structural tests must still pass. Broad Claude live-model reruns are not required when these source boundaries are unchanged; existing CI can continue running them normally.
- [ ] Review that the existing Codex CI job discovers the new tests without changing its marker selection. Run `git diff --check` and inspect all changed files, including generated roles and manifests.
- [ ] Report separately: deterministic harness results, live behavioral results/model/repetitions, any skipped coverage, and installation requirements. Do not call this a runtime-enforced guarantee or claim that existing sessions were fixed.

## Acceptance criteria

1. The recorded resume-then-final incident is rejected by the eval oracle.
2. The synthetic pipeline reaches its next real gate without user nudges across partial implementation, timeouts, and review fixes.
3. A child completion is never sufficient by itself to mark implementation verified; required work and evidence are checked.
4. Approval gates, explicit stops, and diagnosed blockers still terminate correctly with an actionable report.
5. Progress messages describe observed state; a final does not promise continued unattended work.
6. Offline tests and role drift checks pass; live eval outcomes are disclosed accurately.
7. Release instructions cover both the skill source actually invoked and the separately installed Codex role.
8. Shared Claude skill/agent instructions and Claude eval behavior remain unchanged; only Codex reads the new lifecycle rules and implementer overlay.


## Implementation record — September 10

- Implemented the Codex dispatch continuation loop, optional implementer overlay and generator,
  asynchronous eval driver/scenarios, version 1.11.0 package metadata, and release documentation.
- Used parameterized Python scenarios instead of six duplicated JSON transcripts: the same
  stateful simulator covers partial results, missing evidence, internal questions, timeouts, fixes,
  status interruption, and real gates/blockers. This keeps role state and the terminal oracle together.
- Offline verification: 43 tests pass. Collection: 95 total cases, including 21 Codex cases.
- Live baseline/fixed comparisons and three-run repetitions remain unverified: no OPENAI_API_KEY
  is available. All live Codex tests are collected and skipped explicitly, not reported as passing.
- Used PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 because the installed retry plugin opens a loopback socket
  blocked by this sandbox. Test code and assertions were not bypassed.
- Read-only review found status injection and QA-gate assertion gaps; both were corrected and the
  incomplete-gate negative control added.
- Shared Claude instructions, harness/scenarios, and component versions remain unchanged.
  Only the implementer generated TOML changed; generation drift check passes.
- No plugin installation, original-ticket execution, commit, or publication was performed.
