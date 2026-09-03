# ship on Codex — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `/ship` pipeline runnable in Codex (multi-agent V2) with the same five agents, while leaving Claude Code `/ship` behavior unchanged and provably so.

**Architecture:** Codex role files (`plugins/ship/codex-agents/*.toml`) are *generated* from the untouched Claude agent `.md` files by a stdlib Python script with a `--check` drift mode, and copied into `~/.codex/agents/` by an install script (Codex plugins cannot bundle roles). All Codex tool mechanics live in a new `skills/ship/references/codex-dispatch.md`; `SKILL.md` gains only a trailing "Platform adaptation — Codex" section that a Claude runtime is told to ignore. A new OpenAI-driven decision-point eval tier proves the Codex dialect; the existing Claude tiers are re-run unchanged as the regression proof.

**Tech Stack:** Python ≥3.12 stdlib (`tomllib`, `json`, `re`) for plugin scripts; bash for the installer; `uv`, `pytest`, `deepeval`, `openai` for evals; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-03-ship-codex-port-design.md`

## Global Constraints

- **Never modify `plugins/ship/agents/*.md`.** `git diff main -- plugins/ship/agents` must be empty at the end.
- **`plugins/ship/skills/ship/SKILL.md` changes only in two places:** frontmatter `version: 4.1.0` → `version: 4.2.0`, and one appended section (Task 3, exact text given). Nothing else in that file moves.
- No other file under `plugins/ship/skills/` changes except the new `skills/ship/references/codex-dispatch.md`.
- Plugin scripts are **stdlib-only Python** (`#!/usr/bin/env python3`, module docstring first — see `plugins/ship/skills/workflow-retro/analyze_run.py` for the house style) and **POSIX bash** with `set -euo pipefail`.
- Role names carry the `ship-` prefix: `ship-spec-agent`, `ship-task-planner-agent`, `ship-implementator-agent`, `ship-reviewer-agent`, `ship-qa-agent`, `ship-git-agent`.
- Role table (spec): spec `gpt-5.6`/`xhigh`/`read-only`; planner `gpt-5.6`/`xhigh`/`read-only`; implementator `gpt-5.6`/`high`/`workspace-write`; reviewer `gpt-5.6`/`xhigh`/`workspace-write`; qa `gpt-5.6`/`medium`/`workspace-write`; git `gpt-5.6-terra`/`low`/`workspace-write`.
- `ship` skill 4.1.0 → **4.2.0**; package 1.9.0 → **1.10.0** in all six tracked manifests (`plugins/ship/.claude-plugin/plugin.json`, `plugins/ship/.cursor-plugin/plugin.json`, `plugins/ship/.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json`, `.agents/plugins/marketplace.json`). Agent versions unchanged.
- Eval env: `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` for the Claude tiers; `OPENAI_API_KEY` only for the Codex tier. Codex tier generation model: `EVAL_CODEX_MODEL`, default `gpt-4.1`.
- Work on branch `ship-codex-port` cut from `main`. All `uv run …` commands run from `evals/`; everything else from the repo root `/Users/eugene.g/Documents/projects/ship`.
- Commit messages: no `Co-Authored-By` line (repo convention).

---

### Task 0: Branch, baseline, commit the spec + plan

**Files:**
- Create (gitignored): `.superpowers/codex-port/baseline-unit.txt`, `.superpowers/codex-port/baseline-evals.txt`
- Commit: `docs/superpowers/specs/2026-09-03-ship-codex-port-design.md`, `docs/superpowers/plans/2026-09-03-ship-codex-port.md`

**Interfaces:**
- Produces: the baseline outputs Task 6 diffs against.

- [ ] **Step 1: Branch**

```bash
cd /Users/eugene.g/Documents/projects/ship
git status --short          # expect only the pre-existing untracked .agents/skills, .claude, skills-lock.json
git checkout -b ship-codex-port main
```

- [ ] **Step 2: Record the Claude-tier baseline (needs both API keys — if they are not exported, ask the user for them; do not skip this step)**

```bash
mkdir -p .superpowers/codex-port
cd evals && uv sync --frozen
uv run pytest tests -v 2>&1 | tee ../.superpowers/codex-port/baseline-unit.txt | tail -3
uv run deepeval test run agents orchestrator -v 2>&1 | tee ../.superpowers/codex-port/baseline-evals.txt | tail -15
cd ..
```

Expected: unit tests all pass; the agent + orchestrator run reports its pass/fail counts. Note the exact counts — they must match in Task 6.

- [ ] **Step 3: Commit the design docs**

```bash
git add docs/superpowers/specs/2026-09-03-ship-codex-port-design.md docs/superpowers/plans/2026-09-03-ship-codex-port.md
git commit -m "docs: design + plan for running ship on Codex"
```

---

### Task 1: Role-file generator (`sync_codex_agents.py`) with `--check`

**Files:**
- Create: `plugins/ship/scripts/sync_codex_agents.py`
- Create: `plugins/ship/codex-agents/_preamble.md` (a one-line placeholder is enough here; Task 2 writes the real text)
- Test: `evals/tests/test_sync_codex_agents.py`

**Interfaces:**
- Produces: module `sync_codex_agents` with `ROLES: dict[str, dict]`, `parse_agent(text: str) -> tuple[str, str, str]` (name, one-paragraph description, body), `render_role(name, description, body, preamble, cfg) -> str`, `generate(plugin_dir: Path) -> dict[str, str]` (filename → TOML text), `main(argv) -> int` (0 ok, 1 drift, 2 error). CLI: `sync_codex_agents.py [--check] [--plugin-dir DIR]`.
- Output files: `plugins/ship/codex-agents/ship-<agent>.toml` for the five agents in `ROLES`. The hand-written `ship-git-agent.toml` (Task 2) is not generated and is ignored by `--check`.

- [ ] **Step 1: Write the failing tests**

`evals/tests/test_sync_codex_agents.py`:

```python
import importlib.util
import shutil
import tomllib
from pathlib import Path

import pytest

from ship_evals.artifacts import load_agent
from ship_evals.config import PLUGIN_DIR

SCRIPT = PLUGIN_DIR / "scripts" / "sync_codex_agents.py"
GENERATED = ["spec-agent", "task-planner-agent", "implementator-agent", "reviewer-agent", "qa-agent"]


def _load():
    spec = importlib.util.spec_from_file_location("sync_codex_agents", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sync():
    return _load()


def test_parse_agent_extracts_name_first_paragraph_and_body(sync):
    text = (PLUGIN_DIR / "agents" / "reviewer-agent.md").read_text()
    name, description, body = sync.parse_agent(text)
    assert name == "reviewer-agent"
    assert description.startswith("Use this agent to code-review a feature BEFORE it is committed.")
    assert "Examples:" not in description and "\n" not in description
    assert body == load_agent("reviewer-agent")


def test_generate_renders_every_role_as_valid_toml(sync):
    out = sync.generate(PLUGIN_DIR)
    assert sorted(out) == sorted(f"ship-{n}.toml" for n in GENERATED)
    for agent in GENERATED:
        data = tomllib.loads(out[f"ship-{agent}.toml"])
        cfg = sync.ROLES[agent]
        assert data["name"] == f"ship-{agent}"
        assert data["model"] == cfg["model"]
        assert data["model_reasoning_effort"] == cfg["effort"]
        assert data["sandbox_mode"] == cfg["sandbox"]
        assert data["developer_instructions"].endswith(load_agent(agent)), agent
        assert data["description"] and "\n" not in data["description"]


def test_generated_header_marks_file_as_generated(sync):
    out = sync.generate(PLUGIN_DIR)
    text = out["ship-qa-agent.toml"]
    assert text.startswith("# GENERATED by plugins/ship/scripts/sync_codex_agents.py")
    assert "agents/qa-agent.md" in text.splitlines()[0]


def test_render_refuses_triple_single_quotes(sync):
    with pytest.raises(ValueError):
        sync.render_role("x", "d", "body with ''' inside\n", "pre", sync.ROLES["qa-agent"])


def test_check_mode_passes_on_fresh_output_and_fails_on_drift(sync, tmp_path):
    plugin = tmp_path / "plugin"
    shutil.copytree(PLUGIN_DIR / "agents", plugin / "agents")
    (plugin / "codex-agents").mkdir()
    (plugin / "codex-agents" / "_preamble.md").write_text(
        (PLUGIN_DIR / "codex-agents" / "_preamble.md").read_text())
    (plugin / "scripts").mkdir()
    assert sync.main(["--plugin-dir", str(plugin)]) == 0          # writes
    assert sync.main(["--check", "--plugin-dir", str(plugin)]) == 0
    target = plugin / "codex-agents" / "ship-qa-agent.toml"
    target.write_text(target.read_text().replace("gpt-5.6", "gpt-tampered"))
    assert sync.main(["--check", "--plugin-dir", str(plugin)]) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd evals && uv run pytest tests/test_sync_codex_agents.py -v
```
Expected: FAIL — `FileNotFoundError` / `AttributeError` because the script does not exist yet.

- [ ] **Step 3: Write the preamble placeholder**

`plugins/ship/codex-agents/_preamble.md` (Task 2 replaces this):

```markdown
You are running inside Codex as a spawned agent role.
```

- [ ] **Step 4: Write the generator**

`plugins/ship/scripts/sync_codex_agents.py`:

```python
#!/usr/bin/env python3
"""
Generates Codex custom-agent role files (TOML) from the Claude Code agent
definitions in plugins/ship/agents/*.md. Stdlib only.

Codex plugins cannot bundle agent roles, so the roles live in
plugins/ship/codex-agents/ship-<agent>.toml and are copied into
~/.codex/agents/ by scripts/install-codex-agents.sh. The .md files stay the
single source of truth: this script prepends codex-agents/_preamble.md (the
Codex tool-name adapter) to each agent body verbatim.

  sync_codex_agents.py                 # (re)write the TOMLs
  sync_codex_agents.py --check         # exit 1 if any TOML differs from what
                                       # would be generated (CI drift check)

ship-git-agent.toml is hand-written and never touched here.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROLES = {
    "spec-agent": {"model": "gpt-5.6", "effort": "xhigh", "sandbox": "read-only"},
    "task-planner-agent": {"model": "gpt-5.6", "effort": "xhigh", "sandbox": "read-only"},
    "implementator-agent": {"model": "gpt-5.6", "effort": "high", "sandbox": "workspace-write"},
    "reviewer-agent": {"model": "gpt-5.6", "effort": "xhigh", "sandbox": "workspace-write"},
    "qa-agent": {"model": "gpt-5.6", "effort": "medium", "sandbox": "workspace-write"},
}

HEADER = (
    "# GENERATED by plugins/ship/scripts/sync_codex_agents.py from plugins/ship/agents/{name}.md.\n"
    "# Do not edit - edit the .md and re-run the script. CI fails on drift.\n"
)

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def parse_agent(text):
    """Return (name, one-paragraph description, body) from an agent .md file."""
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValueError("agent file has no YAML frontmatter")
    frontmatter, body = match.group(1), match.group(2).lstrip("\n")
    name_match = re.search(r"^name:\s*(\S+)\s*$", frontmatter, re.M)
    if not name_match:
        raise ValueError("frontmatter has no name:")
    lines = frontmatter.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("description:")), None)
    if start is None:
        raise ValueError("frontmatter has no description:")
    paragraph = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        paragraph.append(line.strip())
    return name_match.group(1), " ".join(paragraph), body


def render_role(name, description, body, preamble, cfg):
    instructions = f"{preamble.rstrip()}\n\n{body}"
    if not instructions.endswith("\n"):
        instructions += "\n"
    if "'''" in instructions:
        raise ValueError(f"{name}: developer_instructions contains ''' which TOML literal strings cannot hold")
    return (
        HEADER.format(name=name)
        + f'name = "ship-{name}"\n'
        + f"description = {json.dumps(description)}\n"
        + f'model = "{cfg["model"]}"\n'
        + f'model_reasoning_effort = "{cfg["effort"]}"\n'
        + f'sandbox_mode = "{cfg["sandbox"]}"\n'
        + f"developer_instructions = '''\n{instructions}'''\n"
    )


def generate(plugin_dir):
    plugin_dir = Path(plugin_dir)
    preamble = (plugin_dir / "codex-agents" / "_preamble.md").read_text()
    out = {}
    for agent, cfg in ROLES.items():
        name, description, body = parse_agent((plugin_dir / "agents" / f"{agent}.md").read_text())
        if name != agent:
            raise ValueError(f"{agent}.md declares name {name!r}")
        out[f"ship-{agent}.toml"] = render_role(name, description, body, preamble, cfg)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    parser.add_argument("--plugin-dir", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    plugin_dir = Path(args.plugin_dir)
    try:
        rendered = generate(plugin_dir)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out_dir = plugin_dir / "codex-agents"
    drift = []
    for filename, text in rendered.items():
        target = out_dir / filename
        current = target.read_text() if target.exists() else None
        if current == text:
            continue
        if args.check:
            drift.append(filename)
        else:
            target.write_text(text)
            print(f"wrote {target}")
    if drift:
        print("codex role files are out of date - run plugins/ship/scripts/sync_codex_agents.py:", file=sys.stderr)
        for filename in drift:
            print(f"  {filename}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```bash
chmod +x plugins/ship/scripts/sync_codex_agents.py
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd evals && uv run pytest tests/test_sync_codex_agents.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add plugins/ship/scripts/sync_codex_agents.py plugins/ship/codex-agents/_preamble.md evals/tests/test_sync_codex_agents.py
git commit -m "feat(codex): generate Codex role TOMLs from the ship agent definitions"
```

---

### Task 2: Preamble, git-ops role, generated TOMLs, and the installer

**Files:**
- Modify: `plugins/ship/codex-agents/_preamble.md` (replace the placeholder)
- Create: `plugins/ship/codex-agents/ship-git-agent.toml`
- Create (generated): `plugins/ship/codex-agents/ship-{spec,task-planner,implementator,reviewer,qa}-agent.toml`
- Create: `plugins/ship/scripts/install-codex-agents.sh`
- Test: `evals/tests/test_install_codex_agents.py`

**Interfaces:**
- Consumes: `sync_codex_agents.py` from Task 1.
- Produces: `install-codex-agents.sh [--to DIR] [--check]` — copies every `codex-agents/ship-*.toml` into `DIR` (default `${CODEX_HOME:-$HOME/.codex}/agents`); prints one line per file (`installed`, `updated`, `unchanged`, or in check mode `missing/stale`); exit 0 when everything is in place, 1 when `--check` finds a difference, 2 on bad arguments. Task 3's reference and Task 4's fixtures rely on this exact output vocabulary.

- [ ] **Step 1: Write the failing installer tests**

`evals/tests/test_install_codex_agents.py`:

```python
import os
import subprocess

from ship_evals.config import PLUGIN_DIR

SCRIPT = PLUGIN_DIR / "scripts" / "install-codex-agents.sh"
ROLES = ["ship-spec-agent", "ship-task-planner-agent", "ship-implementator-agent",
         "ship-reviewer-agent", "ship-qa-agent", "ship-git-agent"]


def run(*args, env=None):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def test_installs_all_six_roles_then_reports_unchanged(tmp_path):
    first = run("--to", str(tmp_path))
    assert first.returncode == 0, first.stderr
    assert sorted(p.name for p in tmp_path.glob("*.toml")) == sorted(f"{r}.toml" for r in ROLES)
    assert first.stdout.count("installed") == 6
    second = run("--to", str(tmp_path))
    assert second.returncode == 0 and second.stdout.count("unchanged") == 6


def test_check_mode_reports_missing_and_stale_without_writing(tmp_path):
    assert run("--to", str(tmp_path)).returncode == 0
    (tmp_path / "ship-qa-agent.toml").unlink()
    (tmp_path / "ship-reviewer-agent.toml").write_text("stale")
    check = run("--to", str(tmp_path), "--check")
    assert check.returncode == 1
    assert "missing/stale  ship-qa-agent.toml" in check.stdout
    assert "missing/stale  ship-reviewer-agent.toml" in check.stdout
    assert not (tmp_path / "ship-qa-agent.toml").exists(), "--check must not write"


def test_default_destination_honours_codex_home(tmp_path):
    result = run(env={"CODEX_HOME": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "agents" / "ship-git-agent.toml").exists()


def test_unknown_flag_exits_2():
    assert run("--bogus").returncode == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd evals && uv run pytest tests/test_install_codex_agents.py -v
```
Expected: FAIL — `bash: …/install-codex-agents.sh: No such file or directory` (returncode 127).

- [ ] **Step 3: Write the real preamble**

`plugins/ship/codex-agents/_preamble.md`:

```markdown
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
```

- [ ] **Step 4: Write the hand-authored git-ops role**

`plugins/ship/codex-agents/ship-git-agent.toml`:

```toml
# Hand-written role for ship's Stage 5 (commit / push / draft PR). Not generated.
# Claude Code uses a generic Haiku agent for this stage; Codex needs a named role.
name = "ship-git-agent"
description = "Commits the ship pipeline's verified worktree on the ticket branch, pushes it, and opens a draft PR from the repo template. Does nothing else."
model = "gpt-5.6-terra"
model_reasoning_effort = "low"
sandbox_mode = "workspace-write"
developer_instructions = '''
You are **ship-git-agent**, the commit / push / draft-PR stage of the ship pipeline, running in
Codex. The orchestrator's brief gives you a worktree path, a branch name (the Jira ticket id), and
the change summary. You do exactly the following and nothing else.

1. `cd <worktree>` and confirm `git branch --show-current` prints the ticket branch. If HEAD is
   detached or the branch differs, stop and report that verbatim — do not create or switch branches.
2. Commit everything: `git add -A && git commit -m "<TICKET>: <one-line summary>"`. **Never add a
   `Co-Authored-By` line.** Never amend or rewrite existing commits.
3. Push: `git push -u origin <branch>`. If the push is rejected as non-fast-forward, run
   `git pull --ff-only origin <branch>` once and push again. Never merge or rebase master/main in.
4. Open a draft PR: `gh pr create --draft --title "<TICKET>: <summary>" --body-file <file>` where
   `<file>` is the repo's `.github/pull_request_template.md` with its sections filled in for this
   change — never a custom body format. If the template does not exist, use `--fill`.
5. Report, in your final message: PR number, PR URL, commit SHA, branch. If any step fails, report
   the exact command and its error and stop — do not retry with different flags or work around it.

You never edit source files, never run tests or linters, never touch other branches or worktrees.
'''
```

- [ ] **Step 5: Generate the five role files and sanity-check one**

```bash
python3 plugins/ship/scripts/sync_codex_agents.py
python3 plugins/ship/scripts/sync_codex_agents.py --check; echo "check exit=$?"
python3 -c "import tomllib,pathlib; d=tomllib.loads(pathlib.Path('plugins/ship/codex-agents/ship-reviewer-agent.toml').read_text()); print(d['name'], d['model'], d['sandbox_mode'], len(d['developer_instructions']))"
```
Expected: five `wrote …` lines, then `check exit=0`, then `ship-reviewer-agent gpt-5.6 workspace-write <a number > 5000>`.

- [ ] **Step 6: Write the installer**

`plugins/ship/scripts/install-codex-agents.sh`:

```bash
#!/usr/bin/env bash
# Install the ship pipeline's Codex agent roles.
#
# Codex plugins cannot bundle custom agent roles, so the TOMLs in
# plugins/ship/codex-agents/ are copied into a Codex agents directory.
#
#   install-codex-agents.sh              copy into ${CODEX_HOME:-$HOME/.codex}/agents
#   install-codex-agents.sh --to DIR     copy into DIR (e.g. <repo>/.codex/agents)
#   install-codex-agents.sh --check      write nothing; exit 1 if any role is missing or stale
#
# Output: one line per role - "installed", "updated", "unchanged", or (check mode) "missing/stale".
# Exit codes: 0 all in place, 1 drift found (--check), 2 bad arguments.
# Re-run after every plugin update; restart the Codex session so it reloads the roles.
set -euo pipefail

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../codex-agents" && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/agents"
CHECK=0

while [ $# -gt 0 ]; do
  case "$1" in
    --to) [ $# -ge 2 ] || { usage >&2; exit 2; }; DEST="$2"; shift 2 ;;
    --check) CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

status=0
for src in "$SRC"/ship-*.toml; do
  name="$(basename "$src")"
  dest="$DEST/$name"
  if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
    echo "unchanged  $name"
    continue
  fi
  if [ "$CHECK" = 1 ]; then
    echo "missing/stale  $name"
    status=1
    continue
  fi
  mkdir -p "$DEST"
  if [ -f "$dest" ]; then verb="updated"; else verb="installed"; fi
  cp "$src" "$dest"
  echo "$verb  $name -> $dest"
done

if [ "$CHECK" = 1 ] && [ "$status" != 0 ]; then
  echo "run: bash $SRC/../scripts/install-codex-agents.sh" >&2
fi
exit "$status"
```

```bash
chmod +x plugins/ship/scripts/install-codex-agents.sh
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd evals && uv run pytest tests/test_install_codex_agents.py tests/test_sync_codex_agents.py -v
```
Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add plugins/ship/codex-agents plugins/ship/scripts/install-codex-agents.sh evals/tests/test_install_codex_agents.py
git commit -m "feat(codex): role files, Codex preamble, git-ops role, and installer"
```

---

### Task 3: `codex-dispatch.md` reference + the one `SKILL.md` change

**Files:**
- Create: `plugins/ship/skills/ship/references/codex-dispatch.md`
- Modify: `plugins/ship/skills/ship/SKILL.md` — line 3 (`version: 4.1.0` → `4.2.0`) and append after line 402
- Test: `evals/tests/test_skill_codex_section.py`

**Interfaces:**
- Consumes: role names and installer output vocabulary from Task 2.
- Produces: the system-prompt text Task 4's Codex tier loads (`SKILL.md` body + this reference). The `task_name` scheme `<TICKET>-<role>` (`spec`, `planner`, `implementator`, `reviewer-r<N>`, `qa`, `git`) is asserted by Task 4's fixtures.

- [ ] **Step 1: Write the failing guard tests**

`evals/tests/test_skill_codex_section.py`:

```python
import re

from ship_evals.artifacts import load_skill
from ship_evals.config import PLUGIN_DIR

# NB: not "agent_type" - it is a substring of the Claude tool param "subagent_type" used throughout.
CODEX_WORDS = ("spawn_agent", "followup_task", "wait_agent", "codex-dispatch")
ROLES = ["ship-spec-agent", "ship-task-planner-agent", "ship-implementator-agent",
         "ship-reviewer-agent", "ship-qa-agent", "ship-git-agent"]


def test_codex_section_is_the_last_heading_and_nothing_codex_appears_above_it():
    body = load_skill("ship")
    headings = re.findall(r"^## .*$", body, re.M)
    assert headings[-1] == "## Platform adaptation — Codex"
    above = body[: body.index("## Platform adaptation — Codex")]
    for word in CODEX_WORDS:
        assert word not in above, f"{word!r} leaked into the Claude-facing part of SKILL.md"


def test_codex_section_points_at_the_reference_and_tells_claude_to_ignore_it():
    body = load_skill("ship")
    section = body[body.index("## Platform adaptation — Codex"):]
    assert "references/codex-dispatch.md" in section
    assert "ignore this section" in section


def test_skill_version_is_4_2_0():
    text = (PLUGIN_DIR / "skills" / "ship" / "SKILL.md").read_text()
    assert "\nversion: 4.2.0\n" in text.split("\n---\n", 1)[0]


def test_dispatch_reference_names_every_role_and_the_installer():
    ref = (PLUGIN_DIR / "skills" / "ship" / "references" / "codex-dispatch.md").read_text()
    for role in ROLES:
        assert role in ref
    assert "install-codex-agents.sh" in ref and "--check" in ref
    assert 'fork_turns: "none"' in ref and "followup_task" in ref and "wait_agent" in ref
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd evals && uv run pytest tests/test_skill_codex_section.py -v
```
Expected: 4 failed (no section, version 4.1.0, no reference file).

- [ ] **Step 3: Write the dispatch reference**

`plugins/ship/skills/ship/references/codex-dispatch.md`:

````markdown
# ship on Codex — dispatch reference

Read this only when your tool list has `spawn_agent` / `followup_task` / `wait_agent` (Codex
multi-agent V2). It maps every tool call in `SKILL.md` onto Codex. The pipeline itself — stages,
gates, the 3-round review cap, the handoff contract — is unchanged. Where this file and `SKILL.md`
disagree on *what* to do, `SKILL.md` wins; this file only says *how* on Codex.

## Preflight (before Stage 0)

The six pipeline roles must be installed as Codex custom agents (Codex plugins cannot ship them).
Run:

```bash
bash "$(ls -d ~/.codex/plugins/cache/ship/ship/*/ | sort -V | tail -1)scripts/install-codex-agents.sh" --check
```

- Exit 0 (every line `unchanged`) → proceed.
- Anything else (`missing/stale` lines) → do **not** spawn anything. Tell the user which roles are
  missing or stale and give them the exact command to run themselves — the same path without
  `--check` — because the sandbox may not allow writes under `~/.codex/`. Roles load at session
  start, so also tell them to restart the Codex session afterwards. Then **stop**.
- If a later `spawn_agent` fails with `unknown agent_type`, the session predates the install: ask
  the user to restart Codex and re-run `/ship`.

## Roles

| `SKILL.md` agent | Codex `agent_type` | model / effort | sandbox |
|---|---|---|---|
| spec-agent | `ship-spec-agent` | gpt-5.6 / xhigh | read-only |
| task-planner-agent | `ship-task-planner-agent` | gpt-5.6 / xhigh | read-only |
| implementator-agent | `ship-implementator-agent` | gpt-5.6 / high | workspace-write |
| reviewer-agent | `ship-reviewer-agent` | gpt-5.6 / xhigh | workspace-write |
| qa-agent | `ship-qa-agent` | gpt-5.6 / medium | workspace-write |
| Stage 5 "Haiku agent" | `ship-git-agent` | gpt-5.6-terra / low | workspace-write |

Models are fixed per role (`spawn_agent` has no model parameter). To change one, edit `ROLES` in
`plugins/ship/scripts/sync_codex_agents.py`, re-run it, and re-run the installer.

## Stage 0 on Codex

Skip both model questions. Post one line — *"Codex run — models are fixed per role: planner/spec
gpt-5.6 xhigh, reviewer gpt-5.6 xhigh, implementator gpt-5.6 high, QA gpt-5.6 medium, git
gpt-5.6-terra."* — then build the checklist with `update_plan` and continue exactly as `SKILL.md`
describes. In the progress table, the model detail reads "fixed per role (Codex)".

## Tool mapping

| `SKILL.md` says | On Codex call |
|---|---|
| `Agent(subagent_type: X, model: M, prompt: B)` | `spawn_agent {task_name: "<TICKET>-<role>", agent_type: "ship-X", fork_turns: "none", message: B}` |
| `Agent(…, run_in_background: true)` | the same `spawn_agent` — every spawn is already asynchronous; keep working |
| `SendMessage(agent_id, message)` | `followup_task {target: "<TICKET>-<role>", message}` on the **same** `task_name` |
| `TaskOutput` / waiting for a background agent | `wait_agent {timeout_ms: 300000}`; a child's final answer also lands in your mailbox at the start of your next turn |
| `AskUserQuestion` | nothing — end the turn with the material and the question in prose |
| `TodoWrite` | `update_plan` |
| `Skill(skill, args)` | read that skill's `SKILL.md` from `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md` and follow it with the same `args` |
| `Bash` | `shell` |

`<role>` is one of `spec`, `planner`, `implementator`, `reviewer-r<N>` (N = review round), `qa`,
`git` — e.g. `LEX-1398-implementator`. Every role has exactly one `task_name` per run, except the
reviewer, which `SKILL.md` dispatches fresh each round.

## Rules that change shape on Codex

1. **Clean context, full brief.** Always `fork_turns: "none"` (Codex refuses `agent_type` on a
   full-history fork). The brief must carry everything the agent needs — approved spec/plan text
   inline, ticket id, worktree path + branch, PR URL — exactly as `SKILL.md` already requires.
2. **Resume = `followup_task` on the same `task_name`.** Fix rounds (implementator), change requests
   (spec-agent, planner, qa-agent), and the QA Phase-B resume all go to the existing agent. Never
   `spawn_agent` a second implementator or qa-agent in a run. A child Codex evicted while idle is
   reloaded transparently by `followup_task`.
3. **Gates.** GATE 1/2/3: surface the spec / plan / QA plan verbatim, ask for approval in prose, and
   end the turn with **no tool calls**. GATE 3 also asks "Record video of this QA run?" unless
   `--record` was passed. The user's next message is the verdict.
4. **Parallel QA branch.** After the first verified tree, `spawn_agent` the qa-agent with the
   deferred-PR brief from `SKILL.md` and continue immediately with the reviewer. At Stage 6, if the
   qa-agent's plan has not reached your mailbox, `wait_agent {timeout_ms: 300000}` — never poll with
   short timeouts.
5. **Reviewer escalation.** `SKILL.md` escalates a re-review round to `claude-opus-5[1m]` after a
   Critical finding. Models are per-role on Codex, so this is a no-op: run the round on
   `ship-reviewer-agent` as usual. Cap (3), verdict line, and halt behavior are unchanged.
6. **Stage 5 git ops.** Instead of a Haiku `claude` agent: `spawn_agent {task_name: "<TICKET>-git",
   agent_type: "ship-git-agent", fork_turns: "none", message: <brief>}` with the same brief
   `SKILL.md` gives — commit on the ticket branch, **no `Co-Authored-By`**, `git push -u`,
   `git pull --ff-only` only on a rejection, `gh pr create --draft` from the repo template, ticket in
   the title, return PR number + URL. If it reports a detached HEAD it may not branch from (a Codex
   App-managed worktree), it has committed locally: report the App's **Create branch** hand-off
   instead of a PR URL and wait for the user to provide the PR before Stage 6.
7. **Stage 8.** Same two calls; "dispatch the `engineering-insights` skill" means read
   `skills/engineering-insights/SKILL.md` from the plugin cache and follow it with the given `args`.
8. **Usage reporting.** You still cannot read token counts. Point the user to Codex's `/status`;
   never quote a number.
9. **Progress display.** `update_plan` is bookkeeping only; every user-facing update still ends with
   the full stage table from `SKILL.md`.

## Sandbox notes

- Subagents inherit your sandbox; a role's `sandbox_mode` only adjusts it per role. The
  implementator's worktree must sit under a writable root — `superpowers:using-git-worktrees`
  detects an existing linked worktree or detached HEAD before creating one.
- A role that cannot reach a tool it needs (`gh`, `jira`, network) reports the blocker in its final
  message; relay it to the user and stop rather than working around it.

## Known limits

- No per-run model choice on Codex (edit `ROLES`, re-run the sync script, re-install).
- Role files set no `mcp_servers`; agents use CLI tools (`jira`, `gh`) or whatever MCP servers the
  Codex session already has.
````

- [ ] **Step 4: Edit `SKILL.md` — version line and appended section only**

Change line 3 from `version: 4.1.0` to `version: 4.2.0`.

Append to the very end of the file (after the existing last line ``plugins/ship/agents/CHANGELOG.md`.``), preceded by one blank line:

