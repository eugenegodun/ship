# Automatic engineering-insights retro after `/ship` — Design

## Context

`/ship` runs a full ticket-to-PR pipeline but currently loses everything it learned
the moment the session ends — no record of orchestration friction (review rounds,
escalations, gate change-requests) to inform future pipeline changes, and no record
of codebase discoveries (patterns, gotchas) the implementator/reviewer/qa agents made
along the way. dev-digest already solved the second half of this problem with an
`engineering-insights` skill (`/Users/eugene.g/Documents/projects/dev-digest/.claude/skills/engineering-insights/SKILL.md`):
a per-module `INSIGHTS.md`, 7 fixed sections, append-only, high quality bar ("if this
were obvious to anyone reading the code, don't write it").

This design ports that mechanism into `ship` itself, wired to run **automatically**
after every `/ship` run, writing to **two** targets: the pipeline's own retro (so
`ship`'s own SemVer'd behavior can be improved from real evidence) and the target
project's retro (scoped to `edu-frontend` only, for now).

## Architecture

**New skill:** `plugins/ship/skills/engineering-insights/SKILL.md`, added to the
`ship` plugin repo. Ported from dev-digest's version, with one structural change:
dev-digest's skill **routes** to a target file via a hardcoded module table; this
version has **no routing table** — the caller (ship's orchestrator) passes an
explicit target file path as the skill's `args`, and the skill's job is purely the
capture logic: read the target's existing content, decide what's substantial enough
to append (or write nothing), enforce the 7-section structure and entry format,
never duplicate, never overwrite history.

Everything else carries over unchanged from dev-digest's version: the 7 fixed
sections (`What Works` / `What Doesn't Work` / `Codebase Patterns` / `Tool & Library
Notes` / `Recurring Errors & Fixes` / `Session Notes` / `Open Questions`), the entry
format (`- **YYYY-MM-DD** — <cold-actionable insight> (evidence: path/file.ts:line)`),
the banality test, the "write nothing if nothing substantial" gate, and the red-flags
table for rationalized skips.

**Trigger:** new **Stage 8 — Insights retro** in `ship/SKILL.md`, automatic, **no
human gate**, runs immediately after Stage 7 (Final report). Two calls:

1. **Pipeline-insights call** — target: `$SHIP_REPO_PATH/INSIGHTS.md`.
   - If `SHIP_REPO_PATH` is unset or the directory doesn't exist, **skip silently**
     (note the skip in the Stage 7 report — don't fail the run over a missing env var).
   - Source material for the skill: this run's own orchestration friction — review
     rounds taken, any `BLOCKED`/`NEEDS_CONTEXT` escalations from any subagent, gate
     change-requests, model escalations (fable→opus), anything about the process
     itself worth fixing in a future `ship` version.
   - After the skill returns (if it wrote anything), `git add INSIGHTS.md && git
     commit` inside `$SHIP_REPO_PATH`. **No push.** This is your permanent local
     clone — batch review/push whenever you want.

2. **Project-insights call** — target: `<worktree_path>/edu-frontend/INSIGHTS.md`,
   using the worktree path retained from Stage 3.
   - **Only fires when this run's changed files touched `edu-frontend/`** (check
     against implementator's reported changed-files list from Stage 3/4). No other
     project has a target yet — skip entirely otherwise. (Scoped this narrowly on
     purpose; extending to other apollo modules is future work, not part of this
     change.)
   - Source material: what implementator/reviewer/qa actually discovered while
     working the ticket — new patterns, dead ends, gotchas, tool quirks — same
     framing dev-digest already uses.
   - After the skill returns (if it wrote anything), commit **and push** inside the
     worktree, onto the same branch Stage 5 already pushed. This is deliberately
     different from the pipeline-insights side: `edu-frontend/INSIGHTS.md` lives
     inside the implementator's **worktree**, which is ephemeral (cleaned up after
     merge). A local-only commit there can be lost; pushing is the only way the note
     survives past worktree cleanup. It rides as one more commit on the
     already-open PR — not a new PR.

## Data flow

```
Stage 7 (Final report)
   │
   ▼
Stage 8 (Insights retro, no gate)
   ├── SHIP_REPO_PATH set & exists? ──yes──> Skill(engineering-insights, args=$SHIP_REPO_PATH/INSIGHTS.md)
   │                                          └── wrote anything? ──yes──> git commit (no push), in $SHIP_REPO_PATH
   │                                    no ──> note skip in report
   │
   └── changed files touched edu-frontend/? ──yes──> Skill(engineering-insights, args=<worktree>/edu-frontend/INSIGHTS.md)
                                                       └── wrote anything? ──yes──> git commit + push, in <worktree>
                                                 no ──> skip (nothing to do)
```

## Error handling / edge cases

- **Skill writes nothing** (nothing substantial this run) — valid outcome, matches
  dev-digest's own "a clean 'nothing substantial to add' is correct" rule. No commit
  attempted for that target.
- **`$SHIP_REPO_PATH` set but not a git repo / not the `ship` repo** — best-effort:
  attempt the write and commit; if `git commit` fails (e.g. not a repo), note the
  failure in the Stage 7/8 summary rather than crashing the whole `/ship` run. Stage 8
  failing must never roll back or invalidate the actual shipped PR — it's a
  best-effort addendum, not part of the pipeline's success criteria.
- **Push to the worktree branch fails** (e.g. branch deleted, PR already merged and
  branch cleaned up remotely) — note it in the summary; don't retry indefinitely,
  don't block on it.
- **Ticket touches both `edu-frontend/` and other directories** — still fires (the
  condition is "touched edu-frontend at all", not "only edu-frontend").

## Versioning

- New skill `engineering-insights`: starts at **1.0.0**.
- `ship` orchestrator: **3.0.0 → 3.1.0** (MINOR — new stage, no existing stage's
  inputs/outputs/gate structure changes, backward-compatible).
- Plugin package version (the 4 manifest files, per the repo's own two-version-axes
  convention): **1.0.0 → 1.1.0** (new capability — the plugin gains a skill).
- Record both bumps in `plugins/ship/agents/CHANGELOG.md` (orchestrator bump) and the
  manifests (package bump), per existing repo convention.

## Testing / verification

- Manifest JSON validation (`jq empty`) on the two bumped manifest version fields,
  same as prior PRs to this repo.
- No automated test harness exists for `ship`'s own orchestration logic (it's a
  prose-driven skill, not code) — verification is a read-through: confirm Stage 8's
  wording is unambiguous about the skip conditions, confirm the new skill file is
  self-contained and doesn't reference the removed routing table anywhere.
- Real end-to-end verification (actually running `/ship <TICKET>` against
  edu-frontend and checking both `INSIGHTS.md` files land correctly) is out of scope
  for this change's automated verification — flag it as a manual follow-up the user
  runs once, not something to fake-claim as tested here.
