---
name: ship
version: 3.2.0
description: >
  Orchestrates the feature pipeline (optionally spec-agent →) task-planner-agent → implementator-agent
  → reviewer-agent → qa-agent end-to-end from a Jira ticket, relaying the human's approvals at each
  gate. Use when the user runs `/ship <TICKET> [stage] [model] [--spec]` or asks to "ship a ticket",
  "run the pipeline", "orchestrate the agents", or "take <TICKET> from plan to QA". Drives
  (spec →) plan → implement → autonomous review-fix loop → commit/push/draft-PR (Haiku) → QA, stopping
  for human approval only at the spec (when run with `--spec`), plan, and QA-plan gates. The qa-agent's
  test plan is authored **in parallel** with implementation (launched right after the plan gate) so
  it's ready the moment the PR lands. Do NOT use for one-off single-agent tasks (dispatch the relevant
  agent directly instead).
---

# ship — feature pipeline orchestrator

You orchestrate up to five subagents through a complete feature pipeline — spec-agent is optional,
dispatched only when `/ship` runs with `--spec` — **running in the main session** (you are the only
"agent" that can both dispatch these subagents and pause to relay the human's approvals — subagents
can do neither).

```
/ship <TICKET> [stage] [--spec]
  (Spec ──🛑GATE1──)? Plan ──🛑GATE2── Implement ──┬── Review⇄Fix loop ── Commit/Push/draft-PR ──┐
                                                   │                                              ├── QA-plan ──🛑GATE3── QA-run ── Results
                                                   └── QA-plan authoring (qa-agent Phase A, bg) ──┘
```

Once the implementator reports its **first verified working tree** (end of Stage 3), two branches run
**concurrently**: the review→PR branch in the main session (foreground), and qa-agent's Phase-A plan
authoring in the background. They **join** at GATE 3 — the queued QA plan is surfaced only once the PR
exists. Launching qa after the first verified tree (rather than at GATE 2) means a fast Stage-3 failure
never wastes qa planning tokens.

## Inputs

Parse from the invocation:

- **`TICKET`** (required) — a Jira key like `LEX-1398`. If missing, ask the user; do not guess.
- **`stage`** (optional) — e.g. `stage31`. Passed through to **QA only**. Absent ⇒ qa-agent uses its
  default localhost/stage40 target.
- **`model`** (optional) — one of `fable` | `opus` | `sonnet`. A shortcut that **pre-answers the
  planner-model prompt** (Stage 0): if supplied, use it as the planner's model and skip that question.
  `stage` and `model` are order-independent and unambiguous — a `stageN` token is the stage, a
  `fable`/`opus`/`sonnet` token is the model. Any other value ⇒ ask the user rather than guessing.
- **`--spec`** (optional flag) — when present, dispatch **spec-agent** first (new Stage 1, its own
  gate) before task-planner-agent; task-planner-agent then grounds its plan in the approved spec
  instead of re-reading the ticket. Absent ⇒ skip straight to task-planner-agent, unchanged from
  today's behavior.

## Stage 0 — Choose models (startup prompt)

Before Stage 2 (Stage 1 when `--spec` is set), **ask the user which model to run the planner and
reviewer on** using the `AskUserQuestion` tool — one call with **two questions**, each offering
**`opus`** and **`fable`**:

- **Planner model** (Stage 2). If the `model` param was already supplied on invocation, **skip this
  question** and use the param value.
- **Reviewer model** (Stage 4).

Retain both answers. The planner answer is passed as the Agent `model` override in Stage 2; the
reviewer answer is the reviewer's base model in Stage 4. When `--spec` is set, **spec-agent reuses the
planner-model answer** — no separate question for it. These affect **only** the planner, spec-agent,
and reviewer — implementator, qa, and the git agent are unchanged.

Track the stages below as a TodoWrite checklist so progress is visible. Include a dedicated
**"QA-plan authoring (background)"** item so the parallel branch — launched after the implementator's
first verified tree (end of Stage 3) — stays visible alongside the review→PR branch. When `--spec` is
set, include a **"Spec (GATE 1)"** item ahead of the plan item. Include an **"Insights retro"** item
for Stage 8.

