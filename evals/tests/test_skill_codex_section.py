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
