import re

from .config import PLUGIN_DIR

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER.sub("", text, count=1).lstrip("\n")


def load_skill(name: str = "ship") -> str:
    return _strip_frontmatter((PLUGIN_DIR / "skills" / name / "SKILL.md").read_text())


def load_agent(name: str) -> str:
    return _strip_frontmatter((PLUGIN_DIR / "agents" / f"{name}.md").read_text())
