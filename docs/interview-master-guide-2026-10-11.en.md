# NTBC interview master guide — simple English

Prepared on 11 October 2026, Malaysia time. Code reviewed: `main` at `ab803abe1e89b1938d1dbe0284124eb1b9c18ddf`, after pulling the latest remote main. This guide describes the checked-in implementation. It does not establish that the deployed VM currently runs this commit. Company answers are templates because the employer and job description have not been supplied.

Use this as a discussion workbook. Say each quoted answer aloud, then let your friend ask the follow-up. Learn the reason behind an answer rather than memorising every sentence.

## 1. The project story in 30 seconds

> NTBC is a study assistant for a student's own course material. A student uploads notes or slides and asks a question. We search their documents, ask an AI model to answer using the relevant passages, and show citations that link back to the source. My main contributions were document ingestion and chunking, resource APIs, file workflows, and connecting the file browser to real backend data. We built it as a team of three.

**If they ask what problem it solves:**

> Students often have many files and spend time finding the right explanation. A general chatbot may give an answer that does not match the lecturer's material. We wanted answers that students could trace back to their own documents. We still have limitations, so we do not claim that citations guarantee every answer is correct.

**If they ask for a 90-second explanation:**

> There are two main workflows. First, ingestion: we store an uploaded file, parse its text and tables, split the content into chunks, create embeddings, and save those chunks in PostgreSQL. Second, answering: we check which files the user owns, embed the question, combine vector and keyword search, and send the selected passages to Gemini. We check citation markers and quoted passages before returning the answer. The frontend uses React and TypeScript, the API uses FastAPI, and PostgreSQL with pgvector stores both application data and searchable vectors. I worked mainly on preparing document data and making file operations work across the UI and backend.

**What is difficult here?** Keeping documents, stored bytes, indexing status, search results, and citations consistent. Calling an AI endpoint is only one step.

## 2. A mental map of the architecture

```text
React UI (shared by web and Tauri)
    -> typed HTTP client
    -> FastAPI routes: validate identity, ownership, and input
    -> services: storage, parsing, embedding, retrieval, generation
    -> PostgreSQL: application rows, chunks, vectors, full-text index

Upload -> local file storage -> Docling -> chunks -> local Jina embeddings -> DB
Question -> owned-file scope -> embedding -> hybrid search -> Gemini -> checks -> answer
```

The web and desktop apps are thin shells around `packages/ui`. This is a modular application in a monorepo; do not call it a microservice architecture simply because it has several folders.

| Part | Technology | Plain-English job |
| --- | --- | --- |
| Frontend language | TypeScript | JavaScript with type checking during development |
| UI | React 19 | Components and interactive rendering |
| Web build | Vite | Development server and production asset build |
| Styling | Tailwind CSS 4, Base UI/shadcn components | Styles and reusable UI controls |
| Server data | TanStack Query | Fetching, caching, mutations, and refetching |
| Workspace state | Zustand | Selected course, tabs, and other client state |
| Forms | React Hook Form and Zod | Form handling and client input validation |
| Backend | Python 3.11+, FastAPI, Uvicorn | HTTP API and request execution |
| Validation/ORM | Pydantic, SQLModel, SQLAlchemy | Validate data and map objects to DB rows |
| DB access | asyncpg | Async PostgreSQL driver |
| Database | PostgreSQL 16 and pgvector | Relational records, keyword search, vector search |
| Migrations | Alembic | Controlled database schema changes |
| Parsing | Docling | Extract document content and structure |
| Embeddings | SentenceTransformers, PyTorch, Jina | Turn text into vectors locally |
| Answer generation | Configurable Gemini API | Generate an answer from selected passages |
| Desktop shell | Tauri 2/Rust | Wrap shared UI in a native app |
| Tooling | pnpm, uv, Turborepo, OpenAPI | Dependencies, tasks, shared API contracts |
| Deployment configuration | OCI VM, systemd, Caddy, rootless Podman | Run API/DB, serve web assets, terminate HTTPS |

Model names in configuration are defaults, not proof of live deployment settings. Current defaults are `jinaai/jina-embeddings-v5-text-small`, 1024 dimensions, and `gemini-3.5-flash-lite`. Fake LLM mode defaults to true; a real demo must verify its configuration.

## 3. Your contribution: what you can defend

Git author evidence supports these themes. Authorship is evidence of code work; it does not prove you personally chose every design or worked without assistance.

| Your work | Example commit | How to explain the value |
| --- | --- | --- |
| Document extraction and metadata | `f8707f9`, `796b5f8`, `b266e44` | Prepare searchable text and preserve source locations |
| Token-aware splitting | `d2c66c5`, `632c0fa` | Use model token boundaries and original string offsets |
| Processing/status handling | `93ee9a2`, `b40f5e3` | Make indexing progress and failure visible |
| Course/folder APIs | `0752478`, `ad04377`, `c0d0a9e` | Manage resources and initial folder structure |
| File APIs and workflows | `39938a0`, `f1404dc`, `02e8647` | Read, delete, move, rename, and replace files |
| Deletion order | `acb4a59` | Avoid removing bytes before a DB operation succeeds |
| Stale index prevention | `9878edd` | Prevent old file content from answering new questions |
| Explorer/API integration | `6ea628f` | Replace fixture data with actual server data |
| Structured extraction | `6b80292` | Retain tables and bullet-like content |
| Retrieval experiment | `6041da4` | Compare chunk sizes under controlled conditions |

