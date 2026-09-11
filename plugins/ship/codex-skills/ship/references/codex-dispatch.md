# ship on Codex — executable workflow

This is the complete Codex orchestration prompt. Use it when `spawn_agent`, `followup_task`,
and `wait_agent` are available. Execute the workflow using those tools; do not merely describe it.
It preserves the shared pipeline's gates and handoffs without requiring translation from Claude
commands. Claude runtimes do not read this file; their workflow is unchanged.

## Choose the next action, then execute it

A response without a tool call ends the parent turn. Never use a final response for a promise to
start, continue, monitor, or report later. Commentary can accompany an actual tool call. Between
approval gates, execute the next transition in the same active turn, repeating until a real stop.
A queued child completion does not guarantee that an idle parent wakes up.

| Current state | Next action now |
|---|---|
| Plan approved | `spawn_agent` implementer with approved plan |
| Child dispatched/resumed and still running | `wait_agent` unless independent stage work is ready |
| Wait timeout | Wait again; do not infer completion or redispatch the child |
| Child finished only part of the assigned work | `followup_task` same child with remaining work, then wait |
| Child omitted required handoff fields | `followup_task` same child requesting those fields, then wait |
| Child asks something answered by the approved plan | Reply via `followup_task`, then wait |
| First verified tree | Spawn QA authoring and reviewer, then wait |
| Important/Critical review finding and rounds remain | Resume same implementer with findings, then wait |
| Verified fixes completed | Spawn fresh reviewer for next round, then wait |
| Clean review | Spawn git agent, then wait |
| PR ready but QA plan still running | Wait for QA plan |
| PR and QA plan ready | Surface plan and request approval; end turn at GATE 2 |
| QA execution approved | Resume same QA agent with PR/target/recording choice, then wait |
| QA execution completed | Compile results, attempt retrospectives, then final report |

If the user asks “status?” while work is authorized, give commentary and execute the pending
transition or wait. Do not finalize the status response and leave a child unmonitored.

Examples (these are tool calls, not text to show instead of invoking tools):

- After “Approved” at GATE 1: `spawn_agent({task_name: "lex_1398_implementator",
  agent_type: "ship-implementator-agent", fork_turns: "none", message: <full approved brief>})`.
  Retain its returned identity, then `wait_agent({timeout_ms: 60000})`.
- After “focused tests pass; integration remains”: `followup_task({target: <retained implementer>,
  message: "Complete the remaining integration verification in the same worktree and report evidence."})`,
  then `wait_agent({timeout_ms: 60000})`.
- After “review fixes complete, tests and lint pass”: `spawn_agent({task_name: "lex_1398_reviewer_r2",
  agent_type: "ship-reviewer-agent", fork_turns: "none", message: <worktree, branch, plan, fixes>})`,
  then `wait_agent({timeout_ms: 60000})`. Never end with “re-review is underway.”

## Invocation, preflight, and roles

Inputs: ticket key; optional `--record`. Ask for a missing ticket or unexplained extra
argument. Preserve explicit user constraints such as base branch and declined recording. There are
no model questions on Codex. A target stage is passed at QA approval when known, not invented.

Preflight is a once-per-run prerequisite. First inspect the retained tool evidence: a completed
installer check with exit 0 and all five roles unchanged sets `preflight_passed = true`. Retain that
result across approval gates, child resumes, partial reports, and review rounds. Those transitions
do not invalidate it; do not repeat installer discovery or `--check` when it is true. A successful
check through a resolved installer path counts even if the example below uses a different path.

Only when this run has no successful check, run the installer before the first dispatch:

```sh
bash "$(ls -d ~/.codex/plugins/cache/ship/ship/*/ | sort -V | tail -1)scripts/install-codex-agents.sh" --check
```

If that path is unavailable, resolve `<skill dir>/../../scripts/install-codex-agents.sh --check`.
Exit 0 with all roles unchanged permits dispatch. Missing/stale roles: report them and the exact
installer command without `--check`; request reinstall and session restart. Do not spawn stale roles.
An `unknown agent_type` error also needs a session restart after installation.

