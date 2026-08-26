from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

from .config import JUDGE_MODEL


def rubric(name: str, steps: list[str], threshold: float = 0.7) -> GEval:
    return GEval(
        name=name,
        evaluation_steps=steps,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=JUDGE_MODEL,
        threshold=threshold,
    )
