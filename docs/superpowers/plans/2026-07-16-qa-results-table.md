# qa-agent results as an emoji table — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reformat `qa-agent`'s results output (both the PR comment and the final
report) from unstructured prose into a verdict-line + emoji table, so pass/fail is
scannable at a glance.

**Architecture:** A wording-only change to two adjacent steps in `qa-agent.md`'s
Phase B (post-results, report), plus the version-floor bookkeeping this repo does for
every subagent bump (`ship/SKILL.md`'s Compatibility paragraph, `CHANGELOG.md`).

**Tech Stack:** Prose/markdown only — no code, no test suite in this repo.

## Global Constraints

- Full design at `docs/superpowers/specs/2026-07-16-qa-results-table-design.md`.
- Table format (exact, from the design — every task below must produce this shape):
  ```
  **Overall: <passed>/<total> passed** ✅|❌

  | Test Case | Description | Status | Notes |
  |---|---|---|---|
  | <id/title> | <what it verifies> | ✅ or ❌ | <blank if passing; failure detail /
  console-network errors if failing> |
  ```
  Verdict emoji: ✅ only if every case passed, ❌ if any failed.
- Scope is `qa-agent.md` only — `reviewer-agent`'s findings format and
  `ship/SKILL.md`'s Stage 7 wording are explicitly unchanged (confirmed in the
  design: Stage 7 only links to the PR/report, doesn't reproduce their content).
- Branch: `qa-results-table` (already exists, pushed, design doc is its first commit).
  Continue committing on this branch.
- No test suite — verification is read-through + version cross-checking across the 3
  touched files.

---

### Task 1: Reformat qa-agent.md's Phase B results output

**Files:**
- Modify: `plugins/ship/agents/qa-agent.md`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: nothing consumed by later tasks in this plan (Tasks 2-3 reference this
  task's new version number, not its content).

- [ ] **Step 1: Bump version**

Old: `version: 2.4.0`
New: `version: 2.5.0`

- [ ] **Step 2: Replace Phase B steps 4-5 with the table format**

Old:
```
4. **Post results to the PR** — `gh pr comment <ref> --body '<results>'` listing every tested scenario
   with its **PASS/FAIL** status, an overall verdict, and any notable console/network errors. Include
   the marker `<!-- qa-agent-results -->` on its own line.
5. **Report** — return the same per-scenario PASS/FAIL summary, plus a link to the PR results comment,
   as your final message. Close **every** browser instance (`playwright-cli close` per instance) at
   the end.
```

New:
```
4. **Post results to the PR** — `gh pr comment <ref> --body '<results>'`, where `<results>` is a
   one-line verdict summary followed by a table, one row per test case:

   ```
   **Overall: <passed>/<total> passed** ✅|❌

   | Test Case | Description | Status | Notes |
   |---|---|---|---|
   | <id/title from the plan> | <one line: what this case verifies> | ✅ or ❌ | <blank when passing;
   failure detail and/or notable console/network errors when failing> |
   ```

   Use the case id/title exactly as it appeared in the approved Phase-A plan — don't rename or
   renumber. The verdict emoji is ✅ only when every case passed, ❌ if any failed. Include the marker
   `<!-- qa-agent-results -->` on its own line (outside the table, same as before).
5. **Report** — return the **same verdict-line + table** as your final message (identical structure to
   the PR comment — do not summarize it differently here), plus a link to the PR results comment.
   Close **every** browser instance (`playwright-cli close` per instance) at the end.
```

- [ ] **Step 3: Verify**

Read the file back. Confirm:
- `version: 2.5.0` in frontmatter.
- Phase B still has exactly 5 steps (1 Provision, 2 Enable flags, 3 Execute, 4 Post results, 5 Report)
  — this task only changes steps 4-5's *body text*, not the numbering.
- The table format block is present verbatim in step 4, and step 5 explicitly says to reuse the same
  structure rather than re-describing it.
- Nothing else in the file changed (Phase A, Inputs, target-resolution tables, Conventions &
  guardrails are all untouched).

- [ ] **Step 4: Commit**

```bash
cd /Users/eugene.g/Documents/projects/ship
git add plugins/ship/agents/qa-agent.md
git commit -m "qa-agent: report results as a verdict-line + emoji table"
```

---

### Task 2: Update ship/SKILL.md's Compatibility floor

**Files:**
- Modify: `plugins/ship/skills/ship/SKILL.md`

**Interfaces:**
- Consumes: Task 1's new `qa-agent` version (`2.5.0`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Bump version**

Old: `version: 3.2.0`
New: `version: 3.3.0`

- [ ] **Step 2: Compatibility paragraph — exact find-and-replace**

Old:
```
**Compatibility (current):** `ship` 3.2.0 expects `spec-agent` ≥1.0.0 (single-phase, WHAT/WHY only, no
codebase read — dispatched only when `--spec` is used), `task-planner-agent` ≥2.1.0 (accepts an
optional approved-spec input and skips its own ticket read when one is present), `implementator-agent`
≥1.3.0 (persists plan/spec into the worktree as `specs/<TICKET>/*.md` only in `--spec` mode),
`reviewer-agent` ≥1.2.1 and `qa-agent` ≥2.4.0 (both prefer reading `specs/<TICKET>/*.md` from the
worktree when it exists, falling back to relayed text otherwise; `qa-agent` no longer posts its plan
to the PR, only results), and `engineering-insights` ≥1.0.0 (bundled skill, used by Stage 8 — takes a
target path via `args`, no routing of its own). If a subagent's MAJOR advances, re-check its handoff
against the stage that consumes it before bumping this list. Record every bump in
`plugins/ship/agents/CHANGELOG.md`.
```
New:
```
**Compatibility (current):** `ship` 3.3.0 expects `spec-agent` ≥1.0.0 (single-phase, WHAT/WHY only, no
codebase read — dispatched only when `--spec` is used), `task-planner-agent` ≥2.1.0 (accepts an
optional approved-spec input and skips its own ticket read when one is present), `implementator-agent`
≥1.3.0 (persists plan/spec into the worktree as `specs/<TICKET>/*.md` only in `--spec` mode),
`reviewer-agent` ≥1.2.1 and `qa-agent` ≥2.5.0 (both prefer reading `specs/<TICKET>/*.md` from the
worktree when it exists, falling back to relayed text otherwise; `qa-agent` no longer posts its plan
to the PR, only results, formatted as a verdict line + Test Case/Description/Status/Notes table), and
`engineering-insights` ≥1.0.0 (bundled skill, used by Stage 8 — takes a target path via `args`, no
routing of its own). If a subagent's MAJOR advances, re-check its handoff against the stage that
consumes it before bumping this list. Record every bump in
`plugins/ship/agents/CHANGELOG.md`.
```

- [ ] **Step 3: Verify**

Read the file back. Confirm `version: 3.3.0`, confirm the Compatibility paragraph reads `qa-agent
≥2.5.0`, confirm **no stage or gate structure changed** — this task touches only the frontmatter
version and the Compatibility paragraph, nothing else in the file (no Stage heading, no Guardrails
bullet, no Usage-reporting text).

- [ ] **Step 4: Commit**

```bash
cd /Users/eugene.g/Documents/projects/ship
git add plugins/ship/skills/ship/SKILL.md
git commit -m "Bump qa-agent Compatibility floor to >=2.5.0 for the results-table change"
```

---

### Task 3: Record both bumps in CHANGELOG.md

**Files:**
- Modify: `plugins/ship/agents/CHANGELOG.md`

**Interfaces:**
- Consumes: Task 1's `qa-agent` version (`2.5.0`) and Task 2's `ship` version (`3.3.0`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Insert the new `ship` entry** immediately before the existing
  `## ship — 3.2.0 (2026-07-14)` line:

```
## ship — 3.3.0 (2026-07-16)
- Compatibility floor bumped for `qa-agent` ≥2.5.0 (results-table change, below). No stage or gate
  structure change.

```

- [ ] **Step 2: Insert the new `qa-agent` entry** immediately before the existing
  `## qa-agent — 2.4.0 (2026-07-07)` line:

```
## qa-agent — 2.5.0 (2026-07-16)
- **Results now reported as a verdict-line + table**, both in the PR comment and the final report:
  `**Overall: X/Y passed** ✅|❌` followed by a `Test Case | Description | Status | Notes` table
  (`✅`/`❌` per case, Notes blank when passing). Replaces the previous unstructured prose listing.
  Backward compatible — no change to what data is collected or the handoff contract, only how the
  already-collected pass/fail results are rendered.

```

- [ ] **Step 3: Verify**

Read the file back top to bottom. Confirm: the `ship` group still runs newest-first with `3.3.0` now
at the top (then `3.2.0`, `3.1.0`, ... unchanged below); the `qa-agent` group still runs newest-first
with `2.5.0` now at the top (then `2.4.0`, `2.3.0`, ... unchanged below); no existing entry was altered,
duplicated, or lost; blank-line spacing matches the file's one-blank-line-between-entries convention.

- [ ] **Step 4: Commit**

```bash
cd /Users/eugene.g/Documents/projects/ship
git add plugins/ship/agents/CHANGELOG.md
git commit -m "Record ship 3.3.0 and qa-agent 2.5.0 in CHANGELOG"
```

---

## Verification

No test suite in this repo. Verification is:
- Read-through of all 3 touched files confirming the table format spec (Global
  Constraints, above) is reproduced verbatim in `qa-agent.md`.
- Version cross-check: `qa-agent.md` frontmatter `2.5.0` = CHANGELOG `## qa-agent —
  2.5.0` = `ship/SKILL.md` Compatibility floor `≥2.5.0`. `ship/SKILL.md` frontmatter
  `3.3.0` = CHANGELOG `## ship — 3.3.0` = the paragraph's own self-reference (`` `ship`
  3.3.0 expects... ``).
- Grep for any leftover reference to the old prose-results format (e.g. "listing every
  tested scenario") to confirm nothing stale remains.
- No automated end-to-end test of an actual `/ship` run — that's a manual follow-up,
  same caveat as every prior plan in this repo.
