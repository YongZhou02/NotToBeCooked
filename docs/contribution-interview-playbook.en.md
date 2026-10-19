# NotToBeCooked: Contribution Evidence and Interview Playbook

Audit date: October 2, 2026 (Asia/Kuala_Lumpur).

## 1. Identity, scope, and evidence

**Identity is provisional.** The current repository configuration identifies `BaoSheng05`. This audit groups that author with `CH'NG BAO SHENG`, whose commits use a different email. The user has been asked to confirm these identities. Until confirmed, interpret first-person examples as scripts for the candidate associated with these accounts, not verified statements about the person reading this guide.

Repository: [YongZhou02/NotToBeCooked](https://github.com/YongZhou02/NotToBeCooked).

Evidence examined:

- A fresh `git fetch origin`, followed by local author histories, file histories, selected implementation and test diffs, and current code.
- GitHub REST API records for all pull requests and issue entries returned by the repository. There are four PRs; the four issue-list entries are PRs, not four additional standalone issues.
- PR #4's commits, review, inline comment, and issue comments. Its review is an automated COMMENTED review, not a human approval.
- Stable patch IDs to identify equivalent changes on backup or rewritten branches.

Fetched `main` and `dev` both point to `c8810b8c3dd9822b5eec3f4f5bbf7e74db3917c9` at this snapshot. That is a timestamped observation, not a guarantee that the branches will remain identical.

| Evidence category | Count | What it means |
|---|---:|---|
| Candidate-authored non-merge commits reachable from main | 76 | Includes features, fixes, tests, documentation, formatting, and a revert; not 76 separate features |
| Candidate-authored merge commits reachable from main | 12 | Integration history; does not establish authorship of all merged work |
| Candidate-authored non-merge commits reachable from fetched origin branches | 78 | Includes two commits on the old bao-sheng branch that are not ancestors of main |
| Additional candidate-authored non-merge commits on local branches only | 11 | Includes historical backup/rewritten work; not evidence of 11 additional shipped features |
| Equivalent patch groups across examined branches | 8 | Repeated patches should not be counted as independent contributions |
| PRs opened by BaoSheng05 returned by GitHub | 1 | PR #4; low PR count does not imply little contribution because most evidence is in commit history |

The complete per-commit list, paths, branch status, and duplicate groups are in `output/contribution-audit/commit-ledger.md`; machine-readable data is in `commit-ledger.json`. Stashes are excluded. Deleted or unavailable remote branches, uncommitted work, verbal design discussions, and work in other repositories are outside this audit.

Git author metadata supports attribution but does not prove sole authorship, who made every design decision, or who personally ran every test. Two early commits explicitly include Copilot as co-author. Several later features were extended or corrected by teammates. Interview wording should reflect that collaboration.

This audit reviewed code and historical evidence; it did not rerun the full test suite, benchmark, deployment, or end-to-end workflow. Historical test counts are reported as historical claims, not current verification.

## 2. Your strongest professional positioning

If these accounts are yours, the evidence supports positioning yourself as:

> A backend-focused developer who also contributed across the frontend and API boundary, with particular experience in document ingestion, resource APIs, data consistency, and retrieval evaluation.

Avoid introducing yourself as merely “the person who made the file explorer.” Your work spans document preparation, persistence, lifecycle APIs, UI integration, and evaluation. Avoid claiming to have independently built the entire RAG system.

### A simple 30-second contribution answer

> My main contributions were document ingestion and file-management APIs. I worked on parsing documents, creating chunks with source metadata, and tracking ingestion status. I also connected the file browser to real backend APIs. Two areas I focused on were keeping search results consistent when a file was replaced and evaluating how chunk size affected retrieval.

### A fuller 60-90-second answer

> NotToBeCooked is a study assistant that answers questions using a student's course materials. My main contribution was the document and file-management workflow, from ingestion to API integration.
>
> I implemented document extraction and token-based chunking, preserving headings and page ranges so retrieved content could be traced back to its source. I also added processing orchestration, ingestion status handling, and course, folder, and file APIs with ownership checks.
>
> Later, I connected the file browser to real APIs using query and mutation hooks, including cache invalidation and polling while files were being indexed. One important correctness fix was deactivating old ingestion runs when a file was replaced, so retrieval would not use content that no longer matched the file.
>
> I also built a controlled evaluation comparing 350-token and 500-token chunks. Both reached the same Hit@5 on our small test corpus, so I treated the result as limited evidence rather than claiming one configuration was universally better.
>
> Other team members implemented important parts of authentication, retrieval, generation, and grounding. My role was to contribute these document workflows and integrate them with the wider system.

Use only the parts you can explain from memory. These are contribution statements, not claims of production scale or sole ownership.

## 3. Contribution map across the project

| Area | Evidence and actual contribution | Interview emphasis |
|---|---|---|
| Early integration | `9dbda8d`: backend health-check connection from the web app; `0d97cf7`, `4ccc49c`: ingestion endpoint/schema/contract work | Learning and connecting the HTTP boundary; early commits include AI co-authorship |
| Document ingestion | `f8707f9`, `796b5f8`, `b266e44`: Docling extraction and page/heading metadata | Preparing useful, traceable data for retrieval |
| Chunking and tokenizer integration | `b569b41`, `f60b48b`, `632c0fa`, `d2c66c5` | Token counts, long-text splitting, original-text offsets, and context boundaries |
| Models and ERD | `eaabf7f`, `29b2742`, `5c67578`, `566419b`, `ae98f08` | Contributed diagrams/model alignment, Folder/IngestionRun models, and model registration; architecture decisions were collaborative |
| Processing and status lifecycle | `93ee9a2`, `140b40f`, `cf73bc0`, `b40f5e3`, `1f35022` | Orchestration, empty-content handling, state transitions, tests, and test tooling |
| Ingestion-status API and 202 shell | `1d9bc54`, `1a806f5`; old-branch work `f6bb273`, `fa63696` | Ownership-scoped status lookup and queued response; background body was completed by a teammate |
| Course and folder management | `0752478`, `33f15a8`, `ad04377`, `d3d194b`, `c0d0a9e` | Create/list/update/archive, folder CRUD, default folders, schema and contract changes |
| File lifecycle APIs | `a8258a8`, `f5985de`, `c71e097`, `39938a0`, `f1404dc`, `acb4a59`, `02e8647`, `9878edd` | Listing, renaming/moving, content access, deletion, replacement, consistency and permission boundaries |
| File-explorer and upload UI | `185f0e3`, `975297d`, `1b86718`, `94f89e7`, `12f28cd`, `71126e7`, `b5c99e8`, `466aa81`, `8b34e80`, `7b84f81`, `ea33956`, `443f10a`, `8153d4b`, `7dedf50`, `4c4410e` | Explicit loading/empty/error and processing states, dialogs, upload validation, retry and permanent-delete behavior |
| Reader, layout, and accessibility | `7fa5a72`, `145dfb3`, `cf7df60`, `8ffe206`, `c2aaa1d`, `1824cf6`, `7156b1c`, `cb9fef7` | Keyboard interaction, focus indicators, preview/processing states, responsive layout |
| Retrieval experiment | `6041da4` | Controlled corpus, relevance rules, isolation, Hit@5, transparent limitations |
| Real API integration | `6ea628f` | Removed fixture-based explorer data, introduced query/mutation hooks, expanded API client operations, and wired document-summary intent |
| Summary and structured extraction | `6588949`, `6b80292` | Single-document summary scope/context, table and bullet preservation, tests |
| Integration fixes and configuration | `122773c`, `ec3b327` | Loopback API publishing and local configuration; use of the team's UUID serializer rather than inventing it |
| Cleanup, reversals, and merges | `5a09233`, `ee1e05e`, `51a8a1b`, formatting commits, `cece7bd` then `c02e915`, and 12 merges | Iteration and integration; reverted archive/restore UI is not a shipped feature |

The ledger is exhaustive for the selected author identities and refs. This table groups the work into interview themes; the strongest themes below have implementation-level explanations.

## 4. Story A: Keeping retrieval consistent after file replacement

**Priority: very high.** This is a small, specific fix with an important system-level consequence.

Evidence: [replacement endpoint](https://github.com/YongZhou02/NotToBeCooked/commit/02e8647499d61e418e117be5f6df1505ff1ecb94), [stale-run fix](https://github.com/YongZhou02/NotToBeCooked/commit/9878edd7a49a1769b7480640a9471688cf32d7b1).

### What changed

The replacement endpoint rewrites file content, updates metadata, and resets indexing state. The follow-up fix deactivates previously active ingestion runs for that file before committing the metadata update. Historical runs and their chunks remain, but they are excluded from retrieval until a replacement run becomes active.

### Spoken answer

> One correctness issue I addressed was stale retrieval after replacing a file. Replacing the original document did not automatically invalidate its old embeddings. That meant the reader could show the new file while search still returned chunks from the old content.
>
> I updated the replacement flow to deactivate the file's existing active ingestion runs and reset its indexing state. We retained the historical chunks, but retrieval already filtered by active runs, so the old content was excluded until the replacement was indexed. I also extended the routing test to check the invalidation step.
>
> The tradeoff is that the file is temporarily unavailable for retrieval. I prefer that to presenting an answer based on content that no longer matches the document.

### Follow-up drills

- **Why not just change FILE.status?** Retrieval filters active INGESTION_RUN records. The flag actually used by the search must also change.
- **Why retain old chunks?** Deactivation preserves the run's history without exposing it to current retrieval. Retention policy and storage cleanup are separate decisions.
- **Is replacing bytes and committing metadata one atomic transaction?** No. The filesystem and PostgreSQL are separate resources. A robust improvement could use immutable versioned objects, a database pointer switch, and recovery/cleanup logic.
- **What did the test prove?** The added routing assertion checks that the deactivation operation is issued. A mocked session does not prove full PostgreSQL semantics or crash recovery. An integration test should index A, replace with B, verify A is no longer searchable, index B, and verify B is searchable.
- **Did you design the active-run mechanism?** The evidence supports this replacement fix. The broader mechanism and constraints were team work, not automatically yours.

Understand before practising: FILE metadata, INGESTION_RUN, CHUNK, active filtering, `UPDATE`, `commit`, and the difference between a physical file and a retrieval index.

## 5. Story B: Connecting the file browser to real APIs

**Priority: very high.** Use this to demonstrate that you understand both sides of a button.

Evidence: [real API wiring](https://github.com/YongZhou02/NotToBeCooked/commit/6ea628fa828c2ac5c717666b413ac05c653a75cb).

### What changed

The dashboard moved away from mock course/file fixtures and local mutation overrides. New `useExplorerData` and `useExplorerMutations` hooks query actual resources and perform writes through the API client. Success invalidates affected caches. The file list polls every three seconds when pending files exist. Upload connects to ingestion rather than only changing a local display.

### Spoken answer

> I helped move the file browser from a prototype using mock data to a workflow backed by real APIs. The important part was making the UI reflect the backend's state instead of changing local arrays and assuming the operation succeeded.
>
> I introduced query hooks for courses, folders, and files, plus mutation hooks for actions such as upload, rename, move, and delete. After successful writes, the affected queries are invalidated so the server remains the source of truth. While a file is being indexed, the file list is polled to update its status.
>
> This required coordinating request shapes, resource IDs, loading and error states, and document scope across the frontend and backend.

### Follow-up drills

- **What happens when I upload?** UI validation -> FormData POST `/files` -> ownership check -> storage/metadata -> 201 -> POST ingest -> queued run/202 -> background processing -> file-status polling -> refreshed UI.
- **What happens when I rename?** Dialog input -> mutation -> PATCH file -> backend ownership and update -> commit/response -> cache invalidation -> list refresh.
- **Why invalidate queries?** The cached list may no longer match server state. Refetching resolves canonical metadata instead of maintaining independent local versions.
- **Why TanStack Query and Zustand?** Query manages fetched server data and cache lifecycle; Zustand manages client workspace state such as active course/tabs. They serve different purposes.
- **What if upload succeeds but ingestion fails?** The file and its metadata can exist while indexing is pending or failed. The UI must represent these distinct states and offer a useful retry/error path.
- **Is polling ideal at every scale?** No. Its cost grows with clients. Stop when not needed; consider longer intervals, backoff, or push updates if the workload justifies them.

Do not claim to have originally written the entire dashboard, chat hook, authentication, or API client. Their foundations include teammate work. Your evidence supports substantial extension and integration.

## 6. Story C: Building useful, traceable document chunks

**Priority: high.** This is the clearest explanation of your backend contribution to RAG.

Evidence: [initial extraction](https://github.com/YongZhou02/NotToBeCooked/commit/f8707f9), [token-based chunking](https://github.com/YongZhou02/NotToBeCooked/commit/d2c66c5), [structured-content preservation](https://github.com/YongZhou02/NotToBeCooked/commit/6b802921050024a32aff926d8e7baf5d1318fac0).

### Spoken answer

> I worked on turning parsed documents into chunks that were useful for retrieval. Each chunk carries its content, heading, and page range so we can connect a search result back to the document.
>
> I changed chunking from word-based limits to token-based limits using the embedding model's tokenizer. For long text, I used token offsets to split the original string rather than reconstructing it from decoded tokens.
>
> I later improved extraction to walk document items in order, include tables as Markdown, and preserve bullet-like items that the parser labeled as section headings. Otherwise, useful source content could disappear before retrieval even started.

### Follow-up drills

- **Why tokens rather than words?** The model processes tokens, and the relationship between words and tokens varies by language and text. The tokenizer aligns the budget with the model's representation.
- **Why offsets?** They locate a token boundary in the original string, allowing a split without depending on tokenizer decoding to reproduce formatting exactly.
- **Why preserve headings?** They give a chunk topical context and help avoid mixing unrelated sections.
- **Why preserve page ranges?** They support source tracing and citation navigation. Page metadata depends on the document format; a fallback page value is not proof of real page coordinates in DOCX.
- **Why tables?** Some course material exists in table cells; extracting only prose drops that evidence. Markdown preserves a usable textual representation of the table.
- **Does the current splitter provide overlap?** Do not claim an overlapping-window design unless you implement it. The inspected code splits and accumulates content by token budget and heading boundaries.
- **Does this support all scanned documents?** No. The current PDF parser configuration disables OCR.
- **What would you test next?** Content preservation, long unbroken text, mixed languages, table text, page/heading boundaries, joined-text token counts, and malformed or empty documents.

Do not claim to have written the embedding model or trained it. Your work uses the tokenizer/model and prepares its inputs.

## 7. Story D: A controlled chunk-size evaluation

**Priority: high.** This demonstrates experimental reasoning without invented performance improvements.

Evidence: [original experiment](https://github.com/YongZhou02/NotToBeCooked/commit/6041da48433ad0c8fc3759dbf95bc78f3ac3514d), [committed results](https://github.com/YongZhou02/NotToBeCooked/blob/6041da48433ad0c8fc3759dbf95bc78f3ac3514d/apps/api/evaluation/chunk_retrieval_results.md).

### Recorded experiment

| Item | Recorded value |
|---|---|
| Corpus | One controlled 20-page PDF |
| Extracted items | 106 |
| Questions | 20 |
| Relevance condition | Expected page range AND at least one approved evidence phrase |
| Comparison | Maximum chunk size 350 versus 500 tokens |
| 350-token chunks | 34 chunks; Hit@5 = 20/20 |
| 500-token chunks | 20 chunks; Hit@5 = 20/20 |

These are historical repository results, not measurements rerun for this audit. The report does not establish production accuracy, answer quality, lower latency, or lower cost.

### Spoken answer

> I built a controlled retrieval experiment to compare 350-token and 500-token chunks. I kept the PDF, questions, embedding model, query vectors, and search configuration the same, so chunk size was the main variable.
>
> A hit required a retrieved chunk to match both an expected page and an approved evidence phrase. On the 20-question corpus, both configurations reached 20 out of 20 at Hit@5. The larger chunks produced fewer chunks, but this did not prove they were better overall.
>
> The benchmark had a ceiling effect. To distinguish the configurations more meaningfully, I would expand the corpus and evaluate ranking quality, latency, and answer quality. The original evaluation data was inserted within a transaction and rolled back afterward.

### Follow-up drills

- **Define Hit@5.** The fraction of questions for which at least one relevant chunk appears among the top five retrieved results.
- **Is that answer accuracy?** No. It measures retrieval success under the stated relevance rule; generation and factual correctness are separate.
- **Is that Recall@5?** Not generally. Hit@5 only requires one relevant result; recall needs a definition of all relevant items and measures how many were recovered.
- **Why page and phrase together?** A page alone can contain unrelated material; the phrase adds a content criterion. This heuristic may still miss paraphrases or accept imperfect evidence.
- **Why switch active runs?** Only the tested chunk set should be eligible for retrieval during each configuration's measurement.
- **Who added MRR and the newer ranking comparison?** `94c2ae2` is authored by Calvin Khoo. Claim the original experiment, corpus/question assets, and Hit@5 work; describe later ranking metrics as a teammate extension.
- **Why not say 500 was faster?** Fewer chunks were recorded, but latency was not reported. A hypothesis is not a measured outcome.

## 8. Story E: Ownership-aware resource APIs

Evidence: [course/folder creation and listing](https://github.com/YongZhou02/NotToBeCooked/commit/0752478), [folder CRUD](https://github.com/YongZhou02/NotToBeCooked/commit/ad04377), [cross-course move rejection](https://github.com/YongZhou02/NotToBeCooked/commit/c71e097), [file-content PR #4](https://github.com/YongZhou02/NotToBeCooked/pull/4).

### Spoken answer

> I implemented several course, folder, and file-management endpoints. Beyond the basic CRUD operations, I focused on resource ownership and consistency. A valid login token identifies the user, but it does not mean the user owns every file ID they submit.
>
> For file-content access, the query joins the file to its folder and course and filters by the current user's ID. If nothing matches, the endpoint returns 404. I also rejected cross-course file moves because changing the folder alone could make the file's course metadata inconsistent with its indexed chunks.
>
> I updated the API contracts and added tests for success and failure paths, so the frontend and backend agreed on the operation's shape.

### Follow-up drills

- **Authentication versus authorization?** Identity versus permission to access a particular resource.
- **Why 404 for another user's file?** It avoids confirming whether an inaccessible identifier exists. It is a resource visibility policy, not a replacement for actual filtering.
- **Why reject cross-course moves rather than support them?** Supporting them needs a defined policy for denormalized course metadata, chunks, references, and indexing. The implemented restriction preserves the current invariant.
- **Does a mock prove the ownership SQL is correct?** No. A mocked result tests response handling; a real two-user database test is needed to validate the actual predicate and joins.
- **Did you build the JWT authentication system?** PR #2 and the main authentication foundations belong to Calvin105. Describe resource-level checks on top of the team's authentication system.

### A review issue you should understand

PR #4's automated review identified that the server returned file bytes but the generated contract had a void/absent response representation. Returning `FileResponse` does not, by itself, prove OpenAPI describes the binary response correctly. The reviewed PR contains the feature commit and a merge, not a separate response-schema fix.

The later API client handles content as a Blob (`parseAs: "blob"`). That is useful integration, but it does not prove the generated OpenAPI schema issue was repaired. Do not claim to have resolved this review without checking the specific schema diff. The review is an opportunity to explain the difference between runtime behavior, client parsing, and API contract documentation.

Source: [binary-response review comment](https://github.com/YongZhou02/NotToBeCooked/pull/4#discussion_r3975837193).

PR #4's description reports 11 file-routing tests and 59 tests in a full verification run at that time. These are historical PR-body claims; the audit did not rerun or independently reproduce that run.

## 9. Story F: Processing lifecycle and an honest async claim

Evidence: [processing orchestration](https://github.com/YongZhou02/NotToBeCooked/commit/93ee9a2), [status and empty-content handling](https://github.com/YongZhou02/NotToBeCooked/commit/b40f5e3), [status API](https://github.com/YongZhou02/NotToBeCooked/commit/1d9bc54), [202 interface shell](https://github.com/YongZhou02/NotToBeCooked/commit/1a806f5).

### Spoken answer

> I implemented the processing orchestration that connects parsing, extraction, chunking, embeddings, and chunk persistence. I also added lifecycle handling so ingestion runs record processing, ready, or failed status with timestamps and error information. Empty extracted content is detected before embedding generation.
>
> I contributed the ingestion-status endpoint and the change to a queued 202 response. The asynchronous workflow was collaborative: a teammate completed the background execution body and later moved blocking processing off the event loop.

### Essential ownership distinction

- Your candidate commit `1a806f5` creates the queued response and registers a background task, but its background function still raises `NotImplementedError`.
- `430668d` by SussyMouse completes that background body.
- `2076c8a` by SussyMouse moves parsing and embedding work off the event loop using `to_thread`.

You can explain all these mechanisms, but the record does not support saying you independently implemented all of them.

### Follow-up drills

- **Why detect empty content before embedding?** There is no useful chunk to embed, and the user needs a meaningful failure state rather than an apparently successful empty index.
- **Why a separate background session?** The task must manage its own database lifecycle rather than rely on the request session remaining valid after the response.
- **What does 202 guarantee?** Acceptance, not completion or durable execution.
- **Does async make parsing non-blocking?** No. A synchronous parser called directly inside an async function can still block the event loop.
- **What would you improve?** A durable queue, retry policy, concurrency limits, idempotency, and recovery of interrupted runs, justified by workload requirements.

## 10. Story G: Summary intent and complete-document context

Evidence: [summary retrieval and wiring](https://github.com/YongZhou02/NotToBeCooked/commit/6ea628f), [summary context/prompt changes](https://github.com/YongZhou02/NotToBeCooked/commit/6588949).

### Spoken answer

> I contributed a separate document-summary path because answering a focused question and summarizing a whole document need different source selection. A top-k query can retrieve relevant passages but still omit the middle or end of a document.
>
> For summary intent, the backend requires one file, checks ownership, and reads the active ingestion run's chunks in document order. I also changed context selection so that summary mode was not restricted by the normal source-count cap, and added summary-specific instructions and tests.
>
> This improves source coverage, but supplying all chunks still has context-window and cost limits. For very long documents, I would consider hierarchical summarization rather than assuming the full document always fits.

### Follow-up drills

- **Is the intent classifier an ML model?** The inspected frontend classifier is rule/regex based. Do not call it an intelligent learned classifier.
- **Does full context guarantee a complete summary?** No. Model attention, output limits, context limits, and grounding behavior still matter.
- **Does temperature zero guarantee deterministic or correct output?** No. It reduces sampling variability; it does not prove correctness or guaranteed reproducibility.
- **Did you implement the grounding gate?** Its foundation and later quote-filtering changes were teammate work. Your contribution includes summary integration and tests around that existing pipeline.

## 11. Story H: File deletion across database and storage

Evidence: [delete endpoint](https://github.com/YongZhou02/NotToBeCooked/commit/f1404dc), [delete-order correction](https://github.com/YongZhou02/NotToBeCooked/commit/acb4a59).

### Spoken answer

> I added file deletion and corrected the order of operations across the database and file storage. Deleting the physical file first was risky: if the database commit failed, the record would still exist but its file would already be gone.
>
> I moved physical deletion after the database commit. This protects against that failure case, but it does not make the two resources atomic. If storage deletion fails afterward, an orphan file can remain. A cleanup job or an outbox-based deletion workflow would make recovery more reliable.

### Follow-up drills

- **Did this solve every failure case?** No. It improves the failure order but leaves a cleanup/retry problem.
- **Would a SQL rollback restore a deleted file?** No. PostgreSQL does not own the local filesystem transaction.
- **What would an outbox do?** Record a cleanup obligation in the same database transaction, then let a worker perform and retry physical deletion.

This example can be explained without pretending the project already implements an outbox.

## 12. Supporting UI, testing, and environment contributions

These are valuable secondary examples, especially for frontend or general software-engineering interviews.

- **Upload usability:** multi-stage upload, extension/size/duplicate-selection checks, request errors, and recovery (`ea33956`, `8153d4b`). Explain why frontend validation supplements backend enforcement.
- **Visible lifecycle states:** status badges, explorer loading/empty/error screens, retry dialog, and reader processing states. Explain why “uploaded” and “ready” mean different things.
- **Accessibility:** keyboard actions, visible focus, and narrow-viewport fixes. Describe the concrete interaction you changed; do not claim a full accessibility certification.
- **Contracts and tests:** resource endpoint changes also update OpenAPI/generated types and tests. Generated-file line counts are not handwritten implementation volume.
- **Local container settings:** `122773c` binds the API port to loopback and supplies local origins/model settings. Its title says “secure,” but the diff still includes development configuration and does not establish a comprehensive production-security solution.
- **UUID integration:** `ec3b327` stops manually converting message UUID lists and relies on the database serializer. The serializer itself is introduced in teammate commit `3f239e1`.
- **Reverted archive UI:** `cece7bd` is reverted by `c02e915`; permanent deletion follows in `4c4410e`. Explain the final behavior rather than claiming all intermediate features shipped.
- **ERD evolution:** diagrams and model contributions are real. The final architecture and later constraints have multiple authors; claim contribution and alignment, not sole design ownership.

## 13. Attribution boundaries you must keep clear

| Do not claim sole authorship of | Evidence / accurate alternative |
|---|---|
| Full authentication and token-refresh system | Calvin105's PR #2. Say you built resource APIs on top of the team's auth. |
| Original embedding/query model service and hybrid RRF implementation | Calvin Khoo's `5c7b5b8`, `8928473`. Say you used and integrated them and evaluated retrieval. |
| Original real generation and grounding pipeline | SussyMouse's `6eee72b`, `6737eb2`, and later team changes. Say you extended the summary workflow. |
| The complete 202 background execution implementation | Your shell is `1a806f5`; SussyMouse's body is `430668d`. Describe collaboration. |
| Offloading CPU work with to_thread | SussyMouse's `2076c8a`. Explain why it matters without claiming the fix. |
| Model-loading concurrency lock | Lim Yong Zhou's `9fb8c0e`. Your token-count helper is a different change. |
| The original JSONB UUID serializer | Lim Yong Zhou's `3f239e1`. Your `ec3b327` integrates with it. |
| MRR and later rank-comparison additions | Calvin Khoo's `94c2ae2`. Your original benchmark is `6041da4`. |
| Entire dashboard, chat session management, and API-client foundation | Calvin's earlier contributions exist. Describe your explorer extensions and API integration. |
| An independently designed final database schema | Multiple authors and team decisions. Identify the models and diagrams you actually contributed. |

Knowing a teammate's code is a strength. The appropriate wording is “our system does X; my contribution was Y.”

## 14. Questions to practise, in order

1. **What was your individual contribution?** Give the short answer from section 2, then name two concrete stories.
2. **Walk me through clicking Upload.** Explain both HTTP stages, metadata versus bytes, task states, and polling.
3. **Walk me through replacing a file.** Explain why old vectors cannot remain active.
4. **How did you decide on chunk size?** Explain the controlled experiment and its ceiling effect.
5. **How do you check that a user owns a file?** Explain the joins and ownership predicate.
6. **How did you keep UI state consistent with the backend?** Explain queries, mutations, cache invalidation, and failure states.
7. **What is the difference between async and a background task?** Explain response timing, blocking work, and durable execution.
8. **Tell me about a mistake or incomplete solution.** Deletion across resources, limited benchmark, or the contract mismatch is a concrete discussion; do not invent a personal discovery you did not make.
9. **Where does your project use OOP?** API client encapsulation; model/exception inheritance; explain which classes you used or extended rather than claiming authorship of all class definitions.
10. **What did AI help with, and what did you do?** State your actual workflow. Early commits explicitly show Copilot co-authorship, so do not describe all code as written unaided.
11. **What would you improve next?** Choose one limitation and propose a testable change: real cross-user integration tests, durable ingestion workers, immutable file versions, a harder benchmark, or explicit binary-response contracts.

### A responsible AI-assistance answer

> I used AI assistance for **[the parts you actually used it for]**. My responsibility was to understand the generated changes, check that they matched our data model and API contracts, and verify the relevant behavior. For example, **[a specific review, correction, or test you personally performed]**. I can walk through the implementation and explain its limitations.

Do not fill the example with a review or experiment you have not actually performed.

## 15. Translate evidence into interview impact

Use this structure:

**Problem → your exact change → why it matters → evidence → limitation.**

| Weak description | Stronger, evidence-based wording |
|---|---|
| I wrote some APIs. | I implemented course, folder, and file operations with ownership checks and matching frontend contracts. |
| I fixed a bug. | I prevented retrieval from using old document chunks after file replacement by deactivating the previous ingestion runs. |
| I connected the frontend. | I replaced fixture-driven file-browser state with API-backed queries and mutations, including cache invalidation and processing-status polling. |
| I used Docling. | I turned parsed document items into source-traceable chunks and preserved tables and bullet content that could otherwise be omitted. |
| We got 100% accuracy. | Both chunk configurations achieved Hit@5 of 20/20 on a controlled 20-question corpus; this did not measure overall answer accuracy. |
| I made deletion safe. | I improved deletion ordering to avoid removing bytes before a failed database commit, while recognizing the remaining orphan-cleanup case. |

Do not lead with commit count or added lines. Explain a consequence the user or system actually experiences. Do not claim measured improvements in latency, cost, or user outcomes where the record contains none.

## 16. A focused training plan

Start with three stories: stale-index invalidation, real API wiring, and the controlled chunk-size experiment. Add ingestion extraction as the fourth if the role emphasizes Python or AI systems.

For each story:

1. Read its linked commit and current function.
2. Explain the before/after behavior aloud in English in 60 seconds.
3. Draw the data relationships and name the HTTP method if applicable.
4. Answer the follow-up drills without looking at the script.
5. Perform one practical check yourself and record what it establishes and what it does not.

Use simple sentences. If asked about a part you did not implement:

> That part was implemented by my teammate. I understand how it connects to my work: **[explanation]**. My specific contribution was **[your change]**.

If you have not verified a behavior:

> I have not tested that failure case yet. Based on the code, I would expect **[reasoned behavior]**. I would verify it with **[specific test]** before claiming it is guaranteed.

### First mock interview prompt

> Tell me about your individual contribution to NotToBeCooked. Then explain a correctness issue you addressed when replacing a document.

Aim for 90 seconds. Name your role, one concrete change, the reason it matters, and one remaining limitation.
