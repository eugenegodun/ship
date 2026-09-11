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


def tooluse(name, input, id="tu_x", prose=None):
    block = SimpleNamespace(type="tool_use", id=id, name=name, input=input)
    block.model_dump = lambda: {"type": "tool_use", "id": id, "name": name, "input": input}
    blocks = [block]
    if prose is not None:
        blocks.insert(0, SimpleNamespace(type="text", text=prose))
    return SimpleNamespace(content=blocks)


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


def test_continue_transcript_resumes_and_captures_prose_beside_tool_calls(monkeypatch):
    # Stage-6 shape: the report arrives in the same turn as Stage-7 bookkeeping, then a
    # trailing text-only turn ends the run. Both texts must be captured.
    turns = [
        tooluse("Skill", {"skill": "engineering-insights", "args": "/p/INSIGHTS.md"},
                id="tu_5", prose="Ticket LEX-1 shipped: PR #42. Run /cost for totals."),
        text("Retro noted. Done."),
    ]
    monkeypatch.setattr(sim, "call_model", scripted_model(turns))

    prior = [
        {"role": "user", "content": "/ship LEX-1"},
        {"role": "assistant", "content": [{"type": "text", "text": "QA passed."}]},
        {"role": "user", "content": "thanks"},
    ]
    result = sim.continue_transcript(prior, respond=lambda name, inp: "ok", max_calls=4)

    assert [e.name for e in result.events] == ["Skill"]
    assert "Run /cost for totals." in result.texts[0], "prose beside a tool call is captured"
    assert result.texts[-1] == "Retro noted. Done."
    assert result.stop_reason == "user_replies_exhausted"


def test_observation_stops_at_unanswered_question_after_bookkeeping(monkeypatch):
    turns = [
        tooluse("TodoWrite", {"todos": []}, id="bookkeeping"),
        tooluse("AskUserQuestion", {"questions": [{"question": "What does gpt6 mean?"}]},
                id="question", prose="Please clarify gpt6."),
        tooluse("Agent", {"subagent_type": "task-planner-agent"}),
    ]
    monkeypatch.setattr(sim, "call_model", scripted_model(turns))
    replied = []

    def respond(name, inp):
        replied.append(name)
        return "ok"

    result = sim.continue_transcript(
        [{"role": "user", "content": "/ship LEX-1 gpt6"}], respond,
        stop_after_tools={"AskUserQuestion"},
    )
    assert [e.name for e in result.events] == ["TodoWrite", "AskUserQuestion"]
    assert replied == ["TodoWrite"], "never manufacture an answer to a clarification"
    assert result.texts == ["Please clarify gpt6."]
    assert result.stop_reason == "observed_action"


def test_observation_records_premature_dispatch_in_same_turn_as_question(monkeypatch):
    question = tooluse("AskUserQuestion", {"questions": []})
    dispatch = tooluse("Agent", {"subagent_type": "implementator-agent"})
    monkeypatch.setattr(sim, "call_model", scripted_model([
        SimpleNamespace(content=question.content + dispatch.content),
    ]))

    def respond(name, inp):
        raise AssertionError("observed tools must not be executed or answered")

    result = sim.continue_transcript(
        [{"role": "user", "content": "/ship LEX-1"}], respond,
        stop_after_tools={"AskUserQuestion"},
    )
    assert [e.name for e in result.events] == ["AskUserQuestion", "Agent"]


def test_explicit_question_answers_still_supported_outside_observation(monkeypatch):
    monkeypatch.setattr(sim, "call_model", scripted_model([
        tooluse("AskUserQuestion", {"questions": []}), text("Answer received."),
    ]))
    replied = []
    result = sim.continue_transcript(
        [{"role": "user", "content": "/ship LEX-1"}],
        respond=lambda name, inp: replied.append(name) or "approved",
    )
    assert replied == ["AskUserQuestion"]
    assert result.texts == ["Answer received."]