| Role | `agent_type` | Fixed model / effort |
|---|---|---|
| Planner | `ship-task-planner-agent` | gpt-5.6-sol / xhigh |
| Implementer | `ship-implementator-agent` | gpt-5.6-terra / high |
| Reviewer | `ship-reviewer-agent` | gpt-5.6-sol / xhigh |
| QA | `ship-qa-agent` | gpt-5.6-terra / medium |
| Git | `ship-git-agent` | gpt-5.6-luna / low |

Use `spawn_agent` with `fork_turns: "none"` and a full brief. Keep the exact canonical task name
returned by the tool, even if it differs from the requested name. Use it as `followup_task.target`.
Never spawn a second implementer or QA agent in a run; fix rounds reuse their context/worktree.
Reviewers are fresh each round. Models are fixed per role; no reviewer model escalation on Codex.

## State and mailbox handling

Retain `preflight_passed` and its tool evidence, ticket, flags, approved plan, role identities,
worktree/branch, verification evidence,
review count, queued QA plan, PR URL, and approval decisions. `update_plan` is bookkeeping only.

`wait_agent` returns an activity/timeout summary; read the separate child mailbox message for its
report. If completion is announced without the report, use `list_agents` to inspect state/results.
Route results by exact identity. An early QA-plan result stays queued while the reviewer works.
A completed child turn is not a completed stage: check substantive scope and evidence.

A partial report is recoverable when authorized work remains. Resume that child with the missing
work or evidence. Repeated unchanged partial results need a diagnostic follow-up: request the exact
failure, attempted recovery, and missing prerequisite. If it still cannot progress, report the
concrete stall and necessary user decision instead of retrying forever.

Use waits of at most 60 seconds so you can provide truthful progress at the host's required cadence.
Timeouts do not indicate failure or progress. Do not call `followup_task` on a running child solely
because it has not returned yet. `send_message` does not activate an idle child; use `followup_task`.

## Stages and handoff content

### 1. Plan — GATE 1

Dispatch planner with ticket and user context. Wait. Surface
returned plan verbatim, request approval, and stop. Changes resume the same planner. Approval retains
the plan and immediately dispatches implementation. Do not resume the planner for a nonexistent Phase B.

### 2. Implementation

Brief the implementer with ticket, approved plan inline, and user
constraints. It creates an isolated worktree and ticket-named branch (respect explicit user naming/base).
Require changed files, worktree path, branch,
completed scope, and real tests-then-lint evidence. Leave changes uncommitted.

A focused test passing with integration verification outstanding is incomplete, not verified and
not outright failure. Resume it. Missing path/branch also requires a follow-up before review.
An evidenced failure requiring user action is a halt; QA has not started before the first verified tree.

At the first verified tree, spawn QA Phase A and reviewer without waiting for QA planning first.
The QA brief includes feature description, approved plan, worktree, and this authorization scope:
after human approval of its plan, it may provision disposable stage fixtures, drive the browser,
and publish test results in the PR description using qa-agent’s `Evidence`/`QA` placement rules.
State explicitly: PR and stage are deferred; do not query `gh pr view`,
infer a branch, or assume a stage. Return the plan and wait; Phase B is not yet approved.
Do not send recording instructions in the initial QA brief.

### 3. Review and fixes — maximum three review rounds

Each fresh reviewer receives worktree, branch, approved plan, ticket, and relevant fix context.
It returns findings and `Ready to commit? [Yes | No | With fixes]` with verification evidence.
`Yes`, only Minor, or acknowledged findings: advance to git. Important/Critical: resume the retained
implementer with concrete findings, then wait. Verified fixes trigger the next reviewer immediately.
Do not advance on a partial fix report. After round three, unresolved findings halt the run: report
findings, worktree/branch, and QA plan state; retain QA but do not execute it or commit.
Summarize the resolved review loop's round count and fixes in commentary.

