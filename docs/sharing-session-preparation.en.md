# NotToBeCooked: Bao Sheng's Sharing Session Preparation

Prepared 6 October 2026 for the proposed 10/11 October sharing session. Code reference: local main `c8810b8`; local dev and cached origin/main and origin/dev point to the same commit. No fresh remote fetch was performed for this packet. Statements about implementation refer to this snapshot.

## 1. Your objective and what to bring

Your objective is to explain how your ingestion and frontend work turns an uploaded document into trustworthy, searchable material. Show the behavior, explain the engineering choices, acknowledge a limitation, and support your contribution claims with code and commits. You do not need to present every teammate's implementation.

Bring four things: this speaking outline; one small text-based PDF with a heading, bullet and table; a screenshot or recorded fallback of a successful ingestion; and the team's existing evidence reports. Keep the current evaluation report separate from Calvin's new run, so an old result cannot accidentally become a new measurement.

By the end of the meeting, aim to have a recorded decision about the meeting schedule, a disposition for each of the 19 open Gantt rows, the meaning of the 31 December date, and named owners for the small remaining commitments. These are proposed outcomes, not decisions already agreed.

Suggested opening:

> My part is ingestion and the frontend file workflow. I will show what happens after upload, explain how I preserve useful document content, and discuss how the UI reflects processing and failures. I will separate my implementation from the retrieval and generation work my teammates own.

## 2. Availability reply and proposed agenda

10 October 2026 is Saturday; 11 October is Sunday. The meeting time is not confirmed. Your availability has not yet been supplied, so replace the fields before sending this draft yourself:

> I'm available on Saturday, 10 October, from [start] to [end], and on Sunday, 11 October, from [start] to [end], Malaysia time (UTC+8). For my sharing, I will cover ingestion and the frontend: Docling extraction, labels and OCR choices, token-based chunking, and the real API file-browser workflow. I'll bring the existing chunk-size evaluation and be clear about ownership and limitations.

Suggested 90-minute agenda, adjustable by the team:

- 0-5 minutes: agree on the session outcome and confirm what maintenance mode means.
- 5-20: Calvin presents retrieval and the new evaluation, including corpus and metric definitions.
- 20-35: Bao Sheng presents ingestion and frontend, with a short demonstration.
- 35-50: generation/grounding owner presents the prompt, citation checker and September examples.
- 50-65: interview-style questions and cross-layer integration questions.
- 65-85: classify the 19 remaining rows and decide meeting frequency and the December date.
- 85-90: read back decisions, owners, evidence and next review date.

If time is limited to 60 minutes, use 10 minutes per person, 20 minutes for maintenance decisions, and 10 minutes for opening and action recap. Do not let the technical demonstration consume the time reserved for decisions.

## 3. Maintenance mode: your suggested position

Suggested position: support maintenance mode, replace compulsory weekly development meetings with asynchronous updates and an optional monthly review, and finish a small set of reliability/documentation items before freezing new feature commitments. This is a recommendation for discussion, not an agreed policy.

English statement:

> I support moving to maintenance mode because our semester workload has changed. I would keep the existing core workflow usable, fix defects that affect data integrity or the demo, and defer new product features. I suggest asynchronous updates with a monthly check-in when there is something to review. For each open Gantt item, we should record whether we will finish it, defer it, or remove it from scope, rather than leaving all 19 items as active commitments.

Define maintenance concretely:

- Accepted work: broken core workflows, data-loss or stale-data defects, dependency compatibility, necessary setup documentation and small reproducibility improvements.
- Optional learning work: experiments and UI improvements when an owner has time, with no weekly delivery promise.
- Deferred work: large new features, production rollout or infrastructure expansion unless the team explicitly recommits.
- Communication: one visible issue list; short updates stating problem, impact, owner and proposed action; a check-in when a decision requires the whole team.
- Completion: an issue closes with its evidence, such as a regression test or a demonstrated workflow, rather than a verbal "done."

Do not accept responsibility for immediate support unless you can actually provide it. Maintenance mode needs realistic availability, not an informal on-call obligation.

### Tuesday 8:30 pm options

Keep weekly meetings if external deliverables still require weekly coordination. Make them fortnightly or monthly if there is occasional shared work. Stop recurring meetings if no active milestone remains, and meet only for a decision or demonstration. Your suggested choice is a monthly optional check-in with asynchronous updates; agree a review date so the policy can change if it is ineffective.

### The 31 December end date

Clarify whether this is a coursework deadline, a planning placeholder, or a product finish date. A fixed academic obligation still applies even in maintenance mode. If it is only an internal target, propose changing it to a review/archive checkpoint, not a promise to ship every feature. Preserve the old baseline in the plan and record the agreed revision date. Do not silently remove historical commitments.

> Could we treat 31 December as a review checkpoint for documentation, known issues and project status, unless it is an external submission deadline? That would make the plan consistent with maintenance mode instead of keeping a delivery promise we no longer intend to follow.

## 4. The 19 open Gantt rows: a review method