> I contributed across the document workflow, from parsing and chunking to file APIs and frontend integration. I can explain these parts in detail. Retrieval, authentication, generation, grounding, and deployment also include important teammate work, so I describe those as team features.

Recent CPU dtype, page-boundary chunking, deployment, and prompt changes were authored by Yong Zhou. Calvin built important embedding/retrieval foundations and extended evaluation. You can explain them as part of understanding the whole system, while clearly naming your own work.

## 4. Answer any “what happens when I press this?” question

Use this order: **input -> UI state -> HTTP request -> authentication -> ownership -> service -> DB/storage -> response -> refreshed UI -> failure**.

### A. Register or log in

> The form sends credentials to the auth API. The backend validates the input. Registration hashes the password and creates the account with its initial course in a transaction. Login checks the stored password hash. The response contains a short-lived access token, and the server sets a refresh-token cookie. Later API requests send the access token in the Authorization header.

Passwords are hashed with Argon2, not encrypted for later recovery. Access tokens are JWTs, not encrypted password containers. The client keeps its access token in memory; refresh uses an HttpOnly cookie. The backend defaults are 60 minutes for access and seven days for refresh. Public registration can be disabled to control access and Gemini quota.

**Trap:** HttpOnly reduces token theft through JavaScript, but it does not make XSS harmless. SameSite and secure-cookie configuration are useful protections, not a complete security guarantee.

### B. Create a course or folder

> The frontend submits the name and other fields. FastAPI validates them and checks ownership of the parent resource. The backend inserts the rows and commits. After success, the UI refreshes the affected cached list. New courses get default folders, so a student has somewhere to upload files immediately.

Course deletion in the API is an archive operation. Do not assume every DELETE route physically removes every associated row. Folder deletion needs its own rules; inspect its route before claiming it simply deletes all physical files.

### C. Upload a document

> The upload dialog sends a multipart request to `POST /files` with the selected folder. The backend checks ownership, saves the bytes, and records metadata. Upload and indexing are separate. The frontend then requests `POST /files/{id}/ingest`, which creates a queued run and returns 202. A background task parses, chunks, embeds, and stores the document. The file list polls while the file is uploaded or processing and updates when it becomes ready or failed.

The configured upload limit is 50 MiB, enforced while reading the upload. A frontend check alone is insufficient because a caller can bypass the UI. Upload success does not mean the document is searchable yet.

Run states include queued, processing, ready, and failed. File status is a summary used by the explorer. The file list polls every three seconds while pending files exist. This is polling, not WebSockets.

### D. Retry indexing

> Retry requests another ingestion run. That run records which chunker, model, and dimensions were used. Its chunks are not eligible for retrieval until the run is activated. On success, the backend deactivates the old active run before activating the new one and updates the file status.

The background task opens its own DB session and re-reads rows by ID. Avoid claiming that a request session safely lives forever. The run reaches READY before the final activation step; READY and active are different concepts.

### E. Open a file or click a citation

> The frontend fetches the file's bytes through an authenticated content endpoint. The backend checks that the user owns the file before serving it. A citation includes backend-resolved file and page metadata, so the UI can navigate to the document and source location.

An expired token, deleted file, unsupported preview, or stale citation can prevent opening. A saved chat citation is not a permanent guarantee that the original file still exists. DOCX fallback page metadata is not proof of a true page coordinate.

### F. Rename or move a file

> Rename or move sends a PATCH request. The backend checks the file and destination, applies the permitted changes, and commits. The query cache is invalidated so the list reflects the server's result. Renaming also updates matching open-tab names while keeping their view state.

The current file move API rejects cross-course moves. Renaming metadata does not require re-embedding unchanged content. Moving across a retrieval ownership boundary would require checking the consistency of related data.

### G. Replace a file

> `PUT /files/{id}/content` replaces the bytes while keeping the file identity. The backend checks ownership and the file extension, updates the size and hash, resets indexing metadata, and deactivates old ingestion runs. The new content needs indexing before it becomes searchable. This prevents the reader from showing the new file while the chatbot answers from old chunks.

This endpoint does not itself complete re-indexing. Matching extensions do not prove that uploaded bytes are safe or valid. Filesystem replacement and DB commit are not one atomic transaction; immutable versioned objects would be a stronger design.

### H. Delete a file

> The backend verifies ownership, deletes the DB record, and commits. Related data follows the database's deletion constraints. It then removes the physical file from storage. The frontend refreshes the list after a successful request.

> We commit first to avoid removing the bytes while the database still references them if the transaction fails. There is still a failure window: storage deletion could fail after commit and leave an orphan file. A cleanup process or an outbox would improve this.

### I. Send a question

> The UI sends the question, conversation ID, and course or file scope to `POST /rag/query`. The backend authenticates the user and resolves accessible files. It embeds the question, combines vector and keyword results, and passes selected chunks to Gemini. Then it validates the response and checks citations against those chunks. It saves the messages and returns the answer. The frontend refreshes conversation data and renders the citations.

**Important boundaries:**

- The caller cannot choose other people's documents merely by sending their IDs.
- An empty owned-file scope must return early. The lower search helper treats an empty list as no file filter.
- Normal question retrieval and whole-document summary follow different paths.
- Stored chat history does not mean previous messages are passed into the model prompt. The inspected generation call uses the current question and source context.
- The current response is complete JSON, not token streaming.
- `session.add()` and `flush()` do not mean the transaction is committed.
- Creating a new conversation can commit earlier; the entire chat request is not necessarily one transaction.

### J. Condense / summarise a document

> The request specifies document-summary intent and one file. The backend reads that file's active chunks in order instead of using ordinary top-k retrieval. That gives the model wider coverage for a summary. It still validates citations before returning the answer.

