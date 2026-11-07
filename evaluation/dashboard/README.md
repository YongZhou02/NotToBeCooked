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
   - Inspect dataset questions, answer keys (reference answers), golden quote evidence, required scoring facts, and model outputs.
   - **Split metrics & composition**: Real-time breakdown of `dev` and `test` splits, questions, golden quotes, categories, and verification status.
   - **Filter toolbar**: Filter by split (`dev` / `test`), origin (`Synthetic` / `Human`), answer key status (`Unverified only` / `Verified only`), or search query.
   - **Answer key verification workflow**:
     - Check whether answer keys are `Verified` or `Unverified`.
     - Filter to "Unverified only" to easily ignore verified answer keys.
     - For unverified answer keys: inline editor to edit, correct, and save changes with one-click verification (`Save & Mark as verified`).
   - **Human-written questions & hard cases**:
     - Add new human-authored questions tagged with `[Human]` (distinct from `[Synthetic]` AI-written questions).
     - Support for flagging questions as very hard cases (`[Human · Hard case]`).
     - Includes gold quotes, PDF page mapping, required facts, and categories.
     - Persists in `localStorage` across page reloads.
     - Full export feature (`Export data (JSON)`) generating complete annotated datasets.

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

## Phase Score Definitions

1. Extraction: exact gold-evidence coverage. Fuzzy coverage is diagnostic and uses a normalized, page-aware sliding-window similarity threshold of 0.88.
2. Chunking: required evidence intact in at least one chunk.
3. Embedding + retrieval: hybrid evidence Recall@5 on the test split.
4. Context assembly: hybrid complete-evidence@5 as a temporary proxy.
5. Citation: assistant citation-support review normalized to 100.
6. Generation: assistant faithfulness/correctness/completeness mean normalized to 100.