The message reports 19 open rows out of 70. The actual workbook and full row list are absent from the inspected repository. This packet cannot identify or rank all 19 actual rows. The method below is ready to apply when the team opens the authoritative workbook.

For each row, ask: What behavior is missing? Does it block the current core demo or an external requirement? Does postponing it risk data loss or incorrect scope? Who can finish it? What dependency is missing? What is the smallest acceptance criterion? Is this an existing commitment or a new idea?

Use four dispositions:

- Finish: necessary for an external obligation or a stable core workflow; owner accepts a small scope and evidence requirement.
- Defer: valuable but not required now; remove from the active schedule and retain as backlog.
- Cut: the team deliberately removes it from current project scope; record the reason.
- Already implemented, verify and close: code exists but completion evidence or plan status needs updating.

Do not equate "deferred" with "finished." Do not use the 70-row denominator as a percentage of engineering completeness: rows can differ greatly in effort and value.

For every actual row, record these fields in the meeting: row ID; title; current evidence; disposition; owner; dependency; acceptance criterion; deadline or next review date. A deadline is appropriate only when an owner actually commits.

### Candidate topics to compare against the actual rows

These are implementation-based discussion topics, not a reconstruction of the missing 19-row list:

- File-browser API wiring: the README still describes fixtures, while `useExplorerData.ts`, mutations and dashboard code already use APIs. Compare against r81 before deciding whether only documentation/evidence remains.
- Ingestion failures and retries: preserve visible failure states and test empty-document behavior; check the current demo before adding new scope.
- Scanned PDF support: current PDF OCR is disabled. Either explicitly document text-based PDFs as the supported path or accept a separate OCR feature with realistic effort. Do not mark scanned-PDF support complete.
- File-content OpenAPI contract: the contribution audit identified a binary-response schema mismatch in PR #4. Reproduce the current client/contract issue before deciding whether it blocks a stable release.
- Roadmap UI/backend: repository comments refer to unfinished planning integration. Check actual product need before allocating more work.
- Staging hardening / production rollout: API README mentions r67/r69. These may be candidates to defer if no public deployment is required; actual plan status remains unknown.
- Documentation and evidence: record demo setup, fake versus real AI mode, test provenance and benchmark commands. These are relatively bounded handover tasks.

Suggested decision rule: prioritize data correctness, demonstrability and external obligations before optional features. Do not propose finishing all 19 simply to preserve an old schedule.

## 5. Your 12-minute presentation: slide and timing plan

Use this as a speaking plan even without slide software. Six slides plus a short demo are sufficient.

### Slide 1: My scope - 1 minute

Headline: "From uploaded files to searchable evidence."

> I worked on document ingestion and the file-management frontend. My main concerns were preserving document content, creating useful chunks with metadata, and showing the user whether processing succeeded or failed. Calvin owns the retrieval implementation and its current evaluation, while our other teammate owns generation and grounding.

Show a simple boundary: file selection -> upload API -> ingestion -> chunks -> retrieval handoff. State that the embedding model is integrated by the pipeline but not trained by you.

### Slide 2: Upload is not processing completion - 2 minutes

> Upload and ingestion are separate operations. Upload stores the original bytes and file metadata and returns 201. A second request starts ingestion and returns 202 with a run ID. Processing can take time, so the frontend displays status rather than treating the accepted request as a finished document.

Explain why this matters: the user must not receive a false success signal while the parser or embedding step is still running.

### Slide 3: Structured extraction - 2 minutes

> Docling gives us structured document items. I process them in document order, preserve body text and list items, export tables to Markdown, and retain heading and page metadata. I also addressed a case where a bullet was classified as a section heading, which could otherwise remove part of the source evidence from the chunk body.

Show one table, one bullet and its extracted content. Say explicitly that PDF OCR is currently disabled and scanned PDFs are a limitation.

### Slide 4: Token-based chunking - 2 minutes

> The chunker uses the embedding model's tokenizer rather than a word count. Long items are split using character offsets from that tokenizer so we preserve the original text. We start a new chunk when the token budget would be exceeded or the heading changes, and store the final text's token count with its metadata.

Show the 350/500 experiment: same Hit@5, fewer chunks at 500, limited corpus. Do not claim a universal optimum.

### Slide 5: Frontend consistency and failures - 2 minutes

> I connected the explorer to real APIs and used TanStack Query for server data. Upload, rename, move, delete and ingestion mutations invalidate the relevant queries. While any listed file is uploaded or processing, the file list refreshes every three seconds. The interface includes loading and failure states so users can distinguish an accepted upload from a ready document.

Discuss one real integrity issue: replacing bytes must deactivate the old active ingestion run so search does not use chunks from the previous version.

### Slide 6: Results, ownership and next steps - 1 minute

> The controlled chunk-size experiment used 20 questions over a 20-page PDF. Both settings achieved 20 out of 20 Hit@5, so the result shows no difference on that dataset. It does not prove answer accuracy. My strongest examples are structured-content preservation, the real API file workflow, and protecting consistency after replacement. The main limitations are disabled OCR, background-task durability and the filesystem/database boundary.

