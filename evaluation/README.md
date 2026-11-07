# NTBC evaluation harness

Everything specific to evaluation lives in this folder. Production RAG code remains
under `apps/api`; this harness imports it so the experiment tests real application
components rather than copied substitutes.

## Folder map

```text
evaluation/
|-- README.md                         # this map and methodology
|-- run_eval.py                       # ONE entry point for a new evaluation run
|-- datasets/
|   `-- cpt316/
|       |-- README.md                 # corpus intake limitations
|       |-- candidate_sources.json    # Topic 2/3 candidates, not scored yet
|       |-- documents/                # four immutable semantic-text PDFs
|       `-- topic1/
|           |-- dataset.json          # benchmark/chunk/retrieval settings
|           |-- sources.json          # PDFs/pages/hashes used by this set
|           `-- questions.jsonl       # question+answer+evidence in ONE row
|-- builder/
|   |-- build_dataset.py              # deterministic legacy-to-JSONL builder
|   `-- audit_semantic_pdfs.py        # native-text/PDF intake checker
|-- scorers/
|   |-- retrieval.py                  # Hit@k, evidence recall, complete@5, MRR
|   |-- pipeline.py                   # extraction token fidelity/vector checks
|   |-- answer_quality.py             # human-review aggregation only
|   `-- summarize_reviews.py          # CLI for reviewed generation answers
|-- reports/
|   |-- build_review.py               # compiles scattered run files into HTML
|   |-- review_template.html           # offline interactive report UI
|   `-- generated/
|       `-- topic1-baseline-review.html # OPEN THIS to inspect the harness
|-- runs/                              # one immutable folder per execution
|   |-- 20261107T113258086748Z/        # complete historical baseline
|   |-- 20261107T113635350705Z/        # diagnostic extraction reparse
|   `-- 20261107T115210823381Z/        # extraction-only after filtering fix
|-- baselines/
|   `-- topic1-pilot-2026-11-07.md     # human interpretation of baseline
`-- tests/                             # scorer, report, builder, PDF-audit tests
```

The old complete run predates this layout, so it contains `retrieval.jsonl` and
`summary.csv`. New runs write the clearer names `results.jsonl` and `summary.json`
while retaining `summary.csv` and `report.md` for human inspection. Historical run
files are not rewritten because provenance matters more than cosmetic uniformity.

## What each layer answers

```text
PDF source
   |
   v
Docling extraction ------> Did labelled evidence survive extraction?
   |
   v
350-token chunks --------> Is each required evidence group intact in a chunk?
   |
   v
PostgreSQL + pgvector ---> Did text, pages, tokens and vectors round-trip?
   |
   +--> vector search ----+
   +--> keyword search ---+--> Hit@1/3/5, Recall@5, Complete@5, MRR@5
   `--> hybrid + RRF -----+
                              |
                              v
                          generated answer
                              |
                              v
                 human review: faithfulness, correctness,
                 completeness, citation support (0/1/2)
```

Retrieval scores do not prove answer quality. Citation presence does not prove that
the passage supports the claim. Native PDF text does not prove that a diagram was
transcribed correctly. The UI deliberately keeps these decisions separate.

## Dataset

`datasets/cpt316/topic1/questions.jsonl` has 50 rows. Every row contains:

```text
id, category, split, generation_review, question,
reference_answer, required_facts, evidence_groups
```

There are 15 development and 35 provisional test questions, 73 required evidence
groups, and 15 generation-review questions. Labels were assistant-authored and
source-checked but still await Bao Sheng's owner review. Alternatives inside a
group are OR; separate groups are AND. The answer/evidence fields are used only by
scorers and reviewers, never passed into query embedding, retrieval, or generation.

The Topic 1 source is a 38-page text-transcribed PDF. It is not an original-image
understanding test. Topic 2 and the two Topic 3 variants are stored as candidate
sources but have no reviewed question set or evaluation scores yet.

## Run the evaluation

From the repository root:

```powershell
# extraction and chunk checks only
uv run --project apps/api python evaluation/run_eval.py --extract-only

