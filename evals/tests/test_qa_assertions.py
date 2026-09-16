import pytest

from ship_evals.qa_assertions import has_execution_authorization, parse_labeled_choice


@pytest.mark.parametrize(
    ("text", "labels", "expected"),
    [
        ("recording: No; screenshots: Yes; start_dynamic: Yes", ("recording",), False),
        ("recording: No; screenshots: Yes; start_dynamic: Yes", ("screenshots",), True),
        ("recording: No; screenshots: No; start_dynamic: Yes", ("screenshots",), False),
        ("start dynamic = No. Do not post /dynamic.", ("start dynamic",), False),
        ("The /dynamic comment is authorized: Yes", ("dynamic comment",), True),
    ],
)
def test_parse_labeled_choice_binds_value_to_its_field(text, labels, expected):
    assert parse_labeled_choice(text, labels) is expected


def test_parse_labeled_choice_does_not_turn_a_prohibition_into_yes():
    assert parse_labeled_choice("Do not post /dynamic.", ("dynamic",)) is None


@pytest.mark.parametrize(
    "text",
    [
        "screenshots pending recording Yes",
        "screenshots not authorized recording Yes",
    ],
)
def test_parse_labeled_choice_does_not_borrow_a_later_field_value(text):
    assert parse_labeled_choice(text, ("screenshots",)) is None


@pytest.mark.parametrize(
    "text",
    [
        "Do not execute Phase B.",
        "Never run the approved QA plan.",
        "You must not begin Phase B.",
        "Phase B is not approved.",
    ],
)
def test_execution_prohibitions_are_not_authorization(text):
    assert not has_execution_authorization(text)


@pytest.mark.parametrize(
    "text",
    [
        "Execute Phase B now.",
        "Phase B is authorized.",
        "Do not record video, execute Phase B.",
        "start_dynamic: Yes",
    ],
)
def test_affirmative_execution_language_is_authorization(text):
    assert has_execution_authorization(text)
