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


def test_question_stops_after_bookkeeping_without_reply_or_another_model_call(monkeypatch):
    question = tooluse('AskUserQuestion', {'question': 'Continue without --spec?'},
                       prose='The flag is unsupported.')
    monkeypatch.setattr(sim, 'call_model', scripted_model([
        tooluse('TodoWrite', {'todos': []}), question,
    ]))
    answered = []
    def respond(name, params):
        answered.append(name)
        return 'Todos updated'
    result = sim.continue_transcript([], respond, stop_on_tools={'AskUserQuestion'})
    assert answered == ['TodoWrite']
    assert [e.name for e in result.events] == ['TodoWrite', 'AskUserQuestion']
    assert result.texts == ['The flag is unsupported.']
    assert result.stop_reason == 'awaiting_tool_response'
    assert [m['role'] for m in result.messages] == ['assistant', 'user', 'assistant']
    assert result.messages[1]['content'][0]['content'] == 'Todos updated'
    assert result.messages[-1]['content'][-1]['input'] == question.content[-1].input


def test_question_does_not_hide_dispatch_in_same_response(monkeypatch):
    for names in [('AskUserQuestion', 'Agent'), ('Agent', 'AskUserQuestion')]:
        blocks = [tooluse(name, {'prompt': name}, id=name).content[0] for name in names]
        monkeypatch.setattr(sim, 'call_model', scripted_model([SimpleNamespace(content=blocks)]))
        def respond(name, params):
            raise AssertionError('No tool should execute across the question boundary')
        result = sim.continue_transcript([], respond, stop_on_tools={'AskUserQuestion'})
        assert [e.name for e in result.events] == list(names)
        assert any(e.name == 'Agent' for e in result.events)


def test_question_does_not_hide_earlier_dispatch(monkeypatch):
    monkeypatch.setattr(sim, 'call_model', scripted_model([
        tooluse('Agent', {'subagent_type': 'task-planner-agent'}),
        tooluse('AskUserQuestion', {'question': 'Proceed?'}),
    ]))
    result = sim.continue_transcript([], lambda name, params: 'Planner started',
                                     stop_on_tools={'AskUserQuestion'})
    assert [e.name for e in result.events] == ['Agent', 'AskUserQuestion']


def test_scripted_question_answer_still_reaches_next_turn(monkeypatch):
    calls = []
    def model(**kwargs):
        calls.append(list(kwargs['messages']))
        if len(calls) == 1:
            return tooluse('AskUserQuestion', {'question': 'Which model?'})
        assert kwargs['messages'][-1]['content'][0]['content'] == 'claude-sonnet-5'
        return text('Plan ready for approval.')
    monkeypatch.setattr(sim, 'call_model', model)
    result = sim.run_pipeline('/ship LEX-1', lambda name, params: 'claude-sonnet-5', [])
    assert len(calls) == 2
    assert result.texts == ['Plan ready for approval.']
