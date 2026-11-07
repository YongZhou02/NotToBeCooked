# NTBC end-to-end pipeline evaluation

## Open the single-file evidence review

From `apps/api` (no database, API, or model calls required):

```powershell
uv run python scripts/compile_evaluation_review.py --run ../../evaluation/runs/20261107T113258086748Z --compare-extraction ../../evaluation/runs/20261107T115210823381Z
```

Open `evaluation/runs/20261107T113258086748Z/review.html` in a browser.
The self-contained HTML combines all 50 questions, reference answers, evidence
groups, native PDF page text, filtered extraction, chunks, top-five retrieval,
15 generated answers, citations, and separately labelled assistant opinions.
It verifies the golden dataset hashes and recomputes all 150 saved retrieval
metric records, failing on disagreement rather than silently rewriting scores.
The comparison remains extraction-only; no improved retrieval/generation is implied.

Start with `t1-001` (page 4 filtering fix), then `t1-015` (remaining page 21
missing evidence), `t1-009` (flattened table interpretation), and `t1-050`
(multi-evidence recall versus completeness). Expand passages and check the real
PDF whenever layout or semantics matter. Inspecting text alone cannot validate
the original image-to-text transcription.

Use the separate owner-review fields to agree/disagree with draft labels and
score generated answers with reasons. Save before changing question or method.
Export the review JSON before closing; browser local storage is only a convenience.
Owner ratings do not overwrite automated scores or golden labels. The exported
file includes its baseline run and dataset hashes; no importer is provided yet.
For another run, pass its directory with `--run`; comparison is optional.
Raw artifacts remain unchanged and are traceable through the provenance panel.

This benchmark starts with `CPT316_Topic1_Semantic_Text_Only.pdf` supplied by
Bao Sheng. The 38-page PDF explicitly transcribes diagram relationships. It is
**not** a test of original-image comprehension, transcription correctness against
the original slides, or chart extraction. No OCR/VLM accuracy claim follows from
this text-only corpus.

## Dataset and annotation status

- `corpus_manifest.json`: SHA256, pages, extraction settings, chunk size and search settings.
- `golden/questions.json`: 50 questions; 15 development, 35 provisional test questions.
- `golden/answer_key.json`: reference answers and required facts, keyed by question ID.
- `golden/evidence_key.json`: 73 required evidence groups, anchored to document/page/quote.
- 5 categories, 10 questions each: definitions, exact terminology, paraphrases,
  explicit relationships and multiple evidence. Three test questions per category
  form the 15-answer generation review subset.

The labels are assistant-authored, checked against the supplied text, and **await
owner review**. This is a pilot, not a sealed independently authored test set.
Related questions exist across splits; scores do not establish generalization to
new topics. Do not tune on test results and later describe them as unseen.
Have Bao Sheng review labels, freeze dataset hashes, then use a separately
authored test set for stronger claims. Never change questions merely to create a winner.

Alternative passages belong inside a group's `alternatives` list (OR). Separate
groups are all required (AND). A chunk matches an alternative only when its
document and PDF page range match and its whitespace/Unicode-normalized text
contains the quote. Quotes deliberately preserve direction, symbols and numbers.
Printed slide numbers are not used in place of 1-based PDF positions.

This matcher is deterministic but conservative: a valid paraphrase or a quote
split across chunks can be scored as a miss. Inspect failures before interpreting
scores. Missing evidence stays in the denominator; it is not removed to improve
retrieval results. Citations produced by the system are not the answer key.

## Run

From `apps/api`, with the existing PostgreSQL/pgvector schema available:

```powershell
uv run python scripts/evaluate_pipeline.py --extract-only
uv run python scripts/evaluate_pipeline.py
uv run python scripts/evaluate_pipeline.py --generate
```

The last command makes up to 15 real generation calls using the configured model
and hybrid retrieval. `--generation-method vector` or `keyword` evaluates those
answers separately. Fake generation is rejected. No new providers, credentials
or models are selected. Network/API quota failures can produce production failure
responses; review them as failures, not as unsupported questions.

Chart extraction is disabled only inside the standalone runner; the production
setting and `.env` are not edited. OCR remains on, matching ingestion defaults.
Existing parse/chunk/embed functions are used. The corpus does not use synthetic
embeddings. Each document is searchable in full; gold pages do not filter search.