```markdown
## Platform adaptation — Codex

This skill is written in Claude Code's tool vocabulary (`Agent`, `SendMessage`, `AskUserQuestion`,
`TodoWrite`). If your tool list instead has `spawn_agent`, `followup_task`, and `wait_agent`, you
are running in **Codex**: before Stage 0, read `references/codex-dispatch.md` (next to this file)
and follow its mapping for every dispatch, resume, gate, and the git stage. The pipeline — stages,
gates, the 3-round cap, the handoff contract — is unchanged; only the tool calls differ. If your
tool list has `Agent` and `SendMessage`, ignore this section entirely.
```

- [ ] **Step 5: Verify the SKILL.md diff is exactly those two hunks**

```bash
git diff --stat main -- plugins/ship/skills/ship/SKILL.md
git diff main -- plugins/ship/skills/ship/SKILL.md | grep -E '^[-+][^-+]' 
```
Expected: `1 file changed, 10 insertions(+), 1 deletion(-)` (version line + blank + heading + blank + 6 paragraph lines); the only `-` line is `-version: 4.1.0`, the `+` lines are `+version: 4.2.0` and the appended section. The single `-` line is the invariant that matters — an off-by-one in the `+` count from blank-line placement is fine.

- [ ] **Step 6: Run the guard tests and the whole unit tier**

