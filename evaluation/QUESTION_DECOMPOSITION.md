# Selective question decomposition

This opt-in retrieval enhancement targets questions that need evidence for
multiple facts. A conservative local router handles simple questions without an
extra model call. For a complex question, one bounded LLM call creates two or
three self-contained sub-questions. It receives at most 1,250 characters of
first-pass retrieval hints so vague references can use concrete lecture terms;
unrelated hints are treated as distractors. NTBC retrieves at most three chunks
for each, merges the original and sub-question rankings with reciprocal-rank
fusion, and generates the final answer once from the original question. The
merge keeps at most one chunk per file/page so overlapping chunks do not displace
a different page needed for another fact.

The decomposition and low-confidence query rewrite routes are mutually exclusive
for a turn. Complex questions use decomposition; other low-confidence questions
may use rewrite. This prevents two auxiliary LLM calls for the same request.

## Token and latency bounds

- Zero decomposition tokens for questions rejected by the local complexity router.
- One decomposition call for selected questions.
- Two to three sub-questions, capped by
  `RETRIEVAL_DECOMPOSITION_MAX_QUESTIONS` (default 3).
- No sub-answer generation; sub-questions are retrieval queries only.
- One final answer-generation call, exactly as in the baseline.
- Provider or parsing failure keeps the original retrieval.

Enable with `RETRIEVAL_DECOMPOSITION_ENABLED=true`. The feature is disabled by
default. Traces are stored under `scope_snapshot.question_decomposition`.

## Paired evaluation

Use identical question IDs and compare the baseline against treatment:

```powershell
uv run --project apps/api python evaluation/run_eval.py `
  --dataset evaluation/datasets/cpt316/topic1 --generate `
  --question-id t1-042 --question-id t1-043

uv run --project apps/api python evaluation/run_eval.py `
  --dataset evaluation/datasets/cpt316/topic1 --generate `
  --question-id t1-042 --question-id t1-043 --question-decomposition
```

Primary metrics are complete evidence and evidence recall, followed by a blinded
0/1/2 correctness review. Grounded status is not an accuracy metric. Include
simple questions and unanswerable questions in a larger held-out evaluation to
measure false-positive routing and unsupported-answer regressions.
