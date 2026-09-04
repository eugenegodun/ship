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
    assert first.stdout.count("installed  ") == 6
    second = run("--to", str(tmp_path))
    assert second.returncode == 0 and second.stdout.count("unchanged  ") == 6


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
