# Pipeline Changelog

SemVer changelog for the feature pipeline: the `ship` orchestrator (skill) and its subagents (four
always, five when `spec-agent` runs via `--spec`). Bump rules live in
`plugins/ship/skills/ship/SKILL.md` § Versioning.

- **MAJOR** — breaking contract change (a stage's inputs/outputs, gate structure, or inter-stage
  handoff: approved-spec text, approved-plan text, worktree path + branch, PR URL, reviewer verdict
  line).
- **MINOR** — new backward-compatible capability (an agent gains a skill or step).
- **PATCH** — wording/clarity/typo, no behavior change.

## ship package — 1.9.0 (2026-09-03)
- **New Bash guardrail against a `cd && <relative-path grep>` permission-prompt false positive.**
  `task-planner-agent`, `implementator-agent`, `reviewer-agent`, and `qa-agent` (the four agents with
  both `Bash` and the dedicated `Read`/`Grep`/`Glob` tools) each gain a guardrail bullet: prefer the
  dedicated tools for file search/reads, and if Bash is genuinely required, never chain
  `cd <dir> && <command with a relative path>`. Root cause: a relative path resolved only after a
  dynamic `cd` can't be statically checked by the permission checker against `Read()` allow/deny
  rules, so an otherwise-allowlisted command (e.g. `grep`) falls back to an interactive prompt instead
  of auto-approving — silently defeating `grep`/`cd` allow-listing. `spec-agent` is unaffected (no
  `Read`/`Grep`/`Glob` tool, no codebase access). Wording-only guardrail addition, no workflow/handoff
  change, so PATCH on each of the four agents: `task-planner-agent` 2.1.0 → 2.1.1,
  `implementator-agent` 1.3.0 → 1.3.1, `reviewer-agent` 1.2.1 → 1.2.2, `qa-agent` 3.1.0 → 3.1.1.
  Package version bumped MINOR (1.8.0 → 1.9.0, all 6 manifest locations) per convention — the package
  version is what `claude plugin update` checks, not underlying agent-file content.

## ship — 4.1.0 (2026-08-27)
- **Optional QA video recording, decided at GATE 3.** New `--record` flag on
  `/ship <TICKET> [--spec] [--record]`. The flag only **pre-answers a new GATE 3 question**: without
  it, the user is asked "Record video of this QA run?" via `AskUserQuestion` when the QA plan is
  surfaced — never as a separate later interruption. The decision travels in qa-agent's **Phase-B
  resume** alongside the PR URL and the target stage, never the initial brief. Additive (no flag +
  "No" ⇒ behavior unchanged from 4.0.0), so MINOR. Compatibility floor bumped to `qa-agent` ≥3.1.0.
  (Originally authored as 3.8.0 against the pre-4.0.0 contract; re-versioned and re-worded on rebase —
  the removed `model`-param analogy no longer applies.)

## qa-agent — 3.1.0 (2026-08-27)
- **Optional session video recording** (companion to ship 4.1.0). New optional `record` input on the
  **Phase-B resume** (the same late-arrival slot as the deferred PR ref and the target stage). When
  requested: records each browser instance with `playwright-cli video-start`/`video-stop` to
  `~/.ship/qa-recordings/<TICKET>/<TICKET>-qa-<timestamp>[-<role>].webm` (1280x800, timestamped so
  re-runs never collide), annotates actions on screen (`video-show-actions`), and marks one
  `video-chapter` per test case using the approved plan's case ids; then uploads via the
  `devex:internal-static-hosting` skill (inferred-username prefix, `qa-recordings/<TICKET>/`,
  hosted URL verified with `curl --head`) and appends `🎥 QA recording: <URL>` under the verdict
  line in both the PR comment and the final report. Best-effort throughout: a recording or upload
  failure never fails the run — the local path is reported instead, and local files are kept after
  upload. Backward compatible: resumes without the input behave exactly as 3.0.0. (Originally
  authored as 2.7.0; re-versioned on rebase over the 3.0.0 stage/provenance changes.)

