"""Assertions for structured QA choices emitted by orchestration models."""

import re


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_labeled_choice(text: str, labels: tuple[str, ...]) -> bool | None:
    """Return the explicit boolean bound to a labeled choice, if present."""
    normalized_labels = tuple(_normalize(label) for label in labels)
    for clause in re.split(r"[;,.\n]", text):
        normalized = _normalize(clause)
        for label in normalized_labels:
            marker = normalized.find(label)
            if marker < 0:
                continue
            tail = normalized[marker + len(label):]
            value = re.match(
                r"\s*(?:(?:choice|decision)\s*)?(?:is\s*)?(?:authorized\s*)?"
                r"(yes|no|true|false|on|off)\b",
                tail,
            )
            if value:
                return value.group(1) in {"yes", "true", "on"}
    return None


def has_execution_authorization(text: str) -> bool:
    """Detect affirmative Phase-B execution intent while allowing explicit prohibitions."""
    lowered = text.lower()
    action = re.compile(
        r"\b(?:execute|run|begin) (?:the )?(?:approved )?(?:qa )?(?:plan|phase b)\b")
    for match in action.finditer(lowered):
        prefix = lowered[max(0, match.start() - 24):match.start()]
        if re.search(r"(?:do not|don't|never|must not)\s*$", prefix):
            continue
        return True
    if re.search(r"\bphase b\s+is\s+(?:approved|authorized)\b", lowered):
        return True
    return parse_labeled_choice(
        text, ("start_dynamic", "start dynamic", "dynamic comment")) is True
