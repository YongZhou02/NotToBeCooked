# NotToBeCooked — ERD Known Issues

**Accompanies:** `NotToBeCooked_ERD_2026-08-16.mmd` / `.png`
**Date:** 16 August 2026 · **statuses landed 19 August 2026**
**Author:** Lim Yong Zhou (AI-3, Project Lead)

> **Update, 19 August 2026.** The 18 August meeting settled every finding this file
> had marked *Open — 18 August*: **R3, R13, R14, R15, R16** were decided, and **R6**
> and **R10** were not reached and therefore proceed on the recommendation printed
> here, as the agenda said they would. Each finding below carries its outcome inline;
> **Part D** lists the decisions in one place. Nothing was left in the state "open".

The ERD submitted alongside this note went through two independent reviews after
the 15 August meeting.

The first returned ten findings. Four were corrected in the submitted diagram,
one is closed, and five are open and listed below with the reason and the
schedule.

The second proposed a thirteen-table redesign. Four of its recommendations had
already been applied by the first pass, six restated findings already on this
list, and eleven were new. Two of its new recommendations contradict decisions
taken at the 15 August meeting. All of it is recorded in Part B.

Nothing on this list is unknown to the team. It is published rather than
silently carried so that the diagram and the team's understanding of it stay
the same document.

---

## Index — read this first

**Every finding, its state, and what would reopen it.** This table exists because on
10 September 2026 three of us spent an afternoon re-deriving whether file deletion
should be soft or hard, and reached the opposite of R16, which had settled it on
18 August. The answer was in this file the whole time, in a summary table at line
1126 of 1236. Nobody scrolls that far to find a table of contents.

The body below is organised by review round and by what was open at the time.
**This index is organised by what you probably want to know: is it still live, and
what makes it live again.** The long-form Summary with measurements stays at the end.

### Live — something is still owed

| # | One line | State | Owner / trigger |
|---|---|---|---|
| **R36** | Real lecture slides produce few or no chunks, while the evaluation corpus produces plenty | **Open, raised 22 Sep** — reported by AI-2, nothing measured yet | AI-2 — send the CPC251 PDF and the `DocItemLabel` counts. **Trigger: the counts exist** |
| **R35** | A JSONB column typed `list[UUID]` could not be written at all — every `/rag/query` carrying an @-mention raised | **Closed 21 Sep** — found while building r51, fixed the same day (`json_serializer` on the engine) | Reopens the day someone builds an engine with `create_async_engine` instead of `make_engine` |
| **R34** | Replacing a file's bytes leaves the old chunks retrievable, under the new filename | **Closed 22 Sep** — the fix is merged (`9878edd`, into `dev` as `631a7e0`). **No test proves it: the regression test is r82, 1–3 Oct** | Reopens if r82 slips. Until it lands, this is closed on a reading of the code, not on a measurement |
| **R30** | A corrected re-upload becomes a second FILE row, both retrievable | **Closed 15 Sep** — the PUT landed (`02e8647`) | Its remaining half is now R34 |
| **R27** | Deleting a FILE row leaves its bytes on disk | **Deferred, with a trigger** | Whoever writes the delete-file endpoint. **Trigger: the day it lands** |
| **R5b** | Cross-file `embedding_model` filter | **Deferred, with a trigger** | Whoever changes `settings.MODEL_TYPE` without re-indexing every chunk |
| **R28** | Deleting a FOLDER row cascades to files, runs and chunks | Guarded in the router, not the database | **Reopen the moment a second code path deletes a FOLDER row** |
| **R10** | `MESSAGE` has no `sequence_no` | **Deferred** — accepted v1 defect | Order is implied by `created_at` |
| **R33** | What a mocked session cannot test | Recorded 9 Sep — **a rule, not a defect** | Anything the database enforces is tested against a database |

### Declined — and what would reopen each

| # | One line | Reopen condition |
|---|---|---|
| **R16** | Soft delete on `COURSE` / `FILE` | The first time someone deletes a course by mistake and asks for it back. **Consequence, easy to miss: v1 has no delete-course feature at all** |
| **R13** | `MESSAGE_SCOPE_COURSE` junction table | The first US-12 acceptance case genuinely needing two courses on one turn, neither expressible as an @-mention |
| **R32** | Moving a file between courses | A user story that asks for it. The `409` is the answer, not a placeholder |
| **R21** | `EMBEDDING_PROFILE` as its own entity | Declined for v1 — see R5 |
| **R22** | `STORED_OBJECT` / `FILE` split for global dedup | Declined for v1 |
| **R23** | Remove `CHUNK.file_id` / `course_id` | Declined — see R4 |
| **R24** | Full folder tree | Declined — see R9 |
| **R9b** | Flat folder hierarchy | Not a defect |

### Closed

`R1` `R2` `R3` `R4` `R5` `R6` `R7` `R8` `R9` `R11` `R12` `R14` `R15` `R17` `R18` `R29` `R30`
`R19` `R20` `R25` `R26` `R31` — plus the eight ratified fields dropped in drafting,
restored in Part C. Each carries its date, its commit and its verification in the
Summary at the end of this file.

**Nothing on this list is unowned, and nothing is in the state "open, unassigned".**

---

# Part A — first review

## Corrected in the submitted diagram

### R2 — `MESSAGE.course_id` renamed `scope_course_id`

`CONVERSATION.course_id` is the conversation's home course. `MESSAGE.course_id`
was the retrieval scope of one single turn. Two different meanings sharing one
column name, one join away from each other.

The rename is free right now because the column has not been written yet. After
it ships it costs a migration.

### R3 — `ON DELETE CASCADE` downgraded to `ON DELETE RESTRICT`

The meeting voted CASCADE on the reasoning that deleting a course should take
that course's questions with it. That reasoning holds only while a conversation
and its turns share one course.

They do not have to. A conversation whose home course is CS201 can contain a
turn scoped to CS210, because @-mentions are allowed to cross courses (US-12).
Under CASCADE, deleting CS210 deletes that turn out of the middle of a CS201
conversation the user never asked to touch — and it does so silently, while
`scope_snapshot` on that same row exists specifically to preserve what was
searched.

RESTRICT was chosen over `SET NULL` because `SET NULL` would require making the
column nullable, and sub-decision 2 of item 03 voted it NOT NULL for a separate
and still-valid reason.

**This reverses a decision taken at the 15 August meeting.** It is flagged to
the team and goes back to a vote on 18 August. The diagram shows RESTRICT
because shipping a diagram with a known hole in it is worse than shipping one
whose open question is named.

**Closed 18 August — Decision 2 carried RESTRICT.** The 15 August CASCADE vote is
superseded rather than merely flagged, and `MESSAGE.scope_course_id` now declares
`ondelete="RESTRICT"` in `app/schemas/chat.py`. R13 was taken first, as the agenda
required, and declined — so the junction table did not dissolve this question and
the vote was a real one.

**The consequence R16 leaves behind is recorded under R16.** RESTRICT plus no soft
delete means a course used in any turn cannot be deleted at all.

### R7 — `FILE.sha256` UNIQUE constraint removed

Files belong to a user: `FILE → FOLDER → COURSE → USER`. A global UNIQUE on the
content checksum means the system stores any given PDF exactly once across all
users, and the second student to upload the same lecture slides is rejected with
a duplicate-key error.

The constraint was carried over from the earlier data dictionary without being
re-examined against the ownership chain. Removed. Duplicate detection is still
possible on the checksum; it just has to be scoped, not global.

### R9 — `FOLDER` gains `parent_folder_id`

The UI ships flat, which was the decision at the meeting and is not being
reversed. The column is added now because FOLDER has not been built yet, so it
costs one line today and a migration plus a backfill later.

Nothing reads the column in v1. `is_root` continues to identify the hidden root.

The FOLDER-to-FOLDER edge is deliberately **not** drawn on the diagram: the
layout engine routes a self-reference as a long tail that pushes the
FOLDER-to-FILE edge across CONVERSATION. The column carries the meaning.

---

## Closed

### R1 — `CONVERSATION` carried both `user_id` and `course_id`

`COURSE` already has `user_id`, so a conversation's owner is reachable through
its course. Storing it again allows a row where the conversation's owner and the
course's owner are different people. Nothing enforces that they match.

**Closed rather than deferred.** The 27 July ratified ERD never had
`CONVERSATION.user_id` — the draft of this revision introduced it, which is why
both reviews found it. Removing it restores the ratified shape and is not a
decision anyone has to take.

One thing does remain: the ORM model on the `ck` branch carries the column. That
is now a code-vs-diagram mismatch to reconcile, not a schema question.

---

## Was open for 18 August — neither was reached, both proceed on the recommendation

The agenda's standing rule is that an item not decided on the night proceeds on the
recommendation printed for it and is recorded that way. These two are the only
findings that rule was actually exercised on.

### R6 — `MESSAGE.mentioned_file_ids` is JSONB with no foreign key

The @-mention scope is stored as a JSON array of file IDs. The database cannot
check that those IDs exist, and deleting a file leaves the array pointing at
nothing.

This is intentional in v1 — the array is a frozen record of what the user asked
for at that moment, and a dangling ID is arguably the correct historical answer.
A junction table would enforce referential integrity and lose that property. The
trade is real and worth a decision rather than a default.

Separately: **folder-level @-mentions have no representation at all.** The array
holds file IDs. Mentioning a folder currently has to be expanded to files at
send time, which freezes the folder's contents as of that moment. This has never
been on an agenda.

**18 August — not reached; proceeds on the recommendation.** The column stays JSONB
with no foreign key for v1, which is what the code already does. The frozen-record
property is the reason, not inertia: a dangling file ID is the historically correct
answer to "what did the user ask for".

