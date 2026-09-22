# Chunk Retrieval Evaluation

Date: 2026-09-21

## Objective

Compare retrieval performance using maximum chunk sizes of 350 and 500 tokens.

## Corpus

- File: `controlled_retrieval_evaluation_corpus.pdf`
- Pages: 20
- Extracted items: 106
- Evaluation questions: 20
- Metric: Hit@5

A retrieved chunk is relevant only when:

1. its page range contains an expected page; and
2. its normalized text contains at least one approved evidence phrase.

## Controlled variables

Both configurations used the same:

- PDF;
- extracted text;
- normalization;
- embedding model;
- query vectors;
- hybrid-search configuration;
- metadata filters;
- final result limit;
- evaluation questions.

Only `max_token` changed.

## Results

| Configuration | Chunks produced | Hit@5 |
|---|---:|---:|
| 350 tokens | 34 | 20/20 (100.0%) |
| 500 tokens | 20 | 20/20 (100.0%) |

## Interpretation

No Hit@5 difference was observed on this controlled corpus. Both configurations retrieved at least one relevant chunk in the top five for every question.

The 500-token configuration produced fewer chunks while achieving the same Hit@5. This result does not establish that 500-token chunks are generally superior; it applies only to this corpus, question set, embedding model, and search configuration.

Because both configurations reached 100%, the benchmark has a ceiling effect and does not distinguish their ranking quality beyond the top-five success criterion.

## Data isolation

Evaluation rows were created inside a database transaction and rolled back after the experiment. The 350-token and 500-token chunk sets used separate ingestion runs, with only one run active during each measurement.