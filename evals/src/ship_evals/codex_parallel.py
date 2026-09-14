"""Observe the QA/reviewer fork without imposing an order on independent launches."""
import json

from .codex_harness import continue_codex_transcript

ROLES = {'ship-qa-agent', 'ship-reviewer-agent'}


def observe_parallel_launches(messages):
    agents = {}

    def respond(name, args):
        if name == 'update_plan':
            return 'Plan updated'
        if name == 'spawn_agent':
            role = args.get('agent_type')
            assert role in ROLES, f'unexpected launch: {args}'
            assert role not in agents, f'duplicate launch: {args}'
            identity = '/root/' + args['task_name']
            agents[role] = identity
            return json.dumps({'task_name': identity})
        assert name == 'list_agents', f'unexpected action: {name} {args}'
        return json.dumps({'agents': [
            {'agent_name': identity, 'agent_status': 'running'}
            for identity in agents.values()
        ]})

    return continue_codex_transcript(
        messages, respond, max_calls=6,
        stop_after_tools={'wait_agent', 'followup_task', 'send_message', 'shell'},
    )


def assert_parallel_launches(result):
    detail = repr(result)
    assert result.stop_reason == 'observed_action', detail
    seen = set()
    waited = False
    for event in result.events:
        if event.name == 'spawn_agent':
            assert not waited, 'launch after waiting: ' + detail
            role = event.input.get('agent_type')
            assert role in ROLES and role not in seen, detail
            assert event.input.get('fork_turns') == 'none', detail
            seen.add(role)
        elif event.name == 'wait_agent':
            assert seen == ROLES, 'wait before both launches: ' + detail
            waited = True
        else:
            assert event.name in {'update_plan', 'list_agents'}, detail
    assert waited, 'both launches must be followed by a wait: ' + detail
