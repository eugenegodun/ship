# Ship

AI orchestrator to deliver product features end-to-end, from a Jira ticket to a
reviewed, QA'd pull request.

```
/ship <TICKET> [stage] [model] [--spec]
```

## How it works

```mermaid
flowchart TD
    Start(["/ship TICKET --spec"]) --> Stage0["Stage 0 — choose models\nplanner + reviewer"]

    Stage0 --> SpecCheck{"--spec flag?"}

    SpecCheck -- yes --> S1["Stage 1 — spec-agent\nWHAT/WHY · EARS acceptance criteria\nor invariants-to-preserve"]
    S1 --> G1{{"🛑 GATE 1\nspec approved?"}}
    G1 -- "changes requested" --> S1
    G1 -- approved --> S2

    SpecCheck -- no --> S2["Stage 2 — task-planner-agent\nreads ticket + code, writes plan"]
    S2 --> G2{{"🛑 GATE 2\nplan approved?"}}
    G2 -- "changes requested" --> S2
    G2 -- approved --> S3

    S3["Stage 3 — implementator-agent\nTDD in isolated git worktree"] --> Fork((" "))
    Fork --> S4["Stage 4 — reviewer-agent\nCritical / Important / Minor findings"]
    Fork -.background.-> QA_A["qa-agent Phase A\nauthors test plan"]

    S4 --> ReadyCheck{"ready to commit?"}
    ReadyCheck -- "fix round (max 3×)" --> S3
    ReadyCheck -- yes --> S5["Stage 5 — commit · push · draft PR"]

    S5 --> Join((" "))
    QA_A -.queued.-> Join
    Join --> G3{{"🛑 GATE 3\nQA plan approved?"}}
    G3 -- "changes requested" --> QA_A
    G3 -- approved --> S6["Stage 6 — qa-agent Phase B\nstage account · Playwright · PR results"]
    S6 --> S7(["Stage 7 — final report"])

    classDef gate fill:#f97316,stroke:#c2410c,color:#fff,font-weight:bold
    classDef stage fill:#2563eb,stroke:#1e3a8a,color:#fff
    classDef bg fill:#059669,stroke:#065f46,color:#fff,stroke-dasharray: 4 3
    classDef endpoint fill:#111827,stroke:#111827,color:#fff

    class G1,G2,G3 gate
    class S1,S2,S3,S4,S5,S6,S7 stage
    class QA_A bg
    class Start,Fork,Join endpoint
```

Only three stops need a human: the spec (when `--spec` is used), the plan, and the QA
plan. Everything else — the review⇄fix loop, the parallel QA-plan authoring, the
commit/push/PR — runs on its own.

Five agents, three human gates:

- **spec-agent** (optional, `--spec`) — turns the ticket into a reviewed spec: user
  stories, EARS-format acceptance criteria, or an "Invariants to preserve" section for
  refactor/migration tickets. No codebase access.
- **task-planner-agent** — turns the ticket (or the approved spec) into a reviewed
  implementation plan, grounded in the real codebase.
- **implementator-agent** — implements the approved plan with TDD in an isolated git
  worktree.
- **reviewer-agent** — reviews the uncommitted diff (correctness, security, spec
  compliance) and returns a fix-or-approve verdict; the review⇄fix loop runs
  autonomously up to 3 rounds.
- **qa-agent** — plans and executes an end-to-end browser QA pass, then posts the plan
  and results to the PR.

Plus **`workflow-retro`** (`/workflow-retro`, manual-only) — a read-only observer that
reviews a completed `/ship` run afterward: real per-agent token spend, what went well
or poorly, and improvement suggestions. Not a pipeline stage, no handoff contract with
`ship`.

## Install

### Claude Code
```
/plugin marketplace add eugenegodun/ship
/plugin install ship@ship
```

### Cursor
Cursor Settings → Plugins → add marketplace `eugenegodun/ship` → install **Ship**.

### Codex
Clone this repo, then in Codex: `/plugins` → browse **Ship** → install.

## Versioning

Two independent version axes:

- **Per-agent versions** — each agent's own SemVer, in its frontmatter `version:` and
  tracked in [`plugins/ship/agents/CHANGELOG.md`](plugins/ship/agents/CHANGELOG.md).
  These track behavior changes to the pipeline itself (gate structure, agent
  handoffs, etc).
- **Plugin package version** — the installable package version, in each tool's
  manifest (`plugins/ship/.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`,
  `.codex-plugin/plugin.json`) and the root marketplace indexes. Bump all of these
  together on every release — there's no sync script, this is a single-plugin repo.

## License

MIT — see [LICENSE](LICENSE).