**25 August — the second half is decided. Option A: the freeze is the point.**
Mentioning a folder expands to that folder's file list at send time, and the array
keeps those IDs. Adding a file to the folder afterwards does not reach back into an
earlier turn.

The alternative was storing folder IDs and expanding at retrieval time, which would
mean "whatever is in this folder now". That reading is defensible on its own and
wrong next to the first half of R6: `mentioned_file_ids` would then hold two kinds
of time in one column, frozen for files and live for folders, with nothing in the
schema saying which a given row is.

**A does carry a condition, and it is not a database change.** A user who mentions
a folder is picking a container and getting a list, and the difference only shows up
later, when the list has gone stale. That has to be visible in the UI at the moment
of mention — it cannot live only in a column comment. Logged against F2.

### R10 — `MESSAGE` has no `sequence_no`

Turn order is currently implied by `created_at`, with nothing guaranteeing that two
rows of one conversation carry distinct values. A monotonic integer per conversation
would remove the ambiguity instead of relying on clock resolution. How much
ambiguity there actually is today was measured on 24 August — see below; it is less
than this entry originally asserted.

**18 August — deferred again, and this file previously contradicted itself on it.**
The body said "deferred"; the summary table at the foot said "Open — 18 Aug". The
body was right. R10 was never on the 18 August agenda in the first place, so there
was nothing to not-decide: turn order stays implied by `created_at` for v1.

**What deferring actually costs — measured 24 August, and it is smaller than this
entry used to claim.** The earlier wording said two rows written in one transaction
can share a timestamp, and that a user turn and its assistant turn are exactly that
pair. The second half does not hold for the code as written.

`created_at` is not `server_default=now()`; both rows call Python's
`datetime.now(UTC)` separately (`routers/rag.py:79` and `:181`), and the whole
generation block sits between them. Two calls with a single `sha256` between them
collided **0 times in 20,000**. Back-to-back with nothing in between they collide
83% of the time, which is the clock's resolution rather than our situation.

So the accepted defect is narrower: **turn order is safe while every writer stamps
its own row in Python.** It breaks the day someone switches the column to a server
default, because a transaction timestamp is identical for every row in the
transaction — and `routers/chat.py:99` orders by `created_at` alone, so the
conversation would then render arbitrarily. That is the thing to recognise in a bug
report, not a collision under the current code.

---

## Open — folded into the first Alembic migration

These three are constraints and indexes. They do not appear on an ER diagram at
all; they appear in the migration that builds the schema. Listed here so the
diagram is not mistaken for the whole specification.

**This heading is now historical for two of the three.** R4 closed on 26 August,
across r41 and r42 rather than one migration. R5 was reclassified on 22 August as
a retrieval-layer query predicate and never belonged in a migration at all; it is
open and assigned. Only R20 was ever finished where this heading says it would be.
The heading is kept rather than renamed so that older references to it still land.

### R4 — `CHUNK` holds three independently-valid foreign keys

`ingestion_run_id`, `file_id` and `course_id` can each point at a legitimate row
while together describing something impossible: a chunk attributed to a run of a
file that belongs to a different course.

`file_id` and `course_id` are denormalised on purpose — a citation needs both
without a join, and `course_id` is the filter in front of the vector scan.
Keeping the denormalisation and enforcing consistency needs either a composite
foreign key or a trigger.

**Closed 26 August, in two halves and two migrations.**

The first half shipped with r41 on 22 August: `CHUNK (ingestion_run_id, file_id)`
points at `INGESTION_RUN (id, file_id)`, so a chunk can no longer claim a run
belonging to a different file. That needed `uq_ingestion_run_id_file`, because
PostgreSQL will not accept those two columns as a foreign key target unless some
unique constraint covers exactly them — `id` being a primary key is not enough.

The second half could not be written the same way, and that is why it waited. The
agreement to enforce is between `CHUNK.course_id` and `CHUNK.file_id`, but a
composite foreign key must point at real columns on one table, and no table
carried both `file_id` and `course_id`. FILE reached its course through FOLDER.
There was nothing to point at.

**25 August meeting, Decision 02, option B — measured before the vote.** With
nothing enforcing it, this row went in against a file that lives under CSC3105:

```sql
-- this file is under CSC3105; course_id says CSC3110
INSERT INTO chunk(..., file_id, course_id, chunk_index, ...) VALUES (...);
 chunk_index |   content
-------------+--------------
           8 | wrong course
(1 row)
```

Three options were on the agenda: a trigger, denormalising `course_id` back onto
FILE, or leaving it to `processor.py` and writing that down with a date. B carried.
A trigger hides the logic somewhere neither code review nor `git log` shows it,
which matters more with three people than with thirty.

**Shipped as r42, 26 August (CR-31).** FILE regains `course_id`, and the
constraint becomes a chain rather than a single link:

```
CHUNK (file_id, course_id)   -> FILE   (id, course_id)
FILE  (folder_id, course_id) -> FOLDER (id, course_id)
```

FOLDER and FILE each carry `UNIQUE (id, course_id)` for the same reason
INGESTION_RUN carries `uq_ingestion_run_id_file`: to be a legal target. Neither
forbids anything new.

Verified by `check_r42.py`, eleven cells over `upgrade -> downgrade -> upgrade`.
Three of them are behavioural rather than structural: a file claiming a course
its folder is not in is rejected, a chunk disagreeing with its file is rejected,
and — the cell that matters most — a row where all three agree still goes in. A
constraint that blocks everything passes the first two.

**What this does not close.** The chain binds `course_id` to `file_id`, and r41
bound `file_id` to `ingestion_run_id`. Both links are enforced, so all three keys
now describe one consistent object. `processor.py` is no longer the only thing
standing between a mislabelled chunk and the database.

### R5 — Nothing filters the vector scan by embedding model

`INGESTION_RUN` records `embedding_model` and `embedding_dim`, which is what
makes an embedding-model swap possible without dropping the database. But two
models with the same output dimension produce vectors in different spaces, and
cosine similarity between them is meaningless — it returns a number, not an
answer.

Retrieval must therefore constrain to the active run's model, not merely to
`is_active`.

**25 August meeting, Decision 3 — assigned to AI-1.** R5 left r41 on 22 August
because it is a query condition, not a constraint, and it then sat in this file
as the only entry that was neither decided nor owned. It now has a name.

The work lands in `_vector_similarity_search`, which already takes an optional
`file_ids` filter; "only this run" is the same shape of change in the same place.

**Measured 25 August.** One file, two ingestion runs, two chunks each, one query
vector. The old run is `is_active = false`:

```
current _vector_similarity_search
  1. distance=0.0100  OLD RUN  chunk 0  (superseded-model)
  2. distance=0.0500  OLD RUN  chunk 1  (superseded-model)
  3. distance=0.1000  NEW RUN  chunk 0  (jinaai/jina-embeddings-v5-text-small)
  4. distance=0.1500  NEW RUN  chunk 1  (jinaai/jina-embeddings-v5-text-small)

with an is_active join
  1. distance=0.1000  NEW RUN  chunk 0  (jinaai/jina-embeddings-v5-text-small)
  2. distance=0.1500  NEW RUN  chunk 1  (jinaai/jina-embeddings-v5-text-small)
```

The model names in that output were **relabelled on 31 August**. The probe seeded
two runs with two different `embedding_model` values to show the effect; the
names originally written down were Gemini embedding models, which this project
does not use. The embedder is the local `settings.MODEL_TYPE` model run through
SentenceTransformer. `GEMINI_MODEL_NAME` is the generation LLM and has never been
the embedder. The distances are unchanged -- they were seeded, not computed.

The superseded chunks take rank 1 and 2 and eat two of the five `top_k` slots.
Nothing errors; the answer is simply built on text that was replaced.

`ix_ingestion_run_one_active` (r41, partial unique on `file_id WHERE is_active`)
guarantees at most one active run per file, so a join is enough within a file. It
is not enough across files: two active runs can still name different
`embedding_model` values.

`_full_text_search` had the same hole. Lexical ranking does not care which model
produced the vectors, but it does return chunks from superseded runs.

**Closed 1 September 2026 — AI-1.** Both search paths now join `INGESTION_RUN`
and filter on `is_active`:

```python
.join(IngestionRun, col(Chunk.ingestion_run_id) == col(IngestionRun.id))
.where(col(IngestionRun.is_active).is_(True))
```

Decision 3 of 25 August named only `_vector_similarity_search`. `_full_text_search`
was fixed in the same pass without being asked for, which is why the sentence
above reads "had" rather than "has".

### R5b — the cross-file half, deferred with a trigger

The second filter — constraining to the active run's *model*, not merely to
`is_active` — was deferred at the 1 September meeting. Recorded here rather than
closed, because the reasoning is only true while a condition holds:

> **Deferred while exactly one embedding model is in use anywhere in the system.**
> `ix_ingestion_run_one_active` makes the `is_active` join sufficient within a
> file, and with one model there is nothing for the cross-file case to get wrong.

**Trigger — the day this must be done:**

> The day `settings.MODEL_TYPE` changes without every existing chunk being
> re-indexed.

From that day, two files can each hold an active run under a different model, the
join stops being sufficient, and cosine distance between the two spaces returns a
number rather than an answer. **It raises nothing.** Retrieval simply mixes two
coordinate systems and ranks them against each other.

Whoever changes `settings.MODEL_TYPE` owns this entry from that moment.

### R27 — deleting a FILE row leaves its bytes on disk

`FILE.storage_key` points at an object that nothing owns. Every foreign key into
FILE cascades, so deleting a file takes its chunks and its ingestion runs with
it — and leaves the stored bytes exactly where they were.

