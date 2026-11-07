"""Deterministic evaluation; answer keys are never passed to generation."""

import math
import unicodedata
from collections import Counter
from typing import Any


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def evidence_matches(chunk: dict[str, Any], alternative: dict[str, Any]) -> bool:
    return (
        bool(normalize(alternative["quote"]))
        and chunk["document_id"] == alternative["document_id"]
        and chunk["page_start"] <= alternative["pdf_page"] <= chunk["page_end"]
        and normalize(alternative["quote"]) in normalize(chunk["content"])
    )


def covered_groups(chunks: list[dict[str, Any]], groups: list[dict[str, Any]]) -> set[str]:
    return {
        group["id"]
        for group in groups
        if any(evidence_matches(chunk, alt) for chunk in chunks for alt in group["alternatives"])
    }


def retrieval_metrics(
    chunks: list[dict[str, Any]], groups: list[dict[str, Any]]
) -> dict[str, float]:
    if not groups:
        raise ValueError("Answerable retrieval questions must have required evidence groups")
    ranks = [
        i for i in range(1, min(5, len(chunks)) + 1) if covered_groups([chunks[i - 1]], groups)
    ]
    found = covered_groups(chunks[:5], groups)
    return {
        "hit@1": float(bool(covered_groups(chunks[:1], groups))),
        "hit@3": float(bool(covered_groups(chunks[:3], groups))),
        "hit@5": float(bool(found)),
        "evidence_recall@5": len(found) / len(groups),
        "complete_evidence@5": float(len(found) == len(groups)),
        "mrr@5": 1 / ranks[0] if ranks else 0.0,
    }


def token_fidelity(reference: str, actual: str) -> dict[str, float]:
    """Multiset token coverage, NOT a measure of relationship/semantic correctness."""
    expected, observed = Counter(normalize(reference).split()), Counter(normalize(actual).split())
    overlap = sum((expected & observed).values())
    return {
        "token_recall": overlap / sum(expected.values()) if expected else 1.0,
        "token_precision": overlap / sum(observed.values()) if observed else float(not expected),
    }


def vector_valid(vector: list[float], dimension: int) -> bool:
    return (
        len(vector) == dimension
        and all(math.isfinite(x) for x in vector)
        and sum(x * x for x in vector) > 0
    )


def review_summary(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """Do not turn unreviewed answers into passing scores."""
    dimensions = ("faithfulness", "correctness", "completeness", "citation_support")
    completed = [
        r
        for r in reviews
        if r.get("reviewer") and all(type(r.get(d)) is int and 0 <= r[d] <= 2 for d in dimensions)
    ]
    return {
        "total": len(reviews),
        "completed": len(completed),
        "mean_scores_0_to_2": {
            d: sum(r[d] for r in completed) / len(completed) if completed else None
            for d in dimensions
        },
    }
