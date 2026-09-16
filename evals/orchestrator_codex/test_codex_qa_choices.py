import re

import pytest
from ship_evals.qa_assertions import has_execution_authorization, parse_labeled_choice


def resumed_qa(window):
    return [call for call in window.named("followup_task")
            if call.input_parameters.get("target") == "/root/apollo_1398_qa"]


def assert_choice(message, labels, expected):
    assert parse_labeled_choice(message, labels) is expected, message


def assert_no_execution_authorization(message):
    assert not has_execution_authorization(message), message


@pytest.mark.codex
def test_gate2_keeps_execution_pending_and_asks_all_choices(run_codex_qa_transition):
    window = run_codex_qa_transition("qa_gate_ready")
    assert not resumed_qa(window), window.diagnostics()
    assert not window.named("shell"), "the orchestrator must not post /dynamic"
    text = window.text.lower()
    assert "tc1" in text and ("approv" in text or "change" in text)
    assert "record" in text or "video" in text
    assert "screenshot" in text
    assert "/dynamic" in text or ("start" in text and "server" in text)


@pytest.mark.codex
def test_record_flag_only_preanswers_video_choice(run_codex_qa_transition):
    window = run_codex_qa_transition("qa_gate_ready_record_flag")
    assert not resumed_qa(window), window.diagnostics()
    text = window.text.lower()
    assert "screenshot" in text
    assert "/dynamic" in text or ("start" in text and "server" in text)
    assert not re.search(r"(?:record|video)[^?]{0,100}\?", text)


@pytest.mark.codex
def test_approved_gate_resumes_same_qa_with_all_choices(run_codex_qa_transition):
    window = run_codex_qa_transition("qa_choices_all_answered")
    followups = resumed_qa(window)
    assert followups, window.diagnostics()
    message = followups[0].input_parameters["message"].lower()
    assert "pull/4321" in message and "approv" in message
    assert_choice(message, ("recording", "record video"), False)
    assert_choice(message, ("screenshots", "screenshot"), True)
    assert_choice(message, ("start_dynamic", "start dynamic", "dynamic comment"), True)
    assert not window.named("shell"), "only QA owns the authorized /dynamic write"


@pytest.mark.codex
def test_declined_startup_with_target_resumes_same_qa(run_codex_qa_transition):
    window = run_codex_qa_transition("qa_start_declined_with_target")
    followups = resumed_qa(window)
    assert followups, window.diagnostics()
    message = followups[0].input_parameters["message"].lower()
    assert "stage34.preply.com" in message
    assert_choice(message, ("start_dynamic", "start dynamic", "dynamic comment"), False)
    assert not window.named("shell")


@pytest.mark.codex
def test_declined_startup_without_target_requests_target_or_deferral(run_codex_qa_transition):
    window = run_codex_qa_transition("qa_start_declined_without_target")
    assert not resumed_qa(window), window.diagnostics()
    assert not window.named("shell")
    assert re.search(r"(existing|test).{0,30}(url|environment|target)|defer", window.text, re.I | re.S)


@pytest.mark.codex
def test_revision_request_returns_to_same_qa_without_execution(run_codex_qa_transition):
    window = run_codex_qa_transition("qa_plan_revision_requested")
    followups = resumed_qa(window)
    assert followups, window.diagnostics()
    message = followups[0].input_parameters["message"].lower()
    assert "keyboard" in message and ("revis" in message or "plan" in message)
    assert_no_execution_authorization(message)
    assert not window.named("shell")
