# Playground

A place to try new ideas for the answer pipeline and measure each one the same way.

Run from the repository root:

```
uv run --project apps/api python evaluation/playground/run.py --pipeline <name> --chunks v1
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

`question` is one row of `datasets/cpt316/all/questions.jsonl`. `columns` holds anything the pipeline wants in the results table, using the dotted names below.

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

A step adds columns. It never renames or removes another step's columns. `evaluation/builder/flat_results.py` writes the same table for `run_eval.py` runs, so both kinds of run can be loaded together.

## A run folder

```
runs/<UTC timestamp>-<pipeline>/
  config.json     pipeline name + code fingerprint, chunks version, question-set fingerprint, models, git commit
  trace.jsonl     one line per question: every traced call in order
  results.csv     the table above
```
