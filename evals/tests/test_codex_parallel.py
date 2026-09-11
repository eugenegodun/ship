from unittest.mock import patch

import pytest

from ship_evals.codex_parallel import observe_parallel_launches, assert_parallel_launches
from test_codex_harness import fake_openai_response


def launch(role):
    return {'id': role, 'name': 'spawn_agent', 'arguments': {
        'agent_type': f'ship-{role}-agent', 'task_name': role,
        'fork_turns': 'none', 'message': 'Full brief',
    }}


def wait():
    return fake_openai_response('', [{'id': 'w', 'name': 'wait_agent', 'arguments': {}}])


@pytest.mark.parametrize('order', [('qa', 'reviewer'), ('reviewer', 'qa')])
@pytest.mark.parametrize('batched', [False, True])
def test_both_orders_and_batched_launches_are_observed(order, batched):
    calls = [launch(role) for role in order]
    responses = ([fake_openai_response('', calls)] if batched else
                 [fake_openai_response('', [call]) for call in calls])
    with patch('ship_evals.codex_harness.call_codex_model', side_effect=responses + [wait()]):
        result = observe_parallel_launches([])
    assert_parallel_launches(result)
    assert [e.input['agent_type'] for e in result.events if e.name == 'spawn_agent'] == [
        f'ship-{role}-agent' for role in order]


@pytest.mark.parametrize('ending', ['wait', 'final', 'duplicate', 'wrong_role', 'limit'])
def test_missing_or_invalid_launch_does_not_pass(ending):
    first = fake_openai_response('', [launch('reviewer')])
    endings = {
        'wait': [wait()],
        'final': [fake_openai_response('I will launch QA later')],
        'duplicate': [fake_openai_response('', [launch('reviewer')])],
        'wrong_role': [fake_openai_response('', [launch('git')])],
        'limit': [fake_openai_response('', [
            {'id': 'p', 'name': 'update_plan', 'arguments': {}}])] * 5,
    }
    with patch('ship_evals.codex_harness.call_codex_model', side_effect=[first] + endings[ending]):
        with pytest.raises(AssertionError):
            assert_parallel_launches(observe_parallel_launches([]))


def test_launch_in_same_response_after_early_wait_is_not_accepted():
    response = fake_openai_response('', [launch('reviewer'),
        {'id': 'w', 'name': 'wait_agent', 'arguments': {}}, launch('qa')])
    with patch('ship_evals.codex_harness.call_codex_model', return_value=response):
        with pytest.raises(AssertionError, match='wait before both launches'):
            assert_parallel_launches(observe_parallel_launches([]))