## Stage 1 — Spec (conditional on `--spec`, 🛑 GATE 1)

Skip this stage entirely when `--spec` was not passed — proceed straight to Stage 2 with
task-planner-agent behaving exactly as it does today (it reads the ticket itself).

When `--spec` **was** passed:

1. Dispatch **`spec-agent`** (Agent tool, `subagent_type: spec-agent`) with the ticket key and any
   context the user gave. Pass the **planner model** chosen in Stage 0 as the Agent `model` override
   (spec-agent has no model question of its own).
2. Surface the returned spec to the user **verbatim** and **STOP**. This is GATE 1.
3. Handle the verdict:
   - **Changes requested** → forward them to the **same spec-agent instance** with `SendMessage`; it
     revises and returns to the gate. Re-surface, stay stopped.
   - **Approved** → **keep the approved spec text** (you pass it to task-planner-agent next) and
     proceed to Stage 2. spec-agent is **single-phase** — it posts nothing and needs no resume on
     approval, so you may let it go.

Do not proceed past this gate without explicit approval.

## Stage 2 — Plan (🛑 GATE 2)

1. Dispatch **`task-planner-agent`** (Agent tool, `subagent_type: task-planner-agent`) with a brief:
   the ticket key, any context the user gave, and — **when Stage 1 ran** — the **approved spec text**
   inline (task-planner-agent grounds the plan in it instead of re-reading the ticket). **Pass the
   planner model chosen in Stage 0** as the Agent tool's `model` override for this dispatch. It returns
   a plan and stops at its own review gate.
2. Surface the returned plan to the user **verbatim** and **STOP**. This is GATE 2.
3. Handle the verdict:
   - **Changes requested** → forward them to the **same planner instance** with `SendMessage` (keeps
     its context); the planner revises and returns to the gate. Re-surface, stay stopped.
   - **Approved** → **keep the approved plan text** (you pass it to the implementator next) and
     proceed. The planner is **single-phase** — it posts nothing and needs no resume on approval, so
     you may let it go. Do not send it "run Phase B" (there is no Phase B).

Do not proceed past this gate without explicit approval.

## Stage 3 — Implement

Dispatch **`implementator-agent`** (`subagent_type: implementator-agent`) with: the **approved plan
text** (inline), the **approved spec text** (inline, when Stage 1 ran), and the **ticket id**. It
creates an isolated worktree on a branch named exactly the ticket id and, **only when Stage 1 ran**,
persists the plan and spec into the worktree as `specs/<TICKET>/*.md` (skipped entirely otherwise —
no `specs/<TICKET>/` directory on non-`--spec` runs). It implements with TDD, verifies (tests then
lint), and reports. **Keep this implementator instance's id** — fix rounds (Stage 4) resume it rather
than spawning a new one.

From its report, **capture and retain**:

- the **worktree path**,
- the **branch name**,
- the list of changed files and test/lint evidence.

If the report is missing the worktree path or branch, ask the implementator (`SendMessage`) before
continuing — the reviewer needs them. If implementation **fails outright** (no verified tree), STOP
and hand it to the user; the parallel qa-agent below was never launched, so there is nothing to keep
alive.

### On the first verified tree — launch the parallel QA-plan branch

The moment the implementator reports its **first verified working tree**, dispatch **`qa-agent`** in
the **background** (`subagent_type: qa-agent`, `run_in_background: true`) so its Phase-A test plan is
authored while the review→PR branch proceeds. Brief it with:

- a **feature description** drawn from the approved plan + ticket,
- the **worktree path** (so it can ground the plan on the real implemented code / selectors),
- **`stage`** if one was supplied,
- an explicit **deferred-PR** instruction: *"The PR does not exist yet — you were launched in parallel
  with the review/PR stage. Author the plan from the feature description / plan / ticket and the code
  in the worktree; do not run `gh pr view` or infer a branch. I'll hand you the PR ref when I resume
  you for Phase B."*

