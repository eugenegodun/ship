"""Assertions for plans presented in prose or an approval question."""


def assert_plan_displayed_verbatim(expected, prose, calls):
    """Require the complete plan in one visible surface, ignoring whitespace only."""
    surfaces = [prose]
    surfaces.extend(
        question.get("question", "")
        for call in calls if call.name == "AskUserQuestion"
        for question in call.input_parameters.get("questions", [])
    )
    normalized = " ".join(expected.split())
    assert normalized, "expected plan must not be empty"
    assert any(normalized in " ".join(surface.split()) for surface in surfaces), (
        "the complete queued plan must be displayed verbatim in prose or an approval question"
    )
