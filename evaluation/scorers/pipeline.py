"""Extraction fidelity and embedding sanity checks."""

import math
from collections import Counter

from scorers.retrieval import normalize


def token_fidelity(reference: str, actual: str) -> dict[str, float]:
    """Multiset token coverage, NOT relationship or semantic correctness."""
    expected, observed = (
        Counter(normalize(reference).split()),
        Counter(normalize(actual).split()),
    )
    overlap = sum((expected & observed).values())
    return {
        "token_recall": overlap / sum(expected.values()) if expected else 1.0,
        "token_precision": overlap / sum(observed.values())
        if observed
        else float(not expected),
    }


def vector_valid(vector: list[float], dimension: int) -> bool:
    return (
        len(vector) == dimension
        and all(math.isfinite(value) for value in vector)
        and sum(value * value for value in vector) > 0
    )
