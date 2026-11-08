# Problems and tested solutions

Every problem we have found in what students get, and every fix we have tested for it. A tested fix always names the experiment in [experiments.md](experiments.md) that tested it, so the claim can be checked.

**Rules**

- A problem gets the next number (P1, P2, ...). Numbers are never reused.
- **Status** is one of:
  - **Open:** no fix tested yet.
  - **Fix tested:** an experiment shows a fix works, but it is not in the app.
  - **Fixed in app:** the fix is in `apps/api` and a run after the change confirms it.
  - **Won't fix:** we decided to live with it, and the reason is written down.
- Every row in "Tested solutions" names its experiment (E-number). A fix with no experiment is an idea, and it goes under "Ideas not tested yet".
- Many problems match a concern in [concerns.md](concerns.md). The concern says how we measure the problem. This file says what we tried.
- `tests/test_problem_links.py` checks that every E-number here exists in experiments.md.

## Summary

| # | Problem | Student feels | Status |
|---|---|---|---|
| [P1](#p1) | Correct answers blocked because the `[n]` marker is missing | "It never answers me" | Open |
| [P2](#p2) | Markers written as `【n】` are not read | "It never answers me" | Fix tested |
| [P3](#p3) | The model's quote is not exactly on the page | "It never answers me" | Open |
| [P4](#p4) | A blocked answer is a dead end | "Useless, try again?" | Open |
| [P5](#p5) | Real quotes, but the answer does not fit the question | "That's not what I asked" | Open |
| [P6](#p6) | Questions the notes cannot answer get an answer anyway | "It made that up" | Open |
| [P7](#p7) | Search misses the right page | "It doesn't know my notes" | Open (lead in E6) |
| [P8](#p8) | Keyword search order changes between runs | (scores are noisy) | Open |
| [P9](#p9) | Old gold labels made retrieval look better | (scores too high) | Fixed |
| [P10](#p10) | We could not see why answers were blocked | (problems hidden) | Fixed |
| [P11](#p11) | A model call failed and nobody knows why | "It broke" | Open |
| [P12](#p12) | The AI judge is not checked by a human | (scores may be wrong) | Open |
| [P13](#p13) | Citations point at pages with no gold evidence | "The source doesn't say that" | Open |
| [P14](#p14) | Chunk headings that are not on their page | "The source label is wrong" | Open |
| [P15](#p15) | Long waits | "It's so slow" | Open |

---

<a id="p1"></a>
### P1. Correct answers are blocked because the `[n]` marker is missing

- **What the student sees:** "An answer was written, but its citations could not be checked", even though the answer and its quotes were correct.
- **Size:** 60 of 79 answers in E3 (58 with no marker at all, 2 with `【n】`, see P2). The judge called most of them correct.
- **Cause:** The model puts real quotes in the citation list but leaves the `[n]` marker out of the answer text, even though the prompt asks for it. The check then blocks the whole answer. The citation list already links each quote to its source. The marker only says which sentence the quote supports.
- **Concern:** 1. Good answers are thrown away.
- **Found in:** E1, E2, E4
- **Status:** Open. Ignoring the rule is not acceptable: every shown answer must carry correct citations.

**Tested solutions**

| Solution | Experiment | Result | Verdict |
|---|---|---|---|
| Ignore the missing-marker rule, keep every other rule | E5 | 15 → 75 shown. Judge on the 60 rescued: 51 correct, 5 partly, 4 wrong. | Rejected. The answer has no marker at all, so the student cannot see which sentence each source supports. |
| Place the missing marker ourselves, after the best-matching sentence | E5 | 15 → 75 shown, 82 markers placed, 11 of them weak matches. Nobody checked whether markers sit on the right sentence. | Promising, not proven. Needs a check of where the markers land. |

**Ideas not tested yet**

- Ask the model for sentences that each carry their own sources (`[{text, cites:[1]}]`), so a marker cannot go missing.
- When markers are missing, ask the model once more to add them, giving it its own answer and quotes.
- Try other generation models: does another model follow the marker rule?
- Measure marker placement directly: a person, or a judge, checks whether each placed marker sits on a sentence its quote supports.

<a id="p2"></a>
### P2. Markers written as `【n】` are not read

- **What the student sees:** Same as P1.
- **Size:** 2 of 79 in E3 (t1-049, s1-029). Also 1 of 15 in E2.
- **Cause:** The check only reads `[n]`.
- **Found in:** E2, E4
- **Status:** Fix tested.

**Tested solutions**

| Solution | Experiment | Result | Verdict |
|---|---|---|---|
| Turn `【n】` into `[n]` before the check. Change `(n)` only under strict rules, so `LL(1)` and list numbers stay. | E5 | 15 → 17 shown. One rescued answer is correct (t1-049). The other (s1-029) answers a question the notes cannot answer, see P6. | Works for the marker. The wrong answer it revealed belongs to P6. |

<a id="p3"></a>
### P3. The model's quote is not exactly on the page

- **What the student sees:** The answer is blocked. This block is correct: the quote is not really in the notes.
- **Size:** 3 of 79 in E3 (t1-015, t1-041, t1-044).
- **Cause:** The model glues two lines into one sentence (t1-015, t1-041) or rewrites arrows from a diagram (t1-044).
- **Found in:** E4
- **Status:** Open. Must stay blocked until the quote is right.

**Tested solutions:** none yet. E5 confirmed all 3 stay blocked in every citation check, which is correct.

**Ideas not tested yet**

- Ask the model once more to copy the quote exactly, showing it the failed quote and the source.
- Let a quote span two lines when each part is on the page word for word.

<a id="p4"></a>
### P4. A blocked answer is a dead end

- **What the student sees:** "Try asking again", with nothing useful.
- **Size:** Every blocked answer: 63 of 79 in E3.
- **Found in:** E3
- **Status:** Open.

**Tested solutions:** none yet.

**Ideas not tested yet**

- Show the verified quotes from the notes instead of nothing ("Here is what your notes say: ...").

<a id="p5"></a>
### P5. Real quotes, but the answer does not fit the question

- **What the student sees:** A confident answer, with a real source, that does not answer what they asked.
- **Size:** 3 answers rescued in E5 (s1-002, s1-003, s1-024). Today they are hidden by P1, so fixing P1 alone would show them.
- **Cause:** The quote check only asks "is the quote on the page?". It never asks "does this answer the question?".
- **Concern:** 2. Wrong or half answers.
- **Found in:** E3, E5
- **Status:** Open. Must be solved together with P1.

**Tested solutions:** none yet.

**Ideas not tested yet**

- An on-topic check after generation: does the answer address the question, and do the quotes support it?
- Rewrite the question or rerank the results, so a better source is found before the answer is written.

<a id="p6"></a>
### P6. Questions the notes cannot answer get an answer anyway

- **What the student sees:** An answer to something the notes never say, for example a question with a false premise.
- **Size:** 2 of 5 unanswerable questions in E3 (s1-027 shown today, the judge says wrong). s1-029 would also be shown if P1 or P2 were fixed.
- **Concern:** 5. Saying "I do not know".
- **Found in:** E3, E5
- **Status:** Open.

**Tested solutions:** none yet.

**Ideas not tested yet**

- A retrieval gate: if the best sources are weak, say "this is not in your notes" before writing an answer.
- A false-premise check: does the question assume something the sources contradict?

<a id="p7"></a>
### P7. Search misses the right page

- **What the student sees:** An answer from the wrong part of the notes, or "not in your notes" when it is.
- **Size:** Production hybrid Hit@5 0.878 over all answerable questions, 0.84 on stress questions (E3, E6). 7 of 74 questions had a rank-1 result from the wrong PDF.
- **Concerns:** 4. Real student wording. 9. Answers from the wrong PDF.
- **Found in:** E3
- **Status:** Open, with a lead.

**Tested solutions**

| Solution | Experiment | Result | Verdict |
|---|---|---|---|
| In-memory search: meaning search plus BM25 word search, merged with RRF | E6 | Hit@5 0.919 against 0.878 for production. MRR@5 0.806 against 0.763. | Lead. One question set only. Check on the team's questions, and check whether better retrieval changes the answers. |

<a id="p8"></a>
### P8. Keyword search order changes between runs

- **Effect:** Production keyword and hybrid numbers move by about 0.005 to 0.015 between runs with nothing changed, so small differences mean nothing.
- **Cause:** Postgres returns equal-score matches in storage order, which shifts between runs.
- **Found in:** E6
- **Status:** Open. Written down in the playground README. A real fix needs a tie-break in `apps/api` search.

**Tested solutions:** none yet.

<a id="p9"></a>
### P9. Old gold labels made retrieval look better than it was

- **Effect:** Test Hit@5 was 0.971 on the old labels and 0.912 on the finalized labels.
- **Found in:** E2
- **Status:** Fixed. Every run since E2 uses the finalized labels (decision 9).

<a id="p10"></a>
### P10. We could not see why answers were blocked

- **Effect:** In E1, 0 of 15 answers were shown, and the run could not say why.
- **Found in:** E1
- **Status:** Fixed. Every run now records the raw draft and the exact block reason (decision 7). E2 used this to find P1.

<a id="p11"></a>
### P11. A model call failed and nobody knows why

- **What the student sees:** An error instead of an answer.
- **Size:** 1 of 79 in E3 (t1-013). The model's reply failed validation, so there is no draft.
- **Found in:** E3
- **Status:** Open. Not looked into yet.

<a id="p12"></a>
### P12. The AI judge is not checked by a human

- **Effect:** Every correctness number comes from the `qwen` judge. In E3 it also graded the failed answer's error message as if it were an answer.
- **Concern:** 11. Can we trust the score?
- **Found in:** E3
- **Status:** Open.

**Ideas not tested yet**

- A person grades a sample, for example 20 answers, and we measure how often the judge agrees.

<a id="p13"></a>
### P13. Citations point at pages with no gold evidence

- **Size:** 34 of 117 citations in E3. Some may be fair (the same fact on another page), some may be wrong.
- **Concern:** 6. Citations that do not help.
- **Found in:** E3
- **Status:** Open. Not looked into yet.

<a id="p14"></a>
### P14. Chunk headings that are not on their page

- **Size:** 63 of 67 headed chunks in E3 carry a heading that is not on their pages.
- **Concern:** 8. Wrong headings and page data.
- **Found in:** E3
- **Status:** Open. Not looked into yet. A new chunk version would be needed to test a fix (see the playground README).

<a id="p15"></a>
### P15. Long waits

- **Size:** Median wait 7.3 s. 24 of 79 answers took over 10 s (E3).
- **Concern:** 10. Long waits.
- **Found in:** E3
- **Status:** Open. Not looked into yet.
