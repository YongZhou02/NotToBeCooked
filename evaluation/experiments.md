# Experiments

Every experiment we ran on the answer pipeline, newest last. Each one says what we wanted to know, how we tested it, what we found, and which problems in [problems.md](problems.md) it touches.

**Rules**

- An experiment gets the next number (E1, E2, ...). Numbers are never reused or renumbered.
- Write the result even when it is bad or unclear. A failed idea is still a result.
- Name the evidence: the run folder, the report file, and the commit. Run folders live in `evaluation/runs/` or `evaluation/playground/runs/` and are not in git, so also copy the key numbers here.
- Mark AI-judge numbers "AI judge". Nobody has checked the judge against a human yet.
- A single run is noisy. The production keyword and hybrid search can move by about 1 point on Hit@5 with nothing changed (see E6), so treat smaller differences as no difference.

---

### E1. Do students get any answer at all?

- **Date:** 7 Nov 2026
- **Question:** The stage scores look good. Does the student actually see an answer?
- **Setup:** Topic 1 PDF, 15 questions, production pipeline with `openai/gpt-oss-120b`. Runs `20261107T171830707014Z` and `20261107T172603387342Z`.
- **Result:** Retrieval looked fine (test Hit@5 0.971), but **0 of 15 answers reached the student**. The app wrote the reason only to a log, so the run could not show why.
- **What it means:** The scores we had measured each stage alone. None of them measured what the student receives.
- **Led to:** Recording the model's raw draft and the exact block reason in every run (decision 7).
- **Problems:** [P1](problems.md#p1), [P10](problems.md#p10)

### E2. Why were all the answers blocked?

- **Date:** 7 Nov 2026
- **Question:** With the draft and block reason recorded, what is blocking the answers?
- **Setup:** Same 15 questions, re-run on the finalized gold labels. Run `20261107T192742115989Z`.
- **Result:**
  - All 20 citations had a real quote from the right source, but the model **left the `[n]` markers out of the answer text**. One answer used `【5】` instead. The check blocked all 15.
  - Test Hit@5 dropped from 0.971 to 0.912 on the finalized labels. The old labels made retrieval look better than it was.
- **What it means:** This was a format failure, not a knowledge failure.
- **Problems:** [P1](problems.md#p1), [P2](problems.md#p2), [P9](problems.md#p9)

### E3. Full run: four PDFs, 79 questions, AI judge

- **Date:** 8 Nov 2026
- **Question:** On a bigger, harder set, what does the student get, and are the answers any good?
- **Setup:** Four PDFs, 80 questions: 50 AI-written, 30 hard "student-style" questions including 5 the notes cannot answer. Production hybrid search plus `gpt-oss-120b`. The `qwen` AI judge graded every draft, blocked or not. Concerns were measured after the run. Run `20261108T004258996111Z`, commit `d7422aee`.
- **Result** (AI judge for grades):

  | Measure | Result |
  |---|---|
  | Answers shown / blocked / failed | 15 / 63 / 1 of 79 |
  | Blocked drafts the judge called fully correct | 54 of 63 |
  | Hybrid Hit@5, dev / test / stress | 0.866 / 0.911 / 0.84 |
  | Unanswerable questions that got an answer | 2 of 5 |
  | Citations pointing at a page with no gold evidence | 34 of 117 |
  | Chunks with a heading that is not on their page | 63 of 67 |
  | Rank-1 result from the wrong PDF | 7 of 74 |
  | Median wait / answers over 10 s | 7.3 s / 24 of 79 |

- **What it means:** Most answers are good but thrown away. Several other problems sit behind that one and were never visible before.
- **Problems:** [P1](problems.md#p1), [P5](problems.md#p5), [P6](problems.md#p6), [P7](problems.md#p7), [P11](problems.md#p11), [P12](problems.md#p12), [P13](problems.md#p13), [P14](problems.md#p14), [P15](problems.md#p15)

### E4. What exactly is wrong with the 63 blocked answers?

- **Date:** 8 Nov 2026
- **Question:** Is it a formatting issue, missing evidence, a mistake in our check, or a mistake by the model?
- **Setup:** Read the block reasons and drafts of all 63 blocked answers from E3, and the production check in `apps/api/app/services/grounding.py`. No model calls.
- **Result:**

  | Cause | Count |
  |---|---|
  | Real quotes, but **no marker anywhere** in the answer text | 58 |
  | Real quotes, marker written as `【n】`, which the check does not read | 2 |
  | A quote not really on the page, and no marker either | 2 (t1-015, t1-041) |
  | A quote not really on the page, with correct markers | 1 (t1-044) |

  - 60 of 63 were blocked **only** because a marker was missing or unreadable.
  - The 3 bad quotes come from the model glueing two lines into one (t1-015, t1-041) or rewriting the page's `-> [Compiler] ->` as `Compiler -> ...` (t1-044).
  - The prompt clearly asks for markers in the text (`apps/api/app/services/prompt.py`, the CITING section). The model ignores it.
  - A first count also listed three `(1)`-style markers. E5 showed these are `LL(1)` and `(60)`, which are normal text, not markers.
- **What it means:** The evidence is there, so this is not a gold-label problem. The model does break the marker rule. But our design blocks a correct, quoted answer over a missing pointer: the citation list already links each quote to its source, and the marker only says which sentence it belongs to.
- **Problems:** [P1](problems.md#p1), [P2](problems.md#p2), [P3](problems.md#p3)

### E5. Citation replay: four ways to check the same answers

- **Date:** 8 Nov 2026
- **Question:** If the check handled markers differently, how many answers would students see, and would those answers be good?
- **Setup:** Replayed the 78 saved drafts from E3 through four checks. No new model calls. First, the replay of the production check matched the saved results exactly, 78 of 78. Code: `playground/toolkit/citation.py` and `playground/replay_citations.py`. Report: [playground/reports/citation_replay.md](playground/reports/citation_replay.md). Commit `15f4165`.
  - **prod:** today's check.
  - **marker_styles:** turn `【n】` into `[n]` first. A `(n)` is changed only under strict rules, so `LL(1)` and list numbering stay as they are.
  - **quote_only:** ignore only the "listed but never referred to" rule. Every other rule still applies.
  - **auto_marker:** put the missing `[n]` after the sentence that best matches its quote, then run the normal check.
- **Result** (AI judge for grades):

  | Check | Shown | Rescued vs prod | Judge on rescued: correct / partly / wrong |
  |---|---|---|---|
  | prod | 15 | – | – |
  | marker_styles | 17 | 2 | 1 / 0 / 1 |
  | quote_only | 75 | 60 | 51 / 5 / 4 |
  | auto_marker | 75 | 60 | 51 / 5 / 4 |

  - The 3 made-up quotes stayed blocked in every check.
  - auto_marker placed 82 markers in 60 answers. 11 placements are weak matches, mostly in t1-028, s1-004 and s1-021, and nobody has checked whether each marker sits on the right sentence.
  - The rescued answers rated wrong were s1-029 (an unanswerable question with a false premise), s1-002 and s1-003 (a real quote about the LL(1) table, but not what was asked), and s1-024 (wrongly says two things are identical).
- **What it means:** Most blocked answers are good. But ignoring the marker rule is not a fix. The student would get answers whose citations may sit on the wrong sentence, and the 4 wrong answers show that a quote check cannot tell whether an answer fits the question.
- **Problems:** [P1](problems.md#p1), [P2](problems.md#p2), [P5](problems.md#p5), [P6](problems.md#p6)

### E6. Playground baseline: reproduce production, try an in-memory search

- **Date:** 8 Nov 2026
- **Question:** Can the playground reproduce production exactly, so later experiments compare fairly? Is a simple search without a database any good?
- **Setup:** Chunk version v1, the exact 198 chunks of E3, locked by a fingerprint. The production vector, keyword and hybrid search ran through the playground against the Postgres test database. `memory_hybrid` merges an in-memory meaning search (production embedding model) and a word search (BM25) with RRF. 74 answerable questions. Code: `playground/run.py`, `playground/toolkit/retrieval.py`. Commit `345a2e7`.
- **Result:**

  | Search | Hit@1 | Hit@5 | Recall@5 | MRR@5 |
  |---|---|---|---|---|
  | prod vector | 0.662 | 0.878 | 0.851 | 0.744 |
  | prod keyword | 0.622 | 0.784 | 0.764 | 0.685 |
  | prod hybrid | 0.703 | 0.878 | 0.858 | 0.763 |
  | memory_hybrid | 0.730 | **0.919** | 0.883 | 0.806 |

  - The production numbers match E3 exactly, on every split.
  - Production keyword search returns equal-score matches in a different order on each run, so keyword and hybrid move by about 0.005 to 0.015 between runs. Vector and in-memory search give the same result every time.
- **What it means:** The playground is a fair test bed. The in-memory search is a lead worth checking (hit@5 0.919 against 0.878), but it has only been tested on one question set.
- **Problems:** [P7](problems.md#p7), [P8](problems.md#p8)
