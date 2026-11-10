"""Tell a real change apart from luck on a small question set.

Repeating a deterministic retrieval run adds no evidence. The uncertainty comes
from which questions were asked, so every test here compares the same questions.
"""

import math
import random
from collections.abc import Sequence


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a pass rate. Stays sensible near 0% and 100%."""
    if total < 1:
        raise ValueError("A rate needs at least one question")
    rate = successes / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _paired(baseline: Sequence[float], variant: Sequence[float]) -> None:
    if len(baseline) != len(variant) or not baseline:
        raise ValueError("Compare the same non-empty list of questions")


def mcnemar_exact(baseline: Sequence[bool], variant: Sequence[bool]) -> dict:
    """Exact two-sided test on the questions that changed result."""
    _paired(baseline, variant)
    gained = sum(not b and v for b, v in zip(baseline, variant, strict=True))
    lost = sum(b and not v for b, v in zip(baseline, variant, strict=True))
    changed = gained + lost
    tail = sum(math.comb(changed, i) for i in range(min(gained, lost) + 1))
    p_value = min(1.0, 2 * tail / 2**changed) if changed else 1.0
    return {"gained": gained, "lost": lost, "p_value": p_value}


def paired_bootstrap(
    baseline: Sequence[float],
    variant: Sequence[float],
    samples: int = 10_000,
    seed: int = 37,
) -> dict:
    """Mean change with a 95% interval, resampling questions in pairs."""
    _paired(baseline, variant)
    differences = [v - b for b, v in zip(baseline, variant, strict=True)]
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choices(differences, k=len(differences))) / len(differences)
        for _ in range(samples)
    )
    return {
        "mean_change": sum(differences) / len(differences),
        "low": means[int(0.025 * samples)],
        "high": means[int(0.975 * samples) - 1],
    }


def verdict(comparison: dict) -> str:
    """Plain wording, so a small gain is not reported as a win."""
    if comparison["low"] > 0:
        return "better"
    if comparison["high"] < 0:
        return "worse"
    return "no clear change"