Reserve 2 minutes for a prepared demo or screenshots. If the parser is slow, show a previously completed run and the saved evidence rather than waiting silently.

## 6. What happens when the user clicks Upload?

### The complete request-to-result explanation

1. `UploadModal.tsx` checks selected file extensions and a per-file size limit. Selection deduplication uses filename and size; it is not a content-based deduplication service.
2. The dashboard supplies the upload callback with a destination folder. The browser sends multipart form data containing the file and folder ID to `POST /files`.
3. The backend authenticates the user and checks ownership through the folder's course. The course is derived from the authorized folder rather than trusting an arbitrary course ID from the browser.
4. Storage writes the bytes using a server-controlled key and records size and SHA-256. The original filename is metadata, not the trusted storage path.
5. A FILE record is committed. The upload response is 201 Created. At this point the original exists, but searchable chunks need not exist yet.
6. The frontend requests `POST /files/{file_id}/ingest`. The backend validates ownership, creates a QUEUED, inactive IngestionRun, commits it and registers a FastAPI background task.
7. The API returns 202 Accepted with the ingestion run ID. This means scheduled/accepted work, not successful ingestion.
8. The task opens its own database session. The run moves to PROCESSING; parsing/extraction/chunking run in a thread via `asyncio.to_thread` so blocking work does not directly occupy the request event loop.
9. The pipeline embeds chunk contents using the shared local model, checks the number of returned vectors with `zip(..., strict=True)`, builds Chunk rows and persists them.
10. On success, the run becomes READY; activation handling deactivates prior active runs before making the new run active. On failure, the processing transaction is rolled back and failure status is persisted.
11. The explorer's file-list query refreshes every 3,000 milliseconds while listed files are uploaded or processing. The UI then reflects the server's status.

Important distinction: an ingestion-run detail endpoint exists, but the inspected explorer refreshes the course file list; do not describe that UI as directly polling only `GET /ingestion-runs/{id}`.

### A 45-second interview answer

> Clicking Upload starts two API operations. First, the browser sends the file and folder ID as multipart form data. The backend checks ownership, stores the original file and metadata, and returns 201. Then the frontend requests ingestion. The backend creates a run and returns 202, while a background task parses the document, extracts structured text, chunks it, embeds the chunks and stores them. The frontend refreshes the file list while processing is pending and shows ready or failed status. I worked on the ingestion content handling and file workflow; the embedding model and the nonblocking execution improvement were shared team work.

## 7. Docling, labels, OCR and the content-preservation bug

Docling is the parser library. Your code chooses how to configure it and which parsed content to retain. A label is a category such as text, list item, section heading or table. The content layer distinguishes body material from page furniture such as repeated headers and footers. Provenance identifies source location when available.

### Current extraction rules

- Traverse `document.iterate_items()` so text and tables remain in the parsed document's order.
- Ignore items outside the body content layer.
- Use true section headings as metadata for subsequent content.
- Preserve text and list items as chunkable content.
- Treat section headers that begin with recognized bullet characters as content, so a classification error does not strip the sentence from the chunk body.
- Export tables to Markdown to retain a textual representation of their rows and columns.
- Skip empty content and unsupported labels.
- Keep the minimum and maximum provenance page numbers. When provenance is absent, current code uses page 1 as a fallback; this is not proof of a real page location in DOCX.

### Why OCR is disabled

The current PDF pipeline sets `do_ocr=False`, with the stated intent of avoiding searchable noise from decorative images/logos while using native PDF text. This is a tradeoff: an image-only scanned PDF may yield no useful extractable content. Do not say "we support every scanned document" or "Docling guarantees clean extraction."

> We currently prioritize PDFs with a text layer. We disabled PDF OCR to avoid introducing noise from decorative images. That means scanned documents are a known limitation. If scanned PDFs become a requirement, I would introduce an explicit OCR path and evaluate extraction quality on representative scans before enabling it broadly.

### The bullet-heading incident: a strong story

The grounding code records a September 24 case in which a first bullet was read as a heading. Its text was separated between heading metadata and chunk body. The model combined the pieces, but the citation checker compared the quote with the body, causing a mismatch. Your extraction fix preserves bullet-like headings as body content. Your teammate owns the grounding checker and its narrow quote-removal behavior.

> A document classification error was affecting a downstream citation check. A bullet had been treated as a heading, so part of the evidence was missing from the chunk body. I changed extraction to preserve bullet-like headings as content and added a regression test. My teammate handled the grounding logic. The lesson was that source preservation is a contract between ingestion and citation verification, not just a parsing concern.

Do not claim that this single fix solves every quotation failure. Tables, reading order and unusual formatting still need representative tests.

## 8. Tokenization and chunking: explain the mechanics

A token is a unit defined by a model's tokenizer. A token is not necessarily a word: punctuation, word fragments and different scripts can be split differently. Using the same tokenizer as the embedding model makes your size accounting more meaningful than a whitespace word count.

