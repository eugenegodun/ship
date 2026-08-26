import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = REPO_ROOT / "plugins" / "ship"

EVAL_MODEL = os.environ.get("EVAL_MODEL", "claude-sonnet-5")
JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "gpt-4.1")
MAX_TOKENS = int(os.environ.get("EVAL_MAX_TOKENS", "8192"))