**Measured 1 September 2026**, after a day of end-to-end runs:

```
select count(*) from file;      0
du -sh apps/api/storage        18M      -- six orphaned directories
```

Zero rows, eighteen megabytes. Nothing deleted them because no code path deletes
a blob: `app/services/storage.py` has a `delete()`, and it has no callers.

**Not reachable in v1.** R16 declined soft delete and there is no delete-file
endpoint, so the only way to lose a FILE row today is by hand. The day a delete
endpoint lands, this leaks on every use — silently, because a leak of disk is not
an error.

Two shapes when it matters, and they are not the same decision:

- **Delete on delete.** Simple, and wrong the moment two rows can share a key.
  Today they cannot: `storage_key` is UNIQUE and built from `{user_id}/{file_id}`.
- **Sweep.** A job that lists the store and removes what no row references.
  Survives sharing, and it is the only one that also collects what a crashed
  upload left behind — `write_upload` deletes its partial file, but only if the
  process is still alive to do it.

Nobody owns this yet. It goes with whoever writes the delete endpoint.

### R28 — deleting a FOLDER row takes its files, runs and chunks with it

`FILE.folder_id` and `FOLDER.parent_folder_id` are both `ON DELETE CASCADE`, and
every foreign key into FILE cascades in turn. One `DELETE` against `folder`
therefore removes every file under it, every ingestion run of those files, and
every chunk of those runs — including the chunks that stored citations point at.

**Measured 6 September 2026** against the test database, seeded with one course,
one folder, one file and one ingestion run:

```
before delete: {'folder': 1, 'file': 1, 'ingestion_run': 1}

  delete from folder where id = <the folder>     -- the folder holds one file
  DELETE 1                                       -- no error

after  delete: {'folder': 0, 'file': 0, 'ingestion_run': 0}
```

PostgreSQL reports `DELETE 1`. Three rows are gone, and nothing raised.

**The one endpoint that deletes a folder does guard this.** `delete_folder` in
`app/routers/folder.py` refuses with 409 when the folder still holds a child
folder or a file, and both cases have a test. The guard is correct and it was
written without being asked for.

**It lives in the router, not in the database.** Any other path that removes a
FOLDER row cascades in silence: a bulk delete written later, a data-fix
statement run by hand, a `DELETE /courses/{id}` reworked from today's soft
archive into a real delete, or the endpoint itself losing the race between its
emptiness check and its `DELETE`.

Two shapes when that day comes, and they are not the same decision:

- **`RESTRICT` on `FILE.folder_id`.** The database refuses and the 409 becomes a
  second line of defence rather than the only one. This is what D2 (18 August)
  chose for `MESSAGE`. It costs a migration, and it makes every future
  delete-a-course path explicit about the order it deletes in, because a course
  can no longer be removed by cascading through its folders.
- **Leave `CASCADE` and keep the rule in application code.** What we have today.
  Correct exactly as long as every future delete path remembers, which is the
  property this file exists to stop us assuming.

**Not a defect today** — one endpoint deletes folders and it guards. Recorded
because the guard is a function call away from the rule it enforces, and because
the cost of finding out is a user's chunks.

**Reopen the moment a second code path deletes a FOLDER row.**

### R29 — two citations can share a marker

`Citation.marker` names a **source**, not a citation slot: `prompt.py` says
"Numbering starts at 1 and refers only to sources that appear in the list you
were given". Two claims drawn from the same chunk therefore both carry `[1]`,
each with the line that supports it, and `RagAnswer.citations` holds two entries
under the same number.

**Measured 6 September 2026**, one live call, one question over two real chunks:

```
answer:  A partial index is an index that covers only the rows matching its
         WHERE clause [1]. The planner can only use a partial index when the
         query repeats that same clause [1].

citations:
  [1]  "A partial index covers only the rows matching its WHERE clause."
  [1]  "the planner can only use it when the query repeats that same clause."
```

This is correct behaviour and `check_grounding` accepts it. The first version of
that check rejected duplicate markers outright, which would have thrown away a
well-cited answer; it now rejects only the same marker with the same quote,
which carries no second piece of evidence.

**The open half is rendering.** A frontend that resolves a `[1]` in the answer
text by taking the first citation with `marker === 1` silently drops the second
quote — the reader clicks the second `[1]` and is shown the evidence for the
first claim. Nothing raises, and the two quotes are both genuine, so it does not
look like a bug from either side.

Three shapes, and this is a C4 question rather than a rendering preference:

- **Render every entry for that marker.** One pill, several quoted lines. No
  contract change, and the honest reading of what generation produced.
- **Number the citations rather than the sources.** Unambiguous per pill, but it
  contradicts the published instruction and breaks `selected[marker - 1]`, which
  is how both `_resolve_citations` and `check_grounding` reach provenance.
- **One citation per source, best quote only.** Simplest UI, and it discards
  evidence the model correctly produced.

Owner: AI-3 owns `schemas/rag.py`, AI-1 owns the chat UI that renders it.

**Closed 8 September 2026 — Decision 4, option A.** *Render every entry that
carries that marker*: one pill, several quoted lines. No contract change, and it
is the honest reading of what generation produced.

The two options not taken, and why:

- **Number the citations rather than the sources.** Unambiguous per pill, but it
  contradicts the instruction `prompt.py` publishes to the model and breaks
  `selected[marker - 1]` — which is how both `_resolve_citations` and
  `check_grounding` reach provenance. It would move the one layer that does not
  have to trust the model.
- **One citation per source, best quote only.** Simplest UI, and it throws away
  evidence the model correctly produced.

F3 (r36, AI-1, due 16 Sep) renders to this rule. **A frontend that resolves `[1]`
by first match is the defect this closes** — it shows the first claim's evidence
against the second, and both quotes are genuine, so nothing about it looks wrong
from either side.

### R8 — `INGESTION_RUN.is_active` is a boolean with no uniqueness guarantee

The annotation says exactly one active run per file is visible to retrieval. A
boolean column cannot enforce that; two rows can both be true. The enforcement
is a partial unique index:

```sql
CREATE UNIQUE INDEX ix_ingestion_run_one_active
    ON ingestion_run (file_id) WHERE is_active;
```

### R30 — a corrected re-upload becomes a second FILE row, and both stay retrievable

Uploading a revised version of a file that is already there creates a *second*
FILE row. `POST /files` has no other mode, and no endpoint replaces the bytes of
an existing row: the four file routes are `POST /files`, `POST
/files/{id}/ingest`, `GET /courses/{course_id}/files` and `PATCH /files/{id}`.

The two rows share a filename, hold different bytes, and each carries its own
active ingestion run. Retrieval therefore returns chunks from both versions, and
every citation reads `Week3.pdf`. The reader is given the superseded text and the
current text under the same name, with nothing to tell them apart.

**Measured 8 September 2026** against the development database, inside a
transaction that was rolled back:

```
today -- POST /files twice, same folder, same name, different bytes
    file 473f0786  filename=Week3.pdf  sha256=sha256-of-v1  is_active=true   accepted
    file 6416fd4b  filename=Week3.pdf  sha256=sha256-of-v2  is_active=true   accepted

    what retrieval sees (the is_active join, R5's fix):
      Week3.pdf  sha256-of-v1  is_active=True
      Week3.pdf  sha256-of-v2  is_active=True
    -> 2 active runs, both named Week3.pdf, two different documents

under the proposed fix -- one FILE row, the bytes replaced, re-ingested
    second active run refused: UniqueViolationError
      duplicate key value violates unique constraint "ix_ingestion_run_one_active"
    -> 1 FILE row. one active run per file_id, enforced by the index, not by us
```

**Neither R5 nor R5b covers this.** R5 is superseded runs *of one file*, closed
1 September by the `is_active` join. R5b is the cross-file half, and its trigger
is the day `settings.MODEL_TYPE` changes — here both runs use the same model, so
that trigger never fires. `ix_ingestion_run_one_active` is partial on `file_id`;
two FILE rows are two different `file_id` values and the index has nothing to say
about them.

**A UNIQUE on `(folder_id, filename)` does not fix it.** Retrieval scope is a
course, not a folder — `file_ids` null means the whole of `course_id`
(`schemas/rag.py`) — so two folders can each hold a `Week3.pdf` and the citation
is ambiguous either way. Such a constraint would also reject the legitimate
second copy, which is the case R7 already declined to reject for `sha256`.

The mechanism for replacement already exists and nothing reaches it:

- `storage_key` is `{user_id}/{file_id}` plus the suffix (`services/storage.py`).
  The original filename is deliberately not part of the key, so overwriting the
  bytes of an existing row leaves the key unchanged.
- Re-ingesting a `file_id` deactivates the previous run before activating the new
  one (`routers/files.py`), in that order, because the partial index refuses two
  active runs for even one statement.
- Retrieval already joins `is_active`, so the superseded chunks stop being
  visible without anything deleting them.

**Proposed: one endpoint, `PUT /files/{file_id}/content`.** It streams to the
existing `storage_key`, updates `sha256`, `size_bytes` and `page_count`, returns
`status` to `uploaded`, and stops. Chunking, activation and retrieval are
untouched. The upload UI asks "replace or keep both" when a file of that name is
already in the folder; "keep both" remains legal and produces exactly the state
measured above, but as a choice rather than as the only option.

**The file browser is the visible half.** `GET /courses/{course_id}/files`
selects FILE rows and joins nothing else, so today it lists both copies and the
reader picks between two identical names. Under the proposal it lists one, and
the superseded version is not hidden from the browser — it is not a file at all,
only an inactive run, and `FileRead` carries no run field. Same query, both ways:

