# ship on Codex — design

**Date:** 2026-09-03
**Status:** approved design, pending implementation plan

## Goal

Run the `/ship` pipeline — (spec →) plan → implement → review⇄fix loop → commit/push/draft-PR → QA →
report → insights — inside **Codex** (CLI 0.147+, multi-agent V2) with the same five agents, **without
changing how Claude Code `/ship` behaves**.

## Hard constraint — Claude Code path is unaffected

Claude Code auto-discovers exactly two plugin directories: `plugins/ship/agents/` and
`plugins/ship/skills/`. Everything Codex-specific lives outside them, and the two files Claude does
read change only in ways Claude ignores:

| Claude-visible artifact | Change |
|---|---|
| `plugins/ship/agents/*.md` (5 agents) | **none** — Codex role files are *generated from* these |
| `plugins/ship/skills/ship/SKILL.md` | frontmatter `version` 4.1.0 → 4.2.0, plus **one appended section** that tells a Codex runtime to read `references/codex-dispatch.md` and tells a Claude runtime to ignore it |
| `plugins/ship/skills/engineering-insights/`, `workflow-retro/` | none |

Proof, not intention: the existing deepeval suite (unit + agent + decision-point tiers) is run before
and after; the Claude-facing tiers must be identical. `git diff main -- plugins/ship/agents` must be
empty and `git diff main -- plugins/ship/skills/ship/SKILL.md` must contain only the version line and
the appended section.

## Decisions (settled during brainstorming)