It returns the plan as its Phase-A final message and waits. **Do not surface its plan yet** — it is
queued until GATE 3 (Stage 6). Retain this qa-agent instance's id for later `SendMessage` resume. Then
proceed to Stage 4.

## Stage 4 — Review ⇄ Fix loop (autonomous, max 3 rounds)

Loop, counting rounds (cap = **3**):

1. Dispatch **`reviewer-agent`** (`subagent_type: reviewer-agent`) with: the **worktree path**,
   **branch**, the **approved plan**, and the **ticket id**. It diffs the uncommitted changes,
   re-runs the static checks, and returns findings (Critical / Important / Minor) plus a verdict line
   `Ready to commit? [Yes | No | With fixes]`.
   - **Model:** run the reviewer on the **model chosen in Stage 0** (`opus` or `fable`), passed as the
     Agent `model` override each round. **Escalation:** if the chosen base is **`fable`** and the
     *previous* round surfaced a **Critical** finding, run that re-review round on **`opus`** for a
     more rigorous re-check; if the base is already `opus`, stay on opus (no escalation needed).
2. Decide:
   - Verdict **`Yes`**, or only **Minor**/already-acknowledged findings remain → **exit the loop**.
   - Any **Critical** or **Important** finding → **fix round**: plan the fixes from the findings,
     then **resume the same `implementator-agent` instance** (the one from Stage 3) with `SendMessage`,
     handing it the findings to address. It keeps its worktree + exploration context and applies the
     fixes **in place** (never a new worktree), so it skips cold re-reads. When it reports back,
     **re-dispatch `reviewer-agent`** (next round; apply the model rule above).
3. If the cap (3 rounds) is reached and the review is still not clean → **STOP and hand it to the
   user**: summarize the outstanding findings and the worktree/branch, and ask how to proceed. Do not
   commit on your own. **Keep the parallel qa-agent instance alive** — do not run its Phase B and do
   not discard it. Note in the summary whether its plan is authored ("QA plan ready, awaiting unblock")
   or still in progress, so it can be approved and resumed once the halt is resolved.

This loop is autonomous (no human gate per the chosen design), but post a **one-line summary** after
it resolves: rounds taken and what was fixed.

## Stage 5 — Commit / push / draft PR (Haiku)

Dispatch a **Haiku-powered Agent** (`subagent_type: claude`, `model: haiku`) to handle git ops in the
implementator's worktree. Its brief:

- **Commit** all changes on the ticket branch with a clear message. **Do NOT add a `Co-Authored-By`
  line.**
- **Push** the branch (`-u` to set upstream). On a non-fast-forward rejection, only
  `git pull --ff-only` the same branch — never merge master in.
- **Open a draft PR** with `gh pr create --draft`, using the repo template at
  `.github/pull_request_template.md` for the body (never a custom format). Reference the ticket in
  the title.
- Return the **PR number and URL**.

Capture the PR URL — qa-agent needs it for Phase B (this is the **join point** of the two branches).

## Stage 6 — QA (🛑 GATE 3)

The qa-agent's Phase-A plan was authored in the background since Stage 3's first verified tree —
**do not dispatch a new qa-agent here**. Join the two branches:

1. **Collect the background plan.** Retrieve the parallel qa-agent's Phase-A result. If it is still
   authoring, **wait for it** (normally it finished long before the PR landed).
2. Surface the test plan to the user **verbatim** and **STOP**. This is GATE 3.
3. Relay the verdict to the **same qa-agent instance** with `SendMessage`:
   - **Changes requested** → forward; it revises and returns to the gate. Re-surface, stay stopped.
   - **Approved** → tell it "approved — run Phase B" **and include the PR reference (URL from
     Stage 5)** in the same message, since it was launched in deferred-PR mode without one. It
     provisions a stage account, executes with Playwright, and posts PASS/FAIL results to the PR
     (the plan itself was already shown to the human above at GATE 3 — it is not separately posted).

## Stage 7 — Final report

Return a concise summary: ticket key, branch, PR URL, review outcome (rounds + verdict), and the QA
PASS/FAIL result with links to the PR comments.

