import pytest
from ship_evals.codex_scenarios import AsyncScenario
from ship_evals.codex_harness import CodexSimResult


def test_dispatch_then_final_is_not_success():
    s = AsyncScenario()
    s.respond('spawn_agent', {'task_name': 'impl', 'agent_type': 'ship-implementator-agent'})
    with pytest.raises(AssertionError, match='premature'):
        s.assert_terminal(CodexSimResult(stop_reason='no_tool_calls'))


def test_resume_then_final_is_not_success():
    s = AsyncScenario()
    s.respond('spawn_agent', {'task_name': 'impl', 'agent_type': 'ship-implementator-agent'})
    s.respond('wait_agent', {})
    s.respond('wait_agent', {})
    s.respond('followup_task', {'target': '/root/impl', 'message': 'Finish verification'})
    with pytest.raises(AssertionError, match='premature'):
        s.assert_terminal(CodexSimResult(stop_reason='no_tool_calls'))


def test_timeout_and_partial_require_resume():
    s = AsyncScenario()
    s.respond('spawn_agent', {'task_name': 'impl', 'agent_type': 'ship-implementator-agent'})
    assert 'timeout' in s.respond('wait_agent', {}).content.lower()
    reply = s.respond('wait_agent', {})
    assert 'not review-ready' in reply.mailbox_messages[0]
    with pytest.raises(AssertionError):
        s.respond('spawn_agent', {'task_name': 'qa', 'agent_type': 'ship-qa-agent'})


def test_full_chain_and_gate():
    s = AsyncScenario()
    def spawn(name, role):
        s.respond('spawn_agent', {'task_name': name, 'agent_type': 'ship-' + role + '-agent'})
    spawn('impl', 'implementator')
    s.respond('wait_agent', {})
    s.respond('wait_agent', {})
    s.respond('followup_task', {'target': '/root/impl', 'message': 'Finish'})
    s.respond('wait_agent', {})
    spawn('qa', 'qa')
    spawn('review1', 'reviewer')
    s.respond('wait_agent', {})
    assert s.qa_ready and not s.review_clean
    s.respond('wait_agent', {})
    s.respond('followup_task', {'target': '/root/impl', 'message': 'Fix'})
    s.respond('wait_agent', {})
    spawn('review2', 'reviewer')
    s.respond('wait_agent', {})
    spawn('git', 'git')
    s.respond('wait_agent', {})
    s.assert_terminal(CodexSimResult(stop_reason='no_tool_calls'))
    with pytest.raises(AssertionError, match='exhausted'):
        s.assert_terminal(CodexSimResult())
    with pytest.raises(AssertionError):
        s.respond('followup_task', {'target': '/root/qa', 'message': 'Run QA'})


def test_unknown_shell_is_rejected():
    with pytest.raises(AssertionError):
        AsyncScenario().respond('shell', {'command': 'git push'})


def test_incomplete_gate_report_is_rejected():
    from ship_evals.codex_scenarios import assert_qa_gate_report
    with pytest.raises(AssertionError):
        assert_qa_gate_report('PR 123 ready | QA needs approval')


def test_complete_gate_report_passes_and_missing_stage_does_not():
    from ship_evals.codex_scenarios import assert_qa_gate_report
    report = '''Reschedule before cutoff succeeds. After cutoff is rejected.
Discounted refund uses paid amount.
https://github.com/example/repo/pull/123
Approve the QA plan?
| Stage | Status |
| Plan | complete |
| Implement | complete |
| QA authoring | complete |
| Review | complete |
| Commit | complete |
| QA | awaiting approval |
| Final | pending |
| Insights | pending |'''
    assert_qa_gate_report(report)
    with pytest.raises(AssertionError, match='missing stage row: insights'):
        assert_qa_gate_report(report.replace('| Insights | pending |', ''))