```
today -- uploaded twice, GET /courses/{id}/files returns:
    Week3.pdf    sha=sha-v2    1450 bytes  07:22
    Week3.pdf    sha=sha-v1    1000 bytes  07:17
    -> 2 entries named Week3.pdf

after the fix -- uploaded twice, same query returns:
    Week3.pdf    sha=sha-v2    1450 bytes  07:17
    -> 1 entry named Week3.pdf
    -> 2 runs underneath: [False, True] -- neither is visible to the frontend
```

**`uploaded_at` must be updated by the same endpoint**, and the `07:17` in the
second block above is why: the row holds the second upload's bytes while still
carrying the timestamp of the first. The list is ordered by `uploaded_at DESC`, so
a file the user has just replaced does not move to the top and reads as though
the upload failed. Updating the column is preferred over adding `updated_at`:
the column already means "when did this file arrive", and what has arrived is the
new one. A second column costs a migration and a `FileRead` change to record a
history v1 does not show.

**Doing nothing has no fallback.** R27 records that there is no delete-file
endpoint, so a user who uploads a corrected version cannot remove the old one
either. The two versions stay, and stay retrievable, until someone deletes a row
by hand.

Owner: AI-2 owns the file router. Raised 8 September 2026 by the Lead, out of
AI-2's question about whether one folder may hold two files of the same name.
It may, and that part is not the defect — the defect is that the older document
stays retrievable.

---

### R31 — uploaded files live in the container's writable layer, and a redeploy takes them

`docker-compose.yml` gives the `db` service a named volume and gives the `api`
service none:

```yaml
db:
  volumes:
    - pgvector_data:/var/lib/postgresql/data
api:
  build: .
  # no volumes
```

`STORAGE_DIR` is `_ENV_FILE.parent / "storage"`, and `_ENV_FILE` walks three
parents up from `app/core/config.py`, so inside the image it resolves to
`/app/storage`. Every uploaded blob is therefore written into the container's
writable layer, which Docker deletes along with the container.

The FILE rows do not go with them. They live in the `db` volume and survive, so
after a redeploy the file browser lists every file it listed before and each one
resolves to a path that no longer exists. **Nothing raises at redeploy time; the
failure appears later, one file at a time, as a read that finds nothing.**

**Measured 9 September 2026**, Docker 29.4.0-ce:

```
before -- no volume, the way docker-compose.yml has it today
Week3.pdf
ls: cannot access '/app/storage': No such file or directory

after -- one named volume on the api service
Week3.pdf
Week3.pdf
body
```

Both runs create the container, write the file, destroy the container and start
a fresh one. The only difference between them is the volume.

**This is not R27, and the two point in opposite directions:**

- **R27** — a FILE row is deleted and its bytes stay on disk. Rows lost, bytes kept.
- **R31** — no row is deleted and every byte goes. Bytes lost, rows kept.

They share one cause: `FILE.storage_key` names an object that no component owns.
R27 is the missing owner at delete time; R31 is the missing owner at deploy time.

**Not reachable today.** Development runs the API outside Docker against a local
Postgres, so the writable layer is never the store. **Trigger: the first
`docker compose down && up` on a host where real uploads exist** — which is the
OCI ARM instance of r45, on its first redeploy after go-live.

The fix is one volume on the `api` service plus its declaration:

```yaml
api:
  volumes:
    - api_storage:/app/storage
volumes:
  pgvector_data:
  api_storage:
```

`STORAGE_DIR` is documented as "a local directory today and an object-store
bucket later". When that move happens this entry closes on its own, because the
bytes stop living on the host at all. Until then the volume is what stands
between a redeploy and every uploaded file.

**Fixed 9 September 2026.** Two lines on the `api` service and one declaration:

```yaml
api:
  volumes:
    - api_storage:/app/storage
volumes:
  pgvector_data:
  api_storage:
```

Verified against the real stack, not the compose file. A file was written inside
the container, the container was destroyed with `docker compose rm -sf` and
brought back, and the file was read again:

```
in the container -- write one "uploaded file"
-rw-r--r--. 1 root root 15 Sep  9 04:37 Week3.pdf

destroy and recreate the container (same as down && up)
  container rebuilt, health = healthy
-rw-r--r--. 1 root root 15 Sep  9 04:37 Week3.pdf
--- contents ---
Week3.pdf body
```

The trigger recorded above no longer fires: a redeploy on the r45 host keeps the
uploads. **This entry closes early rather than travelling with the deployment**,
because the cost of carrying it was that it would be discovered by losing files
on a machine that had real ones.

**A healthcheck went in beside it, and it is worth recording why.** The `api`
service had none while `db` had one, so `docker compose ps` printed `Up` for the
twenty-odd seconds `init_db()` spends reflecting every table with `echo=True`
switched on. Docker binds the published port when the container starts, not when
uvicorn begins listening, so during that window a request is accepted and dropped
— `curl` reports `(52) Empty reply from server` rather than a refused connection,
and a browser's `fetch` rejects with a `TypeError` that serialises to `{}`.

**That is what an outage looked like from the frontend on 9 September**: a
registration form showing "An unexpected error occurred" with an empty Dev
Response, which reads as a frontend defect. Two people spent an hour on it, and
one of them (the Lead) misread `CREATED 36 seconds ago / Up 7 seconds` as a crash
loop before the log showed `Application startup complete`. The service now
reports `starting` until `/health` answers:

```
   5s  starting
  10s  starting
  15s  healthy
```

Owner: closed by the Lead, 9 September 2026, out of AI-2's failing registration.
Raised the same day.

---

### R32 — moving a file between courses is not supported, and the database is the reason

**Decided 8 September 2026, Decision 5, option A.** A file cannot be moved from
one course to another. The `409` returned by `PATCH /files/{file_id}` is the
final answer rather than a placeholder, and this entry closes with that.

`PATCH /files/{file_id}` takes a `folder_id`, and a folder belongs to a course,
so the request shape allows an owner to name a folder in a different course.
`routers/files.py` rejects it:

```python
if destination_folder.course_id != file_row.course_id:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                        detail="A file cannot be moved to another course.")
```

**Measured 9 September 2026** against the development database, inside a
transaction that was rolled back. One user, two courses, one root folder each,
one file in CS101 carrying one ingested chunk:

```
seeded: CS101 has one file with one ingested chunk

  move the FILE to the other course (course_id only)
     -> ForeignKeyViolationError: update or delete on table "file" violates
        foreign key constraint "fk_chunk_file_course_agree" on table "chunk"
  move it properly (folder_id AND course_id together)
     -> ForeignKeyViolationError: update or delete on table "file" violates
        foreign key constraint "fk_chunk_file_course_agree" on table "chunk"

  fk_chunk_file_course_agree
     FOREIGN KEY (file_id, course_id) REFERENCES file(id, course_id) ON DELETE CASCADE
```

**Both attempts fail, including the one that moves `folder_id` and `course_id`
together.** The constraint declares `ON DELETE CASCADE` and says nothing about
`ON UPDATE`, and PostgreSQL's default there is `NO ACTION` — so the moment a file
has been ingested, its `course_id` is not writable at all while its chunks exist.

The guard in the router is therefore not the thing preventing this. It is what
turns an unhandled `ForeignKeyViolationError` into an answer the caller can read.

**Option B was to support it**, either by moving `CHUNK.course_id` in the same
statement or by adding `ON UPDATE CASCADE`. Its cost is not the migration:

- Chunks would have to move with the file, or be re-ingested. That decision
  changes what retrieval scope means, and retrieval is not finished (r48).
- No user story asks for it. US-05 is "move files between folders" — within a
  course. US-12's cross-course case is @-mentioning a file from another course
  in a question, which is a read and already works.

**Consequence accepted at the meeting:** a user who files something under the
wrong course deletes it and uploads it again. There is no delete endpoint today
(R27), so in practice that is a v1 limitation, recorded here rather than left to
be rediscovered.

**Closed on decision.** Reopen only if a user story asks for the move.

---

### R33 — what a mocked session cannot test

Not a defect in the schema. It is the reason four separate findings survived a
green test suite, written down so the fifth does not.

A test that replaces the database session with `AsyncMock` exercises the order of
calls in the route and nothing else. **`AsyncMock` has no foreign key, no CHECK,
no partial unique index, no `ON DELETE` behaviour, no column default and no
timezone coercion.** It accepts every value in the right shape and returns
whatever the test told it to.

Four times, in this order:

| | The mock was green, and the database said | Where |
|---|---|---|
| 1 | `is_active` on two runs of one file — the boolean cannot enforce "exactly one" | R8 |
| 2 | The enum stored `'READY'` while every other layer said `'ready'`, so R19's CHECK could never be true | R25 |
| 3 | `PATCH /files/{id}` accepted a cross-course move; the passing test asserted the broken behaviour | 6 Sep, before R32 |
| 4 | Deleting a folder took its files, runs and chunks; the router's guard is not the database's | R28 |

Item 3 is the sharpest: **the test passed because it asserted what the code did.**
A mock cannot disagree with the code under test, so a wrong expectation and a
wrong implementation agree with each other and the suite is green.

**Rule.** Anything that is enforced by the database is tested against a database:

```
constraint, index, FK, CHECK, cascade, default, enum value, timezone
    -> a real session, seeded and rolled back
call order, branching, error mapping, response shape
    -> a mock is fine and faster
```

The probes behind R28, R30, R31 and R32 all run inside a transaction that is
rolled back, so they leave nothing behind. That pattern is cheap enough that
"it needed a real database" stopped being a reason to skip the test.

**Raised 9 September 2026 by the Lead**, out of report 4 of the 8 September
meeting — the fourth instance of "a green verify proves less than it looks".

---