Passing all chunks does not prove complete understanding. Very long documents can exceed a useful context budget; a staged summary would be a future improvement.

### K. Add, complete, or delete a roadmap milestone

> `useRoadmap` loads milestones for the selected course. Adding a milestone creates a row with a position; completing one updates its status; deleting one calls the delete API. The backend checks ownership and commits the change. The hook invalidates the milestone query, then derives progress from refreshed rows.

Roadmap ordering uses position. The displayed percentage is completed milestones divided by total milestones. This is not an AI-generated learning roadmap in the inspected implementation.

### L. Refresh the browser or log out

> Some workspace view state is persisted locally, while application records come from the server. After a refresh, the client can use its refresh cookie to obtain an access token and fetch server data again. Logout clears the refresh cookie and the client clears its session state.

Clearing a cookie does not revoke already issued stateless access tokens everywhere. The current backend logout route itself requires authentication, so expired-access-token behaviour must be handled carefully by the client.

## 5. Understand the AI pipeline without fancy language

**Document:** the original PDF or notes. **Chunk:** a small piece of extracted content. **Token:** a piece of text as represented by a model's tokenizer; it is not always a word. **Embedding:** a list of numbers used to compare text meaning. **RAG:** find relevant source material, then ask a model to answer using it.

> We use two different model jobs. The local embedding model helps find relevant text. Gemini writes the answer. Neither step means we trained a foundation model.

### Parsing and chunking

Docling reads document items. The extraction code keeps body text and lists, exports tables as Markdown, tracks headings, and carries page provenance. Decorative content is skipped. PDF OCR is disabled, so scanned/image-only PDFs can fail to produce useful text.

The current chunker targets 350 tokens, splits long strings using tokenizer offsets, and starts new chunks at heading changes, token-budget boundaries, or page changes. Headings are now written into content so both embedding and keyword search see them. It does not implement overlapping sliding windows or late chunking.

> We use tokens because the model reads tokens, not words. We use original character offsets so splitting can preserve the source text. We keep page metadata because the answer should point back to the right part of the document.

**Subtle limit:** The 350-token value is a target, not a proven strict final bound. A long piece is split using the body budget before a heading is added, and token counts of separately counted strings need not equal the token count of the joined string. Test long headings and re-tokenise final chunks before claiming every output is below 350.

### Cosine similarity

Vectors point in directions in a numerical space. Cosine similarity compares their direction:

`cosine(a,b) = dot(a,b) / (length(a) * length(b))`

For `[1,0]` and `[1,0]`, similarity is 1. For `[1,0]` and `[0,1]`, it is 0. Real embeddings have 1024 dimensions. pgvector orders by cosine distance; the vector-only response maps similarity to `1 - distance`. Similarity is not a probability that an answer is correct.

### Keyword search versus vector search

> Keyword search helps with exact terms, names, and acronyms. Vector search helps when a question uses different words with similar meaning. Combining them makes retrieval less dependent on either method alone.

The DB uses PostgreSQL full-text search with an English text-search configuration and a generated `content_tsv` column. It is not the same as a simple substring search, and the current implementation is not BM25. Its query conversion uses OR between terms, which can improve recall while also returning less precise matches.

### RRF in one example

RRF combines positions in ranked lists rather than raw scores:

`score = vector_weight / (60 + vector_rank) + keyword_weight / (60 + keyword_rank)`

If A is first in vector search and second in keyword search, equal weights give `1/61 + 1/62 ≈ 0.03252`. If B is first in keyword search but absent from vector results, it gets `1/61 ≈ 0.01639`. Missing from a list contributes zero.

> We use ranking positions because cosine scores and keyword scores have different scales. RRF lets us combine them without pretending those raw numbers mean the same thing.

The default search config requests 50 candidates from each search and allows up to 20 fused results. A route can override configuration based on the request. Read the caller before stating that all questions always retrieve 20 chunks. The normalised threshold is different from the raw score returned with a chunk.

A reranker would read question-passage pairs and produce another ranking. It may improve precision but adds inference cost. RRF itself is not a learned reranker. A reranker does not inherently require a GPU.

### Grounding and refusal

Gemini is asked for structured JSON including answer text, citation markers, and quotes. The backend resolves source metadata rather than trusting model-invented file IDs. It checks marker consistency, source bounds, quote presence after whitespace/case normalisation, duplicate quotes, and coverage-field consistency. Some redundant citations can be dropped while preserving a verified quote for a marker.

> The checks help verify that citations point to real retrieved passages. They do not prove that every claim logically follows from those passages. A real quote can still be used to support a wrong conclusion. We reduce risk, but we do not claim zero hallucinations.

Temperature zero does not guarantee deterministic or correct answers. Structured JSON does not guarantee truth. A service failure now produces a service-failure message; it should not be confused with evidence that the document lacks an answer.

## 6. Why A instead of B? Answers with tradeoffs

