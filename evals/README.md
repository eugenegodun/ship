# ship evals

deepeval suite for the `/ship` orchestrator (`plugins/ship/`). Spec:
`docs/superpowers/specs/2026-08-26-ship-deepeval-evals-design.md`.

## Tiers

| Tier | Where | What | CI |
|------|-------|------|----|
| Agent-level | `agents/` | each agent's `.md` + fixture inputs, GEval-judged | blocking on PRs |
| Decision-points | `orchestrator/` | SKILL.md + fixture transcript → assert the next tool call | blocking on PRs |
| E2E | `e2e/` | multi-turn simulator with canned subagent replies | nightly, non-blocking |

## Run

```bash
cd evals && uv sync
export ANTHROPIC_API_KEY=...   # generation (default model: claude-sonnet-5)
export OPENAI_API_KEY=...      # GEval judge (default: gpt-4.1)

uv run pytest tests -v                          # unit tests, no model calls
uv run deepeval test run agents orchestrator -v # the blocking PR suite
uv run pytest e2e -m "e2e" -v                   # the nightly tier
```

Env knobs: `EVAL_MODEL` (generation), `EVAL_JUDGE_MODEL` (judge), `EVAL_MAX_TOKENS`.

## CI

`.github/workflows/ship-evals.yml` — `evals-pr` runs on PRs touching
`plugins/ship/**` or `evals/**` (make it a required check in branch protection);
`evals-e2e` runs nightly and on `workflow_dispatch`. Both need the repo Actions
secrets `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`.

## Adding a case

- Agent tier: drop fixtures under `agents/<agent>/fixtures/`, add a test using
  `ship_evals.judges.rubric` — judge steps must quote the contract being tested.
- Decision-point tier: add a transcript JSON under
  `orchestrator/fixtures/transcripts/` (ends on a `user` message; every `tool_use`
  answered) and a test using the `run_decision` fixture.
- A failing eval is a finding about `plugins/ship/*` (or a broken fixture) — never
  weaken a rubric or assert to make CI green.