Temporary evaluation owner/course/folder/file/run/chunk/message rows live inside
an outer DB transaction. Production route commits are contained by savepoints.
The transaction rolls back even on exceptions, and successful runs verify that
the temporary owner is absent afterward. No uploaded bytes are changed, no schema
is dropped, and no existing active ingestion run is updated. Do not run migrations
or restart the database during an evaluation.

## Outputs

Each unique, ignored `evaluation/runs/<UTC-run-id>/` directory contains:

- `config.json`: corpus/dataset/code hashes, git state, package versions, models,
  seed, hardware platform, repetitions and embedding timings. No keys or DB URL.
- `reference_pages.json`: independent PDFium native text for comparison.
- `extracted_items.json`, `chunks.json`: actual ingestion artifacts before retrieval.
- `docling_structure_<document-id>.json`: raw item labels, text and page provenance
  before NTBC's content filtering, to diagnose material dropped by the filter.
- `checks.json`: per-page token precision/recall, labelled evidence preservation,
  chunk budget violations, DB text/page/token/vector round-trip and rollback result.
- `retrieval.jsonl`: question, method, actual retrieved chunks/pages/scores/ranks,
  query embedding latency, repeated DB retrieval latency and scores.
- `summary.csv`: overall and per-category results, separately for dev and test.
- `generation_reviews.json`: actual answers/citations, references and pending ratings.
- `generation_answers.json`: actual returned answers/citations without answer keys;
  review forms are a separate scoring view that includes references.
- `report.md`: readable results and limitations.

Token fidelity measures occurrence overlap, **not** semantic order. Relationship
anchors are additional checks, not proof that every relationship survived.
DB vectors must be finite, nonzero, the configured dimension, and round-trip
within absolute tolerance 1e-6; stored text and page metadata must match.

Retrieval compares cosine vector search, **PostgreSQL ts_rank full-text search
(not BM25)**, and production hybrid RRF. All use the same chunks/query vectors and
file scope, with top-5 output. Hybrid considers up to 50 candidates per retriever,
RRF k=60, weights 1:1. It performs two searches, which is part of its latency cost.
The model is loaded before scoring; each search path is warmed. Method order is
seeded/shuffled per question. Three latency repetitions do not triple sample size.
Embedding cost is reported separately; DB latency is not full user-visible latency.

Scores: Hit@1/3/5 (any required group), evidence Recall@5 (fraction of required
groups), complete-evidence@5 (all groups), MRR@5 (first relevant rank).
No significance or production p95 claim is made from this small pilot.
Model generation is stochastic and provider implementations can change. The run
records the model name and prompt/code hashes, not a guarantee of identical future
answers. The current LLM adapter does not expose provider token usage, so this
version does not invent token counts or monetary cost estimates.

## Generation review rubric

For each of the 15 answers, read the answer, actual sources, citations, and the
separate reference. Supply a reviewer name, ratings 0/1/2, and notes:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Faithfulness | Material unsupported claims | Some unsupported claims | All factual claims supported by retrieved evidence |
| Correctness | Wrong answer | Partly correct | Correct relative to the verified reference |
| Completeness | Required content absent | Some required facts missing | All required facts covered |
| Citation support | No usable/supporting citations | Partial support or attribution | Claims linked to supporting cited passages |

An empty/refused answer should not receive a perfect faithfulness score merely
because it makes no claims. Explain inappropriate refusals and generation errors
in notes. Existing quote/marker verification is syntactic; reviewers must assess
whether the quote actually supports the claim. Source errors require correction
of the benchmark reference, with a new dataset version, rather than blind copying.

```powershell
uv run python scripts/summarize_pipeline_reviews.py ../../evaluation/runs/<run-id>/generation_reviews.json
```

Pending rows are never treated as 0 or as a pass. Completed means a named reviewer
has supplied all four integer ratings. This workflow does not pretend to have
RAGAS or validated LLM-judge scores.

## Boundaries

The generation adapter substitutes only the selected retriever's results inside
the standalone process, then calls the real single-turn RAG route for context,
generation, grounding and message persistence. This is not an HTTP/auth/UI,
conversation-memory, file-replacement or whole-document-summary test. The current
corpus is one transcribed PDF; use a larger, independently labelled multi-file
corpus before claiming cross-file retrieval or broad quality improvements.