```bash
cd evals && uv run pytest tests -v
```
Expected: all pass (existing unit tests + 4 new guards + Task 1/2 tests).

- [ ] **Step 7: Commit**

```bash
git add plugins/ship/skills/ship/SKILL.md plugins/ship/skills/ship/references/codex-dispatch.md evals/tests/test_skill_codex_section.py
git commit -m "feat(ship): 4.2.0 - Codex dispatch reference behind a trailing platform-adaptation note"
```

---

### Task 4: Codex decision-point eval tier

**Files:**
- Create: `evals/src/ship_evals/codex_tools.py`
- Create: `evals/src/ship_evals/codex_harness.py`
- Create: `evals/orchestrator_codex/__init__.py` (empty), `evals/orchestrator_codex/conftest.py`
- Create: `evals/orchestrator_codex/fixtures/transcripts/{roles_installed_invoke,roles_missing_invoke,impl_verified,review_critical_round1,review_clean}.json`
- Create: `evals/orchestrator_codex/test_codex_dispatch.py`
- Modify: `evals/pyproject.toml` (dependency, marker, testpaths), `evals/conftest.py` (key-skip rule), `.github/workflows/ship-evals.yml` (new job)
- Test: `evals/tests/test_codex_tools.py`

**Interfaces:**
- Consumes: `load_skill` (`ship_evals.artifacts`), `load_transcript` (`ship_evals.harness`), `PLUGIN_DIR`.
- Produces: `CODEX_ORCHESTRATOR_TOOLS: list[dict]` (OpenAI function-tool schemas); `load_codex_system() -> str`; `call_codex_model(system, messages, tools) -> ChatCompletion`; `codex_tool_calls(resp) -> list[ToolCall]`; `codex_output_text(resp) -> str`; `CODEX_MODEL: str`.

