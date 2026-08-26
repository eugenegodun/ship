import json
from pathlib import Path
from types import SimpleNamespace

from ship_evals.harness import load_transcript, output_text, tool_calls
from ship_evals.tools import ORCHESTRATOR_TOOLS


def fake_response():
    return SimpleNamespace(content=[
        SimpleNamespace(type="text", text="Dispatching the planner."),
        SimpleNamespace(type="tool_use", id="tu_1", name="Agent",
                        input={"subagent_type": "task-planner-agent", "prompt": "p",
                               "description": "plan"}),
    ])


def test_tool_calls_extracts_name_and_params():
    calls = tool_calls(fake_response())
    assert [c.name for c in calls] == ["Agent"]
    assert calls[0].input_parameters["subagent_type"] == "task-planner-agent"


def test_output_text_joins_text_blocks():
    assert output_text(fake_response()) == "Dispatching the planner."


def test_orchestrator_tool_names():
    names = {t["name"] for t in ORCHESTRATOR_TOOLS}
    assert names == {"Agent", "SendMessage", "AskUserQuestion", "Skill", "TodoWrite", "TaskOutput"}


def test_load_transcript(tmp_path: Path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"description": "d", "messages": [{"role": "user", "content": "hi"}]}))
    assert load_transcript(p) == [{"role": "user", "content": "hi"}]