## ship — 4.0.0 (2026-08-26)
- **BREAKING (invocation contract).** The invocation slims to `/ship <TICKET> [--spec]` — both the
  `[model]` shortcut and the `[stage]` param are removed.
  - **`model`** (issue #14): the deepeval suite (PR #13) showed the pre-answer rule was not reliably
    followed — given `/ship LEX-1398 sonnet`, the orchestrator still asked the planner question in
    both live runs, so the shortcut promised behavior it didn't deliver. Stage 0 now **always asks
    both** model questions. Eval updated: `test_stray_model_token_does_not_preanswer_stage0` asserts
    the planner question IS asked.
  - **`stage`** (issue #15): a PR's ephemeral stage exists only after Stage 5 creates the draft PR
    and its `/dynamic` environment comes up, so it is unknowable at `/ship` time. The target stage
    is now a **GATE 3 input**: the user names it, if at all, in their QA-plan approval (e.g.
    "approved, run it on stage34"), and the orchestrator relays it in the Phase-B resume alongside
    the PR URL. Never invented; absent ⇒ qa-agent's default localhost/stage40.
  - Any stray extra token (`sonnet`, `stage34`, …) ⇒ ask the user rather than guessing.
- **Provenance machinery retired** (issue #15, deliberate walk-back of the 3.6.0 quoted-authorization
  rule): the qa-agent brief no longer quotes the `/ship` invocation as stage provenance, and the
  Phase-B resume no longer needs the verbatim-quote framing — the GATE 3 relay itself is the
  designed, trusted channel. Requires `qa-agent` ≥3.0.0.

## qa-agent — 3.0.0 (2026-08-26)
- **BREAKING (stage + approval contract; pairs with ship 4.0.0).** The target stage now typically
  arrives **with the Phase-B resume** (named by the human in their GATE 3 approval, after the PR's
  `/dynamic` environment exists) rather than in the initial brief; deferred-PR mode is now
  deferred-PR/deferred-stage. The 2.6.0 provenance challenge is **removed**: no verbatim-invocation
  requirement, no "weak evidence → ask for the user's quoted words" behavior — the agent acts on the
  stage and verdict the orchestrator's resume delivers, runs everything Phase B needs against that
  target, and still never invents a stage (absent ⇒ default localhost/stage40). Evals: the two
  provenance-negative cases are removed with the rule.

## ship — 3.7.0 (2026-08-11)
- **Third model option at Stage 0, plus a cross-model recommendation.** The planner/reviewer model
  picker (`AskUserQuestion`) now offers `claude-fable-5`, `claude-opus-5[1m]`, and `claude-sonnet-5`
  (previously just the first two) — the `/ship [model]` CLI shortcut already accepted `sonnet` but
  Stage 0's own picker never offered it. The reviewer's Critical-finding escalation now targets
  `claude-opus-5[1m]` from any non-Opus base (previously hardcoded to the fable→opus pair). Stage 0
  also now recommends, without requiring, picking a *different* model for planner vs. reviewer, since
  a same-model plan→review pass is more likely to share blind spots. Documented that the picker's
  built-in "Other" choice covers users without access to any of the three listed models — whatever
  they type is passed through verbatim as the `model` override, unvalidated. Additive/backward-compatible
  (existing two-model choices and same-model picks still work), so MINOR. planner/spec-agent's default
  `model:` frontmatter bumped from the stale `claude-opus-4-8[1m]` to `claude-opus-5[1m]` to match —
  config-only, no version bump on those agents (same precedent as the prior canonical-ID pass).

## workflow-retro — 1.0.0 (2026-07-03)
- New manual-only skill (`disable-model-invocation: true`, invoked via `/workflow-retro`). Reviews a
  completed `/ship` run: real per-agent token totals computed by a bundled analyzer script
  (`analyze_run.py`) that sums `message.usage` over each subagent's `subagents/agent-<id>.jsonl`
  transcript — not the inline `toolUseResult.usage` summary, which undercounts by up to ~40× (last-turn
  only). Reports token spend, problems encountered, what went well/poorly, insights, and improvement
  suggestions as a terminal markdown report. Read-only observer — not a pipeline stage, no handoff
  contract with `ship`.

## engineering-insights — 1.0.0 (2026-07-12)
- Baseline. New bundled skill, invoked by `ship`'s Stage 8 with an explicit target `INSIGHTS.md` path
  passed as `args` (no routing table of its own — unlike its dev-digest origin, the caller always
  decides the target). Captures the same 7 fixed sections (What Works / What Doesn't Work / Codebase
  Patterns / Tool & Library Notes / Recurring Errors & Fixes / Session Notes / Open Questions),
  append-only, same quality bar ("if this were obvious to anyone reading the code, don't write it").
  Writes nothing when nothing substantial happened.

## ship — 3.6.0 (2026-07-24)
- **Authorization provenance in QA handoffs.** Subagent permission classifiers judge intent from the
  subagent's own context and were (correctly) refusing stage mutations authorized only by an
  orchestrator paraphrase. The qa-agent's initial brief now quotes the user's original `/ship`
  invocation verbatim (stage provenance) and states the Phase-B authorization scope up front; the
  GATE 3 Phase-B resume now relays the user's approval message verbatim (quoted) plus the invocation
  and PR ref — never a bare "approved — run Phase B". New guardrail: authorization is quoted, never
  paraphrased. Additive brief/resume fields, so MINOR. Compatibility floor bumped to `qa-agent`
  ≥2.6.0.

## qa-agent — 2.6.0 (2026-07-24)
- **Relay-approval mechanics made explicit** (companion to ship 3.6.0). New "The approval channel"
  section: the orchestrator's relay is the designed approval channel, and its strength is the user's
  quoted words inside it — a resume asserting approval without them is weak evidence, and the agent
  must ask the orchestrator for the verbatim approval before mutating a shared stage rather than
  work around a denial. Inputs: a user-quoted stage in the brief *is* the resolved target
  (overrides the localhost/stage40 default — the default is a fallback, not a boundary); a
  non-default stage with no quoted provenance requires asking before Phase B mutates it. New
  optional "authorization scope" input documenting what plan approval authorizes. Backward
  compatible: briefs without provenance/scope still work, matching pre-3.6.0 orchestrators.

## ship — 3.5.0 (2026-07-24)
- **New "Progress display" rule: every user-facing progress message ends with the full pipeline
  table.** One row per stage (`# | Stage | Status`), all rows always present — never the collapsed
  TodoWrite widget ("+N completed"), which is now internal bookkeeping only. Status cells use
  `✅/🔄/⏳/⏭️/⛔ — one-line detail`, completed rows carry concrete outcomes (files/tests, PR URL,
  review verdict), and a **Spec (GATE 1)** row is prepended on `--spec` runs. No stage or gate
  structure change.

## ship — 3.4.0 (2026-07-21)
- **Stage 8's project-insights call no longer pushes.** Previously it committed and pushed
  `edu-frontend/INSIGHTS.md` onto the already-open PR (to survive worktree cleanup); now it
  commits locally only, same as the pipeline-insights call — symmetric behavior, at the accepted
  cost that a captured insight can be lost if the worktree is cleaned up before anyone pushes it.
  No stage or gate structure change.

## ship — 3.3.0 (2026-07-16)
- Compatibility floor bumped for `qa-agent` ≥2.5.0 (results-table change, below). No stage or gate
  structure change.

## ship — 3.2.0 (2026-07-14)
- Stage 3 wording updated to match `implementator-agent` 1.3.0's conditional persistence (below), and
  the Compatibility floors bumped for `implementator-agent` ≥1.3.0, `reviewer-agent` ≥1.2.1, `qa-agent`
  ≥2.4.0. Stage 6 wording also fixed to stop describing qa-agent as posting its plan to the PR. No
  stage or gate structure change.

## ship — 3.1.0 (2026-07-12)
- **New Stage 8 — Insights retro** (automatic, no gate, best-effort). After every run, writes up to
  two `INSIGHTS.md` targets via the new bundled `engineering-insights` skill: pipeline-level
  orchestration friction to `$SHIP_REPO_PATH/INSIGHTS.md` (commit only, no push — permanent local
  clone), and, only when the ticket touched `edu-frontend/`, project-level discoveries to
  `<worktree>/edu-frontend/INSIGHTS.md` (commit **and** push, riding on the already-open PR — the
  worktree is ephemeral, so pushing is the only way the note survives cleanup). Skips or failures in
  Stage 8 never block, invalidate, or roll back the shipped PR. Now requires `engineering-insights`
  ≥1.0.0.

## ship — 3.0.0 (2026-07-07)
- **BREAKING (gate/handoff structure).** Adds an optional **`--spec`** flag: when set, a new **Stage 1
  — Spec** dispatches `spec-agent` before task-planner-agent, with its own human gate (GATE 1). All
  later stages shift by one (plan is now Stage 2/GATE 2, implement Stage 3, review⇄fix Stage 4,
  commit/PR Stage 5, QA Stage 6/GATE 3, report Stage 7). Without `--spec`, behavior is unchanged from
  2.5.0 — task-planner-agent still reads the ticket itself, and there are still only two gates. When
  Stage 1 runs, its approved spec text is passed to task-planner-agent (which grounds the plan in it
  instead of re-reading the ticket) and to implementator-agent (which persists it into the worktree
  alongside the plan, at `specs/<TICKET>/*.md`, for reviewer-agent and qa-agent to read directly). Now
  requires `spec-agent` ≥1.0.0 (only when `--spec` is used), `task-planner-agent` ≥2.1.0,
  `implementator-agent` ≥1.2.0, `reviewer-agent` ≥1.2.0, `qa-agent` ≥2.3.0.

## ship — 2.5.0 (2026-07-03)
- **Stage 0 startup model prompt.** On launch, ship asks the user (via `AskUserQuestion`, one call /
  two questions) which model to run the **planner** and **reviewer** on, each offering **`opus`** and
  **`fable`**. The chosen planner model is the Stage-1 Agent override; the chosen reviewer model is the
  Stage-3 base (a `fable` base still escalates to `opus` for a round after a Critical finding). This
  supersedes the previous sonnet-default for the reviewer. The `model` invocation param now just
  pre-answers the planner question. Affects planner + reviewer only. Compatibility unchanged from 2.4.0.

## ship — 2.4.0 (2026-07-02)
- New optional **`model`** param (`fable` | `opus` | `sonnet`) on `/ship <TICKET> [stage] [model]`.
  When supplied it overrides the **planner agent's** model for the Stage 1 dispatch (passed as the
  Agent tool `model` override); absent ⇒ planner default. Order-independent with `stage` (a `stageN`
  token is the stage, a model token is the model). Does not affect implementator/reviewer/qa/git
  models. Compatibility unchanged from 2.3.0.

## ship — 2.3.0 (2026-07-01)
- Token-saving orchestration changes (no handoff-contract change):
  - **Reviewer model tiering** — dispatch reviewer on **sonnet** by default; escalate to **opus** for
    a round only when the previous round surfaced a **Critical** finding.
  - **Implementator resumed for fix rounds** — Stage 3 fix rounds now **resume the same implementator
    instance** (in place, same worktree) instead of spawning a fresh one, skipping cold re-reads.
    Only the reviewer is dispatched fresh per round.
  - **Parallel qa launched later** — the background qa-agent Phase-A branch now launches after the
    implementator's **first verified tree** (end of Stage 2) rather than at GATE 1, so a fast Stage-2
    failure doesn't waste qa planning tokens. It grounds the plan on the worktree code.
  - Now requires `implementator-agent` ≥1.1.0 and `reviewer-agent` ≥1.1.0.

## ship — 2.2.0 (2026-07-01)
- Stage 1 no longer resumes the planner on approval — the planner is now single-phase, so on approval
  ship keeps the retained approved-plan text and proceeds straight to Stage 2 (no "run Phase B"). The
  planner is still resumed via `SendMessage` for **change requests**. Now requires
  `task-planner-agent` ≥2.0.0.

## ship — 2.1.0 (2026-06-30)
- Adds a **Usage reporting** rule: after each agent and at end-of-flow, the orchestrator points the
  user to the per-task token line in the UI and to `/cost` for the session total. It never quotes
  token numbers — no tool exposes usage to the orchestrator, so any figure would be fabricated.
  Compatibility unchanged from 2.0.0.

## ship — 2.0.0 (2026-06-30)
- **BREAKING (gate/handoff structure).** qa-agent's Phase-A test plan is now authored **in parallel**
  with implementation: launched in the background right after GATE 1 (deferred-PR mode, no PR ref),
  it runs concurrently with implement→review→PR. The plan is queued and GATE 2 is still surfaced
  serially (after the PR exists), so only one gate is pending at a time. PR URL is passed at the
  Phase-B resume (the join point), not at dispatch. On a halt (review cap / impl failure) the parallel
  qa-agent is kept alive with its plan ready. Now requires `qa-agent` ≥2.0.0.

## ship — 1.0.0 (2026-06-25)
- Baseline. Orchestrates plan → implement → review⇄fix → commit/PR → QA. Two human gates (plan, QA
  plan); autonomous review loop (cap 3). Compatible with all four subagents at ≥1.0.0.

## spec-agent — 1.2.0 (2026-07-07)
- **Dropped `Read`/`Grep` from `tools:`** — neither had a legitimate use (ticket/Confluence content
  arrives via Bash/MCP output, never a local file) and their presence silently defeated the "no
  codebase access" guardrail (`Grep` alone can search file contents tree-wide without `Glob`).
  Guardrail wording updated to match. Decoupled Acceptance Criteria / Invariants-to-preserve from
  the feature/refactor classification (step 4 is now framing-only): Acceptance Criteria fires on any
  new/changed behavior, Invariants fires on any explicit preserve-behavior ask, independently — both
  may appear together on a mixed ticket. Same "stated or clearly implied" strictness bar retained for
  Invariants. Backward-compatible; no handoff change.

## spec-agent — 1.1.0 (2026-07-07)
- Step 6 ("Return for review") now optionally runs `grill-me:grill-me` to stress-test the spec before
  returning it, same pattern as task-planner-agent's self-check step. Since spec-agent has no codebase
  tools, any branch grill-me would normally resolve by exploring code instead routes into the spec's
  "Open Questions" section. Backward-compatible; no handoff change.

## spec-agent — 1.0.0 (2026-07-07)
- Baseline. New optional first pipeline stage (dispatched only when `/ship` runs with `--spec`). Reads
  the Jira ticket + linked Confluence spec only — no codebase access — and writes WHAT/WHY: user
  stories, EARS-format acceptance criteria (`WHEN <event> THE SYSTEM SHALL <behavior>`) for
  feature-shaped tickets, or an "Invariants to preserve" section for refactor/migration-shaped tickets.
  Single-phase with its own human review gate, same pattern as task-planner-agent: posts nothing on
  approval, resumed via `SendMessage` only for change requests.

## task-planner-agent — 2.1.0 (2026-07-07)
- Accepts an optional **approved spec** (spec-agent's output) in the orchestrator's brief. When
  present, skips its own ticket + linked-Confluence read (Workflow steps 1-2) and grounds the plan in
  the spec's user stories / acceptance criteria / invariants instead. Absent ⇒ unchanged from 2.0.0
  (reads the ticket and linked spec itself).

## task-planner-agent — 2.0.0 (2026-07-01)
- **BREAKING.** Removed Phase B / Jira posting. The agent is now **single-phase**: plan → human
  review gate → done. On approval it posts nothing (the orchestrator carries the approved plan text
  forward); it is resumed only to handle change requests. Jira/Confluence remain **read only** (ticket
  + linked-spec grounding); the agent makes no Jira writes and no ticket transitions.

## task-planner-agent — 1.0.0 (2026-06-25)
- Baseline. Includes Crew-flag awareness in planning and `frontend-design:frontend-design` +
  `grill-me:grill-me` planning helpers.

## implementator-agent — 1.3.0 (2026-07-14)
- **Persistence into `specs/<TICKET>/*.md` is now entirely conditional on `--spec` mode** — previously
  `plan.md` was always written regardless of `--spec`, cluttering every PR's diff with a
  `specs/<TICKET>/` directory even on non-spec runs. Now both `plan.md` and `spec.md` are written
  together only when the orchestrator passed an approved spec; skipped together otherwise. Backward
  compatible: reviewer-agent/qa-agent already tolerate these files being absent.

## implementator-agent — 1.2.0 (2026-07-07)
- The **Isolate** step now persists the planning text it received into the worktree before starting
  tasks: the approved plan to `specs/<TICKET>/plan.md`, and — when the orchestrator also passed an
  approved spec (`--spec` runs only) — the spec to `specs/<TICKET>/spec.md`. Gives reviewer-agent and
  qa-agent a file to read directly instead of relayed prose. Backward-compatible: absent spec input is
  a no-op.

## implementator-agent — 1.1.0 (2026-07-01)
- Fix-round guardrail made explicit: when **resumed** with review findings, apply them **in place** in
  the existing worktree/branch — never create a new worktree — with the same TDD + verification
  discipline, then re-report. Also dropped the stale "re-fetch the plan from the Jira comment" input
  path (the planner no longer posts to Jira; the orchestrator passes the plan inline).

## implementator-agent — 1.0.0 (2026-06-25)
- Baseline. Includes `vercel:react-best-practices` for FE component/hook structure.

## reviewer-agent — 1.2.1 (2026-07-14)
- PATCH: Inputs wording corrected to reflect that `specs/<TICKET>/plan.md`/`spec.md` are only
  persisted in `--spec` mode (previously implied `plan.md` was always present). No behavior change —
  the fallback-to-relayed-text logic already handled the absent case correctly.

## reviewer-agent — 1.2.0 (2026-07-07)
- Inputs now **prefer reading `specs/<TICKET>/plan.md` (and `spec.md`, if present) from the worktree**
  over the orchestrator's relayed plan text, falling back to relayed text only when those files are
  absent. No change to findings format or the `Ready to commit?` verdict.

## reviewer-agent — 1.1.0 (2026-07-01)
- Token-saving changes (handoff unchanged — same findings groups + `Ready to commit?` verdict):
  - Default **model → sonnet** (was opus[1m]); the orchestrator may override per dispatch (escalates
    to opus for a round after a Critical finding).
  - **`security-review` is now conditional** — run only when the round's diff touches a
    security-sensitive surface (auth/session, payments, PII, permissions, network/API, secrets, file
    upload, deserialization); otherwise skipped and noted as not-applicable. `code-review` still runs
    every round; `storybook-review` still gated to story diffs. On re-review rounds, re-run a skill
    only if this round's changes fall in its scope.

## reviewer-agent — 1.0.0 (2026-06-25)
- Baseline. Runs `code-review`, `security-review`, and (on story diffs)
  `frontend:storybook-review` read-only, folded into the manual review.

## qa-agent — 2.5.0 (2026-07-16)
- **Results now reported as a verdict-line + table**, both in the PR comment and the final report:
  `**Overall: X/Y passed** ✅|❌` followed by a `Test Case | Description | Status | Notes` table
  (`✅`/`❌` per case, Notes blank when passing). Replaces the previous unstructured prose listing.
  Backward compatible — no change to what data is collected or the handoff contract, only how the
  already-collected pass/fail results are rendered.

## qa-agent — 2.4.0 (2026-07-14)
- **No longer posts its test plan to the PR.** Phase B previously posted the plan as a PR comment
  (marker `<!-- qa-agent-plan -->`) in addition to results — redundant, since the human already
  reviews and approves the plan in-session at GATE 3 before Phase B runs. Now only posts results.
  Phase B step numbering shifted down by one; the approval-gate mechanics themselves are unchanged.

## qa-agent — 2.3.0 (2026-07-07)
- Feature-description input now **prefers reading `specs/<TICKET>/spec.md`/`plan.md` from the
  worktree** (when a worktree path is in the brief) for the acceptance criteria to test against,
  falling back to the relayed description when those files are absent or no worktree exists yet.

## qa-agent — 2.2.0 (2026-07-01)
- **Snapshot-first evidence.** Default to a11y snapshots + console/network state for evidence;
  screenshot only to evidence a failure or when the feature under test is genuinely visual. Cuts
  image-token cost, especially on multi-user (separate-instance) runs. The pre-interaction snapshot
  (for element refs) is unchanged.

## qa-agent — 2.1.0 (2026-06-30)
- Multi-user scenarios (e.g. tutor + student) must use a **separate browser instance per user**
  (isolated profile/session), never multiple tabs in one browser — shared cookies/`localStorage`
  make two simultaneous logins impossible. Close every instance at the end. Backward-compatible;
  no handoff change, so `ship`'s `qa-agent ≥2.0.0` requirement still holds.

## qa-agent — 2.0.0 (2026-06-30)
- **BREAKING (PR-ref contract).** Adds a **deferred-PR** mode: when the brief says the PR does not
  exist yet (parallel launch with implementation), Phase A authors the plan from the feature
  description / plan / ticket / existing code only and must **not** run `gh pr view` or infer a
  branch. The PR ref arrives with the Phase-B resume. Enables `ship` 2.0.0's parallel QA-plan branch.

## qa-agent — 1.0.0 (2026-06-25)
- Baseline. Includes Crew flag/experiment enablement before execution.