- [ ] **Step 1: Write the failing unit test for the tool schemas**

`evals/tests/test_codex_tools.py`:

```python
from ship_evals.codex_tools import CODEX_ORCHESTRATOR_TOOLS


def test_codex_tool_set_matches_multi_agent_v2():
    names = {t["function"]["name"] for t in CODEX_ORCHESTRATOR_TOOLS}
    assert names == {"spawn_agent", "followup_task", "send_message", "wait_agent",
                     "interrupt_agent", "list_agents", "update_plan", "shell"}
    spawn = next(t for t in CODEX_ORCHESTRATOR_TOOLS if t["function"]["name"] == "spawn_agent")
    props = spawn["function"]["parameters"]["properties"]
    assert set(props) == {"task_name", "message", "fork_turns", "agent_type"}
    assert "model" not in props, "V2 spawn_agent has no model override"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd evals && uv run pytest tests/test_codex_tools.py -v
```
Expected: FAIL — `ModuleNotFoundError: ship_evals.codex_tools`.

- [ ] **Step 3: Write the tool schemas**

`evals/src/ship_evals/codex_tools.py`:

```python
"""OpenAI function-tool schemas mirroring Codex multi-agent V2 (codex-cli 0.147)."""


def _fn(name, description, properties, required):
    return {"type": "function",
            "function": {"name": name, "description": description,
                         "parameters": {"type": "object", "properties": properties,
                                        "required": required}}}


SPAWN_AGENT = _fn(
    "spawn_agent",
    "Spawns an agent to work on the specified task. Returns its canonical task name. The agent's "
    "final answer arrives later in your mailbox or via wait_agent.",
    {
        "task_name": {"type": "string", "description": "Short unique name for the child task"},
        "message": {"type": "string", "description": "The task brief"},
        "fork_turns": {"type": "string",
                       "description": "'none' (clean context), 'all', or a positive integer string"},
        "agent_type": {"type": "string",
                       "description": "Agent role override. Only allowed when fork_turns is not 'all'."},
    },
    ["task_name", "message"],
)

FOLLOWUP_TASK = _fn(
    "followup_task",
    "Give an existing agent a new task and trigger a turn, keeping its context.",
    {"target": {"type": "string", "description": "task_name of the agent"},
     "message": {"type": "string"}},
    ["target", "message"],
)

SEND_MESSAGE = _fn(
    "send_message",
    "Pass a message to a running agent without triggering a turn.",
    {"target": {"type": "string"}, "message": {"type": "string"}},
    ["target", "message"],
)

WAIT_AGENT = _fn(
    "wait_agent",
    "Wait for mailbox activity from child agents, up to timeout_ms.",
    {"timeout_ms": {"type": "integer"}},
    ["timeout_ms"],
)

INTERRUPT_AGENT = _fn("interrupt_agent", "Interrupt a running child agent.",
                      {"target": {"type": "string"}}, ["target"])

LIST_AGENTS = _fn("list_agents", "List child agents and their states.", {}, [])

UPDATE_PLAN = _fn(
    "update_plan",
    "Create or update the step checklist shown to the user.",
    {"plan": {"type": "array",
              "items": {"type": "object",
                        "properties": {"step": {"type": "string"},
                                       "status": {"type": "string",
                                                  "enum": ["pending", "in_progress", "completed"]}},
                        "required": ["step", "status"]}}},
    ["plan"],
)

SHELL = _fn("shell", "Run a shell command and return its output.",
            {"command": {"type": "string"}}, ["command"])

CODEX_ORCHESTRATOR_TOOLS = [SPAWN_AGENT, FOLLOWUP_TASK, SEND_MESSAGE, WAIT_AGENT, INTERRUPT_AGENT,
                            LIST_AGENTS, UPDATE_PLAN, SHELL]
```

- [ ] **Step 4: Run the unit test to verify it passes**

```bash
cd evals && uv run pytest tests/test_codex_tools.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Add the `openai` dependency, marker, and testpath**

`evals/pyproject.toml` — edit these three places:

```toml
dependencies = [
    "deepeval>=3.4",
    "pytest>=8.0",
    "anthropic>=0.60",
    "openai>=1.50",
]
```

```toml
markers = [
    "e2e: multi-turn pipeline scenarios (nightly job only)",
    "llm: calls a live model (needs ANTHROPIC_API_KEY / OPENAI_API_KEY)",
    "codex: Codex-dialect decision points via the OpenAI API (needs OPENAI_API_KEY)",
]
addopts = "-m 'not e2e'"
testpaths = ["tests", "agents", "orchestrator", "orchestrator_codex", "e2e"]
```

```bash
cd evals && uv lock && uv sync --frozen && uv run python -c "import openai; print(openai.__version__)"
```
Expected: prints a version; `uv.lock` updated.

- [ ] **Step 6: Extend the key-skip rule in the root conftest**

Replace the body of `evals/conftest.py` with:

```python
import os

