# ship evals

deepeval suite for the `/ship` orchestrator (`plugins/ship/`). Spec:
`docs/superpowers/specs/2026-08-26-ship-deepeval-evals-design.md`.

## Tiers

| Tier | Where | What | CI |
|------|-------|------|----|
| Agent-level | `agents/` | each agent's `.md` + fixture inputs, GEval-judged | blocking on PRs |
| Decision-points | `orchestrator/` | SKILL.md + fixture transcript → assert the next tool call | blocking on PRs |
| Codex decision-points and continuation | `orchestrator_codex/` | Standalone `references/codex-dispatch.md` + fixture transcript, driven through the OpenAI API with Codex V2 tool schemas → assert the next tool call | blocking on PRs (own job) |
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

Env knobs: `EVAL_MODEL` (generation), `EVAL_JUDGE_MODEL` (judge), `EVAL_MAX_TOKENS`, `EVAL_CODEX_MODEL` (Codex-tier generation, default `gpt-6-astra`).

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
  `role: tool`); the system prompt is the generated `codex-skills/ship/SKILL.md` body, identical to the standalone `references/codex-dispatch.md`. Assert on
  `spawn_agent`/`followup_task` shape (`agent_type`, `fork_turns`, `target`), never on model names.
- A failing eval is a finding about `plugins/ship/*` (or a broken fixture) — never
  weaken a rubric or assert to make CI green.


## Codex asynchronous continuation

`test_codex_continuation.py` drives simulated asynchronous children through partial implementation,
review fixes, queued QA, and draft PR creation to the QA gate. Additional cases cover active-work
status questions, missing handoff evidence, internal questions, repeated partial results, credentials
blockers, planner/spec waiting, cancellation, and the review cap. No tool executes product commands.
`test_codex_implementator_completion.py` loads the generated Codex role (including its overlay),
then tests remaining verification and honest blocker reports using simulated shell results.

The driver records ordered assistant turns and keeps child mailbox delivery separate from tool
responses. `AsyncScenario` checks stage state independently of the model's final prose. Text-only
responses stop the driver; it never sends a “continue” nudge to rescue premature finalization.
Offline negative controls reject the original dispatch/resume-then-final sequence, an incomplete
QA gate report, and call-budget exhaustion. These tests cannot validate the desktop scheduler or
measure commentary cadence: the chat-completions API does not expose Codex commentary/final channels.

Run the Codex tier three times with `EVAL_CODEX_MODEL` set to the model being evaluated when comparing
prompt changes. Record each outcome; do not silently retry failures. Missing `OPENAI_API_KEY` skips
live cases and is not behavioral verification. Offline checks run with `uv run pytest tests -v`;
if an auto-loaded plugin requires a socket unavailable in the sandbox, use
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest tests -v`.


The Codex workflow is now self-contained: the Codex manifest and evals both load generated `codex-skills/ship/SKILL.md`, whose body comes
from the dispatch reference, instead of combining Claude instructions and a translation appendix. CI explicitly uses `gpt-6-astra` with
medium effort, matching the inspected desktop configuration, and runs three independent repetitions.
GPT-4.1 is a separate non-blocking comparison, also repeated three times; its result cannot make the
target-model check pass. If the API account does not support the target model, the check fails visibly;
there is no fallback to a different model. `EVAL_CODEX_MODEL` and `EVAL_CODEX_REASONING_EFFORT` can
select another explicitly evaluated configuration locally.

Set `EVAL_CODEX_TRACE_DIR` to retain full scenario transcripts and final simulator state, including
on a tool/assertion exception. Every direct API call also records its full request/response and
finish reason, covering decision-point and implementer evals. CI uploads these and all three JUnit reports as artifacts. Tool use
remains optional at the API level: no forced tool calls or automatic continuation mask early exits.
Gate checks require the actual content and an approval request, not transport prefixes or punctuation.
Independent lint can run after blocked integration setup; the final report must still disclose the
blocked verification and must not claim success.


The target uses the Responses API: Astra rejects reasoning plus function tools on Chat Completions.
`EVAL_CODEX_API=responses` preserves returned reasoning items (including encrypted continuation data)
when replaying tool results. GPT-4.1's comparison keeps `EVAL_CODEX_API=chat`; artifact metadata records
the endpoint as well as the model. Preflight includes a function tool to validate the actual API
capability, not merely text generation. An API incompatibility is not a behavioral test failure.