Current default `create_chunk(..., max_token=350)` is 350 tokens. The separate splitter's default is 500, but create_chunk passes its chosen budget into it. The evaluated 500-token configuration does not mean the application default changed to 500.

### Worked grouping example

This is an illustrative example, not a measured result. Suppose the current heading is "Indexes" and three extracted pieces contain 120, 180 and 90 tokens. The first two fit the running 350 budget; the third would take the sum to 390, so the current chunk is emitted and the third begins a new one. If the next item's heading changes to "Transactions," it starts a new chunk even if the current chunk has space.

The actual stored token_count is recalculated on the final joined content. The running budget sums individual piece counts; tokenization at join boundaries can differ. Therefore describe it as token-budget-based grouping, and validate final counts before promising a mathematically strict upper bound on every corpus.

### Why use offsets instead of decoding tokens?

The tokenizer returns the original-text character span for each token. The splitter takes the end character offset for the last allocated token and slices the original string. This avoids reconstructing the text through token decoding, which can alter formatting or spacing. The function recursively handles the remaining text.

> I use the tokenizer to decide where to split, but I slice the original text using its character offsets. That preserves the source wording, which matters because the citation checker later looks for exact source quotations after limited normalization.

### Metadata and tradeoffs

Each chunk retains file ID, chunk index, heading, page range, text and token count; persistence adds course ID, ingestion run ID and embedding. Chunk index preserves sequence for whole-document use. File/course/run IDs connect evidence with ownership and the active source version. Page metadata helps the UI guide a reader back to the document, subject to provenance limits.

Small chunks can improve specificity but lose context and increase record count. Large chunks retain more context but may dilute relevance and increase context usage. Current code uses heading boundaries and a token budget, with no explicit sliding-window overlap or late chunking. A heading kept only as metadata is not automatically included in embedded body text.

If asked about improvements, suggest validating final token budgets, avoiding extremely tiny fragments, testing tables and scans, and measuring retrieval quality across harder corpora. These are ideas, not implemented features.

## 9. Frontend: file browser, state and API contracts

The UI uses React and TypeScript. TanStack Query manages fetched server data and cache invalidation. Zustand manages client workspace state such as the active course or tab. These solve different state needs; a selected tab is not the same kind of state as the server's file list.

`useExplorerData.ts` fetches courses, the selected course's folders and its files. Course IDs are part of the folder/file query keys, and those queries are enabled only when a course is selected. This prevents accidentally fetching with an absent scope and separates cached lists for different courses.

Mutations perform upload, ingest, rename, move, delete and folder actions through the API client. Invalidating the relevant query asks TanStack Query to refetch authoritative server data. It does not guarantee every operation can be optimistic or that all network failures recover automatically.

### Important frontend numbers

- Size check: `50 * 1024 * 1024` bytes, exactly 50 MiB, although the UI calls it 50 MB.
- Selection extensions: pdf, md, markdown, doc and docx. A picker accepting a suffix is not proof of full parser compatibility for every file with that suffix.
- Pending-file refresh: 3,000 ms while any returned file has uploaded/processing status; no interval when that condition is false.
- Selection duplicate check: name plus size. Identical content under a different name can still be selected.

### Parallel batch uploads

The upload modal uses Promise.all over selected uploads. This overlaps requests; it is not a database transaction across the batch. Some requests may succeed before another fails, and Promise.all rejection does not undo them. A retry strategy should distinguish failed items from already completed ones. Raise this as a known design consideration rather than pretending the batch is atomic.

### What a robust UI explanation sounds like

> The frontend has to represent the server's lifecycle honestly. A file can be uploaded but not yet searchable, or processing can fail after upload succeeded. I connected the file browser to the real API, scoped queries by course, invalidated data after mutations, and showed processing and failure states. One future improvement would be per-file progress and partial-batch retry handling.

Generated TypeScript/Zod contracts improve request/response consistency, but do not replace backend authorization or runtime integration tests. A binary download response also needs a suitable contract; the audit's PR #4 finding should be checked against the current implementation before it is presented as resolved.

## 10. File operations and database consistency

### Ownership and moving files

The backend checks file ownership by joining File -> Folder -> Course -> User. Hiding a button in the frontend is not authorization. UUIDs are identifiers, not a security mechanism. Moving a file to another folder in the same course is different from moving it to another course; the current update route rejects cross-course moves with 409 to protect the stored course/chunk relationship.

> We validate the relationship on the server. Cross-course moves are rejected because the chunks and retrieval scope are associated with a course. Allowing the UI to change only the folder would leave inconsistent data.

### Replacing content

The replacement path writes temporary bytes and replaces the local stored file. Metadata is updated, the status returns to uploaded, and old active ingestion runs are deactivated. The old chunks may remain as historical rows, but should not be used as current searchable evidence. A new successful ingestion can create a new active run.

> I addressed stale search results after replacement. Once the original bytes change, the previous chunks no longer represent the current document, so I deactivate the old active run until the replacement is processed. This protects the link between the displayed file and searchable evidence.