import pytest

_NEEDS = {
    "llm": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
    "e2e": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
    "codex": ("OPENAI_API_KEY",),
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        needed = {key for marker, keys in _NEEDS.items() if marker in item.keywords for key in keys}
        missing = sorted(k for k in needed if not os.environ.get(k))
        if missing:
            item.add_marker(pytest.mark.skip(reason=f"missing API keys: {', '.join(missing)}"))
```

- [ ] **Step 7: Write the Codex harness**

`evals/src/ship_evals/codex_harness.py`:

```python
"""OpenAI chat-completions driver for the Codex-dialect orchestrator evals."""
import json
import os

from deepeval.test_case import ToolCall
from openai import OpenAI

from .artifacts import load_skill
from .config import MAX_TOKENS, PLUGIN_DIR

CODEX_MODEL = os.environ.get("EVAL_CODEX_MODEL", "gpt-4.1")
REFERENCE = PLUGIN_DIR / "skills" / "ship" / "references" / "codex-dispatch.md"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def load_codex_system() -> str:
    """What a Codex runtime effectively reads: SKILL.md body + the dispatch reference it points at."""
    return load_skill("ship") + "\n\n" + REFERENCE.read_text()


def call_codex_model(system: str, messages: list[dict], tools: list[dict], model: str = CODEX_MODEL):
    # max_completion_tokens (not max_tokens): accepted by every current model, including the
    # reasoning models a user may set via EVAL_CODEX_MODEL, which reject max_tokens.
    return _get_client().chat.completions.create(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": system}, *messages],
        tools=tools,
    )


def codex_tool_calls(response) -> list[ToolCall]:
    message = response.choices[0].message
    return [ToolCall(name=tc.function.name, input_parameters=json.loads(tc.function.arguments or "{}"))
            for tc in (message.tool_calls or [])]


def codex_output_text(response) -> str:
    return response.choices[0].message.content or ""
```

- [ ] **Step 8: Write the tier's conftest**

`evals/orchestrator_codex/__init__.py`: empty file.

`evals/orchestrator_codex/conftest.py`:

```python
from pathlib import Path

import pytest

from ship_evals.codex_harness import call_codex_model, codex_output_text, codex_tool_calls, load_codex_system
from ship_evals.codex_tools import CODEX_ORCHESTRATOR_TOOLS
from ship_evals.harness import load_transcript

TRANSCRIPTS = Path(__file__).parent / "fixtures" / "transcripts"
SYSTEM = load_codex_system()


class CodexDecision:
    """One assistant turn in the Codex dialect — assert on the NEXT TOOL CALL."""

    def __init__(self, response):
        self.calls = codex_tool_calls(response)
        self.text = codex_output_text(response)

    def named(self, tool_name: str):
        return [c for c in self.calls if c.name == tool_name]

    def spawns(self, agent_type: str):
        return [c for c in self.named("spawn_agent")
                if c.input_parameters.get("agent_type") == agent_type]

    def diagnostics(self) -> str:
        return f"[tools={[(c.name, c.input_parameters.get('agent_type') or c.input_parameters.get('target')) for c in self.calls]} text={self.text[:300]!r}]"


@pytest.fixture
def run_codex_decision():
    def _run(transcript_name: str) -> CodexDecision:
        messages = load_transcript(TRANSCRIPTS / f"{transcript_name}.json")
        return CodexDecision(call_codex_model(SYSTEM, messages, CODEX_ORCHESTRATOR_TOOLS))
    return _run
```

- [ ] **Step 9: Write the five fixture transcripts (OpenAI chat format)**

`evals/orchestrator_codex/fixtures/transcripts/roles_installed_invoke.json`:

```json
{
  "description": "Codex: checklist already created, preflight --check passed. Next move must be spawn_agent for the planner with agent_type ship-task-planner-agent and fork_turns none, with no model question.",
  "messages": [
    {"role": "user", "content": "/ship LEX-1398"},
    {"role": "assistant", "content": "Codex runtime detected (spawn_agent/followup_task in my tool list). Setting up the stage checklist and running the preflight role check.",
     "tool_calls": [
       {"id": "call_0", "type": "function", "function": {"name": "update_plan", "arguments": "{\"plan\": [{\"step\": \"Preflight roles\", \"status\": \"in_progress\"}, {\"step\": \"Plan (GATE 2)\", \"status\": \"pending\"}, {\"step\": \"Implement\", \"status\": \"pending\"}, {\"step\": \"QA-plan authoring (background)\", \"status\": \"pending\"}, {\"step\": \"Review + fix loop\", \"status\": \"pending\"}, {\"step\": \"Commit / Push / Draft PR\", \"status\": \"pending\"}, {\"step\": \"QA (GATE 3)\", \"status\": \"pending\"}, {\"step\": \"Final report\", \"status\": \"pending\"}, {\"step\": \"Insights retro\", \"status\": \"pending\"}]}"}},
       {"id": "call_1", "type": "function", "function": {"name": "shell", "arguments": "{\"command\": \"bash ~/.codex/plugins/cache/ship/ship/1.10.0/scripts/install-codex-agents.sh --check\"}"}}
     ]},
    {"role": "tool", "tool_call_id": "call_0", "content": "Plan updated"},
    {"role": "tool", "tool_call_id": "call_1", "content": "unchanged  ship-git-agent.toml\nunchanged  ship-implementator-agent.toml\nunchanged  ship-qa-agent.toml\nunchanged  ship-reviewer-agent.toml\nunchanged  ship-spec-agent.toml\nunchanged  ship-task-planner-agent.toml\n(exit 0)"}
  ]
}
```

(The checklist is created *in the fixture* so the model's next turn is not consumed by `update_plan` bookkeeping — the same single-turn trap the Claude tier documents in `orchestrator/conftest.py`. If a case still proves flaky on the next-turn assertion, port the Claude tier's `Window` helper rather than loosening the assertion.)

`evals/orchestrator_codex/fixtures/transcripts/roles_missing_invoke.json`:

```json
{
  "description": "Codex: checklist created, preflight --check failed. Orchestrator must not spawn anything; it names the installer command for the user and stops.",
  "messages": [
    {"role": "user", "content": "/ship LEX-1398"},
    {"role": "assistant", "content": "Codex runtime detected. Setting up the stage checklist and running the preflight role check.",
     "tool_calls": [
       {"id": "call_0", "type": "function", "function": {"name": "update_plan", "arguments": "{\"plan\": [{\"step\": \"Preflight roles\", \"status\": \"in_progress\"}, {\"step\": \"Plan (GATE 2)\", \"status\": \"pending\"}, {\"step\": \"Implement\", \"status\": \"pending\"}, {\"step\": \"QA-plan authoring (background)\", \"status\": \"pending\"}, {\"step\": \"Review + fix loop\", \"status\": \"pending\"}, {\"step\": \"Commit / Push / Draft PR\", \"status\": \"pending\"}, {\"step\": \"QA (GATE 3)\", \"status\": \"pending\"}, {\"step\": \"Final report\", \"status\": \"pending\"}, {\"step\": \"Insights retro\", \"status\": \"pending\"}]}"}},
       {"id": "call_1", "type": "function", "function": {"name": "shell", "arguments": "{\"command\": \"bash ~/.codex/plugins/cache/ship/ship/1.10.0/scripts/install-codex-agents.sh --check\"}"}}
     ]},
    {"role": "tool", "tool_call_id": "call_0", "content": "Plan updated"},
    {"role": "tool", "tool_call_id": "call_1", "content": "missing/stale  ship-git-agent.toml\nmissing/stale  ship-implementator-agent.toml\nmissing/stale  ship-qa-agent.toml\nmissing/stale  ship-reviewer-agent.toml\nmissing/stale  ship-spec-agent.toml\nmissing/stale  ship-task-planner-agent.toml\nrun: bash /Users/eugene.g/.codex/plugins/cache/ship/ship/1.10.0/scripts/install-codex-agents.sh\n(exit 1)"}
  ]
}
```

`evals/orchestrator_codex/fixtures/transcripts/impl_verified.json`:

```json
{
  "description": "Codex: implementator reported its first verified tree. Next move must include spawn_agent ship-qa-agent (deferred-PR brief) - and never a followup to the implementator.",
  "messages": [
    {"role": "user", "content": "/ship LEX-1398"},
    {"role": "assistant", "content": "Codex runtime detected - running the preflight role check first.",
     "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "shell", "arguments": "{\"command\": \"bash ~/.codex/plugins/cache/ship/ship/1.10.0/scripts/install-codex-agents.sh --check\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "unchanged  ship-git-agent.toml\nunchanged  ship-implementator-agent.toml\nunchanged  ship-qa-agent.toml\nunchanged  ship-reviewer-agent.toml\nunchanged  ship-spec-agent.toml\nunchanged  ship-task-planner-agent.toml\n(exit 0)"},
    {"role": "assistant", "content": "Roles installed. Codex run - models are fixed per role: planner/spec gpt-5.6 xhigh, reviewer gpt-5.6 xhigh, implementator gpt-5.6 high, QA gpt-5.6 medium, git gpt-5.6-terra. Dispatching the planner.",
     "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-planner\", \"agent_type\": \"ship-task-planner-agent\", \"fork_turns\": \"none\", \"message\": \"Plan the implementation for Jira ticket LEX-1398. Read the ticket with the Jira CLI, study the codebase, list the skills the implementer should use, and return the plan for human review.\"}"}}]},
    {"role": "tool", "tool_call_id": "call_2", "content": "{\"task_name\": \"/root/LEX-1398-planner\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_3", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_3", "content": "LEX-1398-planner completed: PLAN for LEX-1398 - Add reschedule action to lesson card. 1. Extend BookingService.reschedule() guarded by the 12h rule. 2. RescheduleRequest model + tutor confirmation flow. 3. Frontend: Reschedule button on LessonCard + slot picker modal. 4. Tests: service unit, API, component. Skills: frontend:design-system, superpowers:test-driven-development. Awaiting review."},
    {"role": "assistant", "content": "GATE 2 - the planner's plan, verbatim:\n\nPLAN for LEX-1398 - Add reschedule action to lesson card. 1. Extend BookingService.reschedule() guarded by the 12h rule. 2. RescheduleRequest model + tutor confirmation flow. 3. Frontend: Reschedule button on LessonCard + slot picker modal. 4. Tests: service unit, API, component. Skills: frontend:design-system, superpowers:test-driven-development.\n\nApprove, or tell me what to change?"},
    {"role": "user", "content": "Approved - proceed."},
    {"role": "assistant", "content": "Plan approved. Dispatching the implementator into an isolated worktree.",
     "tool_calls": [{"id": "call_4", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-implementator\", \"agent_type\": \"ship-implementator-agent\", \"fork_turns\": \"none\", \"message\": \"Ticket: LEX-1398. Approved plan: 1. Extend BookingService.reschedule() guarded by the 12h rule. 2. RescheduleRequest model + tutor confirmation flow. 3. Frontend: Reschedule button on LessonCard + slot picker modal. 4. Tests: service unit, API, component. Work in an isolated worktree on branch LEX-1398 with TDD, verify tests then lint, leave changes uncommitted, and report the worktree path, branch, changed files, and test/lint evidence.\"}"}}]},
    {"role": "tool", "tool_call_id": "call_4", "content": "{\"task_name\": \"/root/LEX-1398-implementator\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_5", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_5", "content": "LEX-1398-implementator completed: Implementation complete and verified. Worktree: /tmp/worktrees/LEX-1398, branch: LEX-1398. Changed: lessons/services/booking.py, lessons/api.py, LessonCard.tsx (+3 tests). Tests: 218 passed. Lint: clean. Changes left uncommitted."}
  ]
}
```

`evals/orchestrator_codex/fixtures/transcripts/review_critical_round1.json`:

```json
{
  "description": "Codex: reviewer round 1 returned a Critical finding. Next move must be followup_task to LEX-1398-implementator - never a fresh implementator spawn.",
  "messages": [
    {"role": "user", "content": "/ship LEX-1398"},
    {"role": "assistant", "content": "Codex runtime detected - running the preflight role check first.",
     "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "shell", "arguments": "{\"command\": \"bash ~/.codex/plugins/cache/ship/ship/1.10.0/scripts/install-codex-agents.sh --check\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "unchanged  ship-git-agent.toml\nunchanged  ship-implementator-agent.toml\nunchanged  ship-qa-agent.toml\nunchanged  ship-reviewer-agent.toml\nunchanged  ship-spec-agent.toml\nunchanged  ship-task-planner-agent.toml\n(exit 0)"},
    {"role": "assistant", "content": "Roles installed. Codex run - models are fixed per role. Dispatching the planner.",
     "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-planner\", \"agent_type\": \"ship-task-planner-agent\", \"fork_turns\": \"none\", \"message\": \"Plan the implementation for Jira ticket LEX-1398 and return the plan for human review.\"}"}}]},
    {"role": "tool", "tool_call_id": "call_2", "content": "{\"task_name\": \"/root/LEX-1398-planner\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_3", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_3", "content": "LEX-1398-planner completed: PLAN for LEX-1398 - Add reschedule action to lesson card. 1. BookingService.reschedule() with 12h rule. 2. RescheduleRequest model. 3. LessonCard Reschedule button + modal. 4. Tests. Awaiting review."},
    {"role": "assistant", "content": "GATE 2 - plan verbatim: PLAN for LEX-1398 - Add reschedule action to lesson card. 1. BookingService.reschedule() with 12h rule. 2. RescheduleRequest model. 3. LessonCard Reschedule button + modal. 4. Tests. Approve?"},
    {"role": "user", "content": "Approved."},
    {"role": "assistant", "content": "Dispatching the implementator.",
     "tool_calls": [{"id": "call_4", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-implementator\", \"agent_type\": \"ship-implementator-agent\", \"fork_turns\": \"none\", \"message\": \"Ticket LEX-1398. Approved plan: 1. BookingService.reschedule() with 12h rule. 2. RescheduleRequest model. 3. LessonCard Reschedule button + modal. 4. Tests. Isolated worktree on branch LEX-1398, TDD, verify, report worktree path + branch, leave uncommitted.\"}"}}]},
    {"role": "tool", "tool_call_id": "call_4", "content": "{\"task_name\": \"/root/LEX-1398-implementator\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_5", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_5", "content": "LEX-1398-implementator completed: Verified. Worktree: /tmp/worktrees/LEX-1398, branch: LEX-1398. Changed: lessons/services/booking.py, billing/refunds.py, billing/api.py, LessonCard.tsx. Tests: 218 passed. Lint clean."},
    {"role": "assistant", "content": "First verified tree - launching the QA plan authoring in the background and the reviewer.",
     "tool_calls": [
       {"id": "call_6", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-qa\", \"agent_type\": \"ship-qa-agent\", \"fork_turns\": \"none\", \"message\": \"Author a Phase-A QA test plan for LEX-1398 (reschedule action on lesson card). Worktree: /tmp/worktrees/LEX-1398. The PR does not exist yet - you were launched in parallel with review; do not run gh pr view or assume a stage. Return the plan and wait; Phase B is authorized only after the human approves at GATE 3.\"}"}},
       {"id": "call_7", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-reviewer-r1\", \"agent_type\": \"ship-reviewer-agent\", \"fork_turns\": \"none\", \"message\": \"Review the uncommitted diff at worktree /tmp/worktrees/LEX-1398, branch LEX-1398, ticket LEX-1398, against the approved plan. Re-run static checks and return Critical/Important/Minor findings plus the verdict line.\"}"}}
     ]},
    {"role": "tool", "tool_call_id": "call_6", "content": "{\"task_name\": \"/root/LEX-1398-qa\"}"},
    {"role": "tool", "tool_call_id": "call_7", "content": "{\"task_name\": \"/root/LEX-1398-reviewer-r1\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_8", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_8", "content": "LEX-1398-reviewer-r1 completed: Findings - Critical: refund maths uses list_price and overpays discounted orders (billing/refunds.py:18). Important: endpoint swallows exceptions (billing/api.py:47). Minor: naming. Ready to commit? [No]"}
  ]
}
```

`evals/orchestrator_codex/fixtures/transcripts/review_clean.json`:

```json
{
  "description": "Codex: reviewer verdict Yes. Next move must be spawn_agent ship-git-agent with the worktree, 'draft', and the no-co-author rule in the brief.",
  "messages": [
    {"role": "user", "content": "/ship LEX-1398"},
    {"role": "assistant", "content": "Codex runtime detected - running the preflight role check first.",
     "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "shell", "arguments": "{\"command\": \"bash ~/.codex/plugins/cache/ship/ship/1.10.0/scripts/install-codex-agents.sh --check\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "unchanged  ship-git-agent.toml\nunchanged  ship-implementator-agent.toml\nunchanged  ship-qa-agent.toml\nunchanged  ship-reviewer-agent.toml\nunchanged  ship-spec-agent.toml\nunchanged  ship-task-planner-agent.toml\n(exit 0)"},
    {"role": "assistant", "content": "Roles installed. Codex run - models are fixed per role. Dispatching the planner.",
     "tool_calls": [{"id": "call_2", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-planner\", \"agent_type\": \"ship-task-planner-agent\", \"fork_turns\": \"none\", \"message\": \"Plan the implementation for Jira ticket LEX-1398 and return the plan for human review.\"}"}}]},
    {"role": "tool", "tool_call_id": "call_2", "content": "{\"task_name\": \"/root/LEX-1398-planner\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_3", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_3", "content": "LEX-1398-planner completed: PLAN for LEX-1398 - Add reschedule action to lesson card. 1. BookingService.reschedule() with 12h rule. 2. RescheduleRequest model. 3. LessonCard Reschedule button + modal. 4. Tests. Awaiting review."},
    {"role": "assistant", "content": "GATE 2 - plan verbatim: PLAN for LEX-1398 - Add reschedule action to lesson card. 1. BookingService.reschedule() with 12h rule. 2. RescheduleRequest model. 3. LessonCard Reschedule button + modal. 4. Tests. Approve?"},
    {"role": "user", "content": "Approved."},
    {"role": "assistant", "content": "Dispatching the implementator.",
     "tool_calls": [{"id": "call_4", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-implementator\", \"agent_type\": \"ship-implementator-agent\", \"fork_turns\": \"none\", \"message\": \"Ticket LEX-1398. Approved plan: 1. BookingService.reschedule() with 12h rule. 2. RescheduleRequest model. 3. LessonCard Reschedule button + modal. 4. Tests. Isolated worktree on branch LEX-1398, TDD, verify, report worktree path + branch, leave uncommitted.\"}"}}]},
    {"role": "tool", "tool_call_id": "call_4", "content": "{\"task_name\": \"/root/LEX-1398-implementator\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_5", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_5", "content": "LEX-1398-implementator completed: Verified. Worktree: /tmp/worktrees/LEX-1398, branch: LEX-1398. Changed: lessons/services/booking.py, lessons/api.py, LessonCard.tsx (+3 tests). Tests: 218 passed. Lint clean."},
    {"role": "assistant", "content": "First verified tree - launching the QA plan authoring in the background and the reviewer.",
     "tool_calls": [
       {"id": "call_6", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-qa\", \"agent_type\": \"ship-qa-agent\", \"fork_turns\": \"none\", \"message\": \"Author a Phase-A QA test plan for LEX-1398 (reschedule action on lesson card). Worktree: /tmp/worktrees/LEX-1398. The PR does not exist yet - do not run gh pr view or assume a stage. Return the plan and wait for GATE 3 approval before Phase B.\"}"}},
       {"id": "call_7", "type": "function", "function": {"name": "spawn_agent", "arguments": "{\"task_name\": \"LEX-1398-reviewer-r1\", \"agent_type\": \"ship-reviewer-agent\", \"fork_turns\": \"none\", \"message\": \"Review the uncommitted diff at worktree /tmp/worktrees/LEX-1398, branch LEX-1398, ticket LEX-1398, against the approved plan. Re-run static checks and return Critical/Important/Minor findings plus the verdict line.\"}"}}
     ]},
    {"role": "tool", "tool_call_id": "call_6", "content": "{\"task_name\": \"/root/LEX-1398-qa\"}"},
    {"role": "tool", "tool_call_id": "call_7", "content": "{\"task_name\": \"/root/LEX-1398-reviewer-r1\"}"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"id": "call_8", "type": "function", "function": {"name": "wait_agent", "arguments": "{\"timeout_ms\": 300000}"}}]},
    {"role": "tool", "tool_call_id": "call_8", "content": "LEX-1398-reviewer-r1 completed: Findings - Minor: prefer a named constant for the 12h window (lessons/services/booking.py:41). No Critical or Important findings. Ready to commit? [Yes]"}
  ]
}
```

- [ ] **Step 10: Write the Codex decision tests**

`evals/orchestrator_codex/test_codex_dispatch.py`:

```python
import pytest


