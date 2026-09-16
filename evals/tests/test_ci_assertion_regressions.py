"""Exercise CI assertions against valid handoffs and unsafe counterexamples."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_test_module(relative):
    path = Path(__file__).parents[1] / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def completion():
    return load_test_module("orchestrator_codex/test_codex_implementator_completion.py")


REPORT = """Implementation is complete per the handoff; verification is incomplete due to an external prerequisite.
Remaining: integration verification.
Worktree: /worktrees/LEX-999
Integration setup failed because STAGE_API_TOKEN is not set (exit 2). No tests executed.
Focused tests: 7 passed. Lint: All checks passed.
"""


def test_missing_token_wording_from_ci_is_accepted(completion, monkeypatch):
    monkeypatch.setattr(completion, "_run_role", lambda *args: ([completion.INTEGRATION], REPORT))
    completion.test_missing_credentials_reports_evidenced_blocker("unused")


@pytest.mark.parametrize("report", [
    REPORT + "Integration tests passed.",
    REPORT.replace("STAGE_API_TOKEN", "some token"),
    "STAGE_API_TOKEN is not set in /worktrees/LEX-999. Everything is complete.",
])
def test_blocker_assertions_still_reject_invalid_handoffs(completion, monkeypatch, report):
    monkeypatch.setattr(completion, "_run_role", lambda *args: ([completion.INTEGRATION], report))
    with pytest.raises(AssertionError):
        completion.test_missing_credentials_reports_evidenced_blocker("unused")


@pytest.mark.parametrize("premature_dispatch", [False, True])
def test_startup_window_accepts_bookkeeping_but_rejects_dispatch(premature_dispatch):
    routing = load_test_module("orchestrator/test_routing.py")
    questions = [{
        "header": role, "question": f"Choose {role} model",
        "options": [{"label": model} for model in
                    ["claude-fable-5", "claude-opus-5[1m]", "claude-sonnet-5"]],
    } for role in ["planner", "reviewer"]]
    calls = [SimpleNamespace(name="TodoWrite", input_parameters={}),
             SimpleNamespace(name="AskUserQuestion", input_parameters={"questions": questions})]
    if premature_dispatch:
        calls.insert(1, SimpleNamespace(name="Agent", input_parameters={}))
    window = SimpleNamespace(calls=calls, named=lambda name: [c for c in calls if c.name == name])
    if premature_dispatch:
        with pytest.raises(AssertionError, match="no agent"):
            routing.test_plain_invoke_runs_stage0_before_any_dispatch(lambda name: window)
    else:
        routing.test_plain_invoke_runs_stage0_before_any_dispatch(lambda name: window)