The file replacement and database commit are not a distributed transaction. Local atomic path replacement does not make the database update atomic with the filesystem. Discuss compensating cleanup/reconciliation as a possible improvement, not as an existing guarantee.

### Deletion

Your deletion-order change performs the database commit before deleting stored bytes. This avoids a particular failure where a database rollback would leave a live row pointing at bytes already removed. It still allows an orphaned file if physical deletion fails after commit. Explain the remaining failure mode; that demonstrates judgment.

### Background-task limitations

FastAPI BackgroundTasks runs in the application process. It is not a persistent queue. A process crash can interrupt work, and slow parser/model work requires resource limits. `asyncio.to_thread` helps event-loop responsiveness but does not guarantee unlimited throughput or faster parsing. A persistent worker queue is a future option if reliability requirements justify it.

## 11. Numbers: what is measured, reported and pending?

### Confirmed repository report: September 21 chunk-size evaluation

Source: `apps/api/evaluation/chunk_retrieval_results.md`.

- Corpus: one controlled PDF, 20 pages, 106 extracted items.
- Questions: 20.
- 350-token configuration: 34 chunks, Hit@5 = 20/20 = 100%.
- 500-token configuration: 20 chunks, Hit@5 = 20/20 = 100%.
- Difference: 14 fewer chunks, approximately 41.2% fewer, on this corpus. This is record-count reduction, not a measured latency/cost saving.
- Relevant means expected page range AND at least one approved normalized evidence phrase.
- Same corpus, extraction, model, query vectors, search config, filters and top-k; chunk budget was the intended changed variable.
- Evaluation data was isolated by ingestion run and rolled back after the experiment.

> Both chunk sizes achieved the same top-five retrieval success on our controlled dataset. The larger chunks produced fewer records, but the benchmark reached a ceiling and cannot tell us which ranks relevant evidence better or which generalizes better. I would need a broader dataset and additional metrics before changing the default on that basis alone.

### Calvin's requested run: pending

The script is `apps/api/scripts/evaluate_chunk_retrieval.py`. Calvin owns the current retrieval evaluation in the sharing plan. Ask him to attach command, commit, date, model, corpus, per-query ranks and aggregate Hit@5 / Recall@1 / MRR. Do not fill in these values using the old Hit@5 report.

Read the script's exact definitions: its Recall@1 field represents the fraction of queries with a relevant first result. Do not describe it as general recall over all relevant chunks unless the implementation and ground truth support that definition.

For a first relevant rank r, reciprocal rank is 1/r; it is 0 when no relevant result exists within the evaluated cutoff. MRR averages those values across questions. Illustrative ranks 1, 2 and no hit give MRR = (1 + 0.5 + 0)/3 = 0.5. This example is not a project measurement.

### September 24 Gemini observations: code comments, not complete run logs

`prompt.py` records a 33-source summary with 7 of 22 failed quotes, all stitched from separated sentences. `grounding.py` records a case with 46 referenced citations, 45 exact quotations and one failed quote related to bullet-heading extraction. Treat these as separate recorded observations unless the generation owner supplies the full run chronology. Do not call them a controlled before/after accuracy benchmark.

You can explain their relevance to your layer, but say the generation owner measured and investigated those runs. A quote-verification count is not an answer-accuracy score.

### 127 passing tests: team-reported, provenance needed

The teammate's message reports 127 passing tests. This preparation did not rerun the suite, and no matching run log was found in the inspected files. Before showing that figure, attach date, commit, command, backend/frontend scope, skipped tests and environment. Say "our team reported 127 passing tests" until that provenance is available. Passing mocked unit tests does not establish real Gemini quality or successful scanning of every document format.

## 12. Ownership: say exactly what you contributed

The prior audit associates your work with the BaoSheng05 / CH'NG BAO SHENG author identities, consistent with local Git configuration and the teammate's scope allocation. Author history is evidence of changes, not proof of unaided implementation; reconcile this with your own recollection and AI usage.

### Strong examples with commit anchors

- Structured-content extraction: `6b80292`, "Preserve structured content during ingestion". Includes document order, table handling and bullet-heading preservation tests.
- Token splitting and accounting: `632c0fa`, `d2c66c5`, plus earlier chunking changes. Explain offsets, budget and source wording.
- Empty-document and ingestion status behavior: `b40f5e3`, `1d9bc54`, with processing tests and status endpoint work.
- Real API explorer wiring: `6ea628f`. Explain queries, mutations and UI states, not just the number of changed files.
- File operations: `39938a0` content endpoint, `f1404dc` deletion, `acb4a59` deletion order, `02e8647` replacement and `9878edd` stale-run deactivation.
- Original controlled chunk evaluation: `6041da4`. Calvin later extended the evaluator (`94c2ae2`) and now owns the requested run.

Commit links and the broader ledger are in `output/contribution-audit/commit-ledger.md`. Use one or two substantial examples in the presentation; do not recite commit counts as evidence of engineering quality.

### Team boundaries you should acknowledge

