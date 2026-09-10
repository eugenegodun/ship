"""Live Codex implementer regressions using its generated role and simulated shell output."""
import json
import re
import tomllib

import pytest

from ship_evals.codex_harness import call_codex_model
from ship_evals.codex_tools import SHELL
from ship_evals.config import PLUGIN_DIR

pytestmark = pytest.mark.codex

WORKTREE = "/worktrees/LEX-999"
FOCUSED = f"pytest {WORKTREE}/tests/test_survey.py"
INTEGRATION = f"pytest {WORKTREE}/tests/integration"
LINT = f"ruff check {WORKTREE}"


@pytest.fixture
def implementer_instructions():
    role = PLUGIN_DIR / "codex-agents" / "ship-implementator-agent.toml"
    return tomllib.loads(role.read_text())["developer_instructions"]


def _milestone_transcript(*, fix_round=False):
    assignment = "Apply the review fixes" if fix_round else "Implement the approved plan"
    return [
        {"role": "user", "content": (
            f"Orchestrator brief: {assignment} for LEX-999. Worktree: {WORKTREE}; branch: LEX-999. "
            "The plan was approved, repository instructions and required skills were already read, "
            "the checklist is current, and the implementation is complete. Changed file: survey.py. "
            "There are no deviations. The approved verification scope is the focused survey suite, "
            f"then integration verification with `{INTEGRATION}`, then lint with `{LINT}`. "
            "Use those exact commands. This is an isolated simulation: shell is the available tool. "
            "No git operations or external writes are needed. Continue from the focused test result."
        )},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "focused_result", "type": "function", "function": {
                "name": "shell", "arguments": json.dumps({"command": FOCUSED})}}
        ]},
        {"role": "tool", "tool_call_id": "focused_result", "content": "7 passed in 0.24s\n(exit 0)"},
    ]


def _run_role(instructions, messages, outputs, max_calls=6):
    messages = list(messages)
    executed = []
    for _ in range(max_calls):
        response = call_codex_model(instructions, messages, [SHELL])
        message = response.choices[0].message
        calls = message.tool_calls or []
        assistant = {"role": "assistant", "content": message.content}
        if not calls:
            return executed, message.content or ""
        assistant["tool_calls"] = [
            {"id": call.id, "type": call.type, "function": {
                "name": call.function.name, "arguments": call.function.arguments}}
            for call in calls
        ]
        messages.append(assistant)
        for call in calls:
            assert call.function.name == "shell"
            command = json.loads(call.function.arguments)["command"].strip()
            assert command in outputs, f"Unexpected command (never executed): {command}"
            assert command not in executed, f"Repeated command without changed evidence: {command}"
            if command == LINT:
                assert INTEGRATION in executed, "Lint dispatched before integration evidence"
            executed.append(command)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": outputs[command]})
    pytest.fail(f"Implementer exhausted {max_calls} calls without a handoff; commands={executed}")


@pytest.mark.parametrize("fix_round", [False, True], ids=["implementation", "review-fixes"])
def test_focused_pass_continues_remaining_verification(implementer_instructions, fix_round):
    executed, final = _run_role(implementer_instructions, _milestone_transcript(fix_round=fix_round), {
        INTEGRATION: "28 passed in 4.12s\n(exit 0)",
        LINT: "All checks passed!\n(exit 0)",
    })
    assert executed == [INTEGRATION, LINT], f"Premature milestone final: {final}"
    assert WORKTREE in final and "LEX-999" in final, final
    assert "28" in final and "lint" in final.lower(), final


def test_missing_credentials_reports_evidenced_blocker(implementer_instructions):
    executed, final = _run_role(implementer_instructions, _milestone_transcript(), {
        INTEGRATION: (
            "Integration setup failed: STAGE_API_TOKEN is not set. "
            "The test harness requires an externally provisioned stage token; "
            "no tests were executed.\n(exit 2)"
        ),
        LINT: "All checks passed!\n(exit 0)",
    })
    assert executed in ([INTEGRATION], [INTEGRATION, LINT]), final
    assert "STAGE_API_TOKEN" in final and WORKTREE in final, final
    assert re.search(r"block|missing|requires?|unavailable", final, re.I), final
    assert re.search(r"not (?:run|executed|complete|verified)|remaining|pending|could not", final, re.I), final
    assert not re.search(r"(?:integration|all tests)\s+(?:tests\s+)?(?:passed|succeeded)", final, re.I), final
