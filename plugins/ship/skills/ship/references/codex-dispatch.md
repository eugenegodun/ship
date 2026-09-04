# ship on Codex — dispatch reference

Read this only when your tool list has `spawn_agent` / `followup_task` / `wait_agent` (Codex
multi-agent V2). It maps every tool call in `SKILL.md` onto Codex. The pipeline itself — stages,
gates, the 3-round review cap, the handoff contract — is unchanged. Where this file and `SKILL.md`
disagree on *what* to do, `SKILL.md` wins; this file only says *how* on Codex.

## Preflight (before Stage 0)

The six pipeline roles must be installed as Codex custom agents (Codex plugins cannot ship them).
Run:

```bash
bash "$(ls -d ~/.codex/plugins/cache/ship/ship/*/ | sort -V | tail -1)scripts/install-codex-agents.sh" --check
```

If that path does not resolve on your install, resolve the installer relative to the `SKILL.md` you
just read instead: `<skill dir>/../../scripts/install-codex-agents.sh --check`.

- Exit 0 (every line `unchanged`) → proceed.
- Anything else (`missing/stale` lines) → do **not** spawn anything. Tell the user which roles are
  missing or stale and give them the exact command to run themselves — the same path without
  `--check` — because the sandbox may not allow writes under `~/.codex/`. Roles load at session
  start, so also tell them to restart the Codex session afterwards. Then **stop**.
- If a later `spawn_agent` fails with `unknown agent_type`, the session predates the install: ask
  the user to restart Codex and re-run `/ship`.

## Roles

| `SKILL.md` agent | Codex `agent_type` | model / effort | sandbox |
|---|---|---|---|
| spec-agent | `ship-spec-agent` | gpt-5.6-sol / xhigh | read-only |
| task-planner-agent | `ship-task-planner-agent` | gpt-5.6-sol / xhigh | read-only |
| implementator-agent | `ship-implementator-agent` | gpt-5.6-terra / high | workspace-write |
| reviewer-agent | `ship-reviewer-agent` | gpt-5.6-sol / xhigh | workspace-write |
| qa-agent | `ship-qa-agent` | gpt-5.6-terra / medium | workspace-write |
| Stage 5 "Haiku agent" | `ship-git-agent` | gpt-5.6-luna / low | workspace-write |

Models are fixed per role (`spawn_agent` has no model parameter). To change one, edit `ROLES` in
`plugins/ship/scripts/sync_codex_agents.py`, re-run it, and re-run the installer.

## Stage 0 on Codex

Skip both model questions. Post one line — *"Codex run — models are fixed per role: planner/spec
gpt-5.6-sol xhigh, reviewer gpt-5.6-sol xhigh, implementator gpt-5.6-terra high, QA gpt-5.6-terra
medium, git gpt-5.6-luna."* — then build the checklist with `update_plan` and continue exactly as
`SKILL.md` describes. In the progress table, the model detail reads "fixed per role (Codex)".

## Tool mapping

| `SKILL.md` says | On Codex call |
|---|---|
| `Agent(subagent_type: X, model: M, prompt: B)` | `spawn_agent {task_name: "<TICKET>-<role>", agent_type: "ship-X", fork_turns: "none", message: B}` |
| `Agent(…, run_in_background: true)` | the same `spawn_agent` — every spawn is already asynchronous; keep working |
| `SendMessage(agent_id, message)` | `followup_task {target: <the task_name spawn_agent returned>, message}` — retain and pass back the exact string `spawn_agent` returned, not a re-derived one |
| `TaskOutput` / waiting for a background agent | `wait_agent {timeout_ms: 300000}`; a child's final answer also lands in your mailbox at the start of your next turn |
| `AskUserQuestion` | nothing — end the turn with the material and the question in prose |
| `TodoWrite` | `update_plan` |
| `Skill(skill, args)` | read that skill's `SKILL.md` from `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md` and follow it with the same `args` |
| `Bash` | `shell` |

`<role>` is one of `spec`, `planner`, `implementator`, `reviewer-r<N>` (N = review round), `qa`,
`git` — e.g. `LEX-1398-implementator`. That `<TICKET>-<role>` scheme is what you *request* in
`spawn_agent`'s `task_name` parameter; `spawn_agent` returns its own canonical task name (e.g.
`/root/LEX-1398-implementator`), which may differ in form. **Retain the returned value per role** and
pass it back verbatim as `followup_task`'s `target` — never the requested string, never a
re-derived one. Every role has exactly one task per run, except the reviewer, which `SKILL.md`
dispatches fresh each round.

## Rules that change shape on Codex