| Question | Simple spoken answer | Tradeoff / follow-up |
| --- | --- | --- |
| FastAPI instead of Express? | “Our document and model libraries are in Python. FastAPI keeps them in the same backend and gives us validation and OpenAPI support.” | Express is reasonable for a JS-focused team. FastAPI does not automatically make CPU work faster. |
| PostgreSQL instead of MongoDB? | “Our users, courses, folders, files, and runs have clear relationships. SQL constraints and transactions help keep them consistent.” | MongoDB can be useful for different data shapes; do not call it bad. |
| pgvector instead of a separate vector DB? | “It keeps ownership data and searchable chunks in one database. That reduces services and lets us combine filters, vectors, and keyword search.” | At larger scale evaluate specialised vector systems with measurements. |
| RAG instead of fine-tuning? | “Student documents change often. Retrieval lets us use new material without training again and gives us source links.” | Fine-tuning can change behaviour; it is not a reliable replacement for current knowledge lookup. |
| Local embeddings instead of a hosted embedding API? | “We can control the model and avoid a separate remote embedding call for each passage.” | CPU time, RAM, model downloads, and maintenance become our responsibility. |
| Gemini instead of a local generator? | “A hosted model lets us focus on the application without serving a large generation model.” | Network dependency, quota, cost, and sending retrieved content to a third party. We have not proven it beats every alternative. |
| Docling instead of plain PDF text extraction? | “We need structured items such as headings, tables, and page information, not only one long string.” | Parsing costs more and can still make mistakes. |
| 350 instead of 500 tokens? | “350 is the current target. Our earlier experiment did not establish a universal winner.” | Later page/heading changes alter the chunker; rerun evaluation. |
| React Query instead of Zustand for everything? | “Query handles server data and cache freshness. Zustand handles local workspace state.” | Duplicating fetched data into independent stores creates stale-state risk. |
| Polling instead of WebSockets? | “Indexing has a small number of status changes. Polling was simpler for our current scope.” | Traffic grows with clients; add backoff or push when justified. |
| BackgroundTasks instead of Celery? | “It gave us a small implementation for the current deployment.” | It is in-process and not a durable job queue. Restart can interrupt work. |
| Monorepo instead of separate repos? | “Shared UI and generated contracts can change alongside the API.” | Tooling and dependency coordination become more complex. |
| Tauri instead of Electron? | “It lets us package the shared web UI with a native shell using the platform webview.” | Platform differences and Rust tooling; do not invent measured size/RAM improvements. |
| REST instead of GraphQL? | “The resource workflows fit clear endpoints, and we generate types from OpenAPI.” | GraphQL can be useful for flexible queries but adds concepts we did not need yet. |

For any design question: state the requirement, your choice, one downside, and the condition under which you would reconsider it.

## 7. Backend and database traps

### What are the main tables?

User owns courses. A course has folders and milestones. A folder contains files. A file has ingestion runs. A run produces chunks. Conversations contain messages. The schema has nine main entities: USER, COURSE, FOLDER, MILESTONE, FILE, INGESTION_RUN, CHUNK, CONVERSATION, MESSAGE.

### Authentication versus authorization?

> Authentication checks who you are. Authorization checks whether you can act on this particular resource. A valid token does not give access to every file.

### Why IDs and foreign keys?

> IDs identify records. Foreign keys prevent references to records that do not exist. Composite foreign keys can also enforce agreement between related fields, such as the file and course attached to a chunk.

UUIDs make accidental guessing less convenient; they are not authorization. Check constraints and unique indexes enforce invariants even if application code makes a mistake.

### Why only one active ingestion run?

> Old and new chunk generations must not both answer questions for the same file. A partial unique index allows at most one active run per file. We deactivate the old run before activating the new one.

“At most one” is not “exactly one.” Uploaded or failed files may have no active run. Concurrent reindexing can still require retries or explicit coordination. A uniqueness constraint does not automatically solve every race.

### HNSW and GIN?

> HNSW is an approximate nearest-neighbour index for vectors. GIN helps search indexed text terms. They serve different queries.

Approximate search trades some recall for speed. Small data may lead PostgreSQL to choose another plan. Model declarations do not prove an index exists on the live DB; migrations and query plans need verification.

### Why async and `to_thread`?

> Async helps when a request waits for network or DB I/O. Parsing and embedding are blocking work, so we move them off the event loop with `asyncio.to_thread`. That helps the API remain responsive while indexing runs.

Threads do not guarantee faster pure-Python CPU code, and the GIL matters. Native libraries may release it. More concurrent ingestions can still overload CPU/RAM. A loading lock prevents two first-time loads of the embedding model; it does not serialise every encoding call.

### Can one async session execute two searches concurrently?

The current hybrid helper uses `asyncio.gather` with the same AsyncSession. Treat this as a concern to test and improve, because a session represents mutable transactional state and is not a general concurrent-operation container. Sequential execution or separate sessions with deliberate transaction semantics are alternatives. Do not promise this implementation safely scales under all concurrency.

### What is a transaction?

> It groups DB changes so they can commit together or roll back. For example, a new account should not be saved without its initial course. It does not automatically include filesystem writes or remote AI calls.

### Why migrations rather than creating tables on every startup?

> A migration records how an existing database changes. We can review and apply changes in order. Creating tables only handles a much smaller problem and does not safely express every schema evolution.

Model imports share metadata so Alembic can see tables. Review generated migrations; autogeneration is not a guarantee of safety. Schema downgrade is not a complete substitute for backups.

### Is the application secure?

> We have protections such as password hashing, token validation, ownership checks, upload limits, and source scoping. I would not call the whole application secure based only on those features. I would test access boundaries and review operational settings before a wider launch.

SQL expression builders reduce SQL-injection risk for ordinary parameterised values; never interpolate untrusted SQL. CORS is a browser policy, not server authorization. A document can contain prompt injection even when it belongs to the caller.

## 8. Latest changes you should know for today's discussion

The old README still says the explorer uses fixtures and the roadmap/TLS are not started. The current source shows real explorer hooks, milestone API wiring, and Caddy deployment configuration. Use code as evidence, and distinguish configured from observed live behaviour.

