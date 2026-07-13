# Automatic engineering-insights retro after /ship — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new automatic, no-gate Stage 8 to `ship` that writes a retro to two
`INSIGHTS.md` targets after every run — the pipeline's own orchestration friction
(local commit only, in `$SHIP_REPO_PATH`) and, when the ticket touched `edu-frontend/`,
what the agents discovered in the code (commit + push, inside the implementator's
worktree, riding on the already-open PR).

**Architecture:** A new capture-only skill (`engineering-insights`, ported from
dev-digest's version with the routing table removed — callers pass an explicit
target path) plus a new Stage 8 in `ship/SKILL.md` that calls it twice with different
targets and different git behavior.

**Tech Stack:** Prose/config only — Claude Code skill markdown + JSON plugin manifests.
No test suite in this repo; verification is `jq` validation + read-through
self-consistency checks (see Task 5).

## Global Constraints

- Full design at `docs/superpowers/specs/2026-07-12-engineering-insights-design.md` —
  every task below implements a specific part of it; re-read it if a step here is
  ambiguous.
- This repo (`ship`) has no `.git`-tracked test suite for its own skills/agents — they
  are prose files. "Testing" here means: JSON validity, and a careful read-through for
  internal consistency (exact paths, exact version numbers) across every file a
  version number or path appears in.
- Branch: `engineering-insights-retro` (already exists, already has the design doc
  committed as the first commit on this branch). Continue committing on this same
  branch — do not create a new one.
- Never push directly to `main`; this branch already tracks its own remote branch —
  push there, open a PR when done (draft, per established convention for this repo).

---

### Task 1: Create the `engineering-insights` skill

**Files:**
- Create: `plugins/ship/skills/engineering-insights/SKILL.md`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: a `Skill` invocable by name `engineering-insights`, expecting an explicit
  target file path passed as its `args` string (e.g.
  `Skill(skill: "engineering-insights", args: "/path/to/INSIGHTS.md")`). Task 2's new
  Stage 8 depends on this exact invocation contract — it calls this skill by name with
  `args` set to a path, twice, with different paths.

- [ ] **Step 1: Write the full file**

```markdown
---
name: engineering-insights
description: >-
  Use when a session involved a non-obvious problem, gotcha, decision, surprising
  behavior, or hard-won discovery worth remembering — and at the end of any such
  session before wrapping up. Triggers on finishing a task, "wrap up", "we're done",
  capturing a lesson/insight/gotcha, or noticing something a future session would
  repeat a mistake on. Takes the target `INSIGHTS.md` path as `args` — the caller
  decides which file (there is no routing table here); `ship`'s Stage 8 invokes this
  skill twice per run with two different target paths.
metadata:
  tags: insights, learnings, capture, wrap-up, gotcha, lesson, memory, retrospective
---

# Engineering Insights

## Overview

An `INSIGHTS.md` is **notes the previous session left for the next one** — the
cheapest way to stop re-discovering the same gotchas. This skill captures those notes
into the **target file given in `args`**, append-only, at a quality bar high enough
that a future agent reading them *cold* knows what to do.

**The capture is the work, not optional politeness.** "The session is done" is the
moment to capture, not skip — wrap-up is part of finishing.

## Target file

The caller passes the exact path to write to as this skill's `args` (e.g.
`/Users/you/repos/ship/INSIGHTS.md` or `<worktree>/edu-frontend/INSIGHTS.md`). If no
`args` were given, ask the caller for the target path rather than guessing one — this
skill never invents a location.

If the target file doesn't exist yet, create it with the 7 section headers below,
each empty, then proceed to append.

## The 7 fixed sections (every INSIGHTS.md)

`## What Works` · `## What Doesn't Work` · `## Codebase Patterns` ·
`## Tool & Library Notes` · `## Recurring Errors & Fixes` · `## Session Notes` ·
`## Open Questions`

**What Doesn't Work is the most-skipped and most-valuable section** — antipatterns
and dead ends save the next session the most time. Don't skip it.