1. **Clean context, full brief.** Always `fork_turns: "none"` (Codex refuses `agent_type` on a
   full-history fork). The brief must carry everything the agent needs — approved spec/plan text
   inline, ticket id, worktree path + branch, PR URL — exactly as `SKILL.md` already requires.
2. **Resume = `followup_task` on the same task, targeted by the value `spawn_agent` returned.** Fix
   rounds (implementator), change requests (spec-agent, planner, qa-agent), and the QA Phase-B
   resume all go to the existing agent — pass `followup_task`'s `target` the exact task name
   `spawn_agent` gave you for that role (its canonical form, e.g. `/root/LEX-1398-implementator`),
   not the `<TICKET>-<role>` string you requested. Never `spawn_agent` a second implementator or
   qa-agent in a run. A child Codex evicted while idle is reloaded transparently by `followup_task`.
3. **Gates.** GATE 1/2/3: surface the spec / plan / QA plan verbatim, ask for approval in prose, and
   end the turn with no *pending* work — an `update_plan` before the gate prose is fine, but no
   dispatch/resume after it. GATE 3 also asks "Record video of this QA run?" unless `--record` was
   passed. The user's next message is the verdict.
4. **Parallel QA branch.** After the first verified tree, `spawn_agent` the qa-agent with the
   deferred-PR brief from `SKILL.md` and continue immediately with the reviewer. At Stage 6, if the
   qa-agent's plan has not reached your mailbox, `wait_agent {timeout_ms: 300000}` — never poll with
   short timeouts. `wait_agent` returns on *any* child's activity; if the qa-agent's plan arrives
   before the reviewer's result, keep it queued (`SKILL.md`: do not surface it yet) and `wait_agent`
   again.
5. **Reviewer escalation.** `SKILL.md` escalates a re-review round to `claude-opus-5[1m]` after a
   Critical finding. Models are per-role on Codex, so this is a no-op: run the round on
   `ship-reviewer-agent` as usual. Cap (3), verdict line, and halt behavior are unchanged.
6. **Stage 5 git ops.** Instead of a Haiku `claude` agent: `spawn_agent {task_name: "<TICKET>-git",
   agent_type: "ship-git-agent", fork_turns: "none", message: <brief>}`. The message must explicitly
   state every one of: the **worktree path** (the role's first step is `cd` into it — omitting the
   path leaves it nothing to `cd` into), the **branch name**, the **ticket id**, that there must be
   **no `Co-Authored-By`**, `git push -u` with `git pull --ff-only` only on a rejection, a
   `gh pr create --draft` from the repo template with the ticket in the title, and that it must
   return the PR number + URL. If it reports a detached HEAD it may not branch from (a Codex
   App-managed worktree), it has committed locally: report the App's **Create branch** hand-off
   instead of a PR URL and wait for the user to provide the PR before Stage 6.
7. **Stage 8.** Same two calls; "dispatch the `engineering-insights` skill" means read
   `skills/engineering-insights/SKILL.md` from the plugin cache and follow it with the given `args`.
8. **Usage reporting.** You still cannot read token counts. Point the user to Codex's `/status`;
   never quote a number.
9. **Progress display.** `update_plan` is bookkeeping only; every user-facing update still ends with
   the full stage table from `SKILL.md`.

## Sandbox notes

- Subagents inherit your sandbox; a role's `sandbox_mode` only adjusts it per role. The
  implementator's worktree must sit under a writable root — `superpowers:using-git-worktrees`
  detects an existing linked worktree or detached HEAD before creating one.
- Codex sandboxes block network by default. Planner/spec-agent (`jira`), the git role (`git push`,
  `gh pr create`), and qa-agent (Playwright, `curl`, package installs) all need it. If a role hits a
  network denial, tell the user to add `network_access = true` under `[sandbox_workspace_write]` in
  `~/.codex/config.toml` (plus `writable_roots` if the implementator's worktree lives outside the
  repo), or to run the session under an approval policy that lets subagents request escalation.
- On a sandbox denial, a role should **request approval** rather than give up — reserve "report the
  blocker and stop" for genuinely missing tools/credentials (see `_preamble.md`).

## Known limits

- No per-run model choice on Codex (edit `ROLES`, re-run the sync script, re-install).
- Role files set no `mcp_servers`; agents use CLI tools (`jira`, `gh`) or whatever MCP servers the
  Codex session already has.
- `reviewer-agent`'s `code-review` and `security-review` skills are Claude Code built-ins that do not
  exist on Codex. The Codex reviewer runs its own diff review + static checks only — no skill
  dispatch for those two steps; the preamble's "say so and continue" rule applies.