### R34 — replacing a file's bytes leaves the old chunks retrievable, under the new filename

`PUT /files/{file_id}/content` (r79, landed in `02e8647`, in `main` since
15 September) closes R30: the replacement bytes go into the same FILE row, so a
corrected upload no longer becomes a second row. What it does not do is retire
what was indexed from the bytes it just overwrote.

The endpoint updates the FILE row and stops there — `routers/files.py:547-552`:

```python
file_row.size_bytes = size_bytes
file_row.sha256 = sha256
file_row.page_count = None
file_row.status = FileStatus.UPLOADED
file_row.error_message = None
file_row.indexed_at = None
```

**`IngestionRun` is not mentioned in the function.** The code that retires a
previous run exists, and it is in the other endpoint: `_ingest_in_background`,
`routers/files.py:282-286`, reached only by `POST /files/{file_id}/ingest`.

Retrieval does not consult `FILE.status` at all. Both search paths filter on one
thing:

```python
# app/db/vector_ops.py:74 and :111
.where(col(IngestionRun.is_active).is_(True))
```

So `status = 'uploaded'` and `indexed_at = NULL` are written, and nothing reads
them.

**Measured 15 September 2026** on the test database. One READY file, one active
run, one chunk; then exactly the six assignments above, applied by hand; then the
real `_full_text_search`:

```
  before the replacement           : 1 chunk(s) -> 'the midterm is on the fourth of March'
  after  the replacement           : 1 chunk(s) -> 'the midterm is on the fourth of March'
  FILE.status                      : uploaded
  FILE.indexed_at                  : None
  INGESTION_RUN.is_active          : True
  after deactivating the old run   : 0 chunk(s)
```

**What a user sees.** They notice a mistake in a lecture PDF, upload the
corrected file, and ask about it. The answer quotes the sentence they just
removed, and cites `lecture4.pdf` — the same filename and the same `file_id`,
because it *is* the same row. Opening the file shows no such sentence. There is
no state in the UI that distinguishes this from a hallucination, and the citation
machinery is working perfectly the whole time.

The window opens at the PUT and closes at the next successful ingest. If nobody
re-ingests, it does not close.

**Fix.** In the PUT, before committing, deactivate every active run for the file,
using the same statement as `_ingest_in_background`:

```python
await session.exec(
    update(IngestionRun)
    .where(col(IngestionRun.file_id) == file_id, col(IngestionRun.is_active))
    .values(is_active=False)
)
```

Retrieval then returns nothing for that file until it is re-ingested, which is
the correct answer: what was indexed is no longer what the file contains.
`ix_ingestion_run_one_active` is a partial unique index on `file_id WHERE
is_active`, so deactivating without activating anything is legal.

**This finding descends from a wrong instruction.** The 8 September todo list told
AI-2, in writing:

> 旧版自己会退场 —— `ix_ingestion_run_one_active` 那段 deactivate/activate 的码
> 已经在跑了,你不用碰。

That sentence was written from the existence of the code, not from reading which
endpoint it sits in. The endpoint was then built to that instruction. **Owner of
the defect: the Lead. Owner of the fix: AI-2, 22 September**, the same date as
r79, because it is the other half of that row.

Note the shape it shares with R33: `PUT .../content` has tests, they pass, and
none of them could have caught this — a test of the PUT asserts what the PUT
writes, and the damage is in what a *different* endpoint reads.

**Closed 22 September.** AI-2 pushed the fix to `fix/file-replace-ingestion-run`
on 17 September (`9878edd`, nine lines in `routers/files.py` plus five test
assertions) and merged it into `dev` on 22 September as `631a7e0`. It sat unmerged
and unnoticed for five days; the Lead read it as an old commit on 20 September.

**It is closed on a reading of the code, not on a measurement.** The five new
assertions (`tests/test_file_routing.py:862-866`) check that an UPDATE setting
`is_active = False` was composed against `ingestion_run`. They do not check that a
replaced file's old chunk stops coming back from retrieval, which is what this
finding is about — the R33 shape once more. The regression test that would close it
on evidence is **r82, AI-2, 1–3 Oct**. If r82 slips, reopen this.

---

### R35 — a JSONB column typed `list[UUID]` could not be written at all

`MESSAGE.mentioned_file_ids` is declared `list[UUID] | None` over a JSONB column.
A JSONB column is written by calling `json.dumps` on the Python value, and
`json.dumps` has never accepted a `UUID`. So the column committed while it was
`None` or `[]`, and raised the moment it held a single id.

**Measured 21 September 2026** on the test database, against
`PGDialect_asyncpg` — the dialect this project runs:

```
mentioned_file_ids = None      OK
mentioned_file_ids = []        OK
mentioned_file_ids = [UUID]    StatementError: (builtins.TypeError)
                               Object of type UUID is not JSON serializable
```

**What a user sees.** They type `@[Lecture 1.pdf]` in the chat box and the
request fails. `useChatSession.tsx:143` builds `file_ids` from the resolved
mentions, falls back to the workspace scope, and sends it; `rag.py:260` puts
that list straight into the user turn, and the `await session.commit()` a few
lines later raises. **Not a wrong answer — a 500.** Selecting files in the
workspace does the same thing, because `ragScope` fills the same field.

**Two lines in the same constructor got it right.** `rag.py:337`:

```python
citations=[c.model_dump(mode="json") for c in citations],      # converted
mentioned_file_ids=request.file_ids,                           # not converted
scope_snapshot=snapshot.model_dump(mode="json"),               # converted
```

The pattern existed. It was applied to two of three fields.

**Why nothing caught it.** pyright cannot: `list[UUID]` is exactly what the
column claims to hold, and the error happens inside the driver. The tests
cannot: the ones covering `/rag/query` replace the session with a mock, and a
mock serialises nothing. **This is the third finding of that shape — R33, R34,
and now this.** Each time the test asserted what the handler intended and the
damage was one layer down.

**Fix.** `json_serializer` on the engine, so that it covers every JSON and JSONB
column rather than the two that happen to be known today:

```python
def _json_default(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
```

Deliberately not `default=str`: that would make every unserialisable object
succeed, so a model instance left in a payload by mistake would be stored as
`"<Course object at 0x7f...>"` and nobody would find out. Anything that is not
a `UUID` still raises exactly as before.

Reading the column back gives strings, and every response is built through a
Read model declaring `list[UUID]` — `MessageRead`, `MilestoneRead` — so pydantic
converts them back and the string form never leaves the database layer.

**The second half of the fix is the part that keeps it fixed.** Four test
fixtures built their own engines with a bare `create_async_engine(url)`, which
would not have carried the serializer — a test on such an engine passes on code
that fails in production, which is how this stayed hidden. Engines are now built
through one constructor, `app.db.database.make_engine`, and no call to
`create_async_engine` remains outside it.

Covered by `tests/test_jsonb_uuid.py`. Commenting out the one keyword argument
turns that test red with the exact `StatementError` above, which is how the test
was checked to have teeth.

---

### R36 — real lecture slides produce few or no chunks

Raised 22 September by AI-2 at the meeting. The evaluation corpus r52 was measured
on (`apps/api/evaluation/controlled_retrieval_evaluation_corpus.pdf`) was generated
for the purpose and extracts cleanly. Last semester's CPC251 lecture slides
reportedly produce almost nothing. AI-2 attributes this to image-only PDFs; AI-1
suggested a VLM.

**Nothing here has been measured.** docling does not run on the Lead's machine
(`ImportError: libgthread-2.0.so.0` out of `cv2`), so everything below is read off
the source rather than observed.

Two things the source says:

1. **OCR is not obviously the cause.** docling 2.119.0 defaults to `do_ocr=True`
   with `ocr engine = auto`. A PDF of page images should still be OCR'd unless the
   engine failed to load on that machine.

2. **`extract_text` keeps two labels out of thirty.**
   `apps/api/app/services/ingestion.py:24` reads
   `elif document_item.label.value == "text":`, so only `section_header` and `text`
   survive the loop. `DocItemLabel` has 30 members; the discarded ones include
   `list_item`, `title`, `paragraph`, `table`, `caption`, `code` and `formula`.
   Lecture slides are almost entirely bullets, which docling labels `list_item`.
   If that is the cause, the text extracts fine and this codebase throws it away.
   `ingestion.py:25` also drops any item with no `prov`, silently.

**What settles it**, in one run over the CPC251 PDF:
`Counter(t.label.value for t in document.texts)`.

```
all list_item     -> ingestion.py:24, a one-line fix
texts empty       -> then it is OCR, and a VLM is worth discussing
```

**Owner: AI-2**, to produce the counts. No row is opened and no work is scheduled
until they exist — a VLM is an entire second pipeline, and there is no number
supporting one yet.

**This also bears on r52 and r53.** Decision 1 of 22 September read the two
configurations' 20/20 Hit@5 as a ceiling effect and moved r53 to Recall@1 and MRR.
If the corpus is not merely easy but unrepresentative, a sharper metric on the same
corpus still measures the wrong thing. That does not change what r53 should do this
week; it changes what its number will be worth.

---

## Not a defect

### R9b — Flat folder hierarchy

Raised as a gap; it is a decision. Nesting was scoped out for v1 deliberately.
The column added under R9 above is the cheap hedge, not a reversal.

---

# Part B — second review

The second review proposed replacing the nine entities with thirteen, adding
`EMBEDDING_PROFILE`, `MESSAGE_SCOPE_COURSE`, `MESSAGE_SCOPE_FILE` and
`MESSAGE_CITATION`, and removing the denormalised columns on `CHUNK`.