# extraction + storage + all three retrievers
uv run --project apps/api python evaluation/run_eval.py

# also generate the 15 selected answers with the configured real model
uv run --project apps/api python evaluation/run_eval.py --generate
```

Use another dataset only when it has the same documented contract:

```powershell
uv run --project apps/api python evaluation/run_eval.py --dataset evaluation/datasets/cpt316/topic1
```

Each new `runs/<UTC-run-id>/` contains, depending on requested scope:

```text
config.json              exact dataset/code/model/version hashes and settings
reference_pages.json     independent native PDF text reference
docling_structure_*.json raw Docling items and labels
extracted_items.json     content retained by NTBC filtering
chunks.json              actual chunks, pages, headings, token counts
checks.json              extraction/chunk/storage integrity checks
results.jsonl            one question+method trace per row
generation_answers.json  actual generated outputs (only with --generate)
generation_reviews.json  blank owner-review form; null is not a pass
summary.json             machine-readable aggregate metrics
summary.csv              tabular aggregate metrics
report.md                concise human-readable result
```

Run folders are ignored by Git because they can be large and environment-specific.
Archive important runs separately with their hashes; never silently edit them.

## Open the visual report

Open this self-contained file directly in a browser:

[Topic 1 baseline interactive review](reports/generated/topic1-baseline-review.html)

It combines the question, expected evidence, native page text, extraction, chunks,
top-five retrieval, generated answer, citations, exact metric calculation, assistant
opinion, and separate owner-review fields. It works offline.

Rebuild it from the historical baseline:

```powershell
uv run --project apps/api python evaluation/reports/build_review.py --run evaluation/runs/20261107T113258086748Z --compare-extraction evaluation/runs/20261107T115210823381Z --output evaluation/reports/generated/topic1-baseline-review.html
```

The compiler verifies the run's dataset provenance (including the recorded legacy
hashes), recomputes all stored retrieval metrics, and stops if they disagree.

## Scores and their exact meaning

- `Hit@k`: 1 when at least one required evidence group appears by rank k.
- `evidence_recall@5`: distinct required evidence groups found / groups required.
- `complete_evidence@5`: 1 only when every required group appears in the top five.
- `MRR@5`: reciprocal rank of the first matching chunk, else 0.
- extraction token fidelity: occurrence overlap only; it cannot prove order, arrows,
  table structure, or semantic relationships.
- answer-quality dimensions: manually rated 0/1/2. Pending reviews remain `null` and
  are excluded, not turned into zero or a pass.

The matcher requires the same document, a page range containing the expected page,
and a Unicode/case/whitespace-normalized exact quote. It is deterministic and
conservative: an equivalent paraphrase or evidence split across chunks can be a
false negative. Inspect failures in the HTML before interpreting a metric.

## Recorded Topic 1 baseline

On the 35 provisional test questions:

| Method | Hit@1 | Hit@5 | Evidence recall@5 | Complete@5 | MRR@5 | Median DB retrieval |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.829 | 0.971 | 0.948 | 0.914 | 0.887 | 4.4 ms |
| PostgreSQL keyword | 0.829 | 0.971 | 0.962 | 0.943 | 0.880 | 4.1 ms |
| Hybrid + RRF | 0.886 | 0.971 | 0.962 | 0.943 | 0.920 | 18.7 ms |

Hybrid improved first-hit ranking in this pilot but did not improve Hit@5 over the
other methods and tied keyword evidence recall. Timing excludes query embedding,
generation, HTTP, and UI. This small, related-question, single-document pilot does
not establish statistical significance or a universal winner.

The original extraction retained 70/73 evidence anchors (95.9%). The targeted
`code`-label filtering fix retained 71/73 (97.3%) in the later extraction-only run.
Retrieval and generation were not rerun after that fix, so no downstream improvement
is claimed.

## Tests

From the repository root:

```powershell
uv run --project apps/api pytest evaluation/tests -q
uv run --project apps/api ruff check evaluation
```
