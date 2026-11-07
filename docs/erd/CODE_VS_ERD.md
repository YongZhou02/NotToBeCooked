# Code vs ERD

**Generated 08 November 2026 from `b74fddf` by `apps/api/scripts/erd_diff.py`. Do not edit by hand.**

`docs/erd/erd.mmd` is the schema of record; the code side is introspected from
live `SQLModel.metadata` and compiled against `postgresql.dialect()`, not read
off the source and summarised.

Nullability is **not** compared -- `erd.mmd` has no syntax for it. Types are
compared as families, so `string` and `VARCHAR` agree. See the script's
docstring for why both of those are deliberate.

> The hand-written version of this file, which this replaces, ended with the
> reason it now exists: *being ratified was not enough to get them done -- they
> needed a line in a diff.* That version is in git; the last one is at `1633138`.

## Totals

| | Count |
|---|---|
| Entities in the diagram | 9 |
| Tables in the code | 10 |
| In the diagram, absent from the code | 0 |
| In the code, absent from the diagram | 1 |
| Column-level differences | 0 |

## Tables

| Table | Where it is |
|---|---|
| `answerfeedback` | code only |

## Columns

Every shared table matches the diagram column for column.

---

Regenerate with `uv run python scripts/erd_diff.py --write` from `apps/api`.
