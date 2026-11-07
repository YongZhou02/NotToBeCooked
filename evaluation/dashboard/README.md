# Evaluation dashboard prototype

Minimal static UI for the six-stage RAG evaluation pipeline. It has no live-run
backend and does not change evaluation artifacts.

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

Rebuild the JSON from the repository root:

```powershell
uv run --project apps/api python evaluation/dashboard/build_dashboard_data.py
```

Preview locally:

```powershell
python -m http.server 8766 --directory evaluation
```

Then open `http://127.0.0.1:8766/dashboard/` (served from `evaluation/` so the PDFs in `datasets/cpt316/documents/` resolve).

The phase scores use different, explicitly labelled measurements:

1. Extraction: exact gold-evidence coverage. Fuzzy coverage is diagnostic and uses
   a normalized, page-aware sliding-window similarity threshold of 0.88.
2. Chunking: required evidence intact in at least one chunk.
3. Embedding + retrieval: hybrid evidence Recall@5 on the test split.
4. Context assembly: hybrid complete-evidence@5 as a temporary proxy.
5. Citation: assistant citation-support review normalized to 100.
6. Generation: assistant faithfulness/correctness/completeness mean normalized to 100.

The last three are not equivalent to independently validated production KPIs.
Citation and generation scores are visibly labelled assistant review; owner review
is still pending. Context assembly needs a dedicated scorer in a later backend phase.
