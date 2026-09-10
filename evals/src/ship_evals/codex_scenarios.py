"""Stateful child-tool simulator; never wakes a parent after it finalizes."""
import json
import re

from .codex_harness import CodexToolReply


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
                    report = 'Blocked: Docker ECR pull failed: no basic auth credentials. Need user ECR login. Worktree /tmp/worktrees/LEX-1398, branch LEX-1398. No verified tree.'
                    self.blocker_delivered = True
                elif self.stalled and self.impl_round >= 2:
                    report = 'Blocked after diagnosis: ticket and plan do not define refund behavior for partially consumed bundles. Inspected ticket and existing tests; no policy found. Need user decision on remaining-credit allocation. Worktree /tmp/worktrees/LEX-1398, branch LEX-1398. Integration verification remains.'
                    self.blocker_delivered = True
                elif self.impl_round == 0 or self.stalled:
                    report = self.partial_report or 'Focused tests pass; V2 integration verification remains. Worktree /tmp/worktrees/LEX-1398, branch LEX-1398; not review-ready. No external blocker.'
                elif self.partial_fix and self.needs_fix and self.impl_round == 2:
                    report = 'Refund fix implemented; integration verification remains. Worktree /tmp/worktrees/LEX-1398, branch LEX-1398. Not verified yet; no external blocker.'
                else:
                    report = 'Verified tree. All assigned integration work and review fixes complete. Worktree /tmp/worktrees/LEX-1398, branch LEX-1398. Changed LessonCard.tsx, billing/refunds.py. Tests 218 passed; lint clean.'
                    self.verified = True
                    self.needs_fix = False
            elif role == 'ship-qa-agent':
                report = 'QA PLAN: 1. Reschedule before cutoff succeeds. 2. After cutoff is rejected. 3. Discounted refund uses paid amount. Await approval before execution.'
                self.qa_ready = True
            elif role == 'ship-reviewer-agent':
                if self.review_round == 1:
                    report = 'Important: refund uses list_price rather than paid amount in billing/refunds.py:18. Ready to commit? [No]'
                    self.needs_fix = True
                    self.verified = False
                else:
                    report = 'No findings. Tests 218 passed, lint clean. Ready to commit? [Yes]'
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
