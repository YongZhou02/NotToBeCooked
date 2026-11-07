# Decisions

Each entry says what we did first, then why we did it.

1. organize and centralized the whole evaluation harness.
2. prompt the harness to be minimalistic, no backend logic and how i want the UI to appear. objective is to at least be able to visualize all the ai written questions, answer keys. this is to make sure the questions are hard and realistic, answer keys are verified manually by human.
3. put question marks UI to inform us on each component, what they means to answer where and what the number means
4. organize the eval harness to 3 tabs: dashboard, evaluate and visualize. Visualise enable humans to visualize the questions, answer keys. able to edit unverified answer keys and AI written questions can be added too
5. Committed the existing dashboard work on a new local branch, `calvin-feat-evaluation-overnight`. We did this so a pull cannot remove the work again, and so the shared branch with Bao Sheng stays untouched until you review it.
6. Set the rules for the overnight work: fix the evaluation first and build React second, change only `evaluation/` and never `apps/api`, and use at most about 500 Groq calls. We fix first because React only displays the scores, so the scores must be trustworthy before we display them nicely.
7. Recorded the model's raw draft and the exact reason for every blocked answer in each run. We did this because the app only wrote those reasons to a log, so nobody could see why students got no answer.
8. Found why almost every Groq answer was blocked: the model gave a valid quote for all 20 citations, but it left the `[1]` markers out of the answer text (one answer used `【5】` instead). The check treated this as a failure, so 0 of 15 answers reached the student. This is a format failure and not a knowledge failure, and no stage score could show it.
9. Re-ran the evaluation on the finalized labels. We did this because every earlier score used the old labels. Test Hit@5 dropped from 0.971 to 0.912, so the old number was too high.
10. Changed the goal of the overnight work: find and define every concern, and do not try to solve them yet. We dropped the pipeline variants and proposals because the team will write its own questions, and those questions need a harness that shows problems clearly.
11. Scheduled a wake-up for 6:15am. We did this so the work can continue if tokens run out before the 6:10am reset.
