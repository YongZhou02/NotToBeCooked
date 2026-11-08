# Team questions

One file per person, so git never has to merge two people's work.

1. In the dashboard, open Export and tick **Human-written only**.
2. Save the file here as `team/<yourname>.json`, for example `team/aisha.json`.
3. From the repo root, run `uv run --project apps/api python evaluation/builder/merge_team_questions.py`.
4. Read the printed list of skipped rows and fix them in your file. Run the merge again.
5. Commit your file together with `all/questions.jsonl` and `all/merge_report.json`.

You can also paste question rows into your file by hand (a JSON list of rows is fine).
Your ids get your file name in front, so your `human-001` never clashes with anyone else's.