End the report with a **token-usage pointer** (see § Usage reporting): tell the user to run `/cost`
for the whole-flow session total, and that per-agent counts are on each completed task's line in the
Claude Code UI. **Do not state token numbers yourself** — you cannot read them; quoting any figure
would be fabrication.

## Stage 8 — Insights retro (automatic, no gate)

Runs immediately after Stage 7, regardless of outcome, **best-effort** — a failure or skip here must
never block, invalidate, or roll back an already-shipped PR.

1. **Pipeline-insights call** — check whether `$SHIP_REPO_PATH` is set and the directory exists
   (`[ -n "$SHIP_REPO_PATH" ] && [ -d "$SHIP_REPO_PATH" ]`). If not, skip this call and note the skip
   in your final report (append a line — don't re-open or restructure the Stage 7 report). If it
   exists:
   - Dispatch the **`engineering-insights`** skill (Skill tool) with `args` set to
     `$SHIP_REPO_PATH/INSIGHTS.md`. Ground it in **this run's own orchestration friction**: review
     rounds taken, any `BLOCKED`/`NEEDS_CONTEXT` escalation from any subagent, gate change-requests,
     model escalations (`fable`→`opus`), or anything else about *the pipeline itself* worth fixing in
     a future `ship` version. Never invent friction that didn't happen — a clean run may write
     nothing, which is correct.
   - If the skill wrote anything, commit it locally: `cd $SHIP_REPO_PATH && git add INSIGHTS.md &&
     git commit -m "<one-line summary of what was captured>"`. **Do not push.** This is the user's
     permanent local clone — they review and push in their own batches. If the commit fails (not a
     git repo, nothing staged, etc.), note the failure in the report; do not treat it as a pipeline
     failure.
2. **Project-insights call** — check whether Stage 3's changed-files list touched `edu-frontend/`. If
   not, skip (no other project target exists yet — this is scoped narrowly on purpose). If it did:
   - Dispatch the **`engineering-insights`** skill with `args` set to
     `<worktree_path>/edu-frontend/INSIGHTS.md` (the worktree path retained from Stage 3). Ground it
     in what implementator/reviewer/qa actually discovered while working the ticket — new patterns,
     dead ends, gotchas, tool quirks. Same "write nothing if nothing substantial" rule applies.
   - If the skill wrote anything, commit **and push** inside the worktree, onto the **same branch**
     Stage 5 already pushed: `cd <worktree_path> && git add edu-frontend/INSIGHTS.md && git commit -m
     "<one-line summary>" && git push`. This rides as one more commit on the already-open PR — never
     open a new PR for it. Push (unlike the pipeline-insights call) because the worktree is
     **ephemeral**: a local-only commit there can be lost once the worktree is cleaned up after merge.
     If the push fails (branch already deleted, PR already merged, etc.), note it in the report and
     move on — do not retry indefinitely and do not block on it.
3. Append one line per call to the final report: written / skipped (with why) / failed (with why).

## Guardrails

- **Two or three human gates**: the plan (Stage 2) and the QA plan (Stage 6) always; plus the spec
  (Stage 1) when `/ship` runs with `--spec`. The review→fix loop runs autonomously up to the 3-round
  cap regardless.
- **QA plan authored in parallel, surfaced serially**: qa-agent Phase A is launched in the background
  after the implementator's **first verified tree** (end of Stage 3) and runs concurrently with
  review→PR, but its plan stays **queued** — the QA gate is surfaced only after the PR exists
  (Stage 6), so you never juggle two pending gates at once. Launching post-verify (not at the plan
  gate) avoids wasting qa tokens when Stage 3 fails fast.
- **Deferred-PR handoff**: the parallel qa-agent has no PR at launch. Pass the PR URL (from Stage 5)
  in the **Phase-B resume** `SendMessage`, not at initial dispatch. The PR is the join point of the
  two branches.
- **Resume, don't re-spawn, across phases**: only **qa-agent** has an internal Phase A/B gate —
  relay its approval to the *same* instance via `SendMessage` so its context persists. The parallel
  qa-agent is launched once (after the first verified tree) and resumed for Phase B; never dispatch a
  second qa-agent at Stage 6. The **planner and spec-agent are both single-phase**: resume either
  (`SendMessage`) only to forward *change requests*; on approval neither needs a resume. The
  **implementator is resumed** (same instance from Stage 3) for every fix round — it applies fixes in
  place in its existing worktree, so never spawn a fresh implementator per round. Only the **reviewer**
  is dispatched fresh each round, always with the **worktree path + branch** (on the Stage-0 reviewer
  model; `fable` base escalates to `opus` for a round after a Critical finding).
- **Model selection (Stage 0)**: ask the user — via `AskUserQuestion` — for the **planner** and
  **reviewer** models (options `opus`/`fable`) before Stage 1/2. The `model` param pre-answers the
  planner question. Spec-agent (when run) reuses the planner-model answer — no separate question.
  Applies to planner + spec-agent + reviewer only.
- **On a halt** (review cap reached or implementation failed): keep the parallel qa-agent instance
  alive, do not run its Phase B, and report whether its plan is ready or still authoring.
- **Never skip a gate**, and never commit when the review is unresolved after the cap.
- **Git ops go through the Haiku agent** with: no co-author line, ff-only pulls on the same branch
  only, and the repo PR template.
- Pass `stage` through to qa-agent unchanged; do not invent one.
- **`--spec` changes only Stage 1's presence** — every other stage's mechanics (models, gates, loop
  cap, git ops, usage reporting) are unchanged whether or not it ran.
- **Stage 8 never gates and never fails the run** — it always attempts to run after Stage 7, but any
  skip (env var unset, ticket didn't touch edu-frontend) or failure (commit/push error) is noted in
  the report and otherwise ignored. The shipped PR's success is independent of Stage 8's outcome.
- **Never quote token numbers** — you have no tool to read them. Usage is surfaced per § Usage
  reporting, not by inventing figures.

## Usage reporting

You cannot read token counts (no tool exposes per-agent or session usage to the orchestrator —
`TaskGet`/`TaskList`/`TaskOutput` and the Agent result carry no usage data). So **point, don't
quote**:

- **After each agent finishes** a stage (spec-agent when run, planner, implementator per round,
  reviewer per round, the Haiku git agent, qa-agent), add a one-line note that its token usage is shown
  on that task's line in the Claude Code UI.
- **At the end of the flow** (Stage 7), tell the user to run **`/cost`** for the full-session total
  across all agents.
- Never print a number you didn't get from a tool — there is no such tool, so never print one at all.

## Versioning

This skill and its subagents (four always, five when `--spec` is used) are versioned with **SemVer**
(`version:` in each frontmatter). The orchestrator is the **contract owner** — bump its MAJOR whenever
an inter-stage handoff changes.

- **MAJOR** — breaking contract change: a stage's inputs/outputs, the gate structure, or the data
  passed between stages (approved-spec text, approved-plan text, worktree path + branch, PR URL, the
  reviewer's `Ready to commit?` verdict line).
- **MINOR** — new backward-compatible capability (e.g. an agent gains a skill or step).
- **PATCH** — wording/clarity/typo, no behavior change.

**Compatibility (current):** `ship` 3.2.0 expects `spec-agent` ≥1.0.0 (single-phase, WHAT/WHY only, no
codebase read — dispatched only when `--spec` is used), `task-planner-agent` ≥2.1.0 (accepts an
optional approved-spec input and skips its own ticket read when one is present), `implementator-agent`
≥1.3.0 (persists plan/spec into the worktree as `specs/<TICKET>/*.md` only in `--spec` mode),
`reviewer-agent` ≥1.2.1 and `qa-agent` ≥2.4.0 (both prefer reading `specs/<TICKET>/*.md` from the
worktree when it exists, falling back to relayed text otherwise; `qa-agent` no longer posts its plan
to the PR, only results), and `engineering-insights` ≥1.0.0 (bundled skill, used by Stage 8 — takes a
target path via `args`, no routing of its own). If a subagent's MAJOR advances, re-check its handoff
against the stage that consumes it before bumping this list. Record every bump in
`plugins/ship/agents/CHANGELOG.md`.
