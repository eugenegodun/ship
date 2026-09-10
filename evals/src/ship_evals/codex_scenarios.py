"""Stateful child-tool simulator; never wakes a parent after it finalizes."""
import json
import re

from .codex_harness import CodexToolReply


WORKTREE_REPORT = (
    'Worktree /tmp/worktrees/LEX-1398, branch LEX-1398; changes remain uncommitted. '
    'Changed LessonCard.tsx, billing/refunds.py, LessonCard.test.tsx, billing/tests/test_refunds.py, '
    'and tests/integration/reschedule.test.ts. Completed scope: lesson rescheduling before the '
    '12-hour cutoff, cutoff rejection, preserved booking on errors with success/error feedback, '
    'ownership checks, and refunds based on the amount actually paid. No plan deviations. '
)
FOCUSED_EVIDENCE = (
    'From that worktree, yarn test LessonCard.test.tsx --runInBand: 7 passed, exit 0; '
    'pytest billing/tests/test_refunds.py: 12 passed, exit 0. '
)
VERIFICATION_EVIDENCE = (
    FOCUSED_EVIDENCE + 'Then yarn test tests/integration/reschedule.test.ts --runInBand: 199 passed, exit 0, including V2 '
    'rescheduling and paid-amount refund integration coverage. Total 218 tests passed. '
    'After all tests completed, yarn lint LessonCard.tsx LessonCard.test.tsx tests/integration/reschedule.test.ts '
    'and ruff check billing/refunds.py billing/tests/test_refunds.py: both exit 0, lint clean. '
)


