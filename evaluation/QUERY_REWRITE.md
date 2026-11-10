# Query rewrite recovery

Opt-in recovery for ordinary questions runs before answer generation. It scores
the original vector retrieval; when confidence is below the configured threshold,
it rewrites the question, retrieves once more, merges both ranked lists with
weighted reciprocal-rank fusion, and generates one answer from the merged evidence.
Summaries and fake mode skip recovery. The rewrite sees only the question and
previous user question; it never reads benchmark answers or evidence labels.

The retry uses the same owner, course, file scope and top-k. Rewrite failure
keeps the original retrieval. The normal citation grounding gate still checks
the single generated answer. Recovery adds one rewrite call, one query embedding
and one retrieval, but no second answer-generation call.

## Confidence calculation

The score is an explainable routing heuristic, not the probability that a chunk
or answer is correct. It uses cosine similarity from vector search, not hybrid
RRF scores (RRF scores are ranking values and are not calibrated relevance).

- `peak_component = clamp((best_similarity - 0.35) / (0.65 - 0.35), 0, 1)`
- A strong chunk has cosine similarity at least `0.48`.
- `support_component = clamp(strong_chunk_count / 3, 0, 1)`
- `confidence = 0.7 * peak_component + 0.3 * support_component`
- Rewrite when confidence is below `QUERY_REWRITE_CONFIDENCE_THRESHOLD` (default `0.50`).

The peak asks whether at least one passage is close to the question. Support
asks whether the result is backed by several passages instead of one accidental
match. In the measured Topic 2 corpus, t2-026 had similarities 0.507, 0.479,
0.477, 0.476 and 0.472: peak 0.523, support 0.333, confidence 0.466, so it
triggers rewriting. Thresholds are corpus-calibrated and must be revalidated on
held-out data; low confidence does not prove irrelevance, and high confidence
does not prove complete evidence or answer correctness.

Fusion gives the rewritten list a 1.2 discovery weight versus 1.0 for the
original list. This keeps a useful rewrite-only passage in top-k when several
old passages occur in both lists. A chunk found by both still ranks strongly.
The rewritten hybrid search also uses keyword:vector weights of 2:1. This helps
exact lecture terminology survive when a passage is strong in full-text search
but only moderately similar in embedding space; the original search remains 1:1.
It also runs one-term full-text probes for up to eight distinct content words
from the original question and keeps the best hit per term. Common framing words
are removed. Anchor results are interleaved with rewritten hybrid results before
fusion, so an exact `comment` passage is not hidden by broad topic pages.

## Enable in the app

Set `QUERY_REWRITE_ENABLED=true` in `apps/api/.env`, then restart the API.
Default is false. `QUERY_REWRITE_TIMEOUT_SECONDS` defaults to 15 seconds and
`QUERY_REWRITE_CONFIDENCE_THRESHOLD` defaults to 0.50. The rewrite request
itself does not retry quota errors.

## Paired evaluation

Run from the repository root, using identical model, corpus and question IDs:

```powershell
# Baseline: CLI explicitly disables rewrite, even if enabled in .env.
uv run --project apps/api python evaluation/run_eval.py --dataset evaluation/datasets/cpt316/topic2 --generate --question-id t2-026

# Treatment: real hybrid search on the rewritten query.
uv run --project apps/api python evaluation/run_eval.py --dataset evaluation/datasets/cpt316/topic2 --generate --question-id t2-026 --query-rewrite
```

The feature flag is recorded in each run manifest. In `generation_answers.json`:

- `generation_trace.retry_sources` and `retry_retrieval_metrics` record the final merged search.
- `scope_snapshots[].query_rewrite` records queries, page/chunk IDs, adoption,
  confidence components, errors and added latency. `accepted` means the merged
  retrieval was used, not that answer correctness was independently established.

Existing top-level retrieval scores remain first-pass scores. Compare retry
metrics separately; do not describe the existing report as final retrieval
performance. Review answers against the reference answer manually. Include
unanswerable questions to check whether recovery increases unsupported answers.
Use held-out questions for the final comparison; one example cannot establish
an improvement. Repeated calls can vary even with temperature zero.

For a 15-question pilot including two unanswerable questions, run both commands
with `--split dev --generate --generate-all --repeats 1` instead of a single
`--question-id`. Keep the recorded run directories, then compare them:

```powershell
uv run --project apps/api python evaluation/compare_rewrite.py evaluation/runs/BASELINE evaluation/runs/TREATMENT --dataset evaluation/datasets/cpt316/topic2 --out evaluation/reports/rewrite-pilot
```

The output includes `comparison.json` and `review.md`. Correctness ratings start
empty deliberately. Review each response against required facts: 0 incorrect or
missing, 1 partially correct, 2 fully correct. Report the fully-correct rate and
partial-credit score separately, alongside appropriate refusals, generation
failures, evidence recall and latency. Label AI reviews as provisional rather
than human-verified accuracy. Both runs generate initial answers independently,
so changes can also come from model variation; inspect the treatment's initial
draft and repeat the experiment before attributing differences to rewriting.

## Branch and ownership

Implemented on `feat/query-rewrite-retry`, based on the evaluation branch.
At creation, local main was 25 commits behind that branch. Merge the prerequisite
evaluation work first or extract the feature commits before targeting main.
No commits or remote publication are performed automatically. Existing local
LLM and dependency changes are separate from this feature.

This is AI-assisted implementation. Describe personal design, review, testing
and analysis accurately when reporting your contribution.
