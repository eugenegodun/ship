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
| spec-agent | `ship-spec-agent` | gpt-5.6 / xhigh | read-only |
| task-planner-agent | `ship-task-planner-agent` | gpt-5.6 / xhigh | read-only |
| implementator-agent | `ship-implementator-agent` | gpt-5.6 / high | workspace-write |
| reviewer-agent | `ship-reviewer-agent` | gpt-5.6 / xhigh | workspace-write |
| qa-agent | `ship-qa-agent` | gpt-5.6 / medium | workspace-write |
| Stage 5 "Haiku agent" | `ship-git-agent` | gpt-5.6-terra / low | workspace-write |

Models are fixed per role (`spawn_agent` has no model parameter). To change one, edit `ROLES` in
`plugins/ship/scripts/sync_codex_agents.py`, re-run it, and re-run the installer.

## Stage 0 on Codex

Skip both model questions. Post one line — *"Codex run — models are fixed per role: planner/spec
gpt-5.6 xhigh, reviewer gpt-5.6 xhigh, implementator gpt-5.6 high, QA gpt-5.6 medium, git
gpt-5.6-terra."* — then build the checklist with `update_plan` and continue exactly as `SKILL.md`
describes. In the progress table, the model detail reads "fixed per role (Codex)".

## Tool mapping

| `SKILL.md` says | On Codex call |
|---|---|
| `Agent(subagent_type: X, model: M, prompt: B)` | `spawn_agent {task_name: "<TICKET>-<role>", agent_type: "ship-X", fork_turns: "none", message: B}` |
| `Agent(…, run_in_background: true)` | the same `spawn_agent` — every spawn is already asynchronous; keep working |
| `SendMessage(agent_id, message)` | `followup_task {target: "<TICKET>-<role>", message}` on the **same** `task_name` |
| `TaskOutput` / waiting for a background agent | `wait_agent {timeout_ms: 300000}`; a child's final answer also lands in your mailbox at the start of your next turn |
| `AskUserQuestion` | nothing — end the turn with the material and the question in prose |
| `TodoWrite` | `update_plan` |
| `Skill(skill, args)` | read that skill's `SKILL.md` from `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md` and follow it with the same `args` |
| `Bash` | `shell` |

`<role>` is one of `spec`, `planner`, `implementator`, `reviewer-r<N>` (N = review round), `qa`,
`git` — e.g. `LEX-1398-implementator`. Every role has exactly one `task_name` per run, except the
reviewer, which `SKILL.md` dispatches fresh each round.

## Rules that change shape on Codex

1. **Clean context, full brief.** Always `fork_turns: "none"` (Codex refuses `agent_type` on a
   full-history fork). The brief must carry everything the agent needs — approved spec/plan text
   inline, ticket id, worktree path + branch, PR URL — exactly as `SKILL.md` already requires.
2. **Resume = `followup_task` on the same `task_name`.** Fix rounds (implementator), change requests
   (spec-agent, planner, qa-agent), and the QA Phase-B resume all go to the existing agent. Never
   `spawn_agent` a second implementator or qa-agent in a run. A child Codex evicted while idle is
   reloaded transparently by `followup_task`.
3. **Gates.** GATE 1/2/3: surface the spec / plan / QA plan verbatim, ask for approval in prose, and
   end the turn with **no tool calls**. GATE 3 also asks "Record video of this QA run?" unless
   `--record` was passed. The user's next message is the verdict.
4. **Parallel QA branch.** After the first verified tree, `spawn_agent` the qa-agent with the
   deferred-PR brief from `SKILL.md` and continue immediately with the reviewer. At Stage 6, if the
   qa-agent's plan has not reached your mailbox, `wait_agent {timeout_ms: 300000}` — never poll with
   short timeouts.
5. **Reviewer escalation.** `SKILL.md` escalates a re-review round to `claude-opus-5[1m]` after a
   Critical finding. Models are per-role on Codex, so this is a no-op: run the round on
   `ship-reviewer-agent` as usual. Cap (3), verdict line, and halt behavior are unchanged.
6. **Stage 5 git ops.** Instead of a Haiku `claude` agent: `spawn_agent {task_name: "<TICKET>-git",
   agent_type: "ship-git-agent", fork_turns: "none", message: <brief>}` with the same brief
   `SKILL.md` gives — commit on the ticket branch, **no `Co-Authored-By`**, `git push -u`,
   `git pull --ff-only` only on a rejection, `gh pr create --draft` from the repo template, ticket in
   the title, return PR number + URL. If it reports a detached HEAD it may not branch from (a Codex
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
- A role that cannot reach a tool it needs (`gh`, `jira`, network) reports the blocker in its final
  message; relay it to the user and stop rather than working around it.

## Known limits

- No per-run model choice on Codex (edit `ROLES`, re-run the sync script, re-install).
- Role files set no `mcp_servers`; agents use CLI tools (`jira`, `gh`) or whatever MCP servers the
  Codex session already has.