1. **CPU embeddings use float32.** The repository records a large slowdown with bfloat16 on the OCI CPU. The code now chooses float32 on CPU and bfloat16 on CUDA. Explain this as matching the representation to hardware support, at a memory cost. These historical measurements are not universal speed claims or measurements rerun today.
2. **Chunks stop at page boundaries and include headings.** A multi-page chunk could cite the first page while the quote came from a later page. A heading stored only as metadata was invisible to vector and keyword text inputs. Both problems affect user-visible retrieval quality.
3. **File status shows PROCESSING and stores page count.** Page count comes from the parsed document, not the last searchable chunk, so image-only final pages still count.
4. **Replacement has a regression test.** It checks that the old run is excluded from retrieval. Understand the test setup before claiming it covers a real DB or every crash scenario.
5. **Roadmap reads and writes through the API.** It is not only local view state.
6. **HTTPS configuration serves frontend and `/api` from one origin.** Caddy strips `/api` before forwarding to loopback Uvicorn. Same-origin deployment fits the refresh-cookie design. SPA fallback serves `index.html` for client-side routes.
7. **Logging and generation-failure messaging improved.** API logs have a handler/file destination, and an AI service outage is separated from a grounding refusal.
8. **Prompt changes require cited openings, separate citation brackets, and verbatim source quotes.** Quotes preserve source typos rather than silently fixing them. These are instructions plus checks, not guarantees of perfect model behaviour.

## 9. Testing, evaluation, and honest numbers

Checks run while preparing this guide: the existing UI test suite passed all 41 tests. The selected backend logging/registration checks passed three tests. The replacement/retrieval PostgreSQL integration test could not start because the local test database refused the connection. No live Gemini call, production deployment check, complete `pnpm verify`, or new retrieval benchmark was run. Treat these as limited checks, not a claim that every feature passed end-to-end today.

> I separate retrieval quality from answer quality. A retrieved relevant passage does not prove that the model's final explanation is correct.

Your historical experiment used one controlled 20-page PDF and 20 questions. The 350-token configuration made 34 chunks and the 500-token configuration made 20. Both reached Hit@5 of 20/20 under the report's page-and-evidence-phrase rule. This is a small benchmark with a ceiling effect, not 100% product accuracy. It also predates the newest chunker.

- **Hit@k:** fraction of questions with at least one relevant result in the top k.
- **Recall@k:** fraction of all defined relevant items retrieved in the top k.
- **MRR:** average `1/rank` of the first relevant result; zero for a miss.
- **Precision@k:** fraction of the returned top-k results that are relevant, under an explicit evaluation convention.

If the first relevant passage is third, reciprocal rank is `1/3`. Hit@5 is a hit, but ranking can still improve. Calvin's later MRR work should be credited to him.

> Next, I would use more realistic documents, paraphrased questions, exact-term questions, questions with no answer, and ownership boundary cases. I would measure retrieval ranking, answer faithfulness, citation usability, latency, and memory separately.

Meaningful test scenarios: upload A -> index A -> answer from A; replace with B -> ensure A is excluded -> index B -> retrieve B; unauthorized IDs; empty scope; malformed documents; scanned PDFs; duplicate indexing; restart mid-job; storage failure after commit; quote from wrong marker; Gemini timeout; stale frontend response; expired token.

Mock tests are useful for logic and error paths. PostgreSQL integration tests are needed for constraints, transaction behaviour, and indexes. An end-to-end test exercises UI/API/storage together. A fake LLM test does not measure real model quality.

## 10. Difficult technical scenario questions

**“The UI says processing forever. What do you do?”**

> I check the file and run status, then logs using their IDs. I separate a stopped job from a slow parser or model call. I check CPU, memory, the worker process, and whether the background task recorded an error. A restart can interrupt an in-process task, so a future improvement is recovery for stale runs and a durable queue.

**“The answer is wrong. Do you immediately change the prompt?”**

> First I inspect the extracted text, chunks, and retrieved passages. If the correct evidence never reached the model, a prompt change will not fix retrieval. If the evidence was present, I inspect generation and citation checks. I add the failing question to a regression set before comparing changes.

**“The user clicks Send twice or the connection times out.”**

> A disabled button helps the UI, but requests can still be repeated. I would check current handling and add idempotency where duplicate writes matter. After a timeout, the client may not know whether the server committed, so automatic retry needs care.

**“Two users index large files at once.”**

> The model loading lock protects initialisation, but concurrent jobs still compete for CPU and RAM. I would measure resource usage, limit job concurrency, and put indexing behind a queue if needed. Moving work to a thread does not create unlimited capacity.

**“A file is replaced while an old indexing task runs.”**

> That is a version race. Deactivating existing runs is useful, but an older task could finish later unless we validate the document version before activation. I would bind the job to an immutable content version or hash and only activate it if that version is still current.

**“Your DB commit succeeds but deleting storage fails.”**

> The user-visible record is gone, but bytes may remain. I would log and retry cleanup using a persistent cleanup task. DB and storage require explicit coordination; a DB transaction alone cannot cover both.

**“There are 10,000 users tomorrow.”**

> I would not promise this VM handles them. I would measure concurrent requests, query latency, ingestion throughput, memory, and model quota. Likely changes include queued ingestion with bounded workers, object storage, rate limits, database tuning, and monitoring. I would address the measured bottleneck before adding many services.

**“Gemini is down or rate-limited.”**

> Return a clear temporary-service failure, preserve useful diagnostics, and avoid unbounded retries. For a larger deployment I would consider bounded backoff, quotas, and a circuit breaker. A fallback model would need its own quality and privacy checks.