@pytest.mark.codex
def test_roles_installed_first_dispatch_is_planner_role_with_clean_fork_and_no_model_question(run_codex_decision):
    d = run_codex_decision("roles_installed_invoke")
    planner = d.spawns("ship-task-planner-agent")
    assert planner, "first dispatch must be spawn_agent with agent_type ship-task-planner-agent " + d.diagnostics()
    assert planner[0].input_parameters.get("fork_turns") == "none"
    assert "LEX-1398" in planner[0].input_parameters.get("task_name", "")
    assert "which model" not in d.text.lower() and "planner model" not in d.text.lower(), (
        "Stage 0 model questions are skipped on Codex " + d.diagnostics())
    assert not d.named("shell"), "preflight already passed - no second check"


@pytest.mark.codex
def test_roles_missing_stops_and_names_the_installer(run_codex_decision):
    d = run_codex_decision("roles_missing_invoke")
    assert not d.named("spawn_agent"), "never spawn with roles missing " + d.diagnostics()
    assert "install-codex-agents.sh" in d.text, d.diagnostics()


@pytest.mark.codex
def test_first_verified_tree_spawns_qa_role_with_deferred_pr_brief(run_codex_decision):
    d = run_codex_decision("impl_verified")
    qa = d.spawns("ship-qa-agent")
    assert qa, "qa-agent Phase A is launched after the first verified tree " + d.diagnostics()
    assert qa[0].input_parameters.get("fork_turns") == "none"
    brief = qa[0].input_parameters["message"].lower()
    assert "pr" in brief and any(k in brief for k in ("does not exist", "not exist", "no pr", "deferred", "not yet")), (
        "the deferred-PR instruction must be in the qa brief " + d.diagnostics())
    assert not [c for c in d.named("followup_task") if "implementator" in c.input_parameters.get("target", "")]


