import os

import pytest


def pytest_collection_modifyitems(config, items):
    missing = [k for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") if not os.environ.get(k)]
    if not missing:
        return
    skip = pytest.mark.skip(reason=f"missing API keys: {', '.join(missing)}")
    for item in items:
        if "llm" in item.keywords or "e2e" in item.keywords:
            item.add_marker(skip)