**“A malicious PDF says ignore instructions.”**

> Treat document content as untrusted data. Ownership does not make its instructions safe. Separate rules from content, restrict what the model can do, validate outputs, and test injection cases. Our quote checks do not solve prompt injection completely.

**“Can student data leave the machine?”**

> Embeddings are computed locally, but retrieved passages and the question are sent to the configured Gemini service in real mode. I would explain that clearly and check the required privacy rules before processing sensitive material.

**“Can you swap embedding models without rebuilding?”**

> Not safely just by changing a name. Embedding spaces differ even with the same dimensions. Documents and queries need compatible vectors. We would re-index, version runs, and review dimensional constraints and activation.

**“Can citation verification still accept a wrong answer?”**

> Yes. A quote can exist while the conclusion misinterprets it. The checks verify traceability and consistency, not complete semantic truth. Evaluation still needs human judgment or a carefully validated additional method.

**“Why not just use ChatGPT or upload the whole PDF?”**

> That can be a useful baseline. Our project explores a reusable course workspace, ownership-aware retrieval, file lifecycle, and source navigation. We should compare usability, cost, and answer quality rather than assume our application is always better.

**“Explain OOP and SOLID using this code.”**

> Schemas and model classes describe data, while services hide implementation details behind functions. For example, storage operations are separate from parsing. This supports separation of responsibilities. The project also uses many functions, so I would not pretend every part is a textbook OOP hierarchy.

Inheritance exists in SQLModel/BaseModel types; composition is often simpler for assembling workflows. Dependency injection supplies sessions and authentication. Async is a concurrency model, not an OOP principle.

**“Would you start with microservices?”**

> No, not for this team and scope. A modular application is easier to develop and operate. If indexing needs independent scaling, I would first separate workers around a clear job interface.

**“How do you debug a 500?”**

> Reproduce it with the smallest request, record the endpoint and resource IDs, inspect the traceback, and identify which layer failed. Then fix the cause and add a regression test. I keep detailed internal logs separate from safe user messages.

**“How do you deploy safely?”**

> Build and test, review migrations, back up data, deploy a known commit, apply compatible schema changes, restart services, and check health plus a real workflow. The repository has scripts and service configuration, but I would inspect actual deployment state before claiming a live rollout succeeded.

**“Did deleting the feature branch delete your work?”**

> No. The checked local tips of our nine deleted remote feature branches are ancestors of current main, so their commits remain in history. A branch is a name pointing to a commit. Unmerged branch deletion can be risky, so we check reachability first.

## 11. Four evidence-based stories for behavioural answers

Use STAR: **Situation, Task, Action, Result**. Focus on your action. Results can be a verified behaviour change; they do not need invented percentages.

### Story 1 — file replacement consistency

> In NTBC, replacing a document could leave old chunks available to search. My task was to keep the reader and retrieval consistent. I updated replacement to deactivate the old active runs and reset indexing state. The old content became ineligible for retrieval until the replacement was indexed. It taught me that changing a file means updating all derived data, not just the bytes.

Useful for: bug fixing, ownership, attention to detail, tradeoffs. Follow-up: storage/DB atomicity, version races, and what the tests actually cover. Do not invent a customer incident or production outage.

### Story 2 — connecting the prototype to the API

> Our file browser initially used fixture data. I worked on connecting it to real course, folder, and file endpoints. I added query and mutation hooks, refreshed caches after writes, and represented loading, processing, and failure states. The important result was that the UI reflected the backend rather than only changing a local list. I learned to think about the whole user action across both layers.

Useful for: initiative, learning, teamwork, full-stack understanding.

### Story 3 — preserving document evidence

> Search quality depends on extraction. I worked on token-based splitting and preserving page and heading information. I also improved extraction for tables and bullet-like items. This kept useful source material available to retrieval and made it easier to trace chunks back to documents. I learned to debug the data pipeline before blaming the model.

Useful for: technical difficulty, learning unfamiliar tools, quality. Attribute the newest page-boundary/headings-in-content changes to the team member who authored them.

### Story 4 — an experiment without a dramatic winner

> I compared 350-token and 500-token chunks using the same controlled PDF and questions. Both reached the same Hit@5 in our small benchmark. Instead of claiming one was better, I documented the limits and the ceiling effect. I would expand the evaluation before making a stronger decision.

Useful for: judgment, honesty, handling ambiguity, explaining a result that did not match expectations. Do not call it 100% answer accuracy.

## 12. Behavioural questions: simple English answer bank

These samples are wording options, not invented life events. Replace brackets with true details. For hypothetical scenarios, explain what you would do. For past-experience questions, use something that actually happened.

### Tell me about yourself

> I am a student interested in building software that works across the frontend and backend. In our NTBC project, I worked on document processing, file APIs, and connecting the UI to real server data. I enjoyed understanding what happens after a user clicks a button, including validation, database changes, and failure handling. I am looking for a role where I can contribute, improve my engineering fundamentals, and learn from code reviews.

### Why should we hire you?

> I can contribute to practical application work and explain the reasoning behind it. In NTBC, I worked on both backend workflows and frontend integration, including a fix for stale retrieval after file replacement. I am still learning, but I take feedback seriously and check results rather than assuming a change works. I would bring that approach to your team and build my skills around the work you need.

Avoid “I am better than all other candidates.” Give evidence and fit, not a promise of unlimited ability.

### Why our company?

