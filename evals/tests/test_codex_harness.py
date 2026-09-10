"""Tests for codex_harness module."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ship_evals.codex_harness import continue_codex_transcript


def fake_openai_response(text: str, tool_calls: list = None):
    """Create a fake OpenAI response object matching the structure expected by codex_harness."""
    if tool_calls is None:
        tool_calls = []

    tool_call_objs = []
    for tool_call in tool_calls:
        tool_call_objs.append(SimpleNamespace(
            id=tool_call["id"],
            type="function",
            function=SimpleNamespace(
                name=tool_call["name"],
                arguments=json.dumps(tool_call["arguments"])
            )
        ))

    message = SimpleNamespace(
        content=text or None,
        tool_calls=tool_call_objs if tool_call_objs else None
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )


def test_continue_codex_transcript_captures_text_with_tool_calls():
    """Text emitted alongside tool calls should be captured in result.texts."""

    # Mock the call_codex_model to return a response with both text and tool calls
    responses = [
        # Turn 1: text alongside a tool call
        fake_openai_response(
            "Dispatching the tool.",
            [{"id": "tc_1", "name": "spawn_agent", "arguments": {"task_name": "t1", "message": "m1"}}]
        ),
        # Turn 2: no tool calls (stops)
        fake_openai_response("Done.")
    ]
    response_iter = iter(responses)

    def mock_call_codex_model(system, messages, tools):
        return next(response_iter)

    def mock_respond(tool_name, tool_input):
        return f"Response to {tool_name}"

    with patch("ship_evals.codex_harness.call_codex_model", side_effect=mock_call_codex_model):
        result = continue_codex_transcript(
            messages=[],
            respond=mock_respond,
            max_calls=10
        )

    # Verify that the text from the turn with tool calls was captured
    assert "Dispatching the tool." in result.texts
    assert "Done." in result.texts
    assert len(result.texts) == 2
    assert len(result.events) == 1
    assert result.events[0].name == "spawn_agent"
    assert result.stop_reason == "no_tool_calls"


def test_continue_codex_transcript_captures_empty_text_on_no_tool_calls():
    """Empty or whitespace-only text on a no-tool-calls turn should be captured (for consistency)."""

    responses = [
        # Turn 1: tool call with no text
        fake_openai_response(
            None,
            [{"id": "tc_1", "name": "spawn_agent", "arguments": {"task_name": "t1", "message": "m1"}}]
        ),
        # Turn 2: no tool calls, empty text
        fake_openai_response("")
    ]
    response_iter = iter(responses)

    def mock_call_codex_model(system, messages, tools):
        return next(response_iter)

    def mock_respond(tool_name, tool_input):
        return f"Response to {tool_name}"

    with patch("ship_evals.codex_harness.call_codex_model", side_effect=mock_call_codex_model):
        result = continue_codex_transcript(
            messages=[],
            respond=mock_respond,
            max_calls=10
        )

    # The empty text on the no-tool-calls turn should be captured
    assert "" in result.texts
    assert len(result.texts) == 1


def test_continue_codex_transcript_skips_empty_text_with_tool_calls():
    """Empty or whitespace-only text alongside tool calls should not be captured."""

    responses = [
        # Turn 1: tool call with only whitespace text
        fake_openai_response(
            "   ",
            [{"id": "tc_1", "name": "spawn_agent", "arguments": {"task_name": "t1", "message": "m1"}}]
        ),
        # Turn 2: no tool calls
        fake_openai_response("Final.")
    ]
    response_iter = iter(responses)

    def mock_call_codex_model(system, messages, tools):
        return next(response_iter)

    def mock_respond(tool_name, tool_input):
        return f"Response to {tool_name}"

    with patch("ship_evals.codex_harness.call_codex_model", side_effect=mock_call_codex_model):
        result = continue_codex_transcript(
            messages=[],
            respond=mock_respond,
            max_calls=10
        )

    # Whitespace-only text alongside tool calls should be skipped
    # Only the text from the final no-tool-calls turn should be captured
    assert result.texts == ["Final."]


def test_mailbox_delivery_follows_all_tool_replies():
    from ship_evals.codex_harness import CodexToolReply
    seen = []
    responses = iter([
        fake_openai_response('Waiting', [
            {'id': 'a', 'name': 'wait_agent', 'arguments': {}},
            {'id': 'b', 'name': 'list_agents', 'arguments': {}}]),
        fake_openai_response('Gate'),
    ])
    def call(system, messages, tools):
        seen.append(list(messages))
        return next(responses)
    with patch('ship_evals.codex_harness.call_codex_model', side_effect=call):
        result = continue_codex_transcript([], lambda name, args: CodexToolReply('activity', ['child result'])
                                           if name == 'wait_agent' else 'states')
    assert [m['role'] for m in seen[1]] == ['assistant', 'tool', 'tool', 'user']
    assert 'child result' in seen[1][-1]['content']
    assert result.turns[0].tools[0].name == 'wait_agent'
    assert result.turns[1].text == 'Gate'
    assert result.turns[1].tools == []


def test_runtime_prompt_is_the_codex_reference_without_claude_translation():
    from ship_evals.codex_harness import REFERENCE, load_codex_system
    assert load_codex_system() == REFERENCE.read_text()


def test_failure_trace_includes_full_output_and_pending_state(tmp_path, monkeypatch):
    import json
    from ship_evals.codex_scenarios import AsyncScenario
    monkeypatch.setenv('EVAL_CODEX_TRACE_DIR', str(tmp_path))
    scenario = AsyncScenario()
    with patch('ship_evals.codex_harness.call_codex_model', return_value=fake_openai_response('Still working')):
        result = continue_codex_transcript([], scenario.respond)
    trace = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert trace['result']['turns'][-1]['text'] == 'Still working'
    assert trace['state']['pr_ready'] is False
    assert result.stop_reason == 'no_tool_calls'


def test_token_exhaustion_is_not_reported_as_a_final_answer():
    response = fake_openai_response('partial output')
    response.choices[0].finish_reason = 'length'
    with patch('ship_evals.codex_harness.call_codex_model', return_value=response):
        result = continue_codex_transcript([], lambda name, args: 'ok')
    assert result.stop_reason == 'length'
    assert result.turns[-1].finish_reason == 'length'


def test_direct_api_call_logs_full_response_without_forcing_tools(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from ship_evals.codex_harness import call_codex_model
    monkeypatch.setenv('EVAL_CODEX_TRACE_DIR', str(tmp_path))
    monkeypatch.setattr("ship_evals.codex_harness.CODEX_API", "chat")
    client = MagicMock()
    client.chat.completions.create.return_value.model_dump.return_value = {
        'choices': [{'finish_reason': 'stop', 'message': {'content': 'Full response'}}]}
    with patch('ship_evals.codex_harness._get_client', return_value=client):
        call_codex_model('system', [{'role': 'user', 'content': 'brief'}], [])
    trace = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert trace['response']['choices'][0]['message']['content'] == 'Full response'
    assert trace['response']['choices'][0]['finish_reason'] == 'stop'
    assert 'tool_choice' not in trace['request']


@pytest.mark.parametrize('ending,expected', [('final', 'no_tool_calls'), ('action', 'observed_action'), ('bookkeeping', 'max_calls')])
def test_bounded_action_observation_never_nudges_a_final(ending, expected):
    bookkeeping = fake_openai_response('', [{'id': 'p', 'name': 'update_plan', 'arguments': {}}])
    final = fake_openai_response('I will dispatch later')
    action = fake_openai_response('', [
        {'id': 's', 'name': 'spawn_agent', 'arguments': {'agent_type': 'ship-git-agent'}},
        {'id': 'f', 'name': 'followup_task', 'arguments': {'target': 'unexpected'}}])
    responses = [bookkeeping, {'final': final, 'action': action, 'bookkeeping': bookkeeping}[ending]]
    replies = []
    with patch('ship_evals.codex_harness.call_codex_model', side_effect=responses) as call:
        result = continue_codex_transcript([], lambda name, args: replies.append(name) or 'ok',
                                          max_calls=2, stop_after_tools={'spawn_agent'})
    assert call.call_count == 2
    assert result.stop_reason == expected
    if ending == 'action':
        assert [e.name for e in result.events] == ['update_plan', 'spawn_agent', 'followup_task']
        assert replies == ['update_plan']
