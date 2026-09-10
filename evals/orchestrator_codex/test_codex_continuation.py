"""Live Codex continuation checks with no user nudges after dispatch."""
import json
import re

import pytest

from ship_evals.codex_harness import continue_codex_transcript
from ship_evals.codex_scenarios import AsyncScenario, assert_qa_gate_report, assert_approval_request, assert_report_preserved


PREFLIGHT = [
    {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'preflight', 'type': 'function', 'function': {'name': 'shell',
         'arguments': json.dumps({'command': 'bash ~/.codex/plugins/cache/ship/ship/1.11.0/scripts/install-codex-agents.sh --check'})}}]},
    {'role': 'tool', 'tool_call_id': 'preflight', 'content': '\n'.join(
        'unchanged  ship-' + role + '-agent.toml' for role in
        ['git', 'implementator', 'qa', 'reviewer', 'spec', 'task-planner']) + '\n(exit 0)'},
]

SPEC_REPORT = """SPEC: LEX-1398 — lesson rescheduling and paid-amount refunds
Source: Jira LEX-1398 and the supplied lesson-card/refund requirements. The current lesson card
has no reschedule action, and discounted refunds must preserve the amount actually paid.
Scope: let students reschedule an eligible booked lesson and preserve paid-amount refund behavior.
User story: As a student, I can move a booked lesson before the cutoff without losing the money
actually paid for it.
Acceptance criteria:
1. When a student reschedules more than 12 hours before the lesson, the system saves the new time
   and shows success feedback on the lesson card.
2. When a student attempts rescheduling at or after the 12-hour cutoff, the system rejects the
   request and preserves the original booking.
3. When a discounted lesson is refunded, the refund equals its recorded paid amount, not list price.
4. When rescheduling fails, the lesson card retains the original booking and shows error feedback.
Out of scope: changing pricing policy, translations, schema migrations, or QA execution before approval.
Existing authorization and booking ownership checks remain required. No unresolved product decisions
for these acceptance criteria. Ready for human spec review; no implementation has started."""

PLAN_REPORT = """PLAN: LEX-1398 — lesson rescheduling and paid-amount refunds
Repository: /tmp/repo. Jira LEX-1398 requires a lesson-card reschedule action with the existing
12-hour eligibility rule and refunds based on the recorded paid amount. Inspected LessonCard.tsx,
billing/refunds.py, their focused tests, and the V2 integration test configuration.
Scope and acceptance: an eligible lesson reschedules with success feedback; requests at or after
the cutoff preserve the original booking and show rejection; failed requests retain the booking
and show error feedback; discounted refunds use paid amount rather than list price.
Implementation steps:
1. Create one isolated worktree on branch LEX-1398 and read its applicable AGENTS.md instructions.
2. Extend the existing LessonCard.tsx action/modal using the shared design-system components and
   existing reschedule endpoint; preserve ownership checks, cutoff handling, and request feedback.
3. In billing/refunds.py, calculate eligible refunds from the existing recorded paid amount.
   Reuse the current refund path; no schema or pricing-policy changes are required.
4. Add regression cases in LessonCard.test.tsx for success, cutoff rejection, and failure recovery;
   extend billing/tests/test_refunds.py with discounted-payment coverage. Add V2 integration coverage
   in tests/integration/reschedule.test.ts for saved booking time and rejected requests.
Verification, in order: yarn test LessonCard.test.tsx --runInBand;
pytest billing/tests/test_refunds.py; yarn test tests/integration/reschedule.test.ts --runInBand;
yarn lint LessonCard.tsx LessonCard.test.tsx tests/integration/reschedule.test.ts;
ruff check billing/refunds.py billing/tests/test_refunds.py. Record actual command results and fix
failures before handing off the uncommitted tree, changed files, branch, and verification evidence.
Risks: cutoff boundary errors and discounted refunds accidentally using list price. The regression
cases above exercise both; reuse existing time and money helpers to preserve their semantics.
Skills: executing-plans, using-git-worktrees, test-driven-development, design-system,
react-best-practices, systematic-debugging when needed, and verification-before-completion.
Constraints: do not edit translation catalogs, commit, push, create a PR, or run QA in implementation.
Review and draft PR creation follow the verified handoff; QA execution requires its separate approval.
Ready for human plan review; no implementation has started."""