| Decision | Choice | Why |
|---|---|---|
| Where Codex mechanics live | `skills/ship/references/codex-dispatch.md`, loaded only when the runtime's tool list has `spawn_agent` | keeps `SKILL.md` text (which 20 decision-point evals assert against) unchanged |
| Agent roles on Codex | TOML role files in `plugins/ship/codex-agents/`, **generated** from `agents/*.md` by a stdlib Python script with a `--check` drift mode | single source of truth stays the Claude `.md`; CI fails on drift |
| Stage 0 model question on Codex | **dropped** — models are baked per role in the TOML | `spawn_agent` has no `model`/`reasoning_effort` params; cross-family review (the question's purpose) is impossible on Codex anyway |
| Role installation | `scripts/install-codex-agents.sh` copies TOMLs into `~/.codex/agents/` (`--to DIR` for repo-scoped `.codex/agents/`; `--check` for preflight) | Codex plugins **cannot bundle agent roles** (`plugin.json` supports only `skills`, `hooks`, `mcpServers`, `apps`, `interface`); copy not symlink because the plugin cache path is versioned |
| Git stage | new hand-written role `ship-git-agent` on a fast model | Claude uses the generic `claude` subagent + `model: haiku`; Codex needs a named role |
| Codex evals | new decision-point tier `evals/orchestrator_codex/` driven through the OpenAI API with V2 tool schemas; its own CI job | proves Codex behavior without touching the Claude tiers |

## Verified Codex facts this design relies on (codex-cli 0.147.0, 2026-09-03)

- `multi_agent` is `stable true` by default; sessions report `multi_agent_version: v2`.
- V2 collaboration tools: `spawn_agent {task_name, message, fork_turns: "none"|"all"|"<int>", agent_type?}`,
  `followup_task {target, message}` (resume + trigger a turn), `send_message` (no turn),
  `wait_agent {timeout_ms}`, `interrupt_agent {target}`, `list_agents`. **No `close_agent`** in V2.
  `agent_type` is refused when `fork_turns: "all"`. No `model`/`reasoning_effort` params.
- Custom roles: TOML in `~/.codex/agents/` (personal) or `<repo>/.codex/agents/` (project). Fields:
  `name`, `description`, `developer_instructions` (required, non-blank), `model`,
  `model_reasoning_effort`, `sandbox_mode` (`read-only` | `workspace-write`), `mcp_servers`.
  Built-ins: `default`, `worker`, `explorer`.
- `[agents]` config: `enabled`, `max_concurrent_threads_per_session`, `max_depth`,
  `default_subagent_model`, `default_subagent_reasoning_effort`, `job_max_runtime_seconds`.
- No `AskUserQuestion` equivalent: a gate = end the turn with the question as prose; the user's next
  message continues the run.
- Plugin cache path: `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/` — `ship@ship` 1.9.0
  is already installed there; its `skills/` load, its `agents/*.md` are inert.

## Architecture — new and changed files

```
plugins/ship/
├── agents/*.md                              (unchanged — source of truth)
├── codex-agents/                            NEW — Codex role files
│   ├── _preamble.md                         Codex adapter text prepended to every generated role
│   ├── ship-spec-agent.toml                 GENERATED
│   ├── ship-task-planner-agent.toml         GENERATED
│   ├── ship-implementator-agent.toml        GENERATED
│   ├── ship-reviewer-agent.toml             GENERATED
│   ├── ship-qa-agent.toml                   GENERATED
│   └── ship-git-agent.toml                  hand-written (Stage 5 role)
├── scripts/                                 NEW
│   ├── sync_codex_agents.py                 .md → .toml generator, `--check` drift mode (stdlib only)
│   └── install-codex-agents.sh              copy roles to ~/.codex/agents (`--to`, `--check`)
└── skills/ship/
    ├── SKILL.md                             version bump + appended "Platform adaptation — Codex"
    └── references/codex-dispatch.md         NEW — the Codex tool mapping, stage by stage
evals/
├── src/ship_evals/codex_tools.py            NEW — OpenAI function schemas for the V2 tools
├── src/ship_evals/codex_harness.py          NEW — OpenAI chat-completions driver + skill+reference loader
├── orchestrator_codex/                      NEW — Codex decision-point tier (fixtures + tests)
└── tests/                                   NEW unit tests: generator, install script, SKILL guard, versions
.github/workflows/ship-evals.yml             + `evals-codex` PR job
README.md, evals/README.md, plugins/ship/agents/CHANGELOG.md, 6 manifest versions
```

## Role file format (generated)

```toml
# GENERATED by plugins/ship/scripts/sync_codex_agents.py from plugins/ship/agents/<name>.md.
# Do not edit — edit the .md and re-run the script. CI fails on drift.
name = "ship-<name>"
description = "<first paragraph of the .md description, single line>"
model = "<see table>"
model_reasoning_effort = "<see table>"
sandbox_mode = "<see table>"
developer_instructions = '''
<contents of codex-agents/_preamble.md>

<verbatim body of agents/<name>.md, frontmatter stripped>
'''
```

TOML literal multi-line strings (`'''`) need no escaping; the generator fails if a body contains
`'''`. Role names carry the `ship-` prefix because `~/.codex/agents/` is a global namespace.

| Role (`agent_type`) | Source | model | effort | sandbox |
|---|---|---|---|---|
| `ship-spec-agent` | spec-agent.md | `gpt-5.6` | `xhigh` | `read-only` |
| `ship-task-planner-agent` | task-planner-agent.md | `gpt-5.6` | `xhigh` | `read-only` |
| `ship-implementator-agent` | implementator-agent.md | `gpt-5.6` | `high` | `workspace-write` |
| `ship-reviewer-agent` | reviewer-agent.md | `gpt-5.6` | `xhigh` | `workspace-write` (re-runs tests/lint, which write caches; the body already forbids editing code) |
| `ship-qa-agent` | qa-agent.md | `gpt-5.6` | `medium` | `workspace-write` |
| `ship-git-agent` | hand-written | `gpt-5.6-terra` | `low` | `workspace-write` |

Reviewer runs at a higher effort than the implementator on purpose — the closest Codex can get to
"a different model reviews". `mcp_servers` is intentionally omitted (format unverified; the agents
already prefer the Jira CLI). Changing a model = edit the table in `sync_codex_agents.py`, re-run it,
re-install.

### `_preamble.md` (Codex adapter, prepended to every generated role)

Tells the agent it is running in Codex and how to read the Claude tool names in its instructions:
`TodoWrite` → `update_plan`; "the Skill tool" / `<plugin>:<skill>` → find the skill's `SKILL.md`
(under `~/.codex/plugins/cache/*/*/*/skills/<skill>/SKILL.md` or `~/.codex/skills/<skill>/SKILL.md`),
read it and follow it; `Read`/`Grep`/`Glob` → shell (`cat`, `rg`, `find`) with absolute paths;
`mcp__claude_ai_Atlassian__*` → the `atlassian` MCP tools if present, else the Jira CLI; "ask the
orchestrator" → end your turn with the question as your final message (the orchestrator resumes you
with `followup_task`); "you may be resumed" → a `followup_task` arrives in the same thread with your
context intact.

## Codex dispatch mapping (`references/codex-dispatch.md`)

