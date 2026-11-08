# Citation check replay

Run: `20261108T004258996111Z`. 79 saved answers from the production model. No new model calls were made.

## What was tested

The production check blocks an answer when the model lists a citation but forgets to write the marker, like [1], in the answer text. Most blocked answers were blocked for only that reason. Three other ways of checking were tried on the same saved answers. In all of them, a quote must still be found word for word on the page it names.

- **prod**: the real production check, unchanged.
- **marker_styles**: turns marker styles like 【1】 and (1) into [1] first. A (1) is changed only when 1 is a listed citation and it is not a list number such as "(1) Compiler".
- **quote_only**: shows the answer when every quote is on its page. It ignores only the "listed but never referred to" problem.
- **auto_marker**: adds the missing [n] after the sentence that best matches the quote, then runs the unchanged production check.

Checking the replay itself: the replayed production check gave the same result as the saved run for all 78 answers that have a draft (1 answer had no draft because the model call failed).

## Results

Judge grades are from the AI judge (qwen), which graded the draft whether or not it was shown. Grades are written as correct / partly correct / wrong.

| Variant | Shown | Blocked | Rescued vs prod | Judge on all shown | Judge on rescued |
|---|---|---|---|---|---|
| prod | 15 | 64 | 0 | 10 / 2 / 3 | - |
| marker_styles | 17 | 62 | 2 | 11 / 2 / 4 | 1 / 0 / 1 |
| quote_only | 75 | 4 | 60 | 61 / 7 / 7 | 51 / 5 / 4 |
| auto_marker | 75 | 4 | 60 | 61 / 7 / 7 | 51 / 5 / 4 |

(Shown counts include honest "not in the notes" answers, which production already shows.)

The answers that looked like they used "(1)" markers were checked by hand. They wrote "LL(1)", which is the name of a parsing method, not a citation. marker_styles leaves these alone on purpose. Only the 【1】 style was a real marker, in 2 answers.

## Risks

**marker_styles**
- Unanswerable question s1-029 was rescued. Judge grade: wrong. This is a real risk.
- No rescued answer was rated wrong by the judge.

**quote_only**
- Unanswerable question s1-029 was rescued. Judge grade: wrong. This is a real risk.
- s1-002 was rescued but the judge rated it wrong: The answer describes an LL(1) parsing table, which is completely unrelated to the symbol table described in the reference.
- s1-003 was rescued but the judge rated it wrong: The answer addresses parsing table construction steps rather than the compiler phases requested in the reference.
- s1-024 was rescued but the judge rated it wrong: The answer incorrectly claims the splits are identical, ignoring that the front end includes intermediate code generation and symbol table creation.

**auto_marker**
- Unanswerable question s1-029 was rescued. Judge grade: wrong. This is a real risk.
- s1-002 was rescued but the judge rated it wrong: The answer describes an LL(1) parsing table, which is completely unrelated to the symbol table described in the reference.
- s1-003 was rescued but the judge rated it wrong: The answer addresses parsing table construction steps rather than the compiler phases requested in the reference.
- s1-024 was rescued but the judge rated it wrong: The answer incorrectly claims the splits are identical, ignoring that the front end includes intermediate code generation and symbol table creation.

## The quote failures

3 answers have a quote that is not on its page. No variant shows them, which is correct: the check works as it should here.

- t1-015 (blocked in every variant): the model put a full stop between two lines. The page reads "t1 = id3 * 60.0 id1 = id2 + t1" with no full stop. It also wrote no marker.
- t1-041 (blocked in every variant): the model joined two separate lines of the page into one sentence ("Output of analysis = ..." and "Input to synthesis = ..."). Other text sits between them on the page. It also wrote no marker.
- t1-044 (blocked in every variant): the page has arrows with brackets, like "-> [Compiler] -> Target Assembly Program". The model rewrote them as "Compiler -> Target Assembly Program", which is not on the page. It did write markers, so this is its only problem.

## Where auto_marker put the markers

It added markers to 60 answers (82 markers in all). 6 answers got markers on more than one sentence. 11 placements were weak matches (little shared wording between the quote and the sentence). A person should look at those before this is trusted. The sentence chosen for each marker is kept in the replay (the `changes` of each report).

## Recommendation

Today a student sees an answer for only 15 of these 79 questions, because the check blocks answers whose quotes are fine but whose [n] markers are missing. Adding the missing markers (auto_marker) would show 75 answers, and each one still has to pass the full quote check, so no made-up quote gets through. Of the 60 newly shown answers the judge rated 51 correct and 4 wrong. auto_marker is better than quote_only because it shows the same answers but with clickable citations, so the student can see which line supports which sentence; quote_only would show plain text with no markers at all. Fixing the marker styles helps only 2 answers, so it is a small extra, not the fix. The cost is that the old check was also hiding some bad answers by accident: the wrong ones quote real lines but answer a different question, or go along with a wrong idea in the question. The quote check cannot catch those. So this change should go together with a check that the answer is about what was asked, and a person should read the weak marker placements first.

