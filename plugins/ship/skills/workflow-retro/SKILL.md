---
name: workflow-retro
version: 1.0.0
description: >
  Use when the user runs `/workflow-retro` or explicitly asks to retro, review, or post-mortem a
  completed `/ship` pipeline run — reporting real per-agent token spend, problems encountered, and
  improvement suggestions. Manual-only: never invoked automatically.
disable-model-invocation: true
---

# workflow-retro — /ship pipeline retrospective

Reviews a completed `/ship` run using the real per-agent transcripts Claude Code already writes to
disk — not invented numbers — and reports token spend, problems, and improvement suggestions.

## Inputs

Parse from the invocation:

- **`TICKET`** (optional) — a Jira key like `LEX-1398`. Retros the most recent session that mentions
  that ticket.
- **`session-id`** (optional) — an explicit Claude Code session id to retro a specific past run.
- Neither given ⇒ retro the **current session**.

## How token numbers are computed (read this before running)

`ship`'s own guardrail says the live orchestrator can never quote token numbers — it has no tool for
them. This skill is the one legitimate exception: it runs a **script** that parses the real transcript
files Claude Code writes to disk, and reports only numbers that script computed. Never estimate or
invent a number yourself.

- Each subagent's full transcript lives at
  `~/.claude/projects/<project>/<session-id>/subagents/agent-<agentId>.jsonl`, with an
  `agent-<agentId>.meta.json` sidecar carrying `agentType` (`task-planner-agent`,
  `implementator-agent`, `reviewer-agent`, `qa-agent`, `claude` for the Haiku git agent, etc.).
- Per-turn token usage is in `message.usage` (`input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens`) on every assistant turn in that file — sum
  them for the agent's real total.
- **Never use** the inline `toolUseResult.usage` / `totalTokens` summary in the parent session file for
  token totals — it reflects only the subagent's *last* turn and undercounts by up to ~40×. It's fine
  only for metadata (status, tool-use count, duration).
- The coordinator's own total is the sum of `message.usage` over the parent session file's own
  `type: "assistant"` lines.

## Workflow

1. **Run the analyzer**: `python3 ~/.claude/skills/workflow-retro/analyze_run.py`, adding `--ticket
   <KEY>` or `--session <id>` per the resolved input. It prints one JSON object to stdout: per-agent
   token totals (grouped by role, cache-read vs fresh broken out), the coordinator total, a grand
   total, per-agent turn/duration/tool-error counts, and a truncated excerpt of each agent's final
   message. **Never `Read` the raw `.jsonl` transcript files directly** — they run into the megabytes;
   the script is the only thing that should parse them.
2. **Pull qualitative signal** from the script's per-agent excerpts and error counts, plus (when
   retro-ing the current session) the agents' full reports already in this conversation: review rounds
   taken vs the 3-round cap, GATE 1/2 change-request bounces, reviewer Critical/Important counts and
   verdict, qa PASS/FAIL, implementator deviations/assumptions, which models Stage 0 picked, and any
   lopsided token distribution (one agent dominating, a low cache-read ratio meaning expensive cold
   context).
3. **Print the report** as terminal markdown with exactly these sections, in order:
   - **Run summary** — ticket, branch, PR, stages completed, models used (Stage 0 picks).
   - **Token spend** — a table: agent role → turns → input / output / cache-creation / cache-read /
     total tokens, then a grand-total row. Call out the cache-read share (cheap) vs fresh tokens.
   - **Problems encountered** — grounded in the script's tool-error counts and excerpts; say so
     explicitly if a given agent had none.
   - **What went well**
   - **What went poorly**
   - **Insights**
   - **Improvement suggestions** — concrete, ideally tied to a specific ship stage, param, or agent
     guardrail (e.g. "reviewer hit the Critical-escalation path twice — consider X").

## Guardrails

- **Every token number must trace to the analyzer script's output.** Never estimate, round
  suggestively, or fill a gap with a guess — say "unknown" instead.
- **Never `Read` a raw transcript `.jsonl` file** — always go through `analyze_run.py`; they run into
  the megabytes and the script already extracts what's needed.
- If the script reports `note` (no `subagents/` directory for the session), say so plainly rather than
  presenting an empty token table as "zero cost."
- This skill is **manual-only** (`disable-model-invocation: true`) — it runs only via `/workflow-retro`.
- Distinguish **cache-read** tokens (cheap, near-free) from fresh **input**/**cache-creation** tokens in
  the report — a big cache-read number is not the same cost as a big input number.

## Versioning

SemVer (`version:` in frontmatter). Not a `/ship` pipeline stage — it's a read-only observer — but it
reads the same four agents' reports and the ship contract, so bumps are recorded alongside them in
`~/.claude/agents/CHANGELOG.md`.

- **MAJOR** — the analyzer's output JSON shape changes in a way the workflow section depends on, or the
  report's required section list changes.
- **MINOR** — new input, new report section, or new signal added to the analysis.
- **PATCH** — wording/clarity, no behavior change.