- Calvin: hybrid retrieval, RRF, embedding model integration and the current evaluator.
- Generation owner: prompt, citation checker and the stitched-quote fix.
- Shared ingestion work: you contributed orchestration, schema/content handling and status behavior; the working background execution and `asyncio.to_thread` improvement include teammate implementation.
- File-content frontend foundation and authentication include teammate work. Your API and explorer work should be explained as integration with those foundations.
- AI assistance: state the real assistance used for each story. Git history cannot tell whether AI wrote a draft, suggested tests or debugged an issue.

Safe wording:

> I implemented the structured extraction changes and connected the file-management workflow to the real API. My teammates implemented retrieval and generation, and we integrated the layers together. If I used AI for a draft or debugging, I would explain that explicitly, then describe what I checked, changed and tested myself.

Use that last sentence as a principle, not a fabricated account. Prepare your actual tool usage before the meeting.

## 13. Interview questions: ingestion fundamentals

### Q1. What does ingestion mean in your project?

> It is the process of turning the uploaded document into structured, searchable evidence. We parse it with Docling, extract useful content and metadata, split it into token-based chunks, generate embeddings and store the chunks with their file and ingestion-run relationships.

Follow-up: distinguish the original file, extracted text, a chunk and an embedding. An embedding is a numeric representation used for retrieval; it is not the generated answer.

### Q2. Why Docling rather than just reading PDF text?

> We wanted structured document items, including headings, lists, tables and provenance, rather than one undifferentiated string. The library gives us that structure, but we still need explicit extraction rules and tests because a label can be wrong, as our bullet-heading case showed.

Do not invent a benchmark comparing parser libraries if none was run. Say whether the choice was a team decision and what evidence you personally have.

### Q3. How do you handle a scanned PDF?

> Our current PDF path disables OCR, so a scanned PDF may produce no extractable content and the ingestion run should fail clearly. Supporting scans would require a deliberate OCR path, representative scans and quality checks. I would not describe that as implemented today.

### Q4. Why use tokens instead of characters or words?

> The embedding model consumes tokens, so the tokenizer gives a more relevant size measure. Words and characters do not map consistently to tokens, especially across languages. I also use tokenizer offsets to preserve the original text during splitting.

### Q5. Why 350 tokens? Why not always 500?

> The current default is 350. We compared 350 and 500 on a controlled corpus: 34 versus 20 chunks, with the same 20/20 Hit@5. That experiment did not identify a universal winner, so I would not justify 500 as optimal. A default should be supported by broader retrieval and context-quality evaluation.

### Q6. Do you use overlap?

> The current chunker groups by token budget and heading boundaries; it does not implement explicit sliding-window overlap. Overlap could help continuity across boundaries but adds duplicate material and more records. I would test it rather than assume it is always better.

### Q7. How do tables and page references work?

> Tables are exported to Markdown in document order. We retain available page provenance as a range. For reflowable formats without page coordinates, the current fallback is page 1, so that value should not be presented as a verified page location.

### Q8. What happens if embeddings and chunks have different lengths?

> The persistence path uses strict zip, so a mismatch raises instead of silently truncating. That error should cause processing to fail and roll back the chunk write. There is a regression test for the mismatch case.

## 14. Interview questions: frontend and backend integration

### Q9. What languages and technologies did you use?

> Our frontend uses TypeScript with React and Vite. The backend uses Python with FastAPI. We store data in PostgreSQL and use pgvector for embeddings. For my layer, Docling handles parsing and TanStack Query manages server data in the file browser.

Language is how you write code; framework/library supplies reusable behavior; database is the storage system. SQL is the language used to query the relational database. The desktop shell uses Tauri/Rust, but you need not elaborate unless asked.

### Q10. Why does a successful upload not mean ready?

> Upload means the original bytes and metadata were stored. Parsing and embedding are separate, slower steps, so ingestion has its own run and status. A 202 response means the request was accepted; the frontend must wait for ready or display a failure.

### Q11. Why TanStack Query and Zustand?

> I use TanStack Query for server data such as folders and files, where fetching and invalidation matter. Zustand holds local workspace choices such as the active tab. Separating those helps keep server results authoritative without treating every UI choice as a network resource.

### Q12. Why polling rather than WebSockets?

> Polling was a simple fit for the current file-status workflow. The list refreshes every three seconds while processing is pending. This adds repeated requests and up to roughly an interval of visible delay after a state change, so for more users or richer progress I would consider server events or a more deliberate polling policy.

Do not promise exact three-second completion visibility: network time, query scheduling and server state also matter.

### Q13. Can a user change another user's file?

> The backend checks the file's folder and course ownership against the authenticated user. The frontend is not the security boundary, and knowing a file UUID does not grant access. I would verify this with tests for cross-user access rather than relying on hidden controls.

### Q14. What happens when you replace or move a file?

> Replacing the bytes deactivates the old active ingestion run so retrieval cannot use stale chunks as current evidence. A new ingestion is needed. Moving within a course is supported, but a cross-course move is rejected with 409 because it would otherwise conflict with the stored retrieval scope.

