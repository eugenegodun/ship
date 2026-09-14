from types import SimpleNamespace

from ship_evals.codex_responses import response_view, responses_input


class Item:
    def __init__(self, data):
        self.data = data
    def model_dump(self, **kwargs):
        return self.data


def test_replays_reasoning_and_calls_with_matching_output():
    output = [
        {'type': 'reasoning', 'id': 'rs1', 'summary': [], 'encrypted_content': 'opaque'},
        {'type': 'function_call', 'id': 'fc1', 'call_id': 'call1', 'name': 'wait_agent',
         'arguments': '{"timeout_ms":60000}', 'status': 'completed'},
    ]
    view = response_view(SimpleNamespace(output=[Item(x) for x in output], status='completed'))
    assert view.choices[0].message.tool_calls[0].id == 'call1'
    assert view.choices[0].finish_reason == 'tool_calls'
    messages = [{'role': 'assistant', '_responses_output': view.responses_output},
                {'role': 'tool', 'tool_call_id': 'call1', 'content': 'timeout'}]
    assert responses_input(messages) == output + [
        {'type': 'function_call_output', 'call_id': 'call1', 'output': 'timeout'}]


def test_legacy_fixture_calls_are_converted_without_synthetic_nudges():
    messages = [{'role': 'assistant', 'content': 'Starting', 'tool_calls': [
        {'id': 'a', 'type': 'function', 'function': {'name': 'shell', 'arguments': '{}'}}]},
        {'role': 'tool', 'tool_call_id': 'a', 'content': 'done'},
        {'role': 'user', 'content': 'Approved'}]
    assert responses_input(messages) == [
        {'role': 'assistant', 'content': 'Starting'},
        {'type': 'function_call', 'call_id': 'a', 'name': 'shell', 'arguments': '{}'},
        {'type': 'function_call_output', 'call_id': 'a', 'output': 'done'},
        {'role': 'user', 'content': 'Approved'}]


def test_response_limit_is_not_a_completed_turn():
    view = response_view(SimpleNamespace(output=[], status='incomplete',
                                        incomplete_details=SimpleNamespace(reason='max_output_tokens')))
    assert view.choices[0].finish_reason == 'length'


def test_native_request_preserves_reasoning_and_exposes_tools(monkeypatch):
    from unittest.mock import MagicMock
    from ship_evals.codex_harness import call_codex_model, codex_assistant_message
    from ship_evals.codex_tools import WAIT_AGENT
    monkeypatch.setattr('ship_evals.codex_harness.CODEX_API', 'responses')
    monkeypatch.setattr('ship_evals.codex_harness.CODEX_EFFORT', 'medium')
    output = [{'type': 'reasoning', 'id': 'rs1', 'summary': [], 'encrypted_content': 'opaque'},
              {'type': 'function_call', 'id': 'fc1', 'call_id': 'call1', 'name': 'wait_agent',
               'arguments': '{}', 'status': 'completed'}]
    response = SimpleNamespace(output=[Item(x) for x in output], status='completed',
                               model_dump=lambda **kwargs: {'output': output, 'status': 'completed'})
    client = MagicMock()
    client.responses.create.return_value = response
    monkeypatch.setattr('ship_evals.codex_harness._get_client', lambda: client)
    view = call_codex_model('workflow', [{'role': 'user', 'content': 'start'}], [WAIT_AGENT])
    request = client.responses.create.call_args.kwargs
    assert request['reasoning'] == {'effort': 'medium'}
    assert request['tools'][0]['name'] == 'wait_agent'
    assert 'tool_choice' not in request
    assert request['store'] is False
    assert request['include'] == ['reasoning.encrypted_content']
    assert responses_input([codex_assistant_message(view)]) == output
    client.chat.completions.create.assert_not_called()


def test_implementer_does_not_accept_truncated_handoff(monkeypatch):
    import importlib.util
    import pytest
    from ship_evals.config import REPO_ROOT
    path = REPO_ROOT / 'evals/orchestrator_codex/test_codex_implementator_completion.py'
    spec = importlib.util.spec_from_file_location('implementer_completion', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='length', message=SimpleNamespace(
        content='Verification complete', tool_calls=[]))])
    monkeypatch.setattr(module, 'call_codex_model', lambda *args: response)
    with pytest.raises(AssertionError, match='Incomplete implementer response: length'):
        module._run_role('instructions', [], {})
