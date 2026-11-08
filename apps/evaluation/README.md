# Evaluation Hub (React)

A static review tool for the RAG evaluation harness. It is the React version of
`evaluation/dashboard/` (which stays in place). People use it to read AI-written
questions beside the source PDF, edit them, write their own, and export a chosen
set. There is no backend.

## Run it

From the repository root:

```powershell
pnpm install
pnpm dev:evaluation          # http://localhost:5173
```

Other scripts, from the root with `--filter evaluation` or inside `apps/evaluation`:

```powershell
pnpm --filter evaluation typecheck
pnpm --filter evaluation lint
pnpm --filter evaluation build      # writes apps/evaluation/dist
pnpm --filter evaluation preview    # serves the built folder
```

The built folder is plain static files and uses relative URLs, so it can be
hosted from any path.

## Where the data comes from

Nothing is copied into this app. A small Vite plugin
(`vite-plugin-evaluation-assets.ts`) serves these files from where they already
live, in dev and in the build:

| URL                    | Source in the repository                              |
| :--------------------- | :---------------------------------------------------- |
| `dashboard_data.json`  | `evaluation/dashboard/dashboard_data.json`            |
| `documents/<name>.pdf` | `evaluation/datasets/cpt316/documents/<name>.pdf`     |
| `documents/index.json` | a list of the PDF names in that folder (made by the plugin) |

`dashboard_data.json` is the only data source. Rebuild it with
`uv run --project apps/api python evaluation/dashboard/build_dashboard_data.py`
and refresh the page.

The PDFs the reader and the Source filter offer are the documents listed in
`dataset.documents` (their `id` and the file name from `path`), followed by any
other PDF found in the documents folder. A PDF the data does not list yet keeps
the id older exports used for it (`topic1`, `cpt316-topic2-lexical`,
`cpt316-topic3-updated`, `cpt316-topic3-student`).

### Concerns

If `dashboard_data.json` has a `concerns` field, the Dashboard tab shows one card
per concern, highest severity first. Without it the section shows an empty
message. Clicking an example opens that question in the Visualization tab.

```json
"concerns": {
  "run_id": "...",
  "items": [{
    "id": "blocked_answers",
    "title": "Good answers are blocked",
    "feels_like": "What the student experiences, in one sentence",
    "status": "measured | partly_measured | not_measured",
    "severity": "high | medium | low | unknown",
    "headline": "0 of 15 answers reached the student",
    "metrics": [{ "label": "...", "value": "...", "note": "..." }],
    "examples": [{ "question_id": "t1-008", "note": "..." }],
    "how_measured": "..."
  }]
}
```

## Tabs

1. **Dashboard**: pipeline scorecard, concerns, active run, dataset composition,
   retrieval benchmark.
2. **Run evaluations**: run selector, split composition, run history, and a
   per-question drill-down with the six-stage trace.
3. **Visualization & Annotation**: a fixed-height workbench (the page does not
   scroll) with the question beside its source PDF. Below 1000px wide it becomes
   a normal scrolling page.

| Key             | Action                                          |
| :-------------- | :---------------------------------------------- |
| `Left` / `Right`| Previous / next question                        |
| `1` `2` `3`     | Approve / Needs revision / Reject               |
| `V`             | Verify or unverify the answer key               |
| `E`             | Edit everything about the question              |
| `H`             | Mark or unmark as a hard case                   |
| `N`             | Jump to notes                                   |
| `Esc`           | Leave a text field so the keys above work again |

**Edit**, **+ Question** and **+ Hard case** open the same editor in the left
column, so the PDF stays usable: select text in it and press **Use PDF
selection** to fill a quote, its document and its page; **Check in PDF** shows
whether a typed quote is really on that page.

**Export** lists the questions the filters show, all ticked. **Human-written
only** unticks every AI-written question and keeps them out of the file.
**More > Import JSON** brings in a file exported from this app (or the old
dashboard): new ids are added, ids already here take the file's wording, and the
verified state and review are overwritten for each question in the file.

## Saved edits

Edits live in this browser's `localStorage` under the same keys as the old
dashboard, so edits already made there carry over, and the export file has the
same shape (`dataset`, `exported_at`, `metrics_summary`, `questions[]`). The
original `questions.jsonl` is never changed.

## Code map

- `src/lib/questions.ts`: laying edits over originals, filters, split metrics,
  export and import (plain functions, no React).
- `src/lib/documents.ts`: the list of source PDFs and how a `document_id` finds one.
- `src/lib/editor.ts`: the editor's draft and how a draft is saved.
- `src/components/`: one file per tab or panel. The PDF page itself is drawn by
  `PdfViewer` from `@workspace/ui`.
