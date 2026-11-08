# Evaluation dashboard prototype

Static evaluation interface and review system for the six-stage RAG evaluation pipeline.

```text
datasets + runs + reviews
          |
          v
build_dashboard_data.py
          |
          v
dashboard_data.json     (single UI data contract)
          |
          v
index.html + app.js + styles.css
```

## Structure & Tabs

The evaluation hub is organized into three tabs:

1. **Dashboard (`data-panel="dashboard"`)**:
   - High-level overview of ongoing evaluation data together.
   - Six-stage pipeline scorecard (Extraction, Chunking, Retrieval, Context, Citation, Generation).
   - Active run metrics, execution mode, and source document coverage.
   - Dev vs. Test split quick summary.
   - Phase 3 Retrieval benchmark table on the test split (Vector, Keyword, Hybrid+RRF).

2. **Run evaluations (`data-panel="runs"`)**:
   - Execution details, run selector, and comparative run history table.
   - **Split composition metrics**: Shows what the dataset contains across the `dev` and `test` splits (15 questions and 21 golden quotes in `dev`; 35 questions and 51 golden quotes in `test`). The strict retrieval run excludes `t1-027`, leaving 49 eligible questions overall.
   - Per-question run drill-down with six-stage trace status chips and evidence accordion inspector.

3. **Visualization & Annotation (`data-panel="visualization"`)**:
   - Review one question at a time beside its source PDF, annotate it, edit any part of
     it, write new questions and hard cases, and export a chosen set. See
     [Visualization & Annotation tab](#visualization--annotation-tab).

## Build and Preview

Rebuild the JSON from the repository root:

```powershell
uv run --project apps/api python evaluation/dashboard/build_dashboard_data.py
```

Preview locally:

```powershell
python -m http.server 8766 --directory evaluation
```

Then open `http://127.0.0.1:8766/dashboard/` (served from `evaluation/` so the PDFs in `datasets/cpt316/documents/` resolve).

## Visualization & Annotation tab

A fixed-height workbench: the page does not scroll, and each card keeps a size that
does not depend on its text, so long content scrolls inside its own card. Below
1000px wide it falls back to a normal scrolling page.

| Key | Action |
| :--- | :--- |
| `Left` / `Right` | Previous / next question |
| `1` `2` `3` | Approve / Needs revision / Reject |
| `V` | Verify or unverify the answer key |
| `E` | Edit everything about the question |
| `H` | Mark or unmark as a hard case |
| `N` | Jump to notes |
| `Esc` | Leave a text field so the keys above work again |

**Edit** opens one editor for the question, answer key, split, category, hard-case and
verified flags, gold evidence and required facts. **+ Question** and **+ Hard case** use
the same editor. It replaces the left column only, so the PDF stays usable: select text
there and press **Use PDF selection** to fill a quote, its document and its page, and
**Check in PDF** to confirm a typed quote is really on that page.

Edits are stored as changes over the originals in this browser's `localStorage`.
They do not change `datasets/.../questions.jsonl`, so `run_eval.py` still scores the
original set, and a run's stored results still reflect the evidence it was scored on.

**Export** lists the questions your filters show, all ticked; untick what you do not
want to share. A teammate brings the file in with **More > Import JSON**, which
merges those questions and overwrites their verified state and review for each one.
The Source filter counts each question under the PDFs its evidence points at; only
Topic 1 has questions until the candidate topics get a reviewed set.

## Phase Score Definitions

The phase scores use different, explicitly labelled measurements:

1. Extraction: exact gold-evidence coverage. Fuzzy coverage is diagnostic and uses a normalized, page-aware sliding-window similarity threshold of 0.88.
2. Chunking: required evidence intact in at least one chunk.
3. Embedding + retrieval: hybrid evidence Recall@5 on the test split.
4. Context assembly: hybrid complete-evidence@5 as a temporary proxy.
5. Citation: assistant citation-support review normalized to 100.
6. Generation: assistant faithfulness/correctness/completeness mean normalized to 100.
