"""Summarize a completed generation_reviews.json without calling any models."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scorers.answer_quality import review_summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reviews", type=Path)
    args = parser.parse_args()
    reviews = json.loads(args.reviews.read_text(encoding="utf-8"))
    print(json.dumps(review_summary(reviews), indent=2))
