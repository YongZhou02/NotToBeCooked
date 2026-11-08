# NTBC evaluation harness

Run commands from the repository root. For methodology and score definitions, see
[`dashboard/README.md`](dashboard/README.md). For corpus limitations, see
[`datasets/cpt316/README.md`](datasets/cpt316/README.md).

## Where the findings live

| File | What it holds |
|---|---|
| [`problems.md`](problems.md) | Every problem students hit, and every fix tested for it. Start here. |
| [`experiments.md`](experiments.md) | Every experiment: question, setup, numbers, evidence. |
| [`concerns.md`](concerns.md) | How each problem is measured after every run. |
| [`decision.md`](decision.md) | What we decided to build and why. |
| [`playground/README.md`](playground/README.md) | How to try a new pipeline on frozen chunks. |

## Structure

```text
evaluation/
|-- run_eval.py       # single evaluation entry point
|-- playground/       # frozen chunks, toolkit and pipelines for experiments
|-- datasets/         # PDFs, settings, golden questions and evidence
|-- builder/          # dataset and PDF-audit utilities
|-- scorers/          # pipeline, retrieval and answer-quality metrics
|-- runs/             # immutable artifacts from each execution
|-- dashboard/        # six-stage UI and JSON assembly line
|-- reports/          # detailed offline evidence review
|-- baselines/        # human interpretation of recorded runs
`-- tests/            # harness regression tests
```

```text
datasets -> run_eval.py -> runs -> dashboard/build_dashboard_data.py -> dashboard UI
                         `-----> reports -> evidence review
```

## Evaluation modes

| Mode | Scope | Model call |
|---|---|---|
| Extraction only | Extraction and chunking | No |
| Complete retrieval | Extraction, chunking, storage, vector, keyword and hybrid RRF | No |
| Complete + generation | Complete retrieval plus 15 generated answers | Yes |

```powershell
# Extraction + chunking only
uv run --project apps/api python evaluation/run_eval.py --extract-only

# Complete retrieval evaluation: extraction, storage, vector, keyword and hybrid RRF
uv run --project apps/api python evaluation/run_eval.py

# Complete evaluation + 15 generated answers
uv run --project apps/api python evaluation/run_eval.py --generate
```

Additional options are documented by:

```powershell
uv run --project apps/api python evaluation/run_eval.py --help
```

Results are written to `evaluation/runs/<run-id>/`. Open `report.md` for the short
result, or rebuild the dashboard for complete traces.

## Update and open the dashboard

```powershell
uv run --project apps/api python evaluation/dashboard/build_dashboard_data.py
python -m http.server 8765 --directory evaluation/dashboard
```

Open <http://127.0.0.1:8765/>. The dashboard is read-only; stop it with `Ctrl+C`.

## Concerns report

```powershell
# Judge a finished run with a second AI model and write concerns.json beside it
uv run --project apps/api python evaluation/run_concerns.py [--run RUN_DIR] [--no-judge] [--max-judge-calls 120] [--controls 20]
```

Each concern is defined in plain words in [`concerns.md`](concerns.md). Judge numbers are labelled "AI judge, not yet checked by a human".

## Flat results table

One run spreads a question's results over several files. `results_flat.csv` joins them: **one row is one question under one retrieval method** (`vector`, `keyword` or `hybrid_rrf`) in one run. It sits in each run folder (`runs/<run-id>/results_flat.csv`) and is built automatically at the end of `run_concerns.py`. A run that never went through `run_concerns.py` gets it with:

```powershell
uv run --project apps/api python evaluation/builder/flat_results.py --run evaluation/runs/<run-id>
# every run, plus one file with all of them for comparing runs:
uv run --project apps/api python evaluation/builder/flat_results.py --all   # writes evaluation/reports/results_flat.csv
```

Columns: who the row is (`run_id`, `pipeline` such as `run_eval:hybrid_rrf`, `chunks_version`, `question_id`, `split`, `category`, `origin`, `answerable`, `verified`, `is_hard_case`, `author`), then one column per measure named `<step>.<measure>`: `retrieval.*` (hit, recall, MRR, `ms`), `pipeline.extraction` and `pipeline.chunking` (share of the question's evidence that survived), `answer.*` (was the answer shown, blocked or failed, and why), `judge.*` (raw AI-judge scores) and `concern.*` (1 if the question shows that concern). The same columns are used by `playground/`, so the two kinds of run can be loaded together.

**An empty cell means "not measured", never zero.** For example, answer and judge cells are empty on the methods that were not generated, and retrieval cells are empty for questions the notes cannot answer.

```python
import pandas as pd

df = pd.read_csv("evaluation/reports/results_flat.csv")
df.groupby(["run_id", "pipeline"])["retrieval.hit@5"].mean()        # compare runs
df[df["answer.state"] == "blocked"]["answer.block_reason"].value_counts()
```

## References

- Dashboard data contract and six phase scores: [`dashboard/README.md`](dashboard/README.md)
- Dataset and PDFs: [`datasets/cpt316/`](datasets/cpt316/)
- Golden questions and evidence: [`datasets/cpt316/topic1/`](datasets/cpt316/topic1/)
- Evaluation entry point: [`run_eval.py`](run_eval.py)
- Scorers: [`scorers/`](scorers/)
- Historical baseline: [`baselines/topic1-pilot-2026-11-07.md`](baselines/topic1-pilot-2026-11-07.md)
- Detailed offline review: [`reports/generated/topic1-baseline-review.html`](reports/generated/topic1-baseline-review.html)

## Verify

```powershell
uv run --project apps/api pytest evaluation/tests -q
uv run --project apps/api ruff check evaluation
```
