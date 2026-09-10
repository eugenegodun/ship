"""Live Codex continuation checks with no user nudges after dispatch."""
import json
import re

import pytest

from ship_evals.codex_harness import continue_codex_transcript
from ship_evals.codex_scenarios import AsyncScenario, assert_qa_gate_report, assert_approval_request


APPROVED = [
    {'role': 'user', 'content': '/ship LEX-1398. No video recording.'},
    {'role': 'assistant', 'content': 'Codex preflight passed; all roles unchanged. GATE 2 plan: add rescheduling and paid-amount refund checks in LessonCard.tsx and billing/refunds.py. Verify focused and integration tests, lint. Approve?'},
    {'role': 'user', 'content': 'Approved. Continue through review and draft PR to the QA plan gate.'},
]


@pytest.mark.codex
@pytest.mark.parametrize('status_request,partial_fix', [(False, False), (True, False), (False, True)])
def test_partial_implementation_and_review_fixes_reach_qa_gate(status_request, partial_fix):
    scenario = AsyncScenario(partial_fix=partial_fix)
    messages = list(APPROVED)
    if status_request:
        dispatch = {'task_name': 'impl', 'agent_type': 'ship-implementator-agent',
                    'fork_turns': 'none', 'message': 'Implement the approved LEX-1398 plan and verify.'}
        reply = scenario.respond('spawn_agent', dispatch)
        messages.extend([
            {'role': 'assistant', 'content': 'Implementing.', 'tool_calls': [
                {'id': 'running_impl', 'type': 'function', 'function': {
                    'name': 'spawn_agent', 'arguments': json.dumps(dispatch)}}]},
            {'role': 'tool', 'tool_call_id': 'running_impl', 'content': reply},
            {'role': 'user', 'content': 'What is the status?'},
        ])
    result = continue_codex_transcript(messages, scenario.respond, max_calls=45)
    scenario.assert_terminal(result)
    assert scenario.impl_round == 2 + int(partial_fix), result.events
    assert scenario.review_round == 2, result.events
    assert any(e.name == 'wait_agent' for e in result.events)
    assert_qa_gate_report(result.turns[-1].text)


@pytest.mark.codex
def test_credential_blocker_is_reported_without_retrying_or_claiming_background_work():
    scenario = AsyncScenario(blocked=True)
    result = continue_codex_transcript(APPROVED, scenario.respond)
    scenario.assert_terminal(result)
    final = result.turns[-1].text
    assert re.search(r'ECR|credentials', final, re.I), final
    assert '/tmp/worktrees/LEX-1398' in final, final
    assert not any(e.name == 'followup_task' for e in result.events)


@pytest.mark.codex
@pytest.mark.parametrize('stop', [
    'The user explicitly cancels the pipeline now. Stop; do not dispatch more work.',
    'The spec agent returned: SPEC: Rescheduling must preserve paid-amount refunds. GATE 1 approval has not been given. Surface it and ask.',
    'The planner returned: PLAN: Add rescheduling and test the paid-amount refund. GATE 2 approval has not been given. Surface it and ask.',
    'Review round 3 still has Important findings: discounted refunds overpay. No more review rounds are authorized. Worktree /tmp/worktrees/LEX-1398, branch LEX-1398. QA plan ready but not approved.',
])
def test_legitimate_stops_do_not_dispatch_or_resume(stop):
    def respond(name, args):
        assert name == 'update_plan', 'work dispatched across a stop: ' + name
        return 'Plan updated'
    result = continue_codex_transcript([{'role': 'user', 'content': stop}], respond, max_calls=5)
    assert result.stop_reason == 'no_tool_calls'
    assert result.turns[-1].text.strip()


@pytest.mark.codex
@pytest.mark.parametrize('report,required_brief', [
    ('All assigned tests and lint pass. Changed LessonCard.tsx and billing/refunds.py. '
     'I omitted the worktree and branch from this report.', r'worktree|branch'),
    ('Internal question: the approved plan specifies paid-amount refunds. Should I use paid '
     'amount or list price? Worktree /tmp/worktrees/LEX-1398, branch LEX-1398. '
     'Verification remains; no external blocker.', r'paid'),
])
def test_incomplete_handoff_and_internal_question_resume_same_child(report, required_brief):
    scenario = AsyncScenario(partial_report=report)
    result = continue_codex_transcript(APPROVED, scenario.respond, max_calls=45)
    scenario.assert_terminal(result)
    followups = [e for e in result.events if e.name == 'followup_task']
    assert re.search(required_brief, followups[0].input['message'], re.I)
    assert_qa_gate_report(result.turns[-1].text)


@pytest.mark.codex
@pytest.mark.parametrize('role,gate,report', [
    ('ship-spec-agent', 'GATE 1', 'SPEC: Refunds preserve the amount actually paid.'),
    ('ship-task-planner-agent', 'GATE 2', 'PLAN: Add rescheduling and test paid-amount refunds.'),
])
def test_planning_child_completion_is_awaited_before_gate(role, gate, report):
    messages = [
        {'role': 'user', 'content': '/ship LEX-1398' + (' --spec' if gate == 'GATE 1' else '')},
        {'role': 'assistant', 'content': 'Codex preflight passed, roles unchanged. Dispatching.',
         'tool_calls': [{'id': 'planning', 'type': 'function', 'function': {
             'name': 'spawn_agent', 'arguments': json.dumps({'task_name': 'planning',
                 'agent_type': role, 'fork_turns': 'none', 'message': 'Return material for approval.'})}}]},
        {'role': 'tool', 'tool_call_id': 'planning', 'content': '{"task_name":"/root/planning"}'},
    ]
    waits = []
    def respond(name, args):
        from ship_evals.codex_harness import CodexToolReply
        if name == 'update_plan':
            return 'Plan updated'
        assert name == 'wait_agent', 'unexpected action while waiting: ' + name
        waits.append(args)
        if len(waits) == 1:
            return CodexToolReply('Timeout; /root/planning still running')
        assert len(waits) == 2, 'should surface completed plan at gate'
        return CodexToolReply('Child completed', ['/root/planning: ' + report])
    result = continue_codex_transcript(messages, respond, max_calls=8)
    assert len(waits) == 2, 'parent finalized without awaiting child'
    assert result.stop_reason == 'no_tool_calls'
    assert report.split(': ', 1)[1] in result.turns[-1].text
    assert_approval_request(result.turns[-1].text)


@pytest.mark.codex
def test_repeated_partial_results_are_diagnosed_then_reported_as_a_stall():
    scenario = AsyncScenario(stalled=True)
    result = continue_codex_transcript(APPROVED, scenario.respond, max_calls=15)
    scenario.assert_terminal(result)
    followups = [e for e in result.events if e.name == 'followup_task']
    assert len(followups) == 2
    assert re.search(r'diagnos|block|failure|prerequisite|why', followups[-1].input['message'], re.I)
    assert 'partially consumed' in result.turns[-1].text.lower()
    assert re.search(r'decision|clarif|allocat', result.turns[-1].text, re.I)
