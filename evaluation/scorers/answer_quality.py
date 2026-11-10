"""Aggregate completed manual answer-quality reviews."""


def review_summary(reviews: list[dict]) -> dict:
    """Pending reviews are excluded rather than silently becoming passes or zeros."""
    dimensions = ("faithfulness", "correctness", "completeness", "citation_support")
    completed = [
        review
        for review in reviews
        if review.get("reviewer")
        and all(
            type(review.get(dimension)) is int and 0 <= review[dimension] <= 2
            for dimension in dimensions
        )
    ]
    return {
        "total": len(reviews),
        "completed": len(completed),
        "mean_scores_0_to_2": {
            dimension: (
                sum(review[dimension] for review in completed) / len(completed)
                if completed
                else None
            )
            for dimension in dimensions
        },
    }
