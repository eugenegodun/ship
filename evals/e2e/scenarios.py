"""Canned subagent replies for E2E scenarios."""

PLAN = ("[agent_id: planner-01] PLAN for LEX-1398 - Add reschedule action. "
        "1) BookingService.reschedule with 12h guard 2) RescheduleRequest + tutor "
        "confirmation 3) LessonCard button + modal 4) tests. Awaiting review.")
IMPL_OK = ("[agent_id: impl-01] Implementation complete and verified. Worktree: "
           "/tmp/worktrees/LEX-1398, branch: LEX-1398. Changed: booking.py, api.py, "
           "LessonCard.tsx. Tests: 218 passed. Lint: clean.")
IMPL_FAIL = ("[agent_id: impl-01] BLOCKED - cannot produce a verified tree: the test "
             "suite fails on main before my changes (34 failures in billing/). No "
             "worktree handed over.")
IMPL_FIXED = ("[agent_id: impl-01] Fixes applied in place in the existing worktree. "
              "Tests: 220 passed. Lint: clean.")
QA_PLAN = ("[agent_id: qa-01] Phase-A plan: TC1 happy path, TC2 <12h hides action, "
           "TC3 third reschedule hidden. Flag exp_lesson_reschedule_v1. Awaiting approval.")
QA_DONE = ("[agent_id: qa-01] Phase B done. TC1 PASS TC2 PASS TC3 PASS. "
           "Results posted to PR #4321.")
REVIEW_DIRTY = ("[agent_id: rev-{n}] Critical: refund maths uses list_price "
                "(billing/refunds.py:18). Ready to commit? [No]")
REVIEW_CLEAN = "[agent_id: rev-{n}] Only Minor notes. Ready to commit? [Yes]"
GIT_OK = ("[agent_id: git-01] Committed and pushed LEX-1398. Draft PR: #4321 "
          "https://github.com/preply/edu-frontend/pull/4321")
SPEC = ("[agent_id: spec-01] SPEC LEX-1398 - user stories + EARS criteria: WHEN a booked "
        "lesson starts more than 12 hours from now THE SYSTEM SHALL show a Reschedule "
        "action. Awaiting review.")


class Script:
    """respond() callable: routes canned replies by tool + subagent, counts reviewer rounds.

    clean_review_round: reviewer round that returns [Yes] (1 = first review is clean;
    0 = never clean). impl_ok: whether the implementator produces a verified tree.
    """

    def __init__(self, clean_review_round: int = 1, impl_ok: bool = True):
        self.clean_review_round = clean_review_round
        self.impl_ok = impl_ok
        self.review_rounds = 0

    def __call__(self, tool: str, inp: dict) -> str:
        if tool == "TodoWrite":
            return "Todos updated"
        if tool == "AskUserQuestion":
            asked = str(inp.get("questions", "")).lower()
            if "record" in asked or "video" in asked:
                # ship 4.1.0 GATE 3 recording question - decline; behavior stays as before.
                return '{"Record video of this QA run?": "No"}'
            return '{"Planner model": "claude-sonnet-5", "Reviewer model": "claude-opus-5[1m]"}'
        if tool == "TaskOutput":
            return QA_PLAN
        if tool == "Skill":
            return "engineering-insights: nothing substantial to record for this run."
        if tool == "SendMessage":
            target = inp.get("agent_id", "")
            if "impl" in target:
                return IMPL_FIXED
            if "qa" in target:
                return QA_DONE
            if "planner" in target or "spec" in target:
                return PLAN if "planner" in target else SPEC
            return "ok"
        if tool == "Agent":
            sub = inp.get("subagent_type", "")
            if sub == "spec-agent":
                return SPEC
            if sub == "task-planner-agent":
                return PLAN
            if sub == "implementator-agent":
                return IMPL_OK if self.impl_ok else IMPL_FAIL
            if sub == "qa-agent":
                return QA_PLAN
            if sub == "reviewer-agent":
                self.review_rounds += 1
                clean = (self.clean_review_round
                         and self.review_rounds >= self.clean_review_round)
                tmpl = REVIEW_CLEAN if clean else REVIEW_DIRTY
                return tmpl.format(n=f"{self.review_rounds:02d}")
            return GIT_OK  # subagent_type "claude" (or any other): the git agent
        return "ok"