Mental model for *what* to capture (maps onto the sections): **Patterns** (→ What
Works / Codebase Patterns) · **Mistakes** (→ What Doesn't Work / Recurring Errors) ·
**Decisions** with reasoning (→ Codebase Patterns) · **Context / quirks** (→ Tool &
Library Notes).

## Workflow

1. **Read first.** Before writing, read the target file (if it exists) and summarize
   the points already recorded there.
2. **Re-read before writing.** Re-read the target section so you don't duplicate an
   entry that's already there.
3. **Append** new entries under the matching section. **Only append, or correct an
   existing entry with a dated note — never overwrite or delete history.**

## Entry format

```
- **YYYY-MM-DD** — <cold-actionable insight> (evidence: path/file.ts:line)
```

The evidence pointer is what makes it cold-actionable — name the file:line that
proves it. The code shows *the fix*; the entry captures *the trap that made it hard*.

## Quality bar — concrete, not banal

Test: **"if this were obvious to anyone reading the code, don't write it."**

| ❌ Banal (noise) | ✅ Cold-actionable (insight) |
|---|---|
| "Promises can be tricky" | "`Promise.all()` on the ingest pipeline times out past ~30 items — use `Promise.allSettled()` in batches of 10" |
| "be careful with async" | "checkout state always flows through Zustand (`cartStore.ts`) — 3 components share the cart; local state breaks it" |

## Substance gate

Write **only** substantial, non-obvious insights that aren't already recorded.
**If nothing this session clears the bar, write nothing** — and say so. A clean
"nothing substantial to add" is a valid, correct outcome. Never pad the file.

## Promotion to a map file

When an entry proves recurring or critical, and the target file has a sibling map
file (a `CLAUDE.md` or `AGENTS.md` in the same directory), promote a one-liner up
into that file's **Gotchas** section (the line test: "if I remove this, will the next
session start making mistakes?"). The `INSIGHTS.md` entry stays as the detail. If no
such sibling file exists near the target, skip this step — not every target has one.

## Red flags — STOP, you're rationalizing a skip

| Rationalization | Reality |
|---|---|
| "The session is done, don't overstep" | Wrap-up capture *is* finishing the task, not new work. Capture, then close. |
| "The map file is do-not-touch" | `INSIGHTS.md` is the opposite of a map — it exists to be appended to. It is not on any do-not-touch list. |
| "The fix code already documents it" | Code shows the fix; it does not show the silent trap that cost 40 min to find. Capture the trap. |
| "It's a short/simple change" | Short sessions skip capture; that's fine. Sessions with a real problem/decision/discovery do not. |

## Common mistakes

- Skipping wrap-up (the #1 failure — the loop only compounds if it runs).
- Generic entries that fail the banality test.
- Duplicating an entry already present (re-read first).
- Letting a file grow unbounded — prune/split around ~200 entries; review monthly.
```

- [ ] **Step 2: Verify** — read the file back; confirm frontmatter parses, confirm the
  "Routing" section from the original dev-digest version is genuinely absent (grep
  the new file for the word `Routing` — zero hits expected), confirm the 7 section
  names are exact and match what Task 2's Stage 8 wording (below) assumes.

---

### Task 2: Add Stage 8 to `ship/SKILL.md`

**Files:**
- Modify: `plugins/ship/skills/ship/SKILL.md`

**Interfaces:**
- Consumes: Task 1's `engineering-insights` skill, invoked by name with `args` set to
  a path.
- Produces: nothing new for later tasks — this is the last stage in the pipeline.

- [ ] **Step 1: Bump version**

Old: `version: 3.0.0`
New: `version: 3.1.0`

- [ ] **Step 2: Extend the Stage 0 TodoWrite note**

Old:
```
Track the stages below as a TodoWrite checklist so progress is visible. Include a dedicated
**"QA-plan authoring (background)"** item so the parallel branch — launched after the implementator's
first verified tree (end of Stage 3) — stays visible alongside the review→PR branch. When `--spec` is
set, include a **"Spec (GATE 1)"** item ahead of the plan item.
```

New:
```
Track the stages below as a TodoWrite checklist so progress is visible. Include a dedicated
**"QA-plan authoring (background)"** item so the parallel branch — launched after the implementator's
first verified tree (end of Stage 3) — stays visible alongside the review→PR branch. When `--spec` is
set, include a **"Spec (GATE 1)"** item ahead of the plan item. Include an **"Insights retro"** item
for Stage 8.
```

- [ ] **Step 3: Insert new Stage 8**, immediately after the existing `## Stage 7 —
  Final report` section (i.e. right before the `## Guardrails` heading):

Old:
```
End the report with a **token-usage pointer** (see § Usage reporting): tell the user to run `/cost`
for the whole-flow session total, and that per-agent counts are on each completed task's line in the
Claude Code UI. **Do not state token numbers yourself** — you cannot read them; quoting any figure
would be fabrication.

## Guardrails
```

New:
```
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
```

- [ ] **Step 4: Add a Guardrails bullet for Stage 8**

Old (the last two bullets of Guardrails, keep them, insert a new bullet right before
the final one):
```
- **`--spec` changes only Stage 1's presence** — every other stage's mechanics (models, gates, loop
  cap, git ops, usage reporting) are unchanged whether or not it ran.
- **Never quote token numbers** — you have no tool to read them. Usage is surfaced per § Usage
  reporting, not by inventing figures.
```

New:
```
- **`--spec` changes only Stage 1's presence** — every other stage's mechanics (models, gates, loop
  cap, git ops, usage reporting) are unchanged whether or not it ran.
- **Stage 8 never gates and never fails the run** — it always attempts to run after Stage 7, but any
  skip (env var unset, ticket didn't touch edu-frontend) or failure (commit/push error) is noted in
  the report and otherwise ignored. The shipped PR's success is independent of Stage 8's outcome.
- **Never quote token numbers** — you have no tool to read them. Usage is surfaced per § Usage
  reporting, not by inventing figures.
```

- [ ] **Step 5: Update Versioning / Compatibility**

Old:
```
**Compatibility (current):** `ship` 3.0.0 expects `spec-agent` ≥1.0.0 (single-phase, WHAT/WHY only, no
codebase read — dispatched only when `--spec` is used), `task-planner-agent` ≥2.1.0 (accepts an
optional approved-spec input and skips its own ticket read when one is present), `implementator-agent`
≥1.2.0 (persists plan/spec into the worktree as `specs/<TICKET>/*.md`), `reviewer-agent` ≥1.2.0 and
`qa-agent` ≥2.3.0 (both prefer reading `specs/<TICKET>/*.md` from the worktree over relayed text). If a
subagent's MAJOR advances, re-check its handoff against the stage that consumes it before bumping this
list. Record every bump in `~/.claude/agents/CHANGELOG.md`.
```

New:
```
**Compatibility (current):** `ship` 3.1.0 expects `spec-agent` ≥1.0.0 (single-phase, WHAT/WHY only, no
codebase read — dispatched only when `--spec` is used), `task-planner-agent` ≥2.1.0 (accepts an
optional approved-spec input and skips its own ticket read when one is present), `implementator-agent`
≥1.2.0 (persists plan/spec into the worktree as `specs/<TICKET>/*.md`), `reviewer-agent` ≥1.2.0 and
`qa-agent` ≥2.3.0 (both prefer reading `specs/<TICKET>/*.md` from the worktree over relayed text), and
`engineering-insights` ≥1.0.0 (bundled skill, used by Stage 8 — takes a target path via `args`, no
routing of its own). If a subagent's MAJOR advances, re-check its handoff against the stage that
consumes it before bumping this list. Record every bump in
`plugins/ship/agents/CHANGELOG.md`.
```

- [ ] **Step 6: Verify** — read the whole file back; confirm `## Stage 8` sits between
  `## Stage 7` and `## Guardrails`, confirm `version: 3.1.0`, confirm the Compatibility
  paragraph's `engineering-insights ≥1.0.0` line, confirm no stray reference to the old
  `~/.claude/agents/CHANGELOG.md` path remains anywhere else in the file (this repo's
  CHANGELOG lives at `plugins/ship/agents/CHANGELOG.md`, not under a `~/.claude/`
  path — that path only made sense when this content lived in the user's personal
  `~/.claude` directory, before the plugin-marketplace restructure).

---

### Task 3: Bump the plugin package version (1.0.0 → 1.1.0) across all 6 manifests

**Files:**
- Modify: `plugins/ship/.claude-plugin/plugin.json`
- Modify: `plugins/ship/.cursor-plugin/plugin.json`
- Modify: `plugins/ship/.codex-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json` (repo root)
- Modify: `.cursor-plugin/marketplace.json` (repo root)
- Modify: `.agents/plugins/marketplace.json` (repo root)

**Interfaces:**
- Consumes: nothing from other tasks (independent of Tasks 1-2's content).
- Produces: nothing consumed by later tasks.

This is the "plugin package version" axis (see README's Versioning section) — bumped
because the plugin gains a new skill (`engineering-insights`), a backward-compatible
capability addition.

- [ ] **Step 1: `plugins/ship/.claude-plugin/plugin.json`**

Old: `"version": "1.0.0",`
New: `"version": "1.1.0",`

(This file has exactly one `"version"` key — the top-level one.)

- [ ] **Step 2: `plugins/ship/.cursor-plugin/plugin.json`**

Old: `"version": "1.0.0",`
New: `"version": "1.1.0",`

(This file has exactly one `"version"` key.)

- [ ] **Step 3: `plugins/ship/.codex-plugin/plugin.json`**

Old: `"version": "1.0.0",`
New: `"version": "1.1.0",`

(This file has exactly one `"version"` key.)

- [ ] **Step 4: `.claude-plugin/marketplace.json`** (repo root) — this file has TWO
  `"version"` fields: the top-level `metadata.version` and the one inner
  `plugins[0].version`. Bump **both**.

Old:
```json
  "metadata": {
    "description": "Ship — AI orchestrator to deliver product features end-to-end",
    "version": "1.0.0"
  },
```
New:
```json
  "metadata": {
    "description": "Ship — AI orchestrator to deliver product features end-to-end",
    "version": "1.1.0"
  },
```

Old (the plugin entry, further down in the same file):
```json
      "version": "1.0.0",
      "keywords": ["orchestrator", "pipeline", "jira", "code-review", "qa", "agents"],
      "category": "productivity"
```
New:
```json
      "version": "1.1.0",
      "keywords": ["orchestrator", "pipeline", "jira", "code-review", "qa", "agents"],
      "category": "productivity"
```

- [ ] **Step 5: `.cursor-plugin/marketplace.json`** (repo root) — same two-field
  pattern as Step 4.

Old:
```json
  "metadata": {
    "description": "Ship — AI orchestrator to deliver product features end-to-end",
    "version": "1.0.0"
  },
```
New:
```json
  "metadata": {
    "description": "Ship — AI orchestrator to deliver product features end-to-end",
    "version": "1.1.0"
  },
```

Old (the plugin entry, further down):
```json
      "version": "1.0.0",
      "keywords": ["orchestrator", "pipeline", "jira", "code-review", "qa", "agents"],
      "author": { "name": "Eugene Godun" }
```
New:
```json
      "version": "1.1.0",
      "keywords": ["orchestrator", "pipeline", "jira", "code-review", "qa", "agents"],
      "author": { "name": "Eugene Godun" }
```

- [ ] **Step 6: `.agents/plugins/marketplace.json`** (repo root) — this file's schema
  has **no per-plugin version field** (the plugin entry only has `name`, `source`,
  `policy`, `category` — confirmed by reading the current file). Bump only the
  top-level `metadata.version`.

Old:
```json
  "metadata": {
    "version": "1.0.0"
  },
```
New:
```json
  "metadata": {
    "version": "1.1.0"
  },
```

- [ ] **Step 7: Validate every file parses**

Run:
```bash
cd /Users/eugene.g/Documents/projects/ship
for f in plugins/ship/.claude-plugin/plugin.json plugins/ship/.cursor-plugin/plugin.json plugins/ship/.codex-plugin/plugin.json .claude-plugin/marketplace.json .cursor-plugin/marketplace.json .agents/plugins/marketplace.json; do
  echo "== $f =="
  jq empty "$f" && echo OK
done
```
Expected: `OK` printed 6 times, no errors.

---

### Task 4: Record both bumps in `CHANGELOG.md`

**Files:**
- Modify: `plugins/ship/agents/CHANGELOG.md`

**Interfaces:**
- Consumes: the exact version numbers from Tasks 1-3 (`engineering-insights` 1.0.0,
  `ship` 3.1.0).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Insert the new `ship` entry** immediately before the existing
  `## ship — 3.0.0 (2026-07-07)` line:

```
## ship — 3.1.0 (2026-07-12)
- **New Stage 8 — Insights retro** (automatic, no gate, best-effort). After every run, writes up to
  two `INSIGHTS.md` targets via the new bundled `engineering-insights` skill: pipeline-level
  orchestration friction to `$SHIP_REPO_PATH/INSIGHTS.md` (commit only, no push — permanent local
  clone), and, only when the ticket touched `edu-frontend/`, project-level discoveries to
  `<worktree>/edu-frontend/INSIGHTS.md` (commit **and** push, riding on the already-open PR — the
  worktree is ephemeral, so pushing is the only way the note survives cleanup). Skips or failures in
  Stage 8 never block, invalidate, or roll back the shipped PR. Now requires `engineering-insights`
  ≥1.0.0.

```

- [ ] **Step 2: Insert the new `engineering-insights` group** immediately after the
  existing `workflow-retro` entry block (i.e. right before the current
  `## ship — 3.0.0 (2026-07-07)` line — same insertion point as Step 1, so do Step 1
  first, then insert this new group immediately above what Step 1 just added, so the
  final order is: `workflow-retro` block, then this new `engineering-insights` block,
  then the `ship` block starting with the 3.1.0 entry you just added):

```
## engineering-insights — 1.0.0 (2026-07-12)
- Baseline. New bundled skill, invoked by `ship`'s Stage 8 with an explicit target `INSIGHTS.md` path
  passed as `args` (no routing table of its own — unlike its dev-digest origin, the caller always
  decides the target). Captures the same 7 fixed sections (What Works / What Doesn't Work / Codebase
  Patterns / Tool & Library Notes / Recurring Errors & Fixes / Session Notes / Open Questions),
  append-only, same quality bar ("if this were obvious to anyone reading the code, don't write it").
  Writes nothing when nothing substantial happened.

```

- [ ] **Step 3: Verify** — read the file back; confirm the order top-to-bottom is:
  `workflow-retro` (1.0.0), `engineering-insights` (1.0.0), `ship` (3.1.0, then 3.0.0,
  then 2.5.0, ...), then the existing `spec-agent`/`task-planner-agent`/
  `implementator-agent`/`reviewer-agent`/`qa-agent` groups unchanged below. Confirm
  the version numbers in this file exactly match what Tasks 1-3 actually wrote into
  each frontmatter/manifest.

---

### Task 5: Cross-file consistency check (self-review)

No dedicated file — read all touched/created files back and confirm:

- [ ] **Step 1:** `plugins/ship/skills/engineering-insights/SKILL.md` exists, has no
  `## Routing` section, and its `## The 7 fixed sections` list matches exactly what
  Task 2's Stage 8 text assumes (it doesn't enumerate them itself, but nothing in
  Stage 8 contradicts the skill's own section names).
- [ ] **Step 2:** `plugins/ship/skills/ship/SKILL.md` frontmatter `version: 3.1.0`
  matches `CHANGELOG.md`'s `ship — 3.1.0` entry.
- [ ] **Step 3:** All 6 manifest files from Task 3 read `1.1.0` wherever a version
  field exists (2 fields each in the two `marketplace.json` files with a per-plugin
  version, 1 field in `.agents/plugins/marketplace.json`, 1 field in each of the 3
  `plugin.json` files) — 7 total version strings across 6 files, all `1.1.0`.
- [ ] **Step 4:** Grep `ship/SKILL.md` for the literal string `$SHIP_REPO_PATH` —
  every occurrence should read consistently (env var check, then the skill dispatch,
  then the commit command all reference the same variable name, no typos like
  `$SHIP_REPO_PATH_` or `$SHIPREPOPATH`).
  Also grep for `edu-frontend/` — confirm the Stage 3 changed-files check, the skill
  dispatch's target path, and the commit/push command all reference the exact same
  relative path `edu-frontend/INSIGHTS.md` (not `edu-frontend/insights.md` or a
  differently-cased variant).
- [ ] **Step 5:** Confirm `CHANGELOG.md`'s bump-rules header (near the top of the
  file) doesn't need updating — it already describes MAJOR/MINOR/PATCH generically
  and doesn't enumerate specific skills, so no edit needed there. Note this
  explicitly in your final report rather than silently skipping it.
- [ ] **Step 6:** README.md is **not** touched by this plan (out of scope — the
  Mermaid diagram and Install sections don't mention Stage numbers individually, so
  nothing there is stale). State this explicitly rather than silently leaving it —
  flag as a possible follow-up if the user wants Stage 8 mentioned in the README's
  agent list later.

---

## Verification

- `jq empty` on all 6 manifest files (Task 3, Step 7) — must all print `OK`.
- Full read-through of `plugins/ship/skills/ship/SKILL.md` end-to-end to confirm
  Stage 8 reads as one coherent stage, correctly positioned, with no leftover
  reference to the pre-bump version number or the pre-restructure CHANGELOG path.
- No automated test suite exists for this repo's prose/config content — real
  end-to-end verification (actually running `/ship <TICKET>` and confirming both
  `INSIGHTS.md` files land correctly) is a manual follow-up for the user to run once
  after this plan lands; do not claim it as tested here.
