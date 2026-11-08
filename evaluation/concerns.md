# Concerns

A high score can hide a bad experience. Each concern below is a problem a student can feel.
We measure it, but we do not fix it here. The numbers for each run are in
`runs/<run>/concerns.json`. Create that file with:

```powershell
uv run --project apps/api python evaluation/run_concerns.py
```

Any number marked "AI judge, not yet checked by a human" comes from a second AI model.
It is a guide, not the truth. A person must check it before we trust it.

## 1. Good answers are thrown away

- The student feels: "I asked a clear question and the app said it could not show an answer."
- We measure it: we count answers that the app's own check blocked, and the reason for each. The judge then grades the blocked drafts.
- A bad result looks like: many blocked answers, most of them judged fully correct.

## 2. Wrong or half answers

- The student feels: "The app sounded sure, but the answer was wrong or missed a part."
- We measure it: the judge compares each draft with the reference answer and the required facts.
- A bad result looks like: many answers that the judge scores 0 or 1 instead of 2.

## 3. Dead or copied answers

- The student feels: "The answer just repeats the slide, or it is one short line. It does not help me."
- We measure it: we count how much of the answer is copied word for word from the sources, how long it is, and how helpful the judge thinks it is.
- A bad result looks like: answers that are almost all copied, very short, or scored as flat.

## 4. Real student wording

- The student feels: "It works when I write a neat question. It fails when I write like I really do."
- We measure it: we compare clean questions with stress questions (vague, typo, manglish, explain, cross-part). We look at search results and at the final answer.
- A bad result looks like: a big drop in scores from clean questions to stress questions.

## 5. Saying "I do not know"

- The student feels: "I asked about something the notes never cover, and the app made up an answer." The reverse also hurts: the app refuses a question the notes do cover.
- We measure it: on questions with no answer in the notes, we check if the app said so. On the other questions, we count false refusals.
- A bad result looks like: invented answers to unanswerable questions, or many refusals of good questions.

## 6. Citations that do not help

- The student feels: "I opened the source and it was the wrong page, or it did not prove the answer."
- We measure it: we check if each cited chunk is on a page that holds the true evidence. The judge also checks if the quotes back the claims.
- A bad result looks like: many citations off the true pages, or claims the quotes do not support.

## 7. Text lost before the model sees it

- The student feels: "The answer is in my slides, but the app never saw that text."
- We measure it: we compare the PDF text with what extraction kept and with what survived chunking.
- A bad result looks like: required evidence missing from the chunks, or pages that keep little of their words.

## 8. Wrong headings and page data

- The student feels: "The heading says one topic, but the text under it is about another."
- We measure it: we check if each chunk's heading appears on the pages the chunk covers. We also count missing headings and tiny chunks.
- A bad result looks like: one heading repeated on many chunks, or most headings missing from their own pages.

## 9. Answers from the wrong PDF

- The student feels: "I asked about one lecture and the answer came from another file."
- We measure it: for each question we check if the top search results come from a PDF with the true evidence. The two Topic 3 PDFs may share text, so we list those cases for a person to check.
- A bad result looks like: the first result often comes from the wrong file.

## 10. Long waits

- The student feels: "I waited so long that I gave up."
- We measure it: we time each answer. We report the middle time, the slow end, and the share over 10 seconds. These times include waiting for Groq rate limits.
- A bad result looks like: many answers that take more than 10 seconds.

## 11. Can we trust the score?

- The student feels: nothing directly. The team feels it: the dashboard shows a clean number that may not mean much.
- We measure it: we count questions by author and review status, give the 95% range on the pass rate, and show how many points one question is worth. We compare with a random search baseline and test the judge with known right and wrong answers.
- A bad result looks like: a wide range, few reviewed questions, a random search that scores close to the real one, or a judge that fails its own checks.

## 12. Follow-up questions (not measured)

- The student feels: "I asked 'what about the second one?' and the app did not know what I meant."
- We measure it: we do not. The harness asks one question at a time.
- A bad result looks like: unknown. We need two-turn tests first.

## 13. Real slides with pictures (not measured)

- The student feels: "My real slides have images and diagrams, and the app misses them."
- We measure it: we do not. The test PDFs are text copies, so extraction scores may be too high.
- A bad result looks like: unknown. We need a few real, untouched slide PDFs first.

## 14. Search inside a big shared database (not measured)

- The student feels: "On the real server, search for my file returns too few results."
- We measure it: we do not. Search filters by file, and in a big shared table the index may return too few rows. A nearly empty test database cannot show this.
- A bad result looks like: unknown. We need a large database to test it.
