# qa-agent results as an emoji table — Design

## Context

`qa-agent`'s results output (both the PR comment posted in Phase B step 4, and the
final report returned in step 5) is currently unstructured prose: "listing every
tested scenario with its PASS/FAIL status, an overall verdict, and any notable
console/network errors." This is harder to scan than it needs to be — a reviewer
opening the PR has to read a paragraph to find which cases failed. This change
reformats both outputs as a markdown table with an emoji status column, so pass/fail
is visible at a glance.

## What changes

**Format:** a one-line verdict summary above a 4-column table:

```
**Overall: 2/3 passed ❌**

| Test Case | Description | Status | Notes |
|---|---|---|---|
| TC1 | Happy path checkout | ✅ | |
| TC2 | Invalid card number | ✅ | |
| TC3 | Expired card | ❌ | Error banner didn't render; console: TypeError at CheckoutForm.tsx:142 |
```

- **Test Case** — the case id/title from the approved Phase-A plan (already exists per-case in the plan — nothing new to generate here, just reuse the id/title already assigned when the plan was authored).
- **Description** — one line, what the case actually verifies (new column, per your answer).
- **Status** — `✅` or `❌` (your chosen convention — plain checkmark/cross, not the circle or heavy-weight variants, for consistent rendering on GitHub and in-terminal).
- **Notes** — blank when passing; failure detail and/or notable console/network errors for that case when failing. This replaces the current free-floating "any notable console/network errors" clause — errors now attach to the specific case that surfaced them instead of floating separately.
- **Verdict line** — `**Overall: X/Y passed** ✅` (all passed) or `**Overall: X/Y passed** ❌` (any failed), placed above the table so it's the first thing read.

**Where it applies:** both of qa-agent's own outputs —
- Phase B step 4 (`gh pr comment <ref> --body '<results>'`) — the PR comment body.
- Phase B step 5 (the final report returned as qa-agent's last message) — same table,
  so the orchestrator/human sees identical structure whether reading the PR or the
  in-session report.

**What does NOT change:**
- `reviewer-agent`'s Critical/Important/Minor findings stay prose — out of scope, not asked for.
- `ship/SKILL.md`'s Stage 7 ("Return a concise summary... the QA PASS/FAIL result with links to the PR comments") needs no edit — it already just points at the PR comment/report rather than reproducing their content, so it holds regardless of the PR comment's internal format.
- The `<!-- qa-agent-results -->` marker convention, the account provisioning, flag handling, and execution steps (1-3) are unaffected — only how the already-collected pass/fail data gets *rendered* changes.

## Files to change

- `plugins/ship/agents/qa-agent.md` — Phase B step 4 and step 5 wording, to specify
  the table format instead of the current unstructured "listing every tested
  scenario..." phrase. Version `2.4.0` → `2.5.0` (MINOR — output format change only,
  no gate/handoff-contract change; the data qa-agent produces and what the
  orchestrator does with it are unchanged, just how it's formatted).
- `plugins/ship/agents/CHANGELOG.md` — one new entry for the 2.5.0 bump.
- `plugins/ship/skills/ship/SKILL.md` — Compatibility floor line bump for
  `qa-agent` (`≥2.4.0` → `≥2.5.0`) and its own version bump for the floor-line
  change (`3.2.0` → `3.3.0`, MINOR — same rubric as prior floor-only bumps in this
  repo's history, e.g. the 3.2.0 bump).

## Verification

No test suite in this repo (prose/config only). Verification is a read-through
confirming: the table format is specified precisely enough that qa-agent (an LLM
agent) can reliably produce it from the same data it already collects per test case
during execution (step 3, "Execute" — each case already has an id/title, an expected
result, and pass/fail + evidence by the time results are compiled) — no new data
collection step is needed, only a new rendering step. Also confirm version numbers
are consistent between `qa-agent.md`'s frontmatter, the CHANGELOG, and
`ship/SKILL.md`'s Compatibility paragraph.
