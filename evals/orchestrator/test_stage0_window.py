"""Offline regressions for Stage 0's strictly limited bookkeeping allowance."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from anthropic.types import TextBlock, ToolUseBlock
import pytest

from . import conftest


def response(*names):
    return SimpleNamespace(content=[
        ToolUseBlock(type="tool_use", id=f"tool_{i}", name=name, input={})
        for i, name in enumerate(names)
    ])


def test_bookkeeping_then_question_stops_at_unanswered_gate(monkeypatch):
    calls = []
    question = response("AskUserQuestion")
    responses = iter([response("TodoWrite"), question])

    def model(**kwargs):
        calls.append(deepcopy(kwargs))
        return next(responses)

    monkeypatch.setattr(conftest, "call_model", model)
    prior = [{"role": "user", "content": "/ship LEX-1"}]
    decision = conftest.observe_stage0_question(prior)

    assert decision.response is question
    assert len(calls) == 2
    assert calls[1]["messages"][-1] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tool_0", "content": "Todos updated"}
    ]}
    assert calls[1]["messages"][-2]["content"][0]["name"] == "TodoWrite"
    assert prior == [{"role": "user", "content": "/ship LEX-1"}]


@pytest.mark.parametrize("forbidden", ["Agent", "Bash", "Skill", "TaskOutput"])
@pytest.mark.parametrize("with_question", [False, True])
def test_bookkeeping_cannot_hide_execution(monkeypatch, forbidden, with_question):
    names = [forbidden, "AskUserQuestion"] if with_question else [forbidden]
    model = Mock(side_effect=[response("TodoWrite"), response(*names)])
    monkeypatch.setattr(conftest, "call_model", model)

    with pytest.raises(AssertionError, match="execution before Stage 0"):
        conftest.observe_stage0_question([])
    assert model.call_count == 2


def test_bookkeeping_exhaustion_fails_without_extra_call(monkeypatch):
    model = Mock(side_effect=[response("TodoWrite") for _ in range(3)])
    monkeypatch.setattr(conftest, "call_model", model)

    with pytest.raises(AssertionError, match="within 3 calls"):
        conftest.observe_stage0_question([])
    assert model.call_count == 3


@pytest.mark.parametrize("bookkeeping_first", [False, True])
def test_final_without_question_fails_without_nudge(monkeypatch, bookkeeping_first):
    final = SimpleNamespace(content=[TextBlock(type="text", text="Ready to proceed.")])
    turns = [response("TodoWrite"), final] if bookkeeping_first else [final]
    model = Mock(side_effect=turns)
    monkeypatch.setattr(conftest, "call_model", model)

    with pytest.raises(AssertionError, match="stopped without Stage-0 AskUserQuestion"):
        conftest.observe_stage0_question([])
    assert model.call_count == len(turns)
