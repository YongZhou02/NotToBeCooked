# Topic 1 golden dataset

- `questions.jsonl`: 50 individually reviewed labels.
- `label_review.json`: review counts, verdict groups, revisions, and workbook hash.
- `reviews/`: the source review workbook.
- `history/v2/`: pre-finalization labels used by historical runs.

All 50 labels are verified. The strict retrieval benchmark uses 49 labels because
`t1-027` is a low-value visual inference rather than retrievable source evidence.
New runs use the finalized labels. Historical runs remain tied to the v2 snapshot.
