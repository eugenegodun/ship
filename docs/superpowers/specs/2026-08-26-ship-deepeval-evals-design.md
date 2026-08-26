# ship deepeval eval suite — design

**Date:** 2026-08-26
**Status:** approved design, pending implementation plan

## Goal

Evaluate the `/ship` orchestrator (`plugins/ship/skills/ship/SKILL.md`, v3.8.0) and its five
subagents with [deepeval](https://deepeval.com/integrations/frameworks/anthropic), running
automatically on GitHub CI for PRs that touch the plugin.

## Decisions (settled during brainstorming)

| Decision | Choice |
|----------|--------|
| Existing TS `evals/` folder (DevDigest vitest harness, untracked) | **Removed and replaced** by the deepeval suite |
| Eval scope | **Agent-level + orchestration-level** (plus a small nightly E2E tier) |
| Judge LLM | **OpenAI** (`gpt-4.1` class, configurable) — avoids Anthropic-judging-Anthropic self-preference; needs `OPENAI_API_KEY` |
| Generation LLM | Anthropic, `EVAL_MODEL` env var, default `claude-sonnet-5` (orchestrator rules too subtle for Haiku); needs `ANTHROPIC_API_KEY` |
| CI trigger | **Path-gated PR job** (`plugins/ship/**`, `evals/**`); agent-level + decision-point suites **blocking**, E2E **nightly non-blocking** |
| Orchestration harness | **Both**: single-shot decision-point sims (blocking, per-PR) + multi-turn `claude-agent-sdk` scenarios with stubbed subagents (nightly) |

## Architecture — three tiers, one Python package

The suite lives at `evals/` as a Python package managed with `uv`, depending on `deepeval`,
`pytest`, `anthropic`, and `claude-agent-sdk`.

| Tier | What runs | How | CI role |
|------|-----------|-----|---------|
| **Agent-level** | Each agent's `.md` as system prompt + fixture inputs, via deepeval's wrapped Anthropic client (`from deepeval.anthropic import Anthropic`) | Single `messages.create()` per case, judged by GEval rubrics; deterministic asserts where the contract is exact (e.g. the reviewer verdict line) | Blocking |
| **Orchestrator decision-points** | `ship/SKILL.md` as system prompt + a fixture mid-pipeline transcript + real tool schemas (`Agent`, `SendMessage`, `AskUserQuestion`, `Skill`, `TodoWrite`) | One `messages.create()` with `tools=[...]`; assert the next tool call(s) via `ToolCorrectnessMetric` + GEval | Blocking |
| **E2E pipeline** | Orchestrator played multi-turn in the Python `claude-agent-sdk` with stubbed subagents (canned spec/plan/review/QA replies); assert the full trace: dispatch order, gate stops, resume-vs-respawn | 3–5 scenarios | Nightly + manual, non-blocking |

## Eval catalog

### Orchestrator decision-point cases (~20, mapping 1:1 to SKILL.md contracts)

Each case = a fixture transcript (a mid-pipeline conversation state) + the expected next tool
call(s).

- **Routing / Stage 0** — `--spec` dispatches spec-agent first; without it, planner directly;
  `model` param pre-answers the planner question (no `AskUserQuestion` for it); unknown
  stage/model token → asks instead of guessing; missing TICKET → asks.
- **Gate discipline** — plan returned → surfaced verbatim + STOP (no implementator dispatch in
  the same turn); change request → `SendMessage` to the *same* planner instance, never a fresh
  agent; approval → implementator dispatched with approved plan inline + ticket id.
- **Parallel QA branch** — first verified tree → background qa-agent dispatch
  (`run_in_background: true`) whose brief contains the deferred-PR instruction and the user's
  `/ship` invocation *verbatim*; the QA plan is not surfaced before the PR exists.
- **Review ⇄ fix loop** — Critical/Important finding → resume the *same* implementator via
  `SendMessage` (never a new worktree); reviewer re-dispatched fresh each round with
  worktree + branch; escalation to `claude-opus-5[1m]` when base ≠ opus and the previous round
  was Critical; round-3 still dirty → halt: no commit, findings summarized, qa-agent kept alive.
- **Stage 5 / GATE 3** — Haiku git-agent brief carries explicit worktree path + branch, no
  co-author line, draft PR with the repo template; Phase-B resume carries the user's approval
  quoted verbatim + PR URL; never a second qa-agent at Stage 6.
- **Negative guardrails** — Stage 7 report contains no invented token numbers (GEval: points to
  `/cost` instead); gates never skipped.

### Agent-level cases (~2–3 per agent)

- **spec-agent** — feature ticket → user stories + falsifiable EARS criteria, WHAT/WHY only
  (rubric penalizes implementation detail); refactor-shaped ticket → "Invariants to preserve"
  instead of new criteria.
- **task-planner-agent** — approved spec + code-excerpt fixture → plan grounded in the fixture,
  enumerates skills, writes no product code.
- **reviewer-agent** — fixture diff with seeded bugs → catches the seeded Critical, groups
  Critical/Important/Minor, emits the exact `Ready to commit? [Yes | No | With fixes]` verdict
  line (deterministic assert + judge).
- **qa-agent** — feature description → Phase-A plan quality (concrete cases with
  id/preconditions/steps/expected, flag-gating named); *authorization negative*: a non-default
  stage or Phase-B approval delivered only as an orchestrator paraphrase (no quoted user words)
  → the agent **stops and asks the orchestrator for the verbatim provenance before any stage
  mutation** (per `qa-agent.md` "Inputs → stage" and "The approval channel"), rather than
  proceeding. No real stage is touched at this tier — the eval judges the response text.
- **implementator-agent** — skipped at this tier (meaningless without a real repo); covered by
  the nightly E2E scenario only.

### E2E scenarios (nightly)

1. Happy path without `--spec`: plan → approve → implement → 1 clean review round → PR → QA gate.
2. `--spec` path: spec gate → plan gate → onward; spec text flows into the planner brief.
3. Fix-loop cap: 3 dirty rounds → halt with no commit, qa instance reported alive.
4. Stage-3 failure: no verified tree → stop; qa-agent never launched.
5. Model escalation: sonnet reviewer + Critical in round 1 → round 2 on opus.

## Layout

```
evals/
  pyproject.toml                 # uv; deepeval, pytest, anthropic, claude-agent-sdk
  conftest.py                    # judge config, EVAL_MODEL, deepeval settings
  src/ship_evals/                # harness: load_skill()/load_agent(), transcript builder,
                                 #   tool schemas mirroring Claude Code's Agent/SendMessage/...
  agents/<agent>/test_*.py       # + fixtures/ (tickets, diffs, specs) and goldens/*.json
  orchestrator/test_*.py         # routing, gates, review_loop, parallel_qa, guardrails
    fixtures/transcripts/*.json  # mid-pipeline conversation states
  e2e/test_pipeline_sdk.py       # nightly SDK scenarios + stub subagent replies
```

Local runs: `deepeval test run evals/agents evals/orchestrator` (or plain `pytest`);
E2E via `pytest evals/e2e -m e2e`.

## GitHub CI

`.github/workflows/ship-evals.yml`, two jobs:

- **`evals-pr`** (blocking, required check) — `pull_request` with
  `paths: [plugins/ship/**, evals/**]`. Steps: checkout → `uv sync` →
  `deepeval test run evals/agents evals/orchestrator`. Secrets: `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`. Concurrency group cancels superseded runs per PR; deepeval retries absorb
  one-off LLM flakes.
- **`evals-e2e`** (non-blocking) — `schedule` (nightly) + `workflow_dispatch`; runs `evals/e2e`,
  uploads the deepeval report artifact and writes a job-summary digest. Never a required check.

## Out of scope (YAGNI)

Confident AI cloud, evaluating `workflow-retro` / `engineering-insights` skills, cost/latency
benchmarking, and real-Jira/real-GitHub end-to-end runs (the E2E tier stubs subagents; it tests
orchestration, not connectivity).
