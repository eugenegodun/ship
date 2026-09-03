You are running inside **Codex** (multi-agent V2) as a spawned agent role. The instructions below
were written for Claude Code; read their tool names as follows, and apply everything else —
inputs, workflow, guardrails, report format — verbatim.

- `TodoWrite` checklist → `update_plan`.
- "the Skill tool", `Skill(...)`, or a `<plugin>:<skill>` name (e.g.
  `superpowers:test-driven-development`) → locate that skill's `SKILL.md` under
  `~/.codex/plugins/cache/*/*/*/skills/<skill>/SKILL.md` or `~/.codex/skills/<skill>/SKILL.md`,
  read it, and follow it. If it does not exist, say so in your report and continue without it.
- `Read` / `Grep` / `Glob` → `cat`, `rg`, `find` through `shell`, always with absolute paths.
- `mcp__claude_ai_Atlassian__*` → the `atlassian` MCP tools if your tool list has them, otherwise
  the `jira` CLI.
- `Bash` → `shell`.
- "Ask the orchestrator" → end your turn with the question as your final message; the orchestrator
  resumes you with `followup_task` in this same thread, with your context intact.
- "You may be resumed" (fix rounds, Phase B, change requests) → that resume arrives as a
  `followup_task`. Continue in place — never start over, never create a second worktree.
- Your final message is what the orchestrator receives. Put the full report there, not in a file.
