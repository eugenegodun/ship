from types import SimpleNamespace

import ship_evals.simulator as sim


def scripted_model(turns):
    """Yields canned assistant responses; ignores its inputs."""
    it = iter(turns)

    def _call(system, messages, tools=None, model=None):
        return next(it)
    return _call


def text(t):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=t)])


def tooluse(name, input, id="tu_x"):
    block = SimpleNamespace(type="tool_use", id=id, name=name, input=input)
    block.model_dump = lambda: {"type": "tool_use", "id": id, "name": name, "input": input}
    return SimpleNamespace(content=[block])


def test_loop_records_events_feeds_replies_and_stops(monkeypatch):
    turns = [
        tooluse("Agent", {"subagent_type": "task-planner-agent", "prompt": "p",
                          "description": "d"}, id="tu_1"),
        text("Here is the plan. Approve?"),          # gate stop -> consumes a user reply
        tooluse("Agent", {"subagent_type": "implementator-agent", "prompt": "p2",
                          "description": "d2"}, id="tu_2"),
        text("Final report."),                        # replies exhausted -> run ends
    ]
    monkeypatch.setattr(sim, "call_model", scripted_model(turns))

    result = sim.run_pipeline(
        "/ship LEX-1", respond=lambda name, inp: "ok", user_replies=["approved"],
    )
    assert [e.name for e in result.events] == ["Agent", "Agent"]
    assert result.events[0].input["subagent_type"] == "task-planner-agent"
    assert result.texts == ["Here is the plan. Approve?", "Final report."]
    assert result.stop_reason == "user_replies_exhausted"