@pytest.mark.codex
def test_critical_finding_resumes_implementator_via_followup_task(run_codex_decision):
    d = run_codex_decision("review_critical_round1")
    follow = d.named("followup_task")
    assert follow and follow[0].input_parameters.get("target", "").endswith("LEX-1398-implementator"), (
        "fix rounds resume the SAME implementator task " + d.diagnostics())
    assert "refund" in follow[0].input_parameters["message"].lower()
    assert not d.spawns("ship-implementator-agent"), "never a fresh implementator per round"


@pytest.mark.codex
def test_clean_review_spawns_git_role_with_worktree_draft_and_no_coauthor(run_codex_decision):
    d = run_codex_decision("review_clean")
    git = d.spawns("ship-git-agent")
    assert git, "clean verdict exits the loop into Stage 5's git role " + d.diagnostics()
    brief = git[0].input_parameters["message"].lower()
    assert "/tmp/worktrees/lex-1398" in brief and "draft" in brief and "co-author" in brief
    assert git[0].input_parameters.get("fork_turns") == "none"
```

- [ ] **Step 11: Run the tier (needs `OPENAI_API_KEY`)**

```bash
cd evals && uv run pytest orchestrator_codex -m codex -v
```
Expected: 5 passed. If a case fails, the finding is about `codex-dispatch.md` (or a fixture) — sharpen the reference text, never the assertion. Also confirm the Claude tiers still collect the same count: `uv run pytest --collect-only -q orchestrator agents | tail -1` must equal the baseline's collected count.

- [ ] **Step 12: Add the CI job**

Append to `.github/workflows/ship-evals.yml` under `jobs:` (after `evals-pr`):

```yaml
  evals-codex:
    # Blocking check for the Codex dispatch dialect only. Separate job so a failure here is
    # visibly Codex-only and never masks the Claude-tier result above.
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: evals
    steps:
      - uses: actions/checkout@v4
      - name: Require OpenAI key
        run: |
          if [ -z "$OPENAI_API_KEY" ]; then
            echo "::error::OPENAI_API_KEY missing - Codex eval job cannot run." >&2
            exit 1
          fi
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - name: Codex role files match the agent definitions
        run: python3 ../plugins/ship/scripts/sync_codex_agents.py --check
      - name: Codex decision-point evals (blocking)
        run: uv run pytest orchestrator_codex -m codex -v
```

- [ ] **Step 13: Run the unit tier once more and commit**

```bash
cd evals && uv run pytest tests -v && cd ..
git add evals/src/ship_evals/codex_tools.py evals/src/ship_evals/codex_harness.py evals/orchestrator_codex evals/tests/test_codex_tools.py evals/pyproject.toml evals/uv.lock evals/conftest.py .github/workflows/ship-evals.yml
git commit -m "test(evals): Codex-dialect decision-point tier + CI job with role drift check"
```

---

### Task 5: Docs, changelog, and the package version bump

**Files:**
- Modify: `README.md` (Codex install section, versioning paragraph)
- Modify: `evals/README.md` (tier table, run command, adding-a-case note)
- Modify: `plugins/ship/agents/CHANGELOG.md` (two entries at the top of the log)
- Modify: the six manifests (version `1.9.0` → `1.10.0`)
- Test: `evals/tests/test_manifest_versions.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: user-facing docs; the version invariant guarded by the new test.

- [ ] **Step 1: Write the failing version test**

`evals/tests/test_manifest_versions.py`:

```python
import json

from ship_evals.config import REPO_ROOT

MANIFESTS = [
    REPO_ROOT / "plugins" / "ship" / ".claude-plugin" / "plugin.json",
    REPO_ROOT / "plugins" / "ship" / ".cursor-plugin" / "plugin.json",
    REPO_ROOT / "plugins" / "ship" / ".codex-plugin" / "plugin.json",
    REPO_ROOT / ".claude-plugin" / "marketplace.json",
    REPO_ROOT / ".cursor-plugin" / "marketplace.json",
    REPO_ROOT / ".agents" / "plugins" / "marketplace.json",
]


def _versions(data):
    found = set()
    if "version" in data:
        found.add(data["version"])
    if "version" in data.get("metadata", {}):
        found.add(data["metadata"]["version"])
    for plugin in data.get("plugins", []):
        if "version" in plugin:
            found.add(plugin["version"])
    return found


def test_every_manifest_carries_the_same_package_version():
    versions = set()
    for path in MANIFESTS:
        found = _versions(json.loads(path.read_text()))
        assert found, f"{path} declares no version"
        versions |= found
    assert versions == {"1.10.0"}, versions
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd evals && uv run pytest tests/test_manifest_versions.py -v
```
Expected: FAIL with `{'1.9.0'} != {'1.10.0'}`.

- [ ] **Step 3: Bump the six manifests**

```bash
git ls-files | grep -E 'plugin\.json$|marketplace\.json$' | xargs sed -i '' 's/"1\.9\.0"/"1.10.0"/g'
git diff --stat
```
Expected: exactly 6 files changed; `grep -rn '"1.9.0"' $(git ls-files | grep -E 'plugin\.json$|marketplace\.json$')` prints nothing.

- [ ] **Step 4: Run the version test to verify it passes**

```bash
cd evals && uv run pytest tests/test_manifest_versions.py -v
```
Expected: 1 passed.

- [ ] **Step 5: README — replace the Codex install section**

In `README.md`, replace the two lines under `### Codex` (`Clone this repo, then in Codex: …`) with:

````markdown
### Codex
Add the marketplace and install **Ship** from `/plugins` as usual, then install the pipeline's
agent roles — Codex plugins cannot bundle them, so this is a one-time copy into `~/.codex/agents/`:

```
bash "$(ls -d ~/.codex/plugins/cache/ship/ship/*/ | sort -V | tail -1)scripts/install-codex-agents.sh"
```

Restart the Codex session, then invoke the skill with a ticket as in Claude Code. Differences on
Codex: there are no Stage 0 model questions (models are fixed per role in
`plugins/ship/codex-agents/*.toml` — planner and reviewer `gpt-5.6 xhigh`, implementator
`gpt-5.6 high`, QA `gpt-5.6 medium`, git ops `gpt-5.6-terra`), the three gates are plain prose
questions, and the reviewer model-escalation step is a no-op. Re-run the install script after every
plugin update (`--check` tells you whether you need to). The full mapping lives in
[`plugins/ship/skills/ship/references/codex-dispatch.md`](plugins/ship/skills/ship/references/codex-dispatch.md);
the role files are generated from `agents/*.md` by `plugins/ship/scripts/sync_codex_agents.py`, and
CI fails if they drift.
````