APPROVED = [
    {'role': 'user', 'content': '/ship LEX-1398. Repository /tmp/repo, current working directory /tmp/repo. No video recording.'},
    *PREFLIGHT,
    {'role': 'assistant', 'content': 'Codex preflight passed; all roles unchanged. GATE 2 plan:\n' + PLAN_REPORT + '\nApprove?'},
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
        if name == 'list_agents':
            # These stop fixtures have no running children. Inspecting that fact is not dispatch.
            return json.dumps({'agents': []})
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
    ('ship-spec-agent', 'GATE 1', SPEC_REPORT),
    ('ship-task-planner-agent', 'GATE 2', PLAN_REPORT),
], ids=['spec', 'plan'])
def test_planning_child_completion_is_awaited_before_gate(role, gate, report):
    messages = [
        {'role': 'user', 'content': '/ship LEX-1398' + (' --spec' if gate == 'GATE 1' else '') +
         '. Repository /tmp/repo, current working directory /tmp/repo. Add eligible lesson rescheduling '
         'with the existing 12-hour cutoff and preserve paid-amount refunds. No video recording.'},
        *PREFLIGHT,
        {'role': 'assistant', 'content': 'Codex preflight passed, roles unchanged. Dispatching.',
         'tool_calls': [{'id': 'planning', 'type': 'function', 'function': {
             'name': 'spawn_agent', 'arguments': json.dumps({'task_name': 'planning',
                 'agent_type': role, 'fork_turns': 'none', 'message': (
                     'Ticket LEX-1398. Repository /tmp/repo. User context: add a lesson-card reschedule '
                     'action with the existing 12-hour cutoff, success/error feedback, and refunds '
                     'based on the recorded paid amount rather than list price. Preserve booking '
                     'ownership checks. No pricing-policy, translation, or schema changes. '
                     + ('Read Jira and linked requirements; produce the WHAT/WHY spec with user '
                        'stories, falsifiable acceptance criteria, scope, and open decisions for '
                        'human review. Do not read the codebase or implement.' if gate == 'GATE 1' else
                        'Read Jira and inspect the repository; produce a grounded implementation '
                        'plan with affected files, acceptance coverage, required skills, ordered '
                        'verification commands, and risks for human review. No approved spec was '
                        'provided because this run is not in spec mode. Do not implement.')
                 )})}}]},
        {'role': 'tool', 'tool_call_id': 'planning', 'content': '{"task_name":"/root/planning"}'},
    ]
    waits = []
    def respond(name, args):
        from ship_evals.codex_harness import CodexToolReply
        if name == 'update_plan':
            return 'Plan updated'
        if name == 'list_agents':
            state = 'running' if len(waits) < 2 else {'completed': report}
            return json.dumps({'agents': [{'agent_name': '/root/planning', 'agent_status': state}]})
        if name == 'send_message':
            assert args['target'] == '/root/planning' and len(waits) < 2
            return 'Message queued; child remains running'
        assert name == 'wait_agent', 'unexpected action while waiting: ' + name
        waits.append(args)
        if len(waits) == 1:
            return CodexToolReply('Timeout; /root/planning still running')
        assert len(waits) == 2, 'should surface completed plan at gate'
        return CodexToolReply('Child completed', ['/root/planning: ' + report])
    result = continue_codex_transcript(messages, respond, max_calls=8)
    assert len(waits) == 2, 'parent finalized without awaiting child'
    assert result.stop_reason == 'no_tool_calls'
    assert_report_preserved(report.split(': ', 1)[1], result.turns[-1].text)
    assert_approval_request(result.turns[-1].text)


@pytest.mark.codex
def test_repeated_partial_results_are_diagnosed_then_reported_as_a_stall():
    scenario = AsyncScenario(stalled=True)
    result = continue_codex_transcript(APPROVED, scenario.respond, max_calls=15)
    scenario.assert_terminal(result)
    followups = [e for e in result.events if e.name == 'followup_task']
    assert len(followups) == 2
    assert re.search(r'diagnos|block|failure|prerequisite|why', followups[-1].input['message'], re.I)
    assert 'SHIP_INTEGRATION_CLIENT_CERT' in result.turns[-1].text
    assert '/tmp/worktrees/LEX-1398' in result.turns[-1].text
    assert re.search(r'provision|provid|configur|supply', result.turns[-1].text, re.I)