It was run against the pre-correction diagram, so four of its recommendations —
`FOLDER.parent_folder_id`, dropping the global `sha256` UNIQUE, separating home
course from retrieval scope by name, and not cascading a course delete into
message history — describe changes this submission already contains. Two
independent reviews converging on the same four is treated here as
corroboration, not as two separate findings.

## Applied to the submitted diagram

### R11 — `COURSE` gains `name`

`code` holds "CPC251". Nothing held "Artificial Intelligence". A course was not
displayable without a lookup table that does not exist.

### R12 — `CHUNK.page_number` renamed `page_start`

It sits next to `page_end` and a chunk may straddle a page break, so the pair
describes a range. The old name did not read as one half of a range.

Neither of these touches a decision that was voted on.

## Settled on 18 August

### R13 — `MESSAGE_SCOPE_COURSE` junction table

The strongest item in the second review. A single `scope_course_id` cannot
express a turn scoped to two courses, which US-12 explicitly allows.

It also dissolves R3. With a junction table, deleting a course removes junction
rows and leaves the message intact — neither CASCADE nor RESTRICT has to be
chosen, because neither applies. **R3 and R13 are therefore a single vote, not
two.**

Cost: three tables, the ORM models on the `ck` branch, and a rewrite of the C4
scope-precedence contract. That is why it is a change request and not an edit.

**Declined 18 August.** Not on the merits — the argument above still stands — but on
the cost landing four days before the first migration. `mentioned_file_ids` already
carries cross-course scope for the case US-12 actually describes (@-mentioning files
from another course), so the gap is narrower than the finding reads.

**Reopen condition, recorded so this is not re-argued from memory:** the first US-12
acceptance case that genuinely needs two courses ticked on one turn, with neither
expressible as an @-mention. Until then it stays declined.

### R14 — `MESSAGE_CITATION` table (accepted in part)

The proposal replaces the `citations` JSONB with a table carrying a `chunk_id`
foreign key.

Rejected as proposed: `citations` is a deliberately frozen snapshot. Re-indexing
deletes and recreates chunks, so a `chunk_id` foreign key would either block
re-indexing or point at nothing afterwards. The proposal half-recognises this
and adds `quote_snapshot` alongside, which means storing both representations.

Accepted in part: the review surfaced a real gap. The current `citations` JSONB
holds `file_id`, `course_id`, `page` and `quote` — **no `chunk_id`**. Provenance
stops at the file. Adding `chunk_id` as a field inside the existing JSONB
recovers the traceability at no structural cost. That is the counter-proposal
going to 18 August.

**Accepted 18 August, then routed elsewhere by a Lead ruling the same night.** The
meeting carried "add `chunk_id` to the `citations` JSON". Writing it up against C4
showed that puts the id in the one place C4 forbids it, for the same reason this
finding rejects the foreign-key version: **a citation is a durable anchor, and a
chunk id does not survive a re-index.** A stale id in a citation is a broken
citation; the fix would have recreated the defect one layer down.

**Where it went instead:** `MESSAGE.scope_snapshot`, whose serialised shape is now
`ScopeSnapshot` in `app/schemas/rag.py` — `retrieved_chunk_ids` and `used_chunk_ids`
alongside the scope and the embedding model. A stale chunk id there is acceptable
because **nothing resolves against it**: the snapshot records what happened, it does
not point at anything that has to still exist.

Provenance is therefore chunk-level as the meeting intended, and `Citation` stays
anchored to file + page + quote. Recorded as an amendment rather than a silent edit
because the minutes say `citations`.

### R15 — `CONVERSATION.course_id` required

With R1 closed, `course_id` is the only ownership path and therefore mandatory.
A user cannot open a conversation before creating a course.

This is no longer hypothetical — it is the shape the submitted diagram has. It
is an onboarding constraint rather than a schema defect, and the options are a
default "Unsorted" course created at signup, or allowing a null `course_id` with
ownership carried some other way. 18 August.

**Accepted 18 August — the Unsorted course.** `POST /auth/register` now writes the
user row and one course row in the same transaction (`build_unsorted_course` in
`app/routers/auth.py`). `course_id` stays NOT NULL, so the ownership path stays
single, and first run is not a dead end.

Two details that are decisions rather than implementation:

- **`year` and `sem` are 0, not the calendar year.** They mark the row as a
  placeholder, and under R17's `UNIQUE (user_id, code, year, sem)` they guarantee
  an account holds exactly one Unsorted course however long it lives. A calendar
  year would have allowed one per year.
- **`status` is written as `"active"`.** `COURSE.status` is free text and its value
  set has never been defined — ratified 27 July, never specified since. This picks
  the obvious reading without claiming to settle it. **Still open, still unowned.**

### R16 — Soft delete on `COURSE` and `FILE`

`deleted_at timestamptz nullable` instead of a physical delete, to preserve
conversation history, citations and audit trail.

Related to R3 and R13: soft delete is a third answer to the same question.

**Declined 18 August.** v1 deletes physically. Reopen condition: the first time
someone deletes a course by mistake and asks for it back.

**The consequence, stated plainly because it was not part of the vote.** R3 carried
RESTRICT on `MESSAGE.scope_course_id`, and R16 removed the only other way a course
could leave the system. Together:

> **A course that has been the scope of even one turn cannot be deleted.** The
> database refuses the `DELETE`, and there is no `deleted_at` to fall back on.

So **v1 ships with no delete-course feature at all** — not as a cut item, as an
arithmetic result of two separate decisions. That is defensible for v1 (nothing is
lost, and history is exactly what RESTRICT is protecting), but it must be written
down, because the alternative is discovering it from a `ForeignKeyViolation` in a
demo. Three ways out exist when it matters: soft delete (R16, reopened), reparenting
the affected turns to a tombstone course, or `ON DELETE SET NULL` with a nullable
column — which sub-decision 2 of item 03 voted against for a still-valid reason.

## Folded into the first Alembic migration

R5 is **not** on this list, though the summary table carried it here until 22 Aug.
It is a query condition rather than a constraint; see its row for why.

- **R17** — `UNIQUE (user_id, code, year, sem)` on `COURSE` — **done 22 Aug**
- **R18** — `UNIQUE (ingestion_run_id, chunk_index)` on `CHUNK`
- **R19** — `is_active = true` implies `status = 'ready'`; an active run must not
  be a failed or in-progress one
- **R20** — the supporting index set: `COURSE(user_id)`, `FOLDER(course_id)`,
  `FOLDER(parent_folder_id)`, `FILE(folder_id)`, `FILE(sha256)` (non-unique, per
  R7), `INGESTION_RUN(file_id)`, `CHUNK(ingestion_run_id)`, plus the pgvector ANN
  index on `CHUNK.embedding`

## Declined for v1

### R21 — `EMBEDDING_PROFILE` as its own entity

Proposed to replace `embedding_model` and `embedding_dim` on `INGESTION_RUN`
with a foreign key to a model registry.

The correctness problem it targets is real and is already recorded as R5:
vectors from two models are incomparable even at equal dimension, so retrieval
must constrain to the active run's model. R5 fixes that at the query. A registry
table earns its keep once several models are in rotation; v1 runs one.

### R22 — `STORED_OBJECT` / `FILE` split for global deduplication

Separates the physical stored object (unique by checksum) from the logical file
a user sees, so two users can share one stored blob.

Correct, and the right shape if storage cost becomes a constraint. It is not one
at v1 scale, and it adds a table and a join to every file read.

## Contradicts a decision taken on 15 August

These two are recorded because they will return, not because they are open.

### R23 — remove `CHUNK.file_id` and `CHUNK.course_id`

Both are derivable through `INGESTION_RUN → FILE → FOLDER → COURSE`, and the
second review is right that storing them again is what makes R4 possible.

They are denormalised deliberately. `course_id` is the filter applied *before*
the vector scan; deriving it would put a four-table join in front of every
retrieval query. `file_id` is what a citation needs without a join. Meeting item
04 confirmed both.

The review's own closing section allows denormalisation for performance provided
the redundancy is constrained. That is R4, and R4 is scheduled. The columns stay.

### R26 — the ERD drew one of `CHUNK`'s three foreign keys

**Fixed 23 August.** `erd.mmd` carried a single relationship into `CHUNK`:

```
INGESTION_RUN ||--o{ CHUNK : "produced"
```

while the schema has three, each with `ON DELETE CASCADE`:

```
chunk_ingestion_run_id_fkey  -> ingestion_run    drawn
chunk_file_id_fkey           -> file             not drawn
chunk_course_id_fkey         -> course           not drawn
```

Both undrawn columns are annotated `FK` in the `CHUNK` block and described as
denormalised, which is why the gap survived the 16 August review: the columns
were visible, only the edges were missing. Denormalisation explains why a column
exists; it does not stop the column being a foreign key.

The reading it produced is wrong in a way that matters. Deleting a course looks
like it reaches `CHUNK` along `COURSE -> FOLDER -> FILE -> INGESTION_RUN -> CHUNK`,
four cascades deep, when there is also a direct edge. Anyone changing
`ON DELETE` at the `FILE` level to preserve chunks would find they are deleted
anyway, and nothing in the diagram would explain why.

Added:

```
FILE   ||--o{ CHUNK : "cited as"
COURSE ||--o{ CHUNK : "scopes"
```

`fk_chunk_run_file_agree` — R4's composite foreign key, added 22 August — points
at `INGESTION_RUN` like the first one and gets no separate edge; it is recorded
in the `file_id` annotation instead.

### R24 — a full folder tree

Nesting was scoped out of v1 at meeting item 04. `parent_folder_id` was added
under R9 as the forward-compatible hedge; the UI still ships flat.

---

# Part C — field restoration

Not a review finding. A defect in how this revision was produced.

