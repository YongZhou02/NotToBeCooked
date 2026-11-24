# ERD — source of record

`erd.mmd` is the schema of record for NotToBeCooked. If this file and any other
document disagree, this file wins.

| File | What it is |
|---|---|
| `erd.mmd` | The diagram. Mermaid ER syntax. **Edit this, never the PNG.** |
| `erd.png` | Rendered from `erd.mmd`. Regenerate after every edit — see below. |
| `KNOWN_ISSUES.md` | Findings that are real and not yet fixed, with the reason and the schedule. Read it before assuming a gap is an oversight. |
| `CODE_VS_ERD.md` | Where the running code and this diagram disagree, field by field. **Read this before generating a migration** — autogenerate follows the code, not the diagram. **Generated, not hand-written**: `cd apps/api && uv run python scripts/erd_diff.py --write`. `--check` exits 1 when it is stale. |

Ratified 27 Jul 2026. Amended 4 Aug (CR-23) and 15 Aug 2026 (CR-24 → CR-27).
Handed in 16 Aug 2026 as `NotToBeCooked_ERD_2026-08-16.mmd` / `.png`.

## Filenames are deliberately undated

An earlier `docs/erd/` held both `not-to-be-cooked-erd.png` and
`not-to-be-cooked-final-erd.png`, and nothing in either said which one was
current. Git already records every version and when it changed, so the files
here keep stable names and the history lives in the log:

```bash
git log --follow -p docs/erd/erd.mmd
```

Date-stamped copies exist for hand-ins. They are snapshots, not the record.

## Regenerating the PNG

```bash
npm i @mermaid-js/mermaid-cli
npx mmdc -i docs/erd/erd.mmd -o docs/erd/erd.png -c cfg.json -p pp.json -b white -s 3
```

`cfg.json`:

```json
{ "theme": "neutral", "er": { "layoutDirection": "TB", "entityPadding": 14, "fontSize": 12 } }
```

`pp.json` (only needed where Chrome's sandbox is unavailable):

```json
{ "args": ["--no-sandbox", "--disable-setuid-sandbox"] }
```

Current output is 2352 × 1524, ~250 KB, from `@mermaid-js/mermaid-cli` 11.17.0
(24 Nov, ten entities, after ANSWER_FEEDBACK was added).
If a render comes out several megabytes, `-s 3` has been raised — three is enough
to read every annotation at 100%.

**Height moves between mermaid versions and that is not a defect.** The 13 Sep
render is 258px shorter than the 9 Sep one despite gaining a field, because the
layout engine changed underneath it. Check the content, not the dimensions:

```bash
npx mmdc -i docs/erd/erd.mmd -o /tmp/erd.svg -c cfg.json -p pp.json -b white
grep -c uncovered /tmp/erd.svg          # every field name should appear once
```

An entity or a field silently dropped from the diagram is the failure worth
catching, and a PNG cannot be grepped.

## Three traps, all hit for real

**A bare `%%` line crashes the ER parser.** A comment marker with nothing after
it. The error is `Parse error on line 1: Expecting 'ER_DIAGRAM', got '%'` and it
blames line 1 no matter where the bare line actually sits, which is what makes it
expensive to find. Every comment line needs content after the marker — `%% ---`
is fine, `%%` alone is not.

**Entity declaration order controls edge routing.** dagre ranks nodes in
declaration order, so reordering the blocks reintroduces edge crossings that were
removed by hand. The current order produces zero crossings. Check the render
after any reorder.

**A self-referencing relationship renders as a long dangling tail.**
`FOLDER ||--o{ FOLDER` routes as a spike down the page that shoves the
`FOLDER → FILE` edge across `CONVERSATION`. `parent_folder_id` is therefore
documented as a column with no edge drawn. The column carries the meaning.

## Merging `bao-sheng`: strip the blobs, then merge normally

**Done 20 Aug 2026. This reverses the squash-merge agreed with Bao Sheng on
16 Aug**, and the reversal is recorded here rather than applied quietly.

`ff5600f` and `f801754` added two 8K renders of a superseded 13-entity draft:
7.4 MB on disk, against 1.5 MB for the packed history of everything else in this
repository. `4b320e2` deleted them from the working tree, but the blobs remained
in the branch's history, and a normal merge would make those commits ancestors
of `dev` and then `main` — every clone from then on carrying the 7.4 MB.

Squash keeps them out. It also collapses thirteen commits into one, and on
20 Aug Bao Sheng asked the question that settles this: after the project, would
his contributions still be findable on GitHub for his resume? Under a squash the
honest answer was *the code, but not the commits*.

So the blobs were removed from the branch's history instead. Only 3 of his 13
commits touch those files, all three are ERD-document commits, and stripping the
two paths leaves everything else untouched:

```bash
git checkout bao-sheng
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --index-filter \
  'git rm -r --cached --ignore-unmatch "docs/erd/*8k.png"' \
  --prune-empty -- dev..bao-sheng
```

Then a normal merge, and the branch survives.

**Verify all four before force-pushing**, on a throwaway clone first:

```
no 8K PNG object reachable from the rewritten branch
all 13 commits present
every one still authored by CH'NG BAO SHENG
git diff <old tip> <new tip> is empty — the tree is byte-identical
```

The last one is the important one. It is what says the rewrite removed history
and nothing else.

**The rewrite is published with a force push, and `git pull` is the wrong
action afterwards.** This was learned the hard way on 20 Aug: the push was
done as a pull, git merged the old remote history back into the rewritten
branch, and every blob came back inside a merge commit that reported "no files
in commit". Content unchanged, history restored, work undone. GitHub Desktop
offers Pull in exactly that position, and it will keep offering it as long as
the local branch is an ancestor of the remote one.

**Keep a second copy of the old tip until both sides have verified.** Bao Sheng's
Codex proposed an archive tag; `filter-branch` leaves `refs/original/` behind on
its own. Either works, both were used, and one of them is what made the pull
incident recoverable. Delete them afterwards — a tag or ref pointing at the old
tip keeps the blobs reachable no matter how clean the branch is.

**`--author` still matters for any squash.** A squash commit is authored by
whoever runs the merge. That is not needed here, because a stripped branch keeps
each commit's own author.

The general rule this came from: **multi-megabyte binaries do not belong in git.**
The ERD of record renders to 306 KB.

## Changing the schema

The ERD was ratified by the whole team, so amending it takes a change request,
not a commit. A contract owner may define fields inside their own contract
unilaterally; adding or removing a column here is a different act.

When revising, **diff the new version against the ratified one field-by-field.**
Rewriting from meeting minutes instead dropped eight ratified fields on 15 Aug
2026 — including `MILESTONE.status` and `MILESTONE.file_ids`, which US-16 and
US-17 are built on, so F4 would have become unbuildable and nobody would have
noticed until late September. See Part C of `KNOWN_ISSUES.md`.
