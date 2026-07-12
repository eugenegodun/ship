---
name: engineering-insights
version: 1.0.0
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