The revised diagram was written from the meeting minutes rather than edited on
top of the ratified 27 July / CR-23 ERD. Checking it field-by-field against the
ratified version afterwards showed **eight ratified fields had been dropped** and
one unratified field added. All nine are corrected in the submitted diagram.

| Entity | Restored |
|---|---|
| `MILESTONE` | `position`, `description`, `status`, `file_ids`, `created_at`, `updated_at` |
| `CHUNK` | `token_count`, `created_at` |
| `COURSE` | `status` |
| `FILE` | `filename` — reinstating the Project Lead call of 3 Aug 2026, which chose `filename` over `name`. The interim `display_name` was a third spelling no decision authorised |
| `CONVERSATION` | `user_id` **removed** — see R1 |

`MILESTONE.status` and `file_ids` matter most: US-16 computes course completion by
counting `status = completed`, and US-17 displays a milestone's attached files
from `file_ids`. F4 is a MUST by team vote. Neither story is buildable without
them, and the omission would not have surfaced until F4 was started in late
September.

Four differences from the ratified ERD are deliberate and are recorded as
supersessions rather than drops:

| Ratified | Now | Why |
|---|---|---|
| `FILE.category` | `FOLDER` entity | CR-25 — a free-text label became a real entity |
| `FILE.course_id` | `FILE.folder_id` | CR-25 — course is derived through the folder |
| `FILE.storage_path` | `FILE.storage_key` | Object-store key, not a filesystem path |
| `USER.password_hash` | `USER.hashed_password` | The code already uses it (`schemas/user.py`, `routers/auth.py`). Same reasoning as the `filename` call, resolved the other way because here the code is the older commitment |

`datetime` is `timestamptz` throughout. A system whose citations must survive a
re-index cannot store naive timestamps.

---

# Part D — the 18 August meeting

Ten decisions, **all carried on the recommendation printed in the agenda**. Recorded
here rather than only in the minutes because six of them change this file.

| Label | Decision | Outcome |
|---|---|---|
| **R13** | `MESSAGE_SCOPE_COURSE` junction table | **Declined.** Reopens on a US-12 acceptance case needing two courses on one turn |
| **R16** | Soft delete on `COURSE` / `FILE` | **Declined.** Reopens on the first mistaken delete someone wants back |
| **D1** | Which `CONVERSATION` and which `FILE` — diagram or code | **Option A: both follow the diagram.** Code aligned the same night |
| **D5** | Owners for `FOLDER` and `INGESTION_RUN` | `FOLDER` → **AI-2**; `INGESTION_RUN` → AI-1, **reassigned to AI-2 after the meeting** |
| **D2** | `MESSAGE`: keep all three columns, and RESTRICT | **All three kept, RESTRICT carried.** Closes R3 |
| **R14** | `citations` carries no `chunk_id` | **Accepted**, then routed to `scope_snapshot` by Lead ruling — see R14 |
| **R15** | Required `course_id` blocks first run | **Accepted.** Unsorted course created at signup |
| **D3** | CR-28 — embeddings at 1024, model runs locally | **Approved.** The diagram recorded 1536 until now |
| **D4** | CR-29 — keep `verify.yml` | **Approved** |
| **D6** | C6-D1 / C6-D2 / C6-D3 | **b / b / a** |

The Lead's six calls were read out and all six passed. Two of them land in this
file's territory: **`FILE.size_bytes` → `bigint`** and **`USER.display_name` added to
the diagram** — the code had that column from the first commit and the diagram was
the side that was wrong.

## What this meeting did not settle

Three things are still unowned, and none of them was on the agenda:

1. **`COURSE.status` has no value set.** Ratified 27 July; never specified. R15's
   implementation writes `"active"` because it had to write something.
2. **`FILE.storage_key` is marked `UK` on the diagram and has no unique constraint
   in the code.** Folded into the first migration by default rather than by decision.
3. **`FOLDER` and `INGESTION_RUN` appear in no Gantt row**, even though D5 assigned
   both. Seventeen columns across two models now sit outside the schedule.

---

---

# Part E — found while implementing

## R25 — the database was going to store `'READY'` while everything else said `'ready'`

Found 20 Aug 2026, fixed the same day, and it would not have announced itself.

SQLAlchemy renders a PostgreSQL enum from the Python member **names**, not their
values. `FileStatus.READY = "ready"` therefore becomes the PG value `'READY'`,
while the ERD, `FileRead`'s `Literal`, and every JSON response say `ready`.

Nothing breaks through the ORM, which maps both directions silently. What breaks
is anything that touches the column as text:

- every hand-written query — `WHERE status = 'ready'` matches zero rows, with no
  error to trace
- **R19 itself.** `is_active` implies `status = 'ready'` is a CHECK constraint
  going into the first migration. Spelled lowercase against an uppercase enum it
  is never true, so it never rejects anything, and it looks like it is working.

Both enums now pass `values_callable`, so `filestatus` and `ingestionrunstatus`
carry the lowercase values the rest of the system already uses. It is free
today; after there is data it is an `ALTER TYPE`.

Applies to `FileStatus` (AI-3) and `IngestionRunStatus` (AI-2) equally — it is
SQLAlchemy's default, not anybody's mistake.

## Summary