### Q15. What if two files upload successfully and the third fails?

> The current batch is not atomic. Promise.all can reject after other requests have already succeeded. I would surface per-file outcomes and retry only failed items rather than assume the whole batch was undone.

### Q16. How would you scale ingestion?

> First I would measure parser and embedding resource use and concurrent demand. Thread offloading helps responsiveness, but it is not a persistent queue. If we need recovery across restarts or controlled concurrency, I would move ingestion to a durable worker queue and make job state and retries explicit.

## 15. Interview questions: OOP, testing and honest reasoning

### Q17. Where do you use OOP?

> We use model classes to represent entities such as files, chunks and ingestion runs. SQLModel models combine typed fields with validation and database mapping. We also compose services around parser and embedding components. The ingestion functions themselves are largely procedural, so I would not claim the entire pipeline is an object-oriented design.

OOP basics to rehearse: encapsulation groups state and behavior behind an interface; abstraction exposes a useful contract while hiding details; inheritance derives a type from another; polymorphism allows different implementations through a common contract. A Python underscore convention is not strict access control. React function components are not evidence of class inheritance.

### Q18. How would you improve testability with OOP?

> I could define parser and embedder interfaces and inject implementations into the orchestration service. Production would use Docling and the real model, while tests could use deterministic fakes. I would do that only if it simplifies the code; inheritance is not a goal by itself.

This is a proposed design. Current code imports the services and tests patch dependencies; do not present dependency-injected interfaces as already implemented.

### Q19. What did you test?

> Our processing tests cover preserving text without page provenance, body and list extraction, tables in document order, bullet-like headings, chunk/vector count mismatch, empty content and successful or failed ingestion state changes. Some tests mock parser or embedding dependencies, so they check our orchestration rules rather than the accuracy of the real model.

Describe specific assertions in `apps/api/tests/test_processing.py`. For frontend and database claims, show the relevant actual tests; do not extend a test result beyond its scope.

### Q20. Does 127 passing tests prove the AI works?

> No. Passing tests give evidence for the behaviors those tests cover. Retrieval evaluation measures whether relevant evidence is ranked, and real generation runs exercise a different layer. We need to state the dataset and metric instead of using a suite count as an AI-accuracy score.

### Q21. Tell me about a design tradeoff or mistake.

> A key tradeoff is handling files and database records across two storage systems. I changed deletion ordering to avoid deleting bytes before a failed database commit, but that can still leave orphaned bytes if deletion fails afterward. I would make that failure observable and add reconciliation rather than claim the two systems are fully atomic.

### Q22. What if you do not know the answer?

> I haven't measured that yet. In our current implementation, [state what is known]. To answer the performance question, I would test [specific scenario] and record [metric] under a fixed configuration.

Use this for throughput, retrieval generalization and latency. A specific investigation plan is stronger than an invented number.

## 16. Cross-layer knowledge: enough to explain the handoff

You should understand this handoff without presenting the whole system: ingestion prepares chunks and metadata; retrieval chooses candidate evidence; generation writes an answer using the selected evidence; grounding checks citation structure and quoted source text.

Hybrid search combines vector similarity with PostgreSQL full-text keyword search. The current keyword implementation uses `ts_rank`, not BM25. RRF combines rankings using the weighted sum below:

```text
score(chunk) = sum over lists containing chunk:
               weight / (k + rank)
Current defaults: k = 60, weight_vector = 1,
                  weight_keyword = 1
Illustration: ranks 1 and 2 -> 1/61 + 1/62
                            = about 0.032522
```

RRF ranks chunks; it does not choose the best of several generated answers or produce a calibrated probability that an answer is correct. Ingestion quality affects this stage because missing text cannot be recovered reliably by ranking.

pgvector is a PostgreSQL extension for storing and querying vectors. The embedding model maps text into a numeric vector; the database compares vectors during retrieval. You integrate chunk creation and storage with this step; you did not train the model.

The citation checker validates marker/citation consistency and normalized quotations against the selected chunk. Finding an exact quote does not prove every generated claim is semantically supported. Your structured-extraction fix improves the source available to that checker, while your teammate owns its verification logic.

### Framework discussion: safe, accurate wording

> We implemented the pipeline directly rather than using LangChain. A key reason was to keep source selection and citation verification explicit and inspectable. Our pipeline does not have LangGraph-style orchestration loops, so I would not describe it as a LangGraph implementation.

The teammate says this decision was recorded in July. The actual July record was not found in the inspected repository. Ask for its link before quoting it as a documentary reference. Describe the reason as the team's stated rationale until the record is supplied. Do not imply direct implementation is inherently better than every framework.

## 17. Demonstration and evidence checklist

### Before the meeting

