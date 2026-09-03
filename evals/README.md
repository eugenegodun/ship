# ship evals

deepeval suite for the `/ship` orchestrator (`plugins/ship/`). Spec:
`docs/superpowers/specs/2026-08-26-ship-deepeval-evals-design.md`.

## Tiers

| Tier | Where | What | CI |
|------|-------|------|----|
| Agent-level | `agents/` | each agent's `.md` + fixture inputs, GEval-judged | blocking on PRs |
| Decision-points | `orchestrator/` | SKILL.md + fixture transcript → assert the next tool call | blocking on PRs |
| Codex decision-points | `orchestrator_codex/` | SKILL.md + `references/codex-dispatch.md` + fixture transcript, driven through the OpenAI API with Codex V2 tool schemas → assert the next tool call | blocking on PRs (own job) |
| E2E | `e2e/` | multi-turn simulator with canned subagent replies | nightly, non-blocking |

## Run

```bash
cd evals && uv sync
export ANTHROPIC_API_KEY=...   # generation (default model: claude-sonnet-5)
export OPENAI_API_KEY=...      # GEval judge (default: gpt-4.1)

uv run pytest tests -v                          # unit tests, no model calls
uv run deepeval test run agents orchestrator -v # the blocking PR suite
uv run pytest orchestrator_codex -m codex -v  # Codex dialect (needs OPENAI_API_KEY only)
uv run pytest e2e -m "e2e" -v                   # the nightly tier
```

Env knobs: `EVAL_MODEL` (generation), `EVAL_JUDGE_MODEL` (judge), `EVAL_MAX_TOKENS`, `EVAL_CODEX_MODEL` (Codex-tier generation, default `gpt-4.1`).

## CI

`.github/workflows/ship-evals.yml` — `evals-pr` runs on PRs touching
`plugins/ship/**` or `evals/**`. Caution before marking it a required check: the
workflow is paths-filtered, so PRs that don't touch those paths never report the
status and would wait on it forever — either leave it non-required, or remove the
`paths:` filter and add an in-job path check that no-ops (succeeds) when nothing
relevant changed. `evals-e2e` runs nightly and on `workflow_dispatch`. Both need
the repo Actions secrets `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. Fork PRs don't
receive repo secrets, so the job fails fast with a clear error rather than passing
vacuously.

## Adding a case

- Agent tier: drop fixtures under `agents/<agent>/fixtures/`, add a test using
  `ship_evals.judges.rubric` — judge steps must quote the contract being tested.
- Decision-point tier: add a transcript JSON under
  `orchestrator/fixtures/transcripts/` (ends on a `user` message; every `tool_use`
  answered), then **pick the right observation window**:
  - **`run_decision`** — one assistant turn. Use it *only* for assertions about the next
    **tool call** (dispatch, resume-vs-respawn, model override, brief contents).
  - **`run_window`** — several turns, up to the orchestrator's own stopping point, with
    mandated bookkeeping answered. Use it for every assertion about **prose**.

  This split is not stylistic. SKILL.md requires a TodoWrite stage table with every
  update, so a compliant orchestrator may spend its next turn entirely on tool calls and
  emit its prose a turn later. Asserting prose on a single turn made cases fail
  intermittently on an empty string (`assert 'TC1' in ''`) while the model was behaving
  correctly. Append `w.diagnostics()` to every prose assertion's failure message, so a
  future failure carries the turn count, stop reason, tools called, and captured text.
- Codex tier: transcripts are OpenAI chat format (`assistant` turns carry `tool_calls`, replies are
  `role: tool`); the system prompt is `SKILL.md` + `references/codex-dispatch.md`. Assert on
  `spawn_agent`/`followup_task` shape (`agent_type`, `fork_turns`, `target`), never on model names.
- A failing eval is a finding about `plugins/ship/*` (or a broken fixture) — never
  weaken a rubric or assert to make CI green.
