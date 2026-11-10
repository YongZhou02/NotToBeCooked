# Query rewrite pilot — 10 November 2026

This pilot did not demonstrate an answer-quality improvement from rewrite
recovery. It compared the same 15 Topic 2 development questions (13 answerable,
2 unanswerable), using openai/gpt-oss-120b, the same source-code hashes, dataset
hashes, embedding model and hybrid top-5 retrieval configuration.

| Measure | Before | After |
|---|---:|---:|
| Strict full-reference-answer score (provisional AI review) | 10/15 (66.7%) | 8/15 (53.3%) |
| Partial credit: total points / 30 | 25/30 (83.3%) | 23/30 (76.7%) |
| Gold evidence-group recall@5 on 13 answerable questions | 67.95% | 67.95% |
| Grounded responses, which are not correctness scores | 13/15 | 13/15 |
| Appropriate refusals on unanswerable questions | 2/2 | 2/2 |
| Rewrite attempts | 0 | 2 |
| Adopted recovery answers | 0 | 0 |

The strict answer score combines correctness and required-fact completeness.
A score of 2 requires all substantive reference facts without a material error;
1 means partial coverage or a partly correct answer; 0 means incorrect or
missing. Correct refusals score 2 for unanswerable questions. Some deductions
are deliberately strict: for example, t2-001 names the right component but
does not mention the identifier-token handoff in the supplied required facts.
These are AI judgments, not human-verified accuracy. Topic 2's annotation
metadata also states that evidence-span human review is pending. The small
sample, strict rubric and ambiguous answers limit interpretation.

## What the feature actually changed

Only t2-007 and t2-013 triggered rewriting. Neither has an answer in the source.
The rewritten searches returned different page rankings, but both second
attempts remained unsupported. The application retained its appropriate initial
refusal in both cases. Added recovery latency was about 1.73 and 2.26 seconds
(mean 1.99 seconds per triggered question).

No answerable question triggered recovery. This sample therefore establishes
neither successful recovery of missing evidence nor a benefit on answerable
questions. The feature cannot fix an incorrect answer that the model already
marks grounded: its trigger is a source-free refusal.

The strict score fell on t2-004 (an unsupported `<<` example in the lecture's
relational-operator context) and t2-014 (missing distinguishing attributes).
Neither used rewriting, so this is not evidence that the rewrite step caused
regression. The two independent initial generations differed. Similarly,
t2-003's treatment explains precedence more accurately than baseline, but
retains an inconsistent description of the star and was conservatively scored
partial in both. Its wording change was also independent of rewriting.

## Per-question audit

| Question | Before /2 | After /2 | Reason for partial credit or change |
|---|---:|---:|---|
| t2-001 | 1 | 1 | Correct component; identifier-token handoff omitted |
| t2-002 | 2 | 2 | Lookahead and efficient buffering covered |
| t2-003 | 1 | 1 | Incorrect / inconsistent pattern interpretation |
| t2-004 | 2 | 1 | Treatment introduces unsupported `<<` example |
| t2-005 | 1 | 1 | Symbol-table attribute missing |
| t2-006 | 1 | 1 | Identifier/id classification not explicit |
| t2-007 | 2 | 2 | Correct refusal; rewrite finds no answer |
| t2-008 | 2 | 2 | Alphabet and string distinguished |
| t2-009 | 1 | 1 | Portability/efficiency required facts omitted |
| t2-010 | 2 | 2 | Two-buffer mechanism covered |
| t2-011 | 2 | 2 | Correct expression |
| t2-012 | 2 | 2 | LE / NE / GE mappings covered |
| t2-013 | 2 | 2 | Correct refusal; rewrite finds no benchmark |
| t2-014 | 2 | 1 | Treatment omits distinguishing attributes |
| t2-015 | 2 | 2 | No-matching-prefix lexical error covered |

Detailed judgments are in [ratings](query-rewrite-pilot-20261110-ratings.json).
Full paired answers and references are in the
[review](generated/query-rewrite-pilot-20261110-reviewed/review.md), with
[machine-readable results](generated/query-rewrite-pilot-20261110-reviewed/comparison.json).

## Quota handling and latency limitations

The first runs overlapped and hit Groq's 8,000-token-per-minute limit. Treatment
was interrupted after five saved answers. Baseline t2-010 and t2-011 failed with
429 errors; only those provider failures were retested. Original files were
preserved. No low-quality answer was rerun to improve its score.

The final comparison explicitly records the baseline retest and disjoint
treatment partitions, and validates matching code/data/model configuration.
The restarted jobs used 30-second inter-question spacing and process-local
GROQ_MAX_RETRIES=8. The first jobs used shorter spacing and default retries.

Observed mean generation times were 13.66 s before and 3.35 s after, but these
are confounded by quota waits, different spacing, independent requests and
provider conditions. They do not show that rewriting makes answers faster.
Inter-question spacing is outside the measured generation time. The two
recorded per-recovery increments are more relevant to the feature's added cost.

## Reproduce this comparison

```powershell
uv run --project apps/api python evaluation/compare_rewrite.py `
  evaluation/runs/20261110T071624838269Z `
  evaluation/runs/20261110T072657418320Z `
  --before-supplement evaluation/runs/20261110T072415333747Z `
  --after-prefix evaluation/runs/20261110T071921636369Z `
  --dataset evaluation/datasets/cpt316/topic2 `
  --ratings evaluation/reports/query-rewrite-pilot-20261110-ratings.json `
  --out evaluation/reports/generated/query-rewrite-pilot-reproduced
```

Use a new output directory. Generated artifacts may be ignored by Git; retain
raw run directories with the report if sharing the experiment.

For a stronger follow-up, test the held-out questions including t2-026, repeat
pairs in alternating order, space requests consistently, and have a person
review answers with condition labels hidden. Report results on all questions
and on the subset where answerable questions actually trigger recovery. Do not
replace this trigger with forced rewriting mid-experiment: that is a different
intervention requiring its own baseline.