> I am interested in your work on [specific product or team]. From [job description or company source], I noticed that this role involves [specific responsibility]. That connects with my experience in [relevant NTBC work], and I want to deepen my skills in [relevant area]. I would like to understand how your team handles [a meaningful engineering question].

Research the actual employer before using this. Do not invent its culture, achievements, or technology stack. If no reliable information is available, refer directly to the job description.

### Why this role?

> I enjoy turning a user requirement into working software and checking the details across layers. This role gives me a chance to do that while learning from experienced engineers. My project experience is relevant to [API/frontend/data workflow], and I understand that I still need to learn your tools and working practices.

### What is your strength?

> One strength is following a problem across the system. For example, replacing a file is not only a storage operation; it also affects its searchable chunks and UI status. I try to connect those details and verify the behaviour users will see.

### What is your weakness?

> I sometimes spend too long trying to understand every detail before moving forward. I am improving by defining what I need to know for the current task, timeboxing investigation, and asking for help with a clear summary of what I tried.

Use this only if true. A good weakness has a real effect and a concrete improvement habit; “I work too hard” is unconvincing.

### Tell me about a mistake or failure

> In [real situation], I [specific mistake]. I noticed it through [test, review, or observation]. I corrected [specific issue], checked [behaviour], and changed [habit or test] to reduce the chance of repeating it. I learned [specific lesson].

An old replaced-file issue is usable only if you know your own part in causing or discovering it. Fixing a bug does not automatically mean you caused it. Do not manufacture a confession.

### Disagreement with a teammate

> I would clarify the requirement and ask why they prefer their option. Then I would explain my concern using a concrete example or a small test. If both choices are reasonable, we should decide based on the constraints and record the tradeoff. Once the team decides, I support the agreed approach unless new evidence changes the risk.

For a past disagreement, add a true event, each side's reasoning, your actual action, and the outcome. Do not invent conflict with Yong Zhou or Calvin.

### Your teammate is not delivering

> I would talk privately to understand the blocker and agree on a smaller deliverable with a clear deadline. If it threatens the project, I would make the impact visible to the lead and discuss priorities or redistribution. I would focus on getting the work done rather than blaming the person.

### Deadline versus quality

> I would identify what must work and what can be reduced. I would keep essential checks such as ownership and data consistency. If the deadline cannot fit the full scope, I would communicate early and propose a smaller safe release. I would not silently remove important safeguards.

### Asked to use a technology you do not know

> I would clarify the task, read the relevant documentation, and build a small example around the required behaviour. I would timebox the investigation and ask focused questions when blocked. Then I would submit a small change for review rather than pretending to know the whole technology immediately.

### A senior engineer rejects your code

> I would ask which requirement or tradeoff my implementation missed. I would compare their suggestion with the current behaviour and revise the change. If I still see a risk, I would explain it with evidence. My goal is better code, not defending the first version.

### You find a serious bug just before release

> I would reproduce it, estimate the impact, and notify the person responsible for release. I would provide options: a small tested fix, disabling the affected feature, or delaying the release. The decision should be explicit rather than hiding the problem to meet the date.

### Production is down

> I would follow the incident process, inform the responsible team, and collect facts quickly. I would prioritise restoring service through an approved rollback or known safe action. After recovery, I would help identify the cause and add a test or monitoring improvement. I would not make random changes on the live system.

### You are assigned three urgent tasks

> I would clarify impact, deadlines, and dependencies, then ask the owner to confirm the priority if they conflict. I would make the tradeoff visible and give realistic progress updates. I would not accept three incompatible deadlines without explaining the capacity limit.

### A requirement is unclear

> I would describe the user action and expected result in my own words, identify ambiguous cases, and confirm the most important ones. I can start independent parts while waiting. Writing an example is often more useful than asking a vague question.

### You disagree with your manager

> I would explain the risk privately with evidence and offer an alternative. I would listen to context I may not have. For a normal tradeoff, I would follow the final decision; for a serious security or integrity concern, I would use the appropriate escalation process.

### You do not know an interview answer

> I have not implemented that yet, so I do not want to guess. My current understanding is [what you do know]. I would verify [specific detail] by checking [documentation, test, or code].

This is stronger than inventing a confident answer. You can still reason through the question aloud.

### Did you use AI to write this project?

> Yes, I used AI assistance for parts of development and learning. I am responsible for reviewing changes, understanding how they fit the system, and checking their behaviour. For example, I can walk through replacement and explain why old ingestion runs must be excluded. I would not claim that every line was written unaided.

Only use details about your review process that are true. Be ready to explain a function, modify it, and predict an edge case without relying on a generated script.

### What if AI gives you code you do not understand?

> I would not treat it as finished. I would break down the function, check its assumptions and error paths, and test it with small cases. If I still cannot explain it, I need more understanding or a simpler implementation before relying on it.

### Why are your results not more impressive?

> I prefer a result I can defend to a large claim without evidence. Our small retrieval experiment could not distinguish the chunk sizes at Hit@5. That still helped us identify how the evaluation should improve.

### What would your teammates say about you?

> I hope they would say I contribute to practical document and integration work and care about understanding the behaviour. A specific example is [a real collaboration they can confirm]. I would rather give an example than claim what they think without asking them.

### Where do you see yourself in a few years?

> I want to become an engineer who can own a feature from requirements to deployment and support. My next step is to strengthen fundamentals, learn from reviews, and deliver reliable changes in a real team.

### Salary, overtime, and competing offers

> I would like to understand the role, expectations, and overall package before discussing a specific number.

> I can be flexible for occasional important deadlines. I would also want clear priorities and realistic planning so overtime does not become the normal solution.

