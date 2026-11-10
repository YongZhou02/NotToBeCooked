import math

import pytest
from scorers.answer_quality import review_summary
from scorers.pipeline import token_fidelity, vector_valid
from scorers.retrieval import (
    covered_groups,
    evidence_matches,
    normalize,
    retrieval_metrics,
)


def chunk(text, page=2, document="topic1"):
    return {
        "content": text,
        "page_start": page,
        "page_end": page,
        "document_id": document,
    }


def group(name, quote, page=2):
    return {
        "id": name,
        "alternatives": [{"document_id": "topic1", "pdf_page": page, "quote": quote}],
    }


def test_partial_evidence_is_not_complete_and_first_hit_rank_is_used():
    groups = [group("a", "source program"), group("b", "target program")]
    scores = retrieval_metrics([chunk("irrelevant"), chunk("source program")], groups)
    assert scores["hit@1"] == 0
    assert scores["hit@3"] == scores["hit@5"] == 1
    assert scores["evidence_recall@5"] == 0.5
    assert scores["complete_evidence@5"] == 0
    assert scores["mrr@5"] == 0.5


def test_correct_quote_wrong_document_or_page_does_not_count():
    alternative = group("a", "source")["alternatives"][0]
    assert not evidence_matches(chunk("source", page=3), alternative)
    assert not evidence_matches(chunk("source", document="other"), alternative)
    assert not evidence_matches(chunk("source"), {**alternative, "quote": "  "})


def test_acceptable_alternatives_do_not_inflate_recall_denominator():
    evidence = group("a", "one")
    evidence["alternatives"].append(
        {"document_id": "topic1", "pdf_page": 5, "quote": "other source"}
    )
    assert covered_groups([chunk("other source", 5)], [evidence]) == {"a"}
    assert (
        retrieval_metrics([chunk("other source", 5)], [evidence])["evidence_recall@5"]
        == 1
    )


def test_only_top_five_count_and_empty_evidence_is_invalid():
    scores = retrieval_metrics(
        [chunk("noise")] * 5 + [chunk("answer")], [group("a", "answer")]
    )
    assert scores["hit@5"] == scores["mrr@5"] == 0
    with pytest.raises(ValueError):
        retrieval_metrics([], [])


def test_normalization_preserves_relationship_direction_and_values():
    assert normalize("Source\r\n --> Target") == "source --> target"
    assert normalize("Source --> Target") != normalize("Target --> Source")
    assert token_fidelity("x x y", "x y")["token_recall"] == pytest.approx(2 / 3)
    # Token overlap alone cannot prove direction: this is why anchors also exist.
    assert token_fidelity("a -> b", "b -> a")["token_recall"] == 1


def test_bad_embeddings_are_rejected():
    assert vector_valid([0.6, 0.8], 2)
    for vector in ([0.0, 0.0], [math.nan, 1.0], [math.inf, 1.0], [1.0]):
        assert not vector_valid(vector, 2)


def test_pending_human_reviews_have_no_quality_score():
    assert (
        review_summary([{"faithfulness": None}])["mean_scores_0_to_2"]["faithfulness"]
        is None
    )
    review = {
        "reviewer": "Bao Sheng",
        "faithfulness": 2,
        "correctness": 1,
        "completeness": 0,
        "citation_support": 2,
    }
    scores = review_summary([review, {"faithfulness": None}])
    assert scores["completed"] == 1
    assert scores["mean_scores_0_to_2"]["completeness"] == 0