Also in the **Versioning** section, change `Current: \`ship\` 4.1.0,` to `Current: \`ship\` 4.2.0,` (the agent versions listed there stay as they are).

- [ ] **Step 6: evals/README — document the new tier**

In `evals/README.md`, add a row to the Tiers table after the Decision-points row:

```markdown
| Codex decision-points | `orchestrator_codex/` | SKILL.md + `references/codex-dispatch.md` + fixture transcript, driven through the OpenAI API with Codex V2 tool schemas → assert the next tool call | blocking on PRs (own job) |
```

Add to the **Run** block:

```bash
uv run pytest orchestrator_codex -m codex -v  # Codex dialect (needs OPENAI_API_KEY only)
```

Add to the env-knobs line: `EVAL_CODEX_MODEL` (Codex-tier generation, default `gpt-4.1`).

Add a bullet under **Adding a case**:

```markdown
- Codex tier: transcripts are OpenAI chat format (`assistant` turns carry `tool_calls`, replies are
  `role: tool`); the system prompt is `SKILL.md` + `references/codex-dispatch.md`. Assert on
  `spawn_agent`/`followup_task` shape (`agent_type`, `fork_turns`, `target`), never on model names.
```

- [ ] **Step 7: CHANGELOG — two entries above `## ship package — 1.9.0`**

Insert at the top of the log in `plugins/ship/agents/CHANGELOG.md` (right after the bullet list explaining MAJOR/MINOR/PATCH):

```markdown
## ship package — 1.10.0 (2026-09-03)
- **Codex support.** New `plugins/ship/codex-agents/` (six Codex custom-agent role TOMLs — five
  generated verbatim from `agents/*.md` by `scripts/sync_codex_agents.py`, plus a hand-written
  `ship-git-agent` for Stage 5), `scripts/install-codex-agents.sh` (copies them into
  `~/.codex/agents/`; `--check` for preflight/CI), and `skills/ship/references/codex-dispatch.md`.
  Codex plugins cannot bundle agent roles, hence the installer. Agent `.md` files are unchanged, so
  agent versions do not move. Package MINOR (1.9.0 → 1.10.0, all 6 manifest locations).

## ship — 4.2.0 (2026-09-03)
- **Runs on Codex (multi-agent V2).** `SKILL.md` gains one trailing "Platform adaptation — Codex"
  section: a runtime whose tool list has `spawn_agent`/`followup_task`/`wait_agent` reads
  `references/codex-dispatch.md`, which maps `Agent`→`spawn_agent {agent_type: ship-*, fork_turns:
  "none"}`, `SendMessage`→`followup_task` on the same `task_name`, gates→prose, `TodoWrite`→
  `update_plan`, the Haiku git agent→`ship-git-agent`, and adds a preflight role check. On Codex the
  Stage 0 model questions are skipped (models are baked per role) and the reviewer escalation to
  `claude-opus-5[1m]` is a no-op. A Claude Code runtime is told to ignore the section; no other
  text in `SKILL.md` changed, and the inter-stage contract is untouched — MINOR. Compatibility floors
  unchanged. New eval tier `evals/orchestrator_codex/` (5 cases, own CI job) covers the dialect.
```

- [ ] **Step 8: Unit tier green, then commit**

```bash
cd evals && uv run pytest tests -v && cd ..
git add README.md evals/README.md plugins/ship/agents/CHANGELOG.md evals/tests/test_manifest_versions.py $(git ls-files | grep -E 'plugin\.json$|marketplace\.json$')
git commit -m "docs: Codex install + dispatch docs, changelog, package 1.10.0"
```

---

### Task 6: Verification — prove Claude `/ship` is unchanged, smoke Codex, open the PR

**Files:**
- Create (gitignored): `.superpowers/codex-port/after-unit.txt`, `.superpowers/codex-port/after-evals.txt`

**Interfaces:**
- Consumes: Task 0's baseline files.

- [ ] **Step 1: The Claude-visible surface diff is exactly what the spec allows**

```bash
cd /Users/eugene.g/Documents/projects/ship
git diff --quiet main -- plugins/ship/agents && echo "agents: UNCHANGED" || { echo "agents CHANGED - stop"; git diff --stat main -- plugins/ship/agents; }
git diff --stat main -- plugins/ship/skills
git diff main -- plugins/ship/skills/ship/SKILL.md | grep -cE '^-[^-]'     # expect 1 (the version line)
```
Expected: `agents: UNCHANGED`; `skills` stat lists only `SKILL.md` (10+/1-) and the new `references/codex-dispatch.md`; the removed-line count is `1`.

- [ ] **Step 2: Re-run the Claude tiers and diff against the baseline**

```bash
cd evals
uv run pytest tests -v 2>&1 | tee ../.superpowers/codex-port/after-unit.txt | tail -3
uv run deepeval test run agents orchestrator -v 2>&1 | tee ../.superpowers/codex-port/after-evals.txt | tail -15
cd ..
grep -E "passed|failed" .superpowers/codex-port/baseline-evals.txt | tail -1
grep -E "passed|failed" .superpowers/codex-port/after-evals.txt | tail -1
```
Expected: the agent + orchestrator pass/fail counts are identical to Task 0's baseline (the unit count is higher — new unit tests only). Any Claude-tier case that flipped is a blocker: investigate before continuing (a flaky case must be re-run to confirm it is pre-existing flakiness, not a regression).

- [ ] **Step 3: Codex tier and drift check**

```bash
python3 plugins/ship/scripts/sync_codex_agents.py --check && echo "roles in sync"
cd evals && uv run pytest orchestrator_codex -m codex -v; cd ..
```
Expected: `roles in sync`; 5 passed.

- [ ] **Step 4: Live Codex smoke (manual, with the user)**

Ask the user to run, in a terminal:

```bash
bash /Users/eugene.g/Documents/projects/ship/plugins/ship/scripts/install-codex-agents.sh
ls ~/.codex/agents/ship-*.toml | wc -l    # expect 6
```

Then, in a fresh Codex session opened on a repo with a ticket to ship, invoke the `ship` skill with a ticket. Confirm, and record in the PR description: (a) the preflight `--check` ran and passed; (b) no model question was asked; (c) the planner was spawned as `ship-task-planner-agent` with `fork_turns: "none"` (visible in the Codex step view); (d) GATE 2 stopped in prose. Stopping after GATE 2 is sufficient for the smoke; the user may continue the run if they wish. If `spawn_agent` reports an unavailable model, edit `ROLES` in `sync_codex_agents.py`, re-run it, re-install, and re-test — then commit that change.

- [ ] **Step 5: Live Claude smoke (manual, with the user)**

Update the Claude plugin from this branch (`/plugin update ship` or reinstall from the local marketplace) and run `/ship <TICKET>` in Claude Code up to GATE 2. Confirm Stage 0 still asks both model questions via `AskUserQuestion` and the planner is dispatched with the `Agent` tool exactly as before.

- [ ] **Step 6: Push and open the draft PR**

```bash
git push -u origin ship-codex-port
gh pr create --draft --title "Run ship on Codex (ship 4.2.0, package 1.10.0)" --body "$(cat <<'EOF'
## Summary
- Codex multi-agent V2 support for `/ship`: generated role TOMLs (`plugins/ship/codex-agents/`), installer (`scripts/install-codex-agents.sh`), dispatch reference (`skills/ship/references/codex-dispatch.md`), and a trailing platform-adaptation note in `SKILL.md`.
- Claude Code `/ship` is unchanged: `plugins/ship/agents/*.md` untouched; `SKILL.md` differs only by the version line and the appended section (Claude is told to ignore it).
- New eval tier `evals/orchestrator_codex/` (5 Codex decision points) + `evals-codex` CI job with a role drift check.

## Proof the Claude path is unchanged
- `git diff main -- plugins/ship/agents` → empty.
- Agent + orchestrator eval counts before/after: <paste the two lines from Task 6 step 2>.
- Claude smoke to GATE 2: <result>.

## Codex smoke
<preflight / no model question / planner spawn / GATE 2 - from Task 6 step 4>

Spec: docs/superpowers/specs/2026-09-03-ship-codex-port-design.md
Plan: docs/superpowers/plans/2026-09-03-ship-codex-port.md
EOF
)"
```

Fill the three `<…>` placeholders in the PR body with the actual outputs before submitting.

---

## Self-review notes

- **Spec coverage:** hard constraint (Task 3 step 5, Task 6 steps 1–2, guard tests); generator + drift (Task 1); preamble, git role, installer (Task 2); dispatch reference + SKILL.md section + 4.2.0 (Task 3); Codex eval tier + CI job (Task 4); README/evals README/CHANGELOG/1.10.0 (Task 5); smoke + PR (Task 6). Out-of-scope items (`mcp_servers`, role variants, repo-scoped roles) intentionally have no task.
- **Type consistency:** `ROLES[agent]` keys are `model`/`effort`/`sandbox` in Task 1's script and tests; installer output words `installed`/`updated`/`unchanged`/`missing/stale` are shared by Task 2's tests, Task 3's reference, and Task 4's fixtures; `task_name` scheme `<TICKET>-<role>` is used identically in Task 3's reference and Task 4's fixtures/assertions; `CODEX_ORCHESTRATOR_TOOLS`, `load_codex_system`, `call_codex_model`, `codex_tool_calls`, `codex_output_text` match between Task 4's harness, conftest, and unit test.
- **Known judgment call:** the default `EVAL_CODEX_MODEL=gpt-4.1` is chosen because it is the one OpenAI model id this repo already relies on (the judge); if it proves too weak to follow the reference, raise it via the env var in CI rather than loosening assertions.
