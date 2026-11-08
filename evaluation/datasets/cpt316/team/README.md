# Team questions

One file per person, so git never has to merge two people's work.

1. Run `pnpm dev:evaluation` and edit, verify or add questions. Every change is saved straight to
   `team/<your first name>.json` (from `git config user.name`; set `EVAL_REVIEWER=aisha` to choose).
   The header says where it saved. If it says the file changed elsewhere, reload the page.
2. Without the dev server (the static build), edits stay in the browser: use Export and save the file here by hand.
3. From the repo root, run `uv run --project apps/api python evaluation/builder/merge_team_questions.py`.
4. Read the printed list of skipped rows and fix them in your file. Run the merge again.
5. Commit your file together with `all/questions.jsonl` and `all/merge_report.json`.

You can also paste question rows into your file by hand (a JSON list of rows is fine).
Your ids get your file name in front, so your `human-001` never clashes with anyone else's.
