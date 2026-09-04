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
