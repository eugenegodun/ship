"""Tests for codex_harness module."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ship_evals.codex_harness import continue_codex_transcript


def fake_openai_response(text: str, tool_calls: list = None):
    """Create a fake OpenAI response object matching the structure expected by codex_harness."""
    if tool_calls is None:
        tool_calls = []

    tool_call_objs = []
    for tool_call in tool_calls:
        tool_call_objs.append(SimpleNamespace(
            id=tool_call["id"],
            type="function",
            function=SimpleNamespace(
                name=tool_call["name"],
                arguments=json.dumps(tool_call["arguments"])
            )
        ))

    message = SimpleNamespace(
        content=text or None,
        tool_calls=tool_call_objs if tool_call_objs else None
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )


def test_continue_codex_transcript_captures_text_with_tool_calls():
    """Text emitted alongside tool calls should be captured in result.texts."""

    # Mock the call_codex_model to return a response with both text and tool calls
    responses = [
        # Turn 1: text alongside a tool call
        fake_openai_response(
            "Dispatching the tool.",
            [{"id": "tc_1", "name": "spawn_agent", "arguments": {"task_name": "t1", "message": "m1"}}]
        ),
        # Turn 2: no tool calls (stops)
        fake_openai_response("Done.")
    ]
    response_iter = iter(responses)

    def mock_call_codex_model(system, messages, tools):
        return next(response_iter)

    def mock_respond(tool_name, tool_input):
        return f"Response to {tool_name}"

    with patch("ship_evals.codex_harness.call_codex_model", side_effect=mock_call_codex_model):
        result = continue_codex_transcript(
            messages=[],
            respond=mock_respond,
            max_calls=10
        )

    # Verify that the text from the turn with tool calls was captured
    assert "Dispatching the tool." in result.texts
    assert "Done." in result.texts
    assert len(result.texts) == 2
    assert len(result.events) == 1
    assert result.events[0].name == "spawn_agent"
    assert result.stop_reason == "no_tool_calls"


def test_continue_codex_transcript_captures_empty_text_on_no_tool_calls():
    """Empty or whitespace-only text on a no-tool-calls turn should be captured (for consistency)."""

    responses = [
        # Turn 1: tool call with no text
        fake_openai_response(
            None,
            [{"id": "tc_1", "name": "spawn_agent", "arguments": {"task_name": "t1", "message": "m1"}}]
        ),
        # Turn 2: no tool calls, empty text
        fake_openai_response("")
    ]
    response_iter = iter(responses)

    def mock_call_codex_model(system, messages, tools):
        return next(response_iter)

    def mock_respond(tool_name, tool_input):
        return f"Response to {tool_name}"

    with patch("ship_evals.codex_harness.call_codex_model", side_effect=mock_call_codex_model):
        result = continue_codex_transcript(
            messages=[],
            respond=mock_respond,
            max_calls=10
        )

    # The empty text on the no-tool-calls turn should be captured
    assert "" in result.texts
    assert len(result.texts) == 1


def test_continue_codex_transcript_skips_empty_text_with_tool_calls():
    """Empty or whitespace-only text alongside tool calls should not be captured."""

    responses = [
        # Turn 1: tool call with only whitespace text
        fake_openai_response(
            "   ",
            [{"id": "tc_1", "name": "spawn_agent", "arguments": {"task_name": "t1", "message": "m1"}}]
        ),
        # Turn 2: no tool calls
        fake_openai_response("Final.")
    ]
    response_iter = iter(responses)

    def mock_call_codex_model(system, messages, tools):
        return next(response_iter)

    def mock_respond(tool_name, tool_input):
        return f"Response to {tool_name}"

    with patch("ship_evals.codex_harness.call_codex_model", side_effect=mock_call_codex_model):
        result = continue_codex_transcript(
            messages=[],
            respond=mock_respond,
            max_calls=10
        )

    # Whitespace-only text alongside tool calls should be skipped
    # Only the text from the final no-tool-calls turn should be captured
    assert result.texts == ["Final."]
