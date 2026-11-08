# Playground

A place to try new ideas for the answer pipeline and measure each one the same way.

## Getting started

Run from the repository root:

```
# Run one or more pipelines on the frozen chunks
uv run --project apps/api python evaluation/playground/run.py --pipeline prod_hybrid --pipeline memory_hybrid --chunks v1
uv run --project apps/api python evaluation/playground/run.py --pipeline prod_vector --chunks v1 --split dev --limit 10

# Freeze a new chunk version (never overwrites an existing one)
uv run --project apps/api python evaluation/playground/make_chunks.py v2 --from-run <run_eval run id>
uv run --project apps/api python evaluation/playground/make_chunks.py v2 --ingest

# Replay saved answers through the citation checks (no model calls)
uv run --project apps/api python evaluation/playground/replay_citations.py

# Tests
uv run --project apps/api python -m pytest evaluation/tests -q
```

Pipelines today: `prod_vector`, `prod_keyword`, `prod_hybrid` (the real search, need the Postgres test database from `apps/api/.env`) and `memory_hybrid` (dense + BM25 + RRF in memory, no database). The first run embeds the chunks (about 3 minutes on CPU). After that the embeddings come from `cache/`.

Inside a pipeline:

```python
await tk.prod_hybrid(q)                          # the real apps/api search
tk.rrf([tk.dense(q, 50), tk.bm25(q, 50)], k=5)   # in memory, no database
```

## Folders

| Folder | What lives here | In git? |
|---|---|---|
| `chunks/` | Frozen chunk versions: `v1/`, `v2/`, ... Never edited after they are made. | yes |
| `toolkit/` | Parts you can call from any pipeline: retrieval, embeddings, rerank, query rewrite, router, gate, generate, citation, judge, trace. | yes |
| `pipelines/` | One file per pipeline. Each is a plain Python function, free to loop, branch or retry. | yes |
| `runs/` | One folder per playground run. | no |
| `cache/` | Saved embeddings and model answers, so a re-run costs nothing. | no |

## The rules every part follows

**A chunk version never changes.** `chunks/<version>/manifest.json` records the PDF fingerprints, the chunker and its settings, and the git commit it was made at. A new chunker makes a new version. To test chunking alone, run the same pipeline on two versions. To test anything else, keep the version fixed.

**A pipeline is one async function.** A file in `pipelines/` defines:

```python
NAME = "prod"                     # unique, used in run folders and the results table
DESCRIPTION = "one line"

async def answer(question: dict, tk: "Toolkit") -> dict:
    ...
    return {"answer": text, "citations": [...], "shown": True, "columns": {...}}
```

`question` is one row of `datasets/cpt316/all/questions.jsonl`. `columns` holds anything the pipeline wants in the results table, using the dotted names below. A retrieval pipeline returns `sources` (the ranked chunks) and the runner scores them against the gold evidence.

Set `NEEDS_DATABASE = True` in a pipeline that uses `prod_*` search, so the runner seeds the test database before timing starts. A question that raises an error is recorded as a `pipeline.error` step in the trace, gets empty cells, and the run continues.

**Production parts are optional.** Toolkit functions named `prod_*` call the real `apps/api` code, so the `prod` pipeline measures what students get. A new pipeline never has to use them. Nothing here edits `apps/api`.

**Every toolkit call is traced.** Wrap a toolkit function with `@traced("retrieval.keyword")` from `toolkit/trace.py`. Each call is recorded with its inputs, output summary and time. The trace is how a run explains what it did: which rewrites ran, what each search returned, why the gate decided as it did.

## The results table

Every run writes `results.csv`: one row per question, with these columns first, in this order:

```
run_id, pipeline, chunks_version, question_id, split, category, origin, answerable, verified, is_hard_case, author
```

Then step columns, named `<step>.<measure>`, for example:

```
retrieval.hit@1, retrieval.hit@5, retrieval.evidence_recall@5, retrieval.complete_evidence@5, retrieval.mrr@5,
answer.shown, answer.block_reason, answer.n_citations, judge.correct, judge.supported, judge.useful
```

A step adds columns. It never renames or removes another step's columns. Booleans are written as 1/0 and an empty cell means "not measured", never 0. `retrieval.ms` is the time spent in `retrieval.*` steps only. Query embedding is done up front and is not counted. `evaluation/builder/flat_results.py` writes the same table for `run_eval.py` runs, so both kinds of run can be loaded together.

**Known noise.** Postgres returns keyword matches with equal scores in storage order, which shifts between runs. So `prod_keyword` and `prod_hybrid` can move by about 0.005 to 0.015 on hit@5 and recall@5 from run to run, even with nothing changed. `prod_vector` and the in-memory parts give the same result every time. Treat a difference smaller than that as no difference.

## A run folder

```
runs/<UTC timestamp>-<pipeline>/
  config.json     pipeline name + code fingerprint, chunks version, question-set fingerprint, models, git commit
  trace.jsonl     one line per question: every traced call in order
  results.csv     the table above
```