- Confirm the exact commit to present and keep the working tree stable. Do not switch branches merely for the meeting: this snapshot's main and dev contain the same committed code.
- Use your own test account and a disposable course/folder for demonstrations.
- Prepare a small text-based PDF with heading, bullet and table; test it once before the session. Record the actual format and OCR policy.
- Have a ready file for browsing and a prepared screenshot if ingestion is slow. Do not depend on downloading models during the meeting.
- Know whether the demo uses fake or real LLM mode; label it accurately. A fake generation demo can still demonstrate file UI, but cannot validate Gemini behavior.
- Save a screenshot of extracted body content and metadata, and one of the ready/failed UI state.
- Attach the existing September 21 evaluation report. Ask Calvin for the new run output and the generation owner for the September 24 logs.
- Ask for the 127-test command, commit and scope. Reuse its evidence rather than rerunning an unrelated broad suite just to reproduce a number.
- Prepare three code locations: `ingestion.py`, `useExplorerData.ts`, and the replacement route in `files.py`.

### Demonstration sequence

1. Open the course/file browser and explain where its data comes from.
2. Select the sample document; show extension/size validation without uploading personal documents.
3. Upload and point out the pending state; explain 201 versus 202.
4. Show a completed document and one extracted bullet/table, with chunk metadata.
5. Rename or move a disposable file within the course; show refreshed data.
6. Explain replacement consistency with code or a prepared example rather than overwriting a valuable document live.
7. End with the measured chunk-size report and one limitation.

If the demo fails, state the failure plainly, switch to the saved evidence and explain the layer you would investigate. A failed live demo is not a reason to invent a successful result.

## 18. Questions to ask teammates and the decision record

### For Calvin

- What command and commit produced the new metrics, and which chunk-size configurations did you evaluate?
- How does the script define relevance, Recall@1 and its MRR cutoff?
- Can we save per-query ranks, especially the failures, rather than just aggregate percentages?
- Does the evaluation share the application's active-run and authorization filters, and what remains outside its scope?
- What evidence would justify changing the default chunk size or adding overlap?

### For the generation and grounding owner

- Can you provide the September 24 run logs and explain which observations were separate runs?
- Which failures came from missing extracted body text, and which came from stitched quotations?
- What does the quote checker guarantee, and what semantic correctness does it not verify?
- Can you link the July framework decision so our presentation uses the recorded rationale?
- What is the provenance of the reported 127-test result: command, date, commit and scope?

### For the whole team

- Is 31 December externally required, or can it become a review checkpoint?
- What minimum workflow must stay usable in maintenance mode?
- Can we review each actual open Gantt row with evidence, owner and acceptance criteria?
- Which recurring costs/services remain, and who is willing to maintain them? Do not assume someone is available.
- Where should known limitations and new issues live so the project is easy to resume?

### Copyable decision record

```text
Session date/time:
Attendees:
Presented commit:

Maintenance mode: agreed / not agreed / pending
Meeting schedule:
Policy for new features:
Meaning of 31 December:
Next review date:

For every actual open Gantt row:
ID and title:
Disposition: finish / defer / cut / verify-and-close
Reason and current evidence:
Owner who accepted:
Smallest acceptance criterion:
Deadline or review date:
Dependencies:

Evidence received:
Retrieval run command/commit/results:
September 24 generation run references:
127-test run command/commit/scope:
July tech-stack decision link:

Unresolved questions:
Actions, owners and agreed dates:
```

Suggested closing:

> My recommendation is to preserve the working core, finish only the small reliability or documentation items we explicitly accept, and defer new features. I can own the ingestion and frontend handover material. Before we finish, let's read back the meeting policy, the disposition of every open row and the meaning of the December date, so maintenance mode is an actual agreement rather than an unclear pause.

## 19. Sources and a short rehearsal plan

Primary inspected implementation: `apps/api/app/services/ingestion.py`, `processing.py`, `storage.py`; `apps/api/app/routers/files.py`; `apps/api/tests/test_processing.py`; `packages/ui/src/components/upload/UploadModal.tsx`; `packages/ui/src/hooks/useExplorerData.ts` and `useExplorerMutations.ts`; `packages/ui/src/pages/dashboard.tsx`. Cross-layer references: `vector_ops.py`, `prompt.py`, `grounding.py`, and `apps/api/scripts/evaluate_chunk_retrieval.py`.

Measured report: `apps/api/evaluation/chunk_retrieval_results.md`. Contribution evidence: `output/contribution-audit/commit-ledger.md` and `docs/contribution-interview-playbook.en.md`. Meeting allocation, 19/70 rows, the December date and 127 tests come from the teammate's supplied message. The Gantt workbook, July decision text, full September 24 logs and 127-test run log were unavailable during preparation.

First rehearsal: explain Upload in English without reading, then check every step against section 6. Second rehearsal: practice the bullet-heading story and the replacement-consistency story using problem -> your change -> evidence -> remaining limitation. Third rehearsal: answer questions 3, 5, 15, 20 and 22, because they test honesty and reasoning under pressure. Final rehearsal: deliver the six-slide outline within 12 minutes and leave time for questions.

Your preparation goal is not memorizing every sentence. It is being able to explain your own flow, defend two engineering decisions, identify the evidence for two claims, and state one meaningful limitation confidently.
