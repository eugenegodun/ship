from pathlib import Path

from ship_evals import config


def test_repo_anchors_point_at_the_plugin():
    assert (config.PLUGIN_DIR / "skills" / "ship" / "SKILL.md").is_file()
    assert (config.PLUGIN_DIR / "agents" / "qa-agent.md").is_file()


def test_model_defaults(monkeypatch):
    monkeypatch.delenv("EVAL_MODEL", raising=False)
    monkeypatch.delenv("EVAL_JUDGE_MODEL", raising=False)
    import importlib
    importlib.reload(config)
    assert config.EVAL_MODEL == "claude-sonnet-5"
    assert config.JUDGE_MODEL == "gpt-4.1"
