# Topic 1 baseline: 2026-11-07

Local run: `evaluation/runs/20261107T113258086748Z/`.
Command: `uv run python scripts/evaluate_pipeline.py --generate` (from `apps/api`).
Corpus: the supplied 38-page `CPT316_Topic1_Semantic_Text_Only.pdf`.
50 questions, including 35 provisional test questions. This is a pilot dataset
authored and source-checked by the assistant, awaiting Bao Sheng's review. Related
questions occur across splits; do not present these as independent unseen-topic results.

## Measured stage results

- All 73 answer-key evidence anchors exist in the supplied PDF's native text.
- 70/73 anchors survive NTBC extraction (95.9%); the same 70 are intact in chunks.
- No chunks exceed the configured 350-token budget.
- PostgreSQL text, page metadata, token counts, FTS and pgvector round-trip passed.
- Temporary database records were rolled back; the temporary owner no longer exists.
- Fifteen real hybrid answers were generated (3 per question category).

The extraction misses remain in retrieval scoring. Nothing was removed to improve
results. A quote mismatch is a diagnostic requiring inspection, not automatic proof
that its underlying meaning was lost.

## Provisional test results (35 questions)

| Method | Hit@1 | Hit@5 | Evidence Recall@5 | Complete@5 | MRR@5 | Median DB retrieval ms |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.829 | 0.971 | 0.948 | 0.914 | 0.887 | 4.4 |
| PostgreSQL keyword | 0.829 | 0.971 | 0.962 | 0.943 | 0.880 | 4.1 |
| Hybrid + RRF | 0.886 | 0.971 | 0.962 | 0.943 | 0.920 | 18.7 |

Hybrid did not improve evidence Recall@5 over keyword on this pilot. It improved
first-hit ranking, with higher DB latency. Do not call this a statistically proven
general win. Embedding, generation, cold model loading, HTTP and UI time are not
included in these DB retrieval timings. Detailed dev/category results and repeated
timings are in the run's `summary.csv` and `retrieval.jsonl`.

## Concrete failures to investigate

1. `t1-001-e1` (p4): no body item from the translator page reached extraction.
   A diagnostic reparse confirms Docling labels it `code`; NTBC's filter skips
   that label, despite the item containing the page's full textual explanation.
2. `t1-015-e1` and `t1-050-e1` (p21): the optimized two-line code is absent from
   extracted items, although the explanatory paragraph survives.
   The diagnostic reparse labels the code/arrow region as `picture`, with no text.
   These are different causes: NTBC filtering on p4 versus Docling classification
   or OCR loss on p21. Raw items are in diagnostic run
   `evaluation/runs/20261107T113635350705Z/docling_structure_topic1.json`.
3. Heading `Token classes:` persists in chunks on much later pages (including p38).
   This may pollute indexing; the harness does not change production ingestion.
4. In `t1-009`, generation calls the column `Address Position`, following the
   flattened source `Variable Name | Type | Address Position | Float ...`.
   The correct header is `Address`; `Position` is the first row's variable name.
5. `t1-018` gives the right instruction but adds an uncited storage-shelf analogy.
6. `t1-028` cites the cyan preprocessor-highlight explanation while answering about
   the pink compiler-phase highlight: a syntactically valid quote can support the
   wrong context.
7. `t1-050` is withheld by the production grounding gate because of a repeated
   citation quote. This is not a legitimate "the notes lack an answer" outcome.

## Generation review

`generation_reviews.json` preserves blank owner-review fields. A separate
`assistant_reviews.json` records the assistant's source-based review of all 15
answers; these are **not independent human or validated LLM-judge ratings**.

Mean scores on the documented 0/1/2 rubric: faithfulness 1.67, correctness 1.80,
completeness 1.60, citation support 1.67. These reflect a first-pass review and
should be checked by Bao Sheng. The withheld answer receives zeros rather than
being counted as perfectly faithful through making no claims.

The next useful work is verifying these failures and the labels, then testing a
targeted extraction fix against this frozen baseline. Do not change the gold labels
just to make the current implementation pass.
