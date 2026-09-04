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
