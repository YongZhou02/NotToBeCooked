"""Evidence matching and retrieval metrics."""

import unicodedata
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


def covered_groups(
    chunks: list[dict[str, Any]], groups: list[dict[str, Any]]
) -> set[str]:
    return {
        group["id"]
        for group in groups
        if any(
            evidence_matches(chunk, alt)
            for chunk in chunks
            for alt in group["alternatives"]
        )
    }


def retrieval_metrics(
    chunks: list[dict[str, Any]], groups: list[dict[str, Any]]
) -> dict[str, float]:
    if not groups:
        raise ValueError(
            "Answerable retrieval questions must have required evidence groups"
        )
    ranks = [
        rank
        for rank in range(1, min(5, len(chunks)) + 1)
        if covered_groups([chunks[rank - 1]], groups)
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