> I am considering roles that fit my learning goals and where I can contribute. I can share my real timeline, but I would not invent another offer.

### Why you rather than someone with more experience?

> An experienced engineer will have strengths I do not yet have. For this role, I can offer relevant project work, willingness to learn, and a habit of checking details. I would aim to become useful quickly through small reviewed tasks rather than claim I can replace senior experience.

## 13. Unexpected follow-ups to practise

Ask these after the first answer, not only as separate memorised questions:

1. “Show me the exact code where that happens.”
2. “What is your evidence? Did you measure it?”
3. “Was that your change or your teammate's?”
4. “What happens if the process crashes between those two steps?”
5. “What if I call the endpoint directly without your UI?”
6. “Which operation commits? Which only flushes?”
7. “What changes if the file has only images?”
8. “What if the model returns valid JSON with a false claim?”
9. “What data goes to the third-party service?”
10. “What if the UI shows an old result after switching tabs?”
11. “How would you know the HNSW index is being used?”
12. “Why isn't your historical 100% Hit@5 production accuracy?”
13. “How do you migrate existing vectors to a new model?”
14. “Can logout invalidate a stolen access token?”
15. “Which feature looks complete but has an important limitation?”
16. “What would you remove if you had one week less?”
17. “Can you explain your implementation without library names?”
18. “Can you change this requirement live?”
19. “What did AI help with, and what did you verify?”
20. “What decision would you make differently now?”

## 14. Today's discussion plan with your friends

**First 15 minutes:** each person gives the project story and identifies their actual contribution. Correct ownership claims together.

**Next 25 minutes:** draw upload and chat flows. Ask who validates identity, who checks ownership, where bytes live, when commit happens, and what the user sees on failure.

**Next 20 minutes:** discuss latest changes: dtype, page-aware chunks, heading inclusion, roadmap, HTTPS/cookies, and generation failures. Explain why each matters with a user-visible example.

**Next 20 minutes:** challenge the architecture using five scenarios: restart mid-ingest, replace during indexing, empty scope, malicious document, and Gemini outage.

**Next 25 minutes:** practise two technical stories and four behavioural answers. Use simple sentences and a real result. Let a friend interrupt with follow-ups.

**Last 15 minutes:** identify three weak topics, open their source files, and explain one function each. Record what needs further study.

Score answers from 0 to 2 on each: clear problem, correct flow, ownership honesty, tradeoff, and failure handling. Ten points is the maximum. Do not reward technical vocabulary without understanding.

If time is short, prioritise the introduction, your contribution, upload flow, chat flow, replacement story, why pgvector, grounding limits, why hire you, and why this company.

## 15. Source map for checking your answers

| Topic | Source |
| --- | --- |
| Route registration and application setup | `apps/api/app/main.py` |
| Settings and default models | `apps/api/app/core/config.py` |
| Upload, ingest, read, rename/move, delete, replace | `apps/api/app/routers/files.py` |
| Storage operations and upload limit | `apps/api/app/services/storage.py` |
| Parsing and chunking | `apps/api/app/services/ingestion.py` |
| Processing states and thread handoff | `apps/api/app/services/processing.py` |
| Model loading, dtype, tokenizer, embeddings | `apps/api/app/services/embeddings.py` |
| Search and RRF | `apps/api/app/db/vector_ops.py` |
| Vector/text indexes and constraints | `apps/api/app/schemas/chunk.py`, migrations |
| Scope, summary path, chat persistence | `apps/api/app/routers/rag.py` |
| Prompt, Gemini call, fake mode | `apps/api/app/services/prompt.py`, `llm.py` |
| Citation verification | `apps/api/app/services/grounding.py` |
| Tokens, refresh, registration, logout | `apps/api/app/routers/auth.py` |
| Auth dependency | `apps/api/app/dependencies/auth.py` |
| Typed HTTP boundary | `packages/contracts/src/api_client.ts` |
| Explorer fetch/poll/mutations | `packages/ui/src/hooks/useExplorerData.ts`, `useExplorerMutations.ts` |
| Chat and scope classification | `packages/ui/src/hooks/useChatSession.tsx`, `lib/chatRequest.ts` |
| Roadmap | `packages/ui/src/hooks/useRoadmap.ts`, `apps/api/app/routers/milestone.py` |
| Evaluation evidence | `apps/api/evaluation/chunk_retrieval_results.md` |
| Deployment configuration | `deploy/Caddyfile`, `deploy/nttbc-api.service`, `deploy/deploy.sh` |

For deeper maths and historical details, see the existing `interview-preparation.en.md`. For more contribution evidence, see `contribution-interview-playbook.en.md`. These older files should be read together with this guide's latest-change section.

## 16. Questions you can ask the interviewer

- “What would a successful first three months look like for this role?”
- “How are junior developers supported through code reviews?”
- “What kinds of tasks would I initially own?”
- “How does the team decide when to improve existing code versus build a new feature?”
- “How are bugs and production incidents handled?”
- “Which skill would make me most useful to your team early on?”

## 17. A one-minute answer if you feel nervous

> NTBC helps students ask questions about their own course material. We parse documents, create searchable chunks, retrieve relevant passages, and generate an answer with citations. I mainly worked on document ingestion, file APIs, and frontend integration. One example is file replacement: I made sure old ingestion runs were excluded so search would not use outdated content. I also learned that citations and a good test score do not prove every answer is correct. I would bring that same habit of checking details and being honest about limitations to this role.

Pause. Let them choose the next topic. You do not need to explain the entire repository in one breath.