| `SKILL.md` says | On Codex do |
|---|---|
| **Preflight** (new, before Stage 0) | `bash <plugin-cache>/scripts/install-codex-agents.sh --check`. If it fails: print the install command (`… install-codex-agents.sh`, no flag) for the user to run — the sandbox may block writes to `~/.codex/` — and **stop**. |
| Stage 0 model questions | **Skip.** State the baked models once (planner/spec `gpt-5.6 xhigh`, reviewer `gpt-5.6 xhigh`, implementator `gpt-5.6 high`) and proceed. |
| `Agent(subagent_type: X, model: M)` | `spawn_agent {task_name: "<TICKET>-<role>", agent_type: "ship-X", fork_turns: "none", message: <brief>}` — clean context, brief carries everything (as today). |
| `Agent(run_in_background: true)` (qa Phase A) | same `spawn_agent`; it is already asynchronous — carry on with review. |
| `SendMessage(agent_id)` (fix rounds, change requests, Phase-B resume) | `followup_task {target: "<TICKET>-<role>", message}` on the **same** `task_name` — never a second `spawn_agent` for that role. |
| Collect the background QA plan (Stage 6) | if its result has not arrived in your mailbox, `wait_agent {timeout_ms: 300000}`; never poll under 60 s. |
| `AskUserQuestion` (GATE 1/2/3, recording question) | end the turn with the plan/spec/QA-plan verbatim and the question in prose; the user's reply is the verdict. |
| `TodoWrite` stage checklist | `update_plan`; the full stage table still goes in prose with every update. |
| Reviewer model escalation to `claude-opus-5[1m]` after a Critical | no-op (models are per-role); the round still happens. |
| Stage 5 "Haiku agent, `subagent_type: claude`" | `spawn_agent {agent_type: "ship-git-agent", task_name: "<TICKET>-git", fork_turns: "none", message: <same brief: commit, no co-author, push -u, ff-only, draft PR from template, return PR URL>}` |
| Stage 8 `Skill` tool | read `skills/engineering-insights/SKILL.md` from the plugin cache and follow it with the same `args`. |
| Usage pointer `/cost` | Codex shows usage in its own UI (`/status`); still never quote numbers. |
| Halt / cap reached | same; the QA thread stays alive (V2 evicts idle children automatically — that is fine, `followup_task` reloads them). |

Sandbox notes recorded in the reference: the implementator's worktree must be under a writable root
(`superpowers:using-git-worktrees` handles detection); if the Codex App leaves the repo in a detached
HEAD, Stage 5 commits locally and reports the App's "Create branch" hand-off instead of pushing.

## Evals

- **Unit (no model):** generator produces six parseable TOMLs whose `developer_instructions` end with
  the exact agent body; `--check` passes on fresh output and fails on tampering; install script copies
  and `--check`s correctly against a temp `HOME`; `SKILL.md` guard — the Codex section is the last
  `##` heading and no Codex tool name appears above it; all six manifests share one version.
- **Codex decision points (`orchestrator_codex/`, marker `codex`, OpenAI API, model
  `EVAL_CODEX_MODEL` default `gpt-4.1`):** system prompt = `SKILL.md` body + `codex-dispatch.md`;
  tools = V2 schemas; fixture transcripts in OpenAI chat format. Cases: (1) roles installed → first
  dispatch is `spawn_agent` with `agent_type: ship-task-planner-agent`, `fork_turns: "none"`, and no
  model question; (2) roles missing → no spawn, prose names the install script; (3) first verified
  tree → `spawn_agent ship-qa-agent` whose message says no PR exists yet; (4) Critical finding →
  `followup_task` targeting the implementator's `task_name`, no new implementator spawn; (5) clean
  review → `spawn_agent ship-git-agent` with worktree, "draft", and the no-co-author rule in the
  message. Runs as its own PR job (`evals-codex`) so a Codex regression is visibly Codex-only.
- Claude tiers: untouched, re-run as the regression proof.

## Versioning

- `ship` skill 4.1.0 → **4.2.0** (MINOR: new capability; no inter-stage contract change; compatibility
  floors unchanged). Agents' versions unchanged (their files are unchanged).
- Package 1.9.0 → **1.10.0** in all six tracked manifests (`plugins/ship/.{claude,cursor,codex}-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` ×2 fields, `.cursor-plugin/marketplace.json`,
  `.agents/plugins/marketplace.json`).
- `CHANGELOG.md`: one `ship — 4.2.0` entry and one `ship package — 1.10.0` entry.

## Out of scope

- `mcp_servers` wiring in role files; per-run model choice on Codex (`-fast` role variants); repo-scoped
  `.codex/agents/` commits into consuming repos (the install script's `--to` supports it manually);
  Cursor runtime behavior; changing any agent's instructions for Codex beyond the shared preamble.

## Risks

| Risk | Mitigation |
|---|---|
| Codex model ids (`gpt-5.6`, `gpt-5.6-terra`) differ on the user's plan | `spawn_agent` errors are surfaced verbatim; the table is a one-line edit + re-run |
| Roles installed into `~/.codex/agents/` are picked up only on session start | reference tells the orchestrator to ask the user to restart the Codex session on `unknown agent_type` |
| Sandbox blocks the worktree path or `~/.codex` writes | preflight stops with the exact command for the user to run; worktree note in the reference |
| `EVAL_CODEX_MODEL` default too weak to follow the reference | env-overridable; the tier is a separate job, never blocks Claude tiers |