class AsyncScenario:
    def __init__(self, blocked=False, partial_report=None, partial_fix=False, stalled=False):
        self.agents = {}
        self.impl = None
        self.impl_round = 0
        self.review_round = 0
        self.verified = False
        self.qa_ready = False
        self.review_clean = False
        self.needs_fix = False
        self.pr_ready = False
        self.timed_out = False
        self.stalled = stalled
        self.partial_fix = partial_fix
        self.partial_report = partial_report
        self.blocked = blocked
        self.blocker_delivered = False

    def respond(self, name, args):
        if name == 'update_plan':
            return 'Plan updated'
        if name == 'list_agents':
            return json.dumps({'agents': [{'agent_name': key, 'agent_status': value['state']}
                                         for key, value in self.agents.items()]})
        if name == 'send_message':
            key = args['target']
            assert key in self.agents and self.agents[key]['state'] == 'running', 'message cannot resume an idle child'
            return 'Message queued; child remains running'
        if name == 'spawn_agent':
            key = '/root/' + args['task_name']
            role = args['agent_type']
            assert key not in self.agents, 'duplicate child'
            if role == 'ship-implementator-agent':
                assert self.impl is None, 'second implementer'
                self.impl = key
            elif role == 'ship-qa-agent':
                assert self.verified, 'QA before verified tree'
                assert not any(a['role'] == role for a in self.agents.values()), 'second QA agent'
            elif role == 'ship-reviewer-agent':
                assert self.verified and not self.needs_fix, 'review before verified fixes'
                assert not any(a['role'] == role and a['state'] == 'running'
                               for a in self.agents.values()), 'duplicate running review'
                self.review_round += 1
            elif role == 'ship-git-agent':
                assert self.review_clean, 'commit before clean review'
            else:
                raise AssertionError('unexpected role ' + role)
            self.agents[key] = {'role': role, 'state': 'running'}
            return json.dumps({'task_name': key})
        if name == 'followup_task':
            key = args['target']
            assert key == self.impl, 'only implementer may resume before QA approval'
            assert self.agents[key]['state'] != 'running', 'resumed running child'
            assert not self.blocker_delivered, 'external credentials blocker requires user action'
            self.impl_round += 1
            self.agents[key]['state'] = 'running'
            return 'Resumed'
        if name == 'wait_agent':
            active = [(k, a) for k, a in self.agents.items() if a['state'] == 'running']
            assert active, 'wait with no running work'
            if not self.timed_out:
                self.timed_out = True
                return CodexToolReply('Timeout: children still running')
            key, agent = active[0]
            role = agent['role']
            if role == 'ship-implementator-agent':
                if self.blocked:
                    report = (WORKTREE_REPORT + FOCUSED_EVIDENCE +
                              'Blocked: docker pull 123456789012.dkr.ecr.eu-west-1.amazonaws.com/ship-integration:fixture '
                              'failed with exit 1: no basic auth credentials. docker info succeeded; no cached integration '
                              'image exists. No repeated pull attempted and no authorized alternate integration setup exists. '
                              'Integration tests and subsequent lint were not run; no verified tree. Need user ECR login '
                              'using aws ecr get-login-password --region eu-west-1 | docker login --username AWS '
                              '--password-stdin 123456789012.dkr.ecr.eu-west-1.amazonaws.com, then resume verification.')
                    self.blocker_delivered = True
                elif self.stalled and self.impl_round >= 2:
                    report = (WORKTREE_REPORT + FOCUSED_EVIDENCE +
                              'Blocked after diagnosis: yarn test tests/integration/reschedule.test.ts --runInBand '
                              'exits 2 before executing tests: SHIP_INTEGRATION_CLIENT_CERT is not set. '
                              'The existing integration service requires an externally issued client certificate. '
                              'Inspected tests/integration/setup.ts:18 and the repository integration runbook: '
                              'the environment has no configured certificate and none is present in the approved '
                              'secret mount. The runbook requires the user/platform owner to provision the certificate; '
                              'this agent has no credential-issuance capability or authorized alternate integration service. '
                              'No unchanged retry or bypass attempted. Required user action: provision '
                              'SHIP_INTEGRATION_CLIENT_CERT for this worktree, then resume. Integration tests were '
                              'not executed and subsequent lint remains unrun; no verified tree.')
                    self.blocker_delivered = True
                elif self.impl_round == 0 or self.stalled:
                    report = self.partial_report or (WORKTREE_REPORT + FOCUSED_EVIDENCE +
                              'V2 integration verification and subsequent lint remain unrun; not review-ready. No external blocker.')
                elif self.partial_fix and self.needs_fix and self.impl_round == 2:
                    report = (WORKTREE_REPORT + FOCUSED_EVIDENCE + 'Refund fix now uses paid_amount rather than list_price. '
                              'Integration verification and subsequent lint remain unrun. Not verified yet; no external blocker.')
                else:
                    report = ('Verified tree. ' + WORKTREE_REPORT + VERIFICATION_EVIDENCE +
                              ('Refund review fix uses paid_amount rather than list_price; regression covered. ' if self.needs_fix else '') +
                              'All assigned implementation and verification complete; remaining work: independent review, QA and git handoff.')
                    self.verified = True
                    self.needs_fix = False
            elif role == 'ship-qa-agent':
                report = ('QA PLAN: 1. Reschedule before cutoff succeeds. 2. After cutoff is rejected. '
                          '3. Discounted refund uses paid amount. 4. Failed reschedule preserves the booking and shows error feedback. '
                          'For each case use an owned booked lesson and verify the persisted booking/payment plus visible feedback; '
                          'also confirm a non-owner cannot change the booking. Authoring complete against the approved plan, '
                          'no fixtures provisioned or browser execution started. Await approval before execution; PR and target deferred.')
                self.qa_ready = True
            elif role == 'ship-reviewer-agent':
                if self.review_round == 1:
                    report = ('Reviewed the uncommitted diff against the approved rescheduling and paid-amount plan in '
                          '/tmp/worktrees/LEX-1398, branch LEX-1398. ' + VERIFICATION_EVIDENCE +
                          'Important: refund uses list_price rather than paid amount in billing/refunds.py:18; '
                          'discounted bookings overpay. Use paid_amount and cover the discounted case. No other findings. Ready to commit? [No]')
                    self.needs_fix = True
                    self.verified = False
                else:
                    report = ('Reviewed the full uncommitted diff and refund fix against the approved plan in '
                          '/tmp/worktrees/LEX-1398, branch LEX-1398. Refund now uses paid_amount and discounted '
                          'regression coverage is present. ' + VERIFICATION_EVIDENCE +
                          'No Critical, Important or Minor findings. Ready to commit? [Yes]')
                    self.review_clean = True
            else:
                report = 'Draft PR #123: https://github.com/example/repo/pull/123. Commit abc123 pushed.'
                self.pr_ready = True
            agent['state'] = {'completed': report}
            return CodexToolReply('Mailbox activity: ' + key + ' completed', [key + '\n' + report])
        raise AssertionError('Unexpected tool: ' + name)

    def snapshot(self):
        return dict(vars(self))

    def assert_terminal(self, result):
        detail = json.dumps({'state': self.snapshot(), 'texts': result.texts}, indent=2)
        assert result.stop_reason == 'no_tool_calls', 'scenario exhausted its call budget: ' + detail
        running = [k for k, a in self.agents.items() if a['state'] == 'running']
        assert not running, 'premature final with running children: ' + detail
        assert self.blocker_delivered or (self.pr_ready and self.qa_ready and self.review_clean), 'premature final before expected gate/blocker: ' + detail


def assert_approval_request(text):
    request = re.search(r"\b(?:please\s+)?approve\b[^?]*\?|\bplease\s+approve\b|"
                        r"\breply\s+[\"'“”‘’*]*approved\b|\bif you approve\b|"
                        r"\b(?:do you|would you|can you)\s+approve\b", text, re.I)
    assert request, 'missing approval request: ' + text


def assert_qa_gate_report(text):
    assert_approval_request(text)
    for case in ['Reschedule before cutoff succeeds', 'After cutoff is rejected',
                 'Discounted refund uses paid amount']:
        assert case in text, 'QA plan missing: ' + case
    assert 'https://github.com/example/repo/pull/123' in text, 'missing PR URL'
    rows = '\n'.join(line for line in text.splitlines() if line.strip().startswith('|'))
    for stage in ['plan', 'implement', 'QA', 'review', 'commit', 'final', 'insights']:
        assert re.search(stage, rows, re.I), 'missing stage row: ' + stage