| # | Finding | Status |
|---|---------|--------|
| — | Eight ratified fields dropped in drafting | **Restored — Part C** |
| R2 | `MESSAGE.course_id` → `scope_course_id` | Fixed in diagram |
| R3 | `CASCADE` → `RESTRICT` | **Closed 18 Aug — Decision 2 carried RESTRICT** |
| R7 | `FILE.sha256` global UNIQUE | Fixed in diagram |
| R9 | `FOLDER.parent_folder_id` | Fixed in diagram |
| R11 | `COURSE` had no `name` | Fixed in diagram |
| R12 | `page_number` → `page_start` | Fixed in diagram |
| R13 | `MESSAGE_SCOPE_COURSE` junction | **Declined 18 Aug** — reopen condition recorded |
| R14 | `citations` JSONB carries no `chunk_id` | **Accepted 18 Aug — routed to `scope_snapshot`, not `citations`** |
| R1 | `CONVERSATION.user_id` redundant | **Closed — the column was never ratified; removed** |
| R15 | Required `course_id` blocks first-run onboarding | **Accepted 18 Aug — Unsorted course at signup** |
| R6 | `mentioned_file_ids` has no FK; folders unrepresented | **Closed 25 Aug — both halves.** JSONB stays in v1 (18 Aug, on the recommendation). Folder @-mentions expand to a file list at send time and stay frozen — Decision 5, option A, so one column carries one kind of time. The UI has to say so at the moment of mention; logged against F2 |
| R10 | `MESSAGE` has no `sequence_no` | **Deferred** — accepted v1 defect, order implied by `created_at` |
| R16 | Soft delete on `COURSE` / `FILE` | **Declined 18 Aug** — and so **v1 has no delete-course feature**, see R16 |
| R4 | `CHUNK` FKs can contradict each other | **Closed 26 Aug, in two migrations.** r41 (`efda7a3`, 22 Aug) tied a chunk's run to its file via `fk_chunk_run_file_agree`. r42 (`2a22d57`, 26 Aug) tied `course_id` to `file_id`: Decision 02 option B put `course_id` back on FILE so a composite FK had something to point at, making it a chain — `CHUNK(file_id, course_id)` → `FILE(id, course_id)` → and `FILE(folder_id, course_id)` → `FOLDER(id, course_id)`. CR-31. Verified 11/11 by `check_r42.py`, including that a row where all three agree still inserts |
| R5 | Vector scan not filtered by embedding model | **Closed 1 Sep by AI-1.** Both `_vector_similarity_search` and `_full_text_search` now join `INGESTION_RUN` and filter on `is_active`. Decision 3 of 25 Aug named only the vector path; the lexical one was fixed in the same pass unasked. Measured 25 Aug, before the fix: with two runs over one file, the superseded run's chunks took rank 1 and 2 and ate two of five `top_k` slots, silently. **Retrieval layer, not the migration** — reclassified 22 Aug, because a constraint rejects a row that is itself invalid, and a chunk embedded by an older model is a perfectly valid row; what is wrong is comparing it against a query embedded by a different one, and no constraint sees a comparison. **The cross-file half is R5b, deferred with a trigger.** |
| R5b | Cross-file `embedding_model` filter | **Deferred 1 Sep, with a trigger.** The `is_active` join is sufficient within a file (`ix_ingestion_run_one_active`) and sufficient everywhere while one model is in use. **Trigger: the day `settings.MODEL_TYPE` changes without every existing chunk being re-indexed.** From that day two files can each hold an active run under a different model, and cosine distance across two vector spaces returns a number rather than an answer. It raises nothing. Whoever changes `MODEL_TYPE` owns this entry from that moment |
| R27 | Deleting a FILE row leaves its bytes on disk | **Deferred 1 Sep, with a trigger.** `FILE.storage_key` points at an object nothing owns; every FK into FILE cascades and the blob stays. Measured 1 Sep: 0 rows, 18 MB, six orphaned directories. `storage.delete()` exists with zero callers. **Not reachable in v1** — R16 declined soft delete and there is no delete-file endpoint. **Trigger: the day a delete endpoint lands**, from which it leaks on every use, silently, because a leak of disk is not an error. Goes with whoever writes that endpoint |
| R28 | Deleting a FOLDER row cascades to its files, runs and chunks | **Recorded 6 Sep, not a defect today.** `FILE.folder_id` and `FOLDER.parent_folder_id` are both `ON DELETE CASCADE`. Measured 6 Sep on the test database: one `delete from folder` against a non-empty folder reported `DELETE 1` and removed the folder, its file and its ingestion run, without raising. `delete_folder` guards this with a 409 on child folders and on contained files, both tested — **but the guard is in the router, not in the database**. **Reopen the moment a second code path deletes a FOLDER row** |
| R29 | Two citations can share a marker | **Closed 8 Sep — Decision 4, option A: render every entry carrying that marker.** One pill, several quoted lines; no contract change. Numbering the citations instead was rejected because it breaks `selected[marker - 1]`, the path both `_resolve_citations` and `check_grounding` use to reach provenance. F3 (r36) renders to this rule. Background: `marker` names a source, so two claims from one chunk both carry `[1]`, each with its own supporting line. Measured 6 Sep on a live call: one answer, two entries under `[1]`. `check_grounding` accepts it and rejects only marker-plus-quote repeats. **The open half is rendering** — a frontend resolving `[1]` by first match silently shows the first claim's evidence for the second claim, and both quotes are genuine, so it looks wrong from neither side. AI-3 owns `schemas/rag.py`, AI-1 owns the UI |
| R30 | A corrected re-upload becomes a second FILE row | **Closed 15 Sep — `PUT /files/{file_id}/content` landed in `02e8647` and is in `main`.** The replacement bytes go into the same FILE row, so the duplicate-row symptom is gone. What it does not do is retire the run indexed from the old bytes; that is R34. Originally: **open, raised 8 Sep.** `POST /files` always creates a new row and no endpoint replaces the bytes of an existing one, so a revised file arrives as a second row sharing the filename, each with its own active run. Measured 8 Sep on the development database: two rows named `Week3.pdf`, different `sha256`, **both `is_active`** — retrieval returns superseded and current text under the same name. **Neither R5 nor R5b covers it**: R5 is runs of one file, R5b's trigger is a `MODEL_TYPE` change and both runs here use the same model. `ix_ingestion_run_one_active` is partial on `file_id`, and these are two `file_id` values. A UNIQUE on `(folder_id, filename)` does not help — retrieval scope is a course, not a folder. **Proposed: `PUT /files/{file_id}/content`**, reusing the existing deactivate-then-activate path — and updating `uploaded_at`, since the list is ordered by it and a replaced file would otherwise not move. R27 removes the fallback: there is no delete endpoint, so the old version cannot be removed either. AI-2 owns the file router |
| R31 | Uploaded files live in the container's writable layer | **Fixed 9 Sep — a named volume on the `api` service.** Verified against the real stack: a file written in the container survived `docker compose rm -sf` and a rebuild, contents intact, so a redeploy on the r45 host now keeps the uploads. A healthcheck went in beside it — `api` had none while `db` did, so `ps` printed `Up` through the twenty-odd seconds `init_db()` spends reflecting under `echo=True`, and Docker binds the port at container start rather than when uvicorn listens. In that window a request is accepted and dropped: `curl` says `(52) Empty reply`, a browser's `fetch` rejects with a `TypeError` that serialises to `{}`, and the whole outage reads as a frontend defect — which is exactly how it presented on 9 Sep. Background: `docker-compose.yml` gives `db` a named volume and `api` none, while `STORAGE_DIR` resolves to `/app/storage` inside the image — so every uploaded blob sits in the writable layer Docker deletes with the container. The FILE rows are in the `db` volume and survive, so after a redeploy the browser lists every file and each resolves to a path that is gone. **Nothing raises at redeploy time**; it surfaces later, one read at a time. Measured 9 Sep on Docker 29.4.0-ce: same create/write/destroy/recreate cycle, `No such file or directory` without a volume and the file intact with one. **Opposite of R27** — R27 is bytes outliving their row, R31 is rows outliving their bytes; both are `storage_key` naming an object nothing owns. **Trigger: the first `docker compose down && up` on a host holding real uploads** (the r45 OCI instance). Fix is one volume on `api`. Goes with whoever does the deployment |
| R32 | Moving a file between courses is not supported | **Closed 8 Sep — Decision 5, option A.** The `409` from `PATCH /files/{file_id}` is the final answer, not a placeholder. Measured 9 Sep on the development database: with one ingested chunk present, **both** a `course_id`-only move and a `folder_id`+`course_id` move raise `ForeignKeyViolationError` on `fk_chunk_file_course_agree` — the constraint declares `ON DELETE CASCADE` and nothing for `ON UPDATE`, whose default is `NO ACTION`. So the router's guard is not what prevents the move; it is what turns an unhandled violation into a readable answer. Supporting it would mean deciding whether chunks move or are re-ingested, which changes what retrieval scope means while retrieval is unfinished (r48). No user story asks for it. Reopen only if one does |
| R33 | What a mocked session cannot test | **Recorded 9 Sep, not a defect.** `AsyncMock` has no foreign key, CHECK, partial unique index, `ON DELETE` behaviour, column default or timezone coercion — it accepts every correctly-shaped value. Four findings survived a green suite this way: R8, R25, the cross-course move (6 Sep) and R28. **The sharpest is the third: the passing test asserted the broken behaviour**, because a mock cannot disagree with the code under test. Rule: anything the database enforces is tested against a database, seeded inside a transaction that is rolled back; call order, branching and response shape stay on mocks |
| R34 | Replacing a file's bytes leaves the old chunks retrievable | **Closed 22 Sep — `9878edd`, merged into `dev` as `631a7e0`. Closed on a reading of the code; the regression test is r82, 1–3 Oct.** Originally: **open, raised 15 Sep.** `PUT /files/{file_id}/content` writes `status = 'uploaded'` and `indexed_at = NULL` and never touches `IngestionRun`; the code that retires a previous run lives in `_ingest_in_background` (`routers/files.py:282-286`), reached only by `POST .../ingest`. Retrieval filters on `IngestionRun.is_active` alone (`vector_ops.py:74`, `:111`) and reads neither field that the PUT wrote. Measured 15 Sep on the test database: the replaced file's old chunk still comes back from `_full_text_search` after the replacement, and stops coming back the moment the old run is deactivated. The user-visible shape is an answer quoting a sentence they just deleted, cited to the right filename and the right `file_id`. **AI-2, due 22 Sep** — the other half of r79. The instruction that caused it (「旧版自己会退场」, 8 Sep todo list) was the Lead's |
| R8 | `is_active` needs a partial unique index | **Done 22 Aug** (`efda7a3`) — `ix_ingestion_run_one_active` UNIQUE on `(file_id) WHERE is_active`. Verified from empty: a second active run raises `UniqueViolation`, further inactive runs are accepted |
| R17 | `UNIQUE (user_id, code, year, sem)` | **Done 22 Aug** — declared on `Course.__table_args__` and created in the initial migration as `uq_course_user_code_year_sem`. Verified from an empty database: a duplicate raises `UniqueViolationError`, while a second semester, a second year and a second user all insert. |
| R18 | `UNIQUE (ingestion_run_id, chunk_index)` | **Done 22 Aug** (`efda7a3`) — `uq_chunk_run_index`. Verified: a second chunk 0 in one run is rejected; chunk 0 in a re-index run is accepted |
| R19 | `is_active` implies `status = 'ready'` | **Done 22 Aug** (`efda7a3`) — `ck_ingestion_run_active_is_ready`, written `NOT is_active OR status = 'ready'`, lower case per R25. Verified: `is_active` with `processing` is rejected |
| R20 | Supporting index set | **Done 22 Aug** (`efda7a3`) — five indexes created. `COURSE(user_id)` and `CHUNK(ingestion_run_id)` deliberately **not** created: each is the leftmost column of a UNIQUE declared above, and a UNIQUE builds its own index. `INGESTION_RUN(file_id)` **is** created despite R8's index starting with the same column — R8's is partial, and a partial index only answers a query whose own predicate implies its `WHERE` |
| R25 | PostgreSQL enums were going to store member NAMES | **Fixed 20 Aug** — see below |
| R26 | The ERD drew one of CHUNK's three foreign keys | **Fixed 23 Aug** — `erd.mmd` had `INGESTION_RUN ||--o{ CHUNK` and nothing for `file_id` or `course_id`, though both are real foreign keys with `ON DELETE CASCADE`. Found by the Lead reading the rendered diagram against the constraint list. Two lines added, `erd.png` regenerated |
| R21 | `EMBEDDING_PROFILE` entity | Declined for v1 — see R5 |
| R22 | `STORED_OBJECT` split | Declined for v1 |
| R23 | Remove `CHUNK.file_id` / `course_id` | Declined — item 04, see R4 |
| R24 | Full folder tree | Declined — item 04, see R9 |

**Status of the r41 bucket, 24 August.** The seven constraint-and-index findings
scheduled into the first migration — R4, R5, R8, R17, R18, R19, R20 — have resolved
as follows:

| | Where it stands |
|---|---|
| **R8 · R17 · R18 · R19 · R20** | **Done 22 Aug**, on `dev` in `8767fc7` and `efda7a3`, each verified by rebuilding the database from empty and probing it |
| **R4** | **Closed 26 Aug.** The 25 August meeting chose the denormalised column over a trigger (Decision 02, option B), and r42 shipped it as a two-link chain. A trigger would have hidden the rule where neither code review nor `git log` shows it |
| **R5** | **Closed 1 Sep.** Never a constraint — reclassified 22 Aug as a retrieval-layer query predicate, assigned 25 Aug, fixed in `vector_ops.py` on both search paths. **R5b** carries the cross-file half, deferred with a written trigger |

**Every row on this list is now closed.** R4 closed on 26 August in r42
(`2a22d57`); R5 closed on 1 September in `vector_ops.py`. What remains is **R5b**,
which is not a defect but a deferral with a condition attached: it is correct
today and becomes wrong on a named day. Nothing on this list is marked
"Open — 18 Aug", and nothing is unassigned.