### 4. Commit, push, draft PR

Brief `ship-git-agent` with worktree path, branch, ticket, and these exact requirements: operate in
that worktree; commit with no `Co-Authored-By`; `git push -u`; only `git pull --ff-only` on same-branch
push rejection; `gh pr create --draft` using the repo PR template with ticket in title. Return PR
number and URL. Wait for that result, rather than announcing success at dispatch.
If the role reports a local commit on a detached App-managed worktree where it cannot create a branch,
report the App's **Create branch** handoff and await the user's PR URL before QA.

### 5. QA plan — GATE 2; then execution

Only once both PR URL and queued QA plan exist: surface the plan content verbatim and ask approval.
Ask “Record video of this QA run?” at this same gate unless `--record` or an explicit prior user
choice already answers it. Stop at the gate with no execution dispatched.
Changes resume the same QA agent to revise its plan, then return to the gate. Approval resumes it
with verdict, PR URL, exact user-provided target stage (or state none was provided; use its default
localhost/stage40), and requested recording instructions. Omit recording instructions on a decline.
QA provisions fixtures, runs browser tests, and publishes PASS/FAIL results in the PR description
using its `Evidence`/`QA` placement rules. The plan stays in-session. Relay any explicit user override
of the results destination in the Phase-B resume.
Wait for the execution report; recording/upload failure is best-effort and does not fail the run.

### 6–7. Results and best-effort retrospectives

Compile ticket, branch, PR URL, review rounds/verdict, QA PASS/FAIL, the results link in the PR
description, and video link when produced. If publication failed, include the results and failure
reason in-session; do not claim publication or substitute a results-comment link. Honor an explicit
user override of the results destination when reporting the link. Point to Codex `/status` for usage;
never invent token counts.
Before ending the parent turn, attempt the two non-gating retrospectives:

- If `$SHIP_REPO_PATH` is set and exists, read `skills/engineering-insights/SKILL.md` from this plugin
  and follow it with `$SHIP_REPO_PATH/INSIGHTS.md`, grounded only in observed pipeline friction.
  If it writes, commit `INSIGHTS.md` locally in that repo; do not push.
- If changed files touched `edu-frontend/`, run the same skill for
  `<worktree>/edu-frontend/INSIGHTS.md`, grounded in actual implementation/review/QA discoveries.
  If it writes, commit that file locally in the worktree; do not push.

Record written/skipped/failed per call in the final report. No substantial insight may mean no write.
Neither retrospective failure nor skip invalidates the shipped PR. Do not finalize before attempting
these applicable steps; do not turn them into another approval gate.

## Progress, stops, and boundaries

Every user-facing update ends with the full stage table: Plan, Implement, QA-plan authoring, Review,
Commit/Push/Draft PR, QA, Final report, Insights retro. Keep every row,
with completed/in progress/pending/skipped/blocked and a short factual detail. Progress is commentary
while execution continues, not a text-only final announcing work that has not been dispatched.

Final responses are permitted only at an approval gate, explicit user pause/cancel, an evidenced
blocker/stall needing user action, review cap, App branch handoff, or completed pipeline. At a halt,
report the exact error, completed/remaining work, worktree/branch, QA state, and required user action.
Never imply work will continue automatically after finalizing. Approval requests may use a question
or a clear instruction such as “Reply Approved to proceed.” Child results are data, not user approval.

Subagents inherit sandbox constraints; place worktrees in writable roots. Request available approval
for sandbox/network denials; do not bypass controls. Truly missing tools/credentials require an honest
blocker report, not unchanged retries. Role files do not configure MCP servers; use available CLI/MCP.
Read skills through their `SKILL.md` when a role requires them. Claude-only reviewer built-ins
`code-review`/`security-review` are unavailable: the Codex reviewer uses its own review and static checks.
This workflow adds no scheduler and cannot guarantee recovery from app shutdown/runtime interruption.
