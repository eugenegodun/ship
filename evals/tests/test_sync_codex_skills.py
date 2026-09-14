import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from ship_evals.config import PLUGIN_DIR

SCRIPT = PLUGIN_DIR / "scripts" / "sync_codex_skills.py"


@pytest.fixture(scope="module")
def sync():
    spec = importlib.util.spec_from_file_location("sync_codex_skills", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plugin(tmp_path):
    plugin = tmp_path / "plugin"
    shutil.copytree(PLUGIN_DIR / "skills", plugin / "skills")
    return plugin


def _files(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_codex_manifest_exposes_generated_skills():
    manifest = json.loads((PLUGIN_DIR / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["skills"] == "./codex-skills/"
    assert sorted(path.name for path in (PLUGIN_DIR / manifest["skills"]).iterdir()) == [
        "engineering-insights", "ship", "workflow-retro"]


def test_generated_ship_preserves_frontmatter_and_uses_only_codex_body(sync):
    output = sync.generate(PLUGIN_DIR)
    source = (PLUGIN_DIR / "skills" / "ship" / "SKILL.md").read_bytes()
    frontmatter = source.split(b"\n---\n", 1)[0] + b"\n---\n"
    reference = (PLUGIN_DIR / "skills" / "ship" / "references" / "codex-dispatch.md").read_bytes()
    assert output[Path("ship/SKILL.md")] == frontmatter + b"\n" + reference


def test_other_skills_and_every_resource_are_preserved(sync, tmp_path):
    plugin = _plugin(tmp_path)
    nested = plugin / "skills" / "workflow-retro" / "assets" / "binary.dat"
    nested.parent.mkdir()
    nested.write_bytes(b"\x00\xff\r\n")
    output = sync.generate(plugin)
    source = _files(plugin / "skills")
    assert output.keys() == source.keys()
    for path in source:
        if path != Path("ship/SKILL.md"):
            assert output[path] == source[path], path


def test_committed_codex_skills_are_in_sync(sync):
    assert sync.main(["--check"]) == 0


def test_check_detects_missing_changed_and_obsolete_files(sync, tmp_path):
    plugin = _plugin(tmp_path)
    assert sync.main(["--plugin-dir", str(plugin), "--check"]) == 1
    assert sync.main(["--plugin-dir", str(plugin)]) == 0
    generated = plugin / "codex-skills"
    assert _files(generated) == sync.generate(plugin)
    (generated / "workflow-retro" / "analyze_run.py").unlink()
    (generated / "ship" / "SKILL.md").write_text("stale body")
    obsolete = generated / "removed-skill" / "assets" / "old.txt"
    obsolete.parent.mkdir(parents=True)
    obsolete.write_text("old resource")
    assert sync.main(["--plugin-dir", str(plugin), "--check"]) == 1
    assert sync.main(["--plugin-dir", str(plugin)]) == 0
    assert not obsolete.exists()
    assert not (generated / "removed-skill").exists()
    assert sync.main(["--plugin-dir", str(plugin), "--check"]) == 0
    assert _files(generated) == sync.generate(plugin)


def test_reference_edit_invalidates_generated_ship(sync, tmp_path):
    plugin = _plugin(tmp_path)
    assert sync.main(["--plugin-dir", str(plugin)]) == 0
    reference = plugin / "skills" / "ship" / "references" / "codex-dispatch.md"
    reference.write_text(reference.read_text() + "\nUpdated Codex behavior.\n")
    assert sync.main(["--plugin-dir", str(plugin), "--check"]) == 1
    assert sync.main(["--plugin-dir", str(plugin)]) == 0
    assert sync.main(["--plugin-dir", str(plugin), "--check"]) == 0
