# NotToBeCooked Interview Preparation Guide - Expanded Technical Edition

Expanded English edition prepared on October 2, 2026. Sections 1-11 retain the original interview guide. Sections 12-25 explain the AI pipeline, formulas, teammate responsibilities, and practical exercises in more detail.

The original guide was based on the workspace implementation and the model-loading lock in `main`'s `embeddings.py`. At that time, the workspace was on `dev`; the expanded edition was prepared while it was on `main` at `c8810b8`. Do not describe uncommitted local changes as committed features. Some README descriptions were outdated; the implementation was used as the reference. The expanded AI explanations were checked against the source code and selected primary documentation. This revision does not include a new end-to-end test run, live model call, or performance measurement.

## 1. Introduce the problem before the implementation

A short introduction:

> NotToBeCooked is a study assistant for course materials. It parses uploaded documents, splits them into chunks, and stores their embeddings in PostgreSQL. When a user asks a question, we search only the files they can access, combine vector and keyword search, and pass the relevant content to Gemini. Before returning the answer, we check its citations against the retrieved sources. The frontend uses React and TypeScript, the API backend uses Python and FastAPI, and the desktop app uses Tauri.

Then describe your actual contribution:

> My main responsibility was **[specific module]**. I worked on **[actual problem]** and verified the result using **[tests, logs, or a practical check]**.

Do not claim authorship of work whose ownership you have not confirmed. Practise speaking the introduction aloud and shorten it if it exceeds your allotted time.

## 2. Distinguish languages from frameworks and tools

| Area | Language or syntax | Frameworks, libraries, or tools | Role in the project |
|---|---|---|---|
| Frontend | TypeScript with JSX; CSS for styling | React, Vite, Tailwind, TanStack Query, Zustand | UI, builds, server-data caching, and workspace state |
| API backend | Python | FastAPI, Pydantic, SQLModel, SQLAlchemy | HTTP routes, request validation, and database access |
| Database | SQL is the query language | PostgreSQL, pgvector | Relational data, full-text indexing, and vector storage and search |
| Database connections and migrations | Python | asyncpg, Alembic | Asynchronous PostgreSQL access and schema version management |
| Documents and AI | Python | Docling, SentenceTransformers, PyTorch, Gemini API | Document parsing, local embeddings, and remote answer generation |
| Desktop application shell | Rust; the UI still uses TypeScript and React | Tauri | Packages the shared frontend as a native application |
| Development tooling | Configuration files and scripts | pnpm, uv, Turborepo, Docker, OpenAPI | Dependencies, tasks, database environments, and API contracts |

React, FastAPI, and PostgreSQL are not programming languages. Gemini generates answers; the embedding model generates vectors for retrieval. Running or calling these models does not mean the team trained a foundation model.

The desktop application shell is the native application layer around the UI, not a command-line shell. The API backend is still Python.

If asked about programming languages:

> We use TypeScript for the frontend, Python for the API backend, and SQL for database queries. The Tauri application shell uses Rust.

If asked about the technology stack:

> Our frontend uses React and TypeScript. Our backend uses Python and FastAPI. We use PostgreSQL with pgvector for our database and vector search.

Add Vite and other tools when relevant to a follow-up. You should be able to explain every technology you mention.

## 3. A structure for answering any button-flow question

Follow this sequence:

**UI event → frontend input and state → HTTP method and endpoint → authentication → resource authorization → service logic → database operations and transactions → response → UI update → failure handling.**

Answer in three layers:

1. Give the complete flow in about 30 seconds.
2. Name specific functions and files when the interviewer asks for detail.
3. Explain the design choices and limitations.

Avoid opening with a long list of library names.

## 4. What happens when the user clicks Send?

### Implementation walkthrough

1. `packages/ui/src/components/chat/ChatInput.tsx` submits the text. `handleSend` in `Chat.tsx` calls the external send callback.
2. `packages/ui/src/pages/dashboard.tsx` receives the action and delegates to `packages/ui/src/hooks/useChatSession.tsx`.
3. The hook resolves file mentions and the course/file scope. It supplies `conversation_id`, `question`, `top_k`, and `intent`. For an existing conversation, it first makes an optimistic cache update.
4. `api.chat.query` in `packages/contracts/src/api_client.ts` sends `POST /rag/query`. The client reads the access token from memory and adds the Bearer authorization header.
5. FastAPI validates the request structure, and `get_current_user` verifies identity. `apps/api/app/routers/rag.py` gets or creates a conversation and adds the user message to the database session.
6. For ordinary questions, `_scope_file_ids` resolves accessible files through the file, folder, course, and user relationships. An empty result causes retrieval to return early.
7. `_retrieve` generates the question embedding with `asyncio.to_thread(embed_query, ...)`, then calls `hybrid_search`.
8. `apps/api/app/db/vector_ops.py` performs vector similarity search and PostgreSQL full-text search over chunks from active ingestion runs. Weighted Reciprocal Rank Fusion (RRF) combines the rankings.
9. `build_context` constructs the context with source markers, and `generate_answer` calls Gemini. The `document_summary` intent follows a different path: it reads the complete active run's chunks for one document, rather than ordinary top-k question retrieval.
10. The backend resolves citations, removes unused citations, checks quoted text against source chunks, and checks marker and coverage consistency. A failed grounding check replaces the answer with a message saying it could not be verified.
11. The backend saves the assistant message, citations, and scope snapshot, updates the conversation timestamp, commits, and returns `RagAnswer`.
12. The frontend updates the active conversation and invalidates the message and session-list caches. It fetches server data again and renders the answer and citations.

### A spoken answer

> When the user clicks Send, React collects the question and the current course or file scope, then sends a POST request to `/rag/query`. The backend validates the token and request and determines which files the user can access. It converts the question into an embedding, searches PostgreSQL using both vector and keyword search, and combines the rankings with RRF. The retrieved content goes into the prompt for Gemini. Before returning the answer, we verify the citation sources and quotes. Finally, we save the messages, commit the transaction, and refresh the frontend's conversation cache.

### Likely follow-up questions

- **Why check ownership when the frontend already sends `file_ids`?** Client requests can be modified. Hiding controls in the UI does not enforce authorization.
- **Why return early for an empty file list?** The current retrieval implementation treats an empty list as no file filter. Passing it through could expand the query to other users' data.
- **Is the user message permanently saved after `session.add`?** No. Adding an object to the session is not the same as committing it. Messages are committed near the end of this request. Creating a new conversation may commit earlier, so do not describe the entire request as one transaction.
- **Is this streaming?** This path returns a complete JSON response. Using `async` does not imply token-by-token streaming.
- **Does the model automatically remember earlier questions?** Persisting messages does not mean they are included in the model prompt. The generation call described here passes the current question, context, and sources. A `conversation_id` alone does not prove that conversation history is used for generation.

## 5. What happens when the user clicks Upload?

### Implementation walkthrough

1. `UploadModal.tsx` checks extensions, the 50 MB limit, and duplicates within the current selection, then calls the upload callback. Frontend validation improves usability; it is not a security boundary.
2. The dashboard uses the upload mutation. The API client creates `FormData` containing `folder_id` and `upload`, then sends `POST /files`. The browser sets the multipart boundary.
3. `routers/files.py` verifies the logged-in user and folder ownership. It derives `course_id` from the verified folder.
4. `services/storage.py` reads the upload in pieces, enforces the byte limit, calculates SHA-256, and writes the original file to local storage. The storage key is associated with the user and file UUIDs.
5. The backend inserts FILE metadata with status `uploaded`, commits, and returns `201 Created`. The complete original file's bytes are not stored in PostgreSQL.
6. The dashboard then sends `POST /files/{id}/ingest`. The backend verifies file ownership, creates a queued, inactive INGESTION_RUN, commits it, registers a `BackgroundTasks` task, and returns `202 Accepted`.
7. The background task opens its own database session. Docling parses the document; `extract_text` extracts content; `create_chunk` splits it using content and token counts; and `embed_text` generates embeddings in batches. Blocking parsing and inference run through `to_thread`.
8. The task writes CHUNK rows and records success or failure. Completion handling updates the active run and file status. Retrieval reads only the active version.
9. `useExplorerData.ts` refreshes the course's file list every three seconds while it contains files with `uploaded` or `processing` status. That polling condition stops once no such files remain.

### A spoken answer

> We separate uploading from indexing. The upload request writes the original file to storage, saves its metadata in the database, and returns 201. The frontend then requests ingestion. The backend records the task and returns 202 before the expensive processing finishes. The background task parses the document, creates chunks and embeddings, and stores the chunks. Meanwhile, the frontend polls the file status. Upload success means the file is stored; a ready index means it can be used for retrieval.

### Likely follow-up questions

- **Why return 202?** It means processing has been accepted, not completed.
- **Is `BackgroundTasks` a durable task queue?** It runs work inside the application process after the response. It does not provide the reliable delivery or restart recovery guarantees of a separate durable queue. At greater scale, consider independent workers, a persistent queue, retries, and idempotency.
- **What if the user requests ingestion twice?** Distinguish “only one active run is allowed” from “only one task executes.” A unique constraint enforcing the first does not automatically enforce the second.
- **Why have INGESTION_RUN?** It records model and chunking configuration, versions, and processing status, and helps prevent old and new chunks from being mixed during retrieval.
- **Does SHA-256 automatically prevent duplicate uploads?** Computing a checksum does not implement deduplication by itself. Check whether the code actually looks up and rejects duplicates.
- **What about scanned PDFs?** The PDF configuration described in the original guide disables OCR. A scanned document may yield no extractable text and fail ingestion. On-demand OCR is a possible improvement, not a feature to claim for all scanned documents today.

## 6. Explain OOP using the project

### Classes and objects

A class defines structure and behavior; an object is an instance of that class. `ApiClient` is a class, and `new ApiClient(...)` creates an instance. In Python, `Course` is a model class and `Course(...)` creates an object. Constructing the object does not automatically create a persistent database row; persistence requires database operations and a successful commit.

### Encapsulation

`ApiClient` keeps `baseUrl`, the token getter, `refreshSubscribers`, and the internal request method together. It exposes auth, file, and chat operations, so callers do not repeatedly implement headers, error parsing, and token refresh.

> Encapsulation means keeping related state and behavior together and controlling how callers interact with them. In our API client, request handling is hidden behind methods such as `files.upload` and `chat.query`.

TypeScript's `private` is generally enforced by type checking; do not present it as an unbreakable runtime security boundary. JavaScript's `#private` fields are different. A single leading underscore in Python is usually a convention, not an authorization mechanism.

### Abstraction

The UI calls `api.files.upload` without knowing the details of `fetch`. The storage module uses a storage key to hide local filesystem paths. Abstraction can be provided by functions and modules as well as abstract classes.

> Abstraction means exposing the operation a caller needs while hiding implementation details. Our upload UI calls an API-client method without handling HTTP headers itself.

### Inheritance

Examples include `Course(SQLModel, table=True)`, `Chunk(Base)`, `TSVector(TypeDecorator)`, and `UploadTooLargeError(Exception)`. Inheritance should represent a valid “is-a” relationship and behavioral contract, rather than a hierarchy created merely to remove a few repeated lines.

> Inheritance allows a class to build on a base class. For example, our Course model inherits from SQLModel, and our custom upload exception inherits from Exception.

### Polymorphism

Different implementations can satisfy the same interface. Python supports duck typing; TypeScript can express contracts through interfaces and structural typing. `TSVector` participates in the ORM's type system as a `TypeDecorator` subtype.

A possible extension, not an existing implementation: define a storage contract with `put`, `get`, and `delete`; implement it with local storage and object storage; make the upload service depend on that contract.

> Polymorphism allows callers to use different implementations through the same interface. For example, we could define a storage interface and provide local and cloud-storage implementations without changing the upload workflow.

Say “we could implement this” rather than claiming these storage classes already exist.

### Composition and SOLID

React composes components. The answer pipeline composes retrieval, generation, and grounding checks. Composition expresses “has-a” or “uses-a” relationships and often makes replacement and testing easier than a complex inheritance hierarchy.

- **Single Responsibility Principle:** A module should have one main reason to change. The API client centralizes request handling, and storage isolates file operations. Whether either has too many responsibilities still requires judgment.
- **Open/Closed Principle:** A stable storage contract could allow new implementations without rewriting callers. This is an evolution direction, not a completed refactor to claim.
- **Liskov Substitution Principle:** Subtypes must preserve the behavior callers expect from the base type. Matching method names is not enough.
- **Interface Segregation Principle:** Clients should not be forced to depend on large interfaces containing operations they do not use.
- **Dependency Inversion Principle:** High-level logic should depend on abstractions. FastAPI's `Depends` provides dependency injection, but using it alone does not prove the entire architecture follows this principle.

## 7. Common interview questions and essential answer points

| Interview question | What a sound answer should include |
|---|---|
| Why not give the entire PDF directly to the LLM? | Context limits, cost, latency, and source attribution. RAG selects relevant material, but its effectiveness depends on retrieval quality. |
| Why use hybrid search? | Vector search helps with semantic similarity; keyword search helps with exact terms. They complement each other, but improvement should be measured. |
| What is RRF? | Each ranked list contributes `weight / (k + rank)` to an item's score, then items are sorted by total score. It avoids directly adding similarity scores with different scales. |
| What is an embedding? | A numeric vector representing text. Semantically similar text often has nearby vectors. This project uses 1,024 dimensions; changing models may require re-embedding and rebuilding indexes. |
| What happens if chunks are too large or too small? | Large chunks may contain irrelevant material and consume context; small chunks may lose meaning. Evaluate retrieval and answer evidence. |
| Why PostgreSQL with pgvector? | One database manages relational data, transactions, ownership relationships, and vectors. This simplifies operations, but very large workloads may need a different design. |
| What is pgvector? | A PostgreSQL extension for storing vectors and performing similarity searches. The embedding model generates the vectors; pgvector stores and searches them. |
| Which indexes are used? | HNSW for chunk embeddings and GIN for `content_tsv`. Use EXPLAIN to determine whether a particular query uses an index. |
| What are primary keys, foreign keys, and unique constraints? | Row identity, relationship enforcement, and prevention of duplicate values or combinations. Use user/course/folder/file/run/chunk examples. |
| What are transactions, flush, and commit? | Transactions group database operations for commit or rollback. Flush sends pending SQL without necessarily committing; commit completes the transaction; refresh reads state from the database. |
| What does ACID mean? | Atomicity, Consistency, Isolation, Durability. A database transaction does not automatically include local filesystem writes or remote model requests. |
| Why does async not automatically make work faster? | Waiting for I/O can yield execution; blocking computation can still occupy the event loop. `to_thread` moves blocking work off the loop but does not guarantee better CPU throughput. |
| Why not reload the embedding model for every request? | Loading is expensive and consumes memory. The main version examined caches the model and uses a `threading.Lock` with a second check during initial loading to prevent duplicate concurrent loads. |
| Is JWT encrypted? | A commonly used signed JWT does not encrypt its payload. Verify signatures, allowed algorithms, and expiration. Do not store secrets in the payload. |
| How do authentication and authorization differ? | Authentication establishes identity; authorization determines access to a resource. Being logged in does not grant access to every UUID. |
| Does CORS protect the API? | CORS controls browser cross-origin access. It does not replace authentication or authorization, and it does not block every non-browser client. |
| How are passwords stored? | As Argon2 hashes, not plaintext. Hashing is different from reversible encryption. |
| Where is the access token stored? | The API client gets it from memory. Refresh uses an HttpOnly cookie. The client coordinates refresh after a 401 and retries requests. |
| Does TypeScript validate API responses? | Static types do not guarantee the shape of network JSON. Runtime validation is also needed; the project includes Zod and OpenAPI contracts. |
| How do useState, Zustand, and TanStack Query differ? | Local component state, shared client workspace state, and server data/cache management. Different kinds of state have different owners. |
| What is an optimistic update? | Show an expected change before server confirmation, correct or roll back on failure, and refresh server truth on success. It does not mean the database has committed. |
| How do 401, 403, 404, 422, and 500 differ? | Failed authentication, forbidden access, missing or concealed resources, input validation failures, and server errors. Some project endpoints return 404 to conceal resource existence. |
| How do you reduce hallucinations? | Restrict sources, retrieve relevant material, guide the model, verify citations, and support refusal. Citation existence does not establish the truth of every claim. |
| How would you evaluate RAG? | Fixed questions and relevance labels; Recall@k, MRR/nDCG, citation accuracy, answer quality, latency, and refusal behavior. Do not invent results. |
| How would you test authorization? | Use two users and attempt cross-user file and conversation access. Test empty scope, cross-course selection, and invalid or expired tokens; check for data leakage. |
| Are mocked tests enough? | No. Mocks isolate logic; real PostgreSQL is needed to verify constraints, driver behavior, JSONB serialization, and transactions. |
| How would you investigate slow responses? | Measure parsing, embeddings, database work, model calls, and serialization separately; inspect resource usage; optimize the demonstrated bottleneck. |
| What if the system must serve 1,000 concurrent users? | Define request rate, document size, and latency targets first. Consider rate limits, workers, queues, model resources, connection pools, indexes, and load tests. Adding async is insufficient. |
| If AI helped write the code, what was your contribution? | Explain requirements, constraints, review, debugging, testing, and verification that you actually performed. Be ready to explain and modify your module live. |

## 8. Four concrete engineering stories to study

1. **An empty scope becoming an unfiltered search.** Read `_scope_file_ids`, `_retrieve`, `vector_ops.py`, and `test_rag_scope.py`. Explain why authorization must determine the scope before retrieval.
2. **Blocking document processing making health checks unresponsive.** Read the `to_thread` calls in processing and the related tests. Explain why the event loop was occupied. Measurements in code comments are repository records, not measurements you personally performed or results revalidated for this guide.
3. **Concurrent first-time model loading.** Read `main`'s `embeddings.py` and `test_embeddings.py`. Draw the sequence where two threads both observe `None`, then explain the lock and second check inside it.
4. **UUID serialization failing in JSONB.** Read `database.py` and `test_jsonb_uuid.py`. A mock can miss actual serialization; a real driver exposes it. The serializer converts UUIDs while continuing to reject other unsupported objects.

Structure each story as:

**Trigger → observed symptom → hypothesis → evidence → root cause → fix → regression checks → limitations.**

If you did not implement the fix, say:

> In our team's implementation, I studied **[issue]** and verified **[specific behavior]**.

Use “verified” only when you actually performed the verification.

## 9. Demonstrate ability through specific explanations

Replace a vague claim with the mechanism behind it:

> Parsing is synchronous, blocking work. Putting it inside an async function would still occupy the event loop, so we move parsing and embedding inference to worker threads.

> We cannot trust the file IDs in the request. We resolve accessible files through the current user's courses before retrieval, and we return early if that set is empty.

> We check that citation markers and quoted text match the retrieved sources. That improves traceability, but it does not prove that every inference in the answer is semantically correct. We still need answer-quality evaluation.

Describe your actual responsibilities rather than saying you built everything. Confidence comes from tracing the implementation, explaining tradeoffs, recognizing limitations, and proposing verification steps. Do not invent production scale, performance metrics, or personal contributions.

When you do not know:

> I haven't verified that yet. My current understanding is **[reasoned explanation]**, based on **[code or principle]**. I would confirm it using **[experiment, logs, or a query plan]** before deciding whether to **[proposed change]**.

## 10. A seven-day practice plan

1. **Day 1:** Draw the architecture and relationships between the nine entities. Practise 30-second and 90-second project introductions.
2. **Day 2:** Trace Send using breakpoints or logs. Record the request payload, route, queries, commit, response, and UI update. Do not expose real tokens.
3. **Day 3:** Trace upload and ingestion. Observe 201, 202, and queued/processing/ready/failed states. Test empty content and unauthorized access.
4. **Day 4:** Explain classes, objects, and the four OOP concepts using ApiClient and model classes. Distinguish encapsulation from authorization.
5. **Day 5:** Practise SQL joins, transactions, indexes, async, locks, JWT, and error codes. Give a one-minute answer to each, then handle two follow-up questions.
6. **Day 6:** Prepare two true contribution stories and one failure or improvement story. Include evidence from checks you actually performed.
7. **Day 7:** Run a 45-minute mock interview: project introduction, 3 minutes; button tracing, 10 minutes; technical follow-ups, 15 minutes; code or SQL, 12 minutes; your questions to the interviewer, 5 minutes.

If you only have one day, prioritize the project introduction, Send flow, two-stage upload flow, OOP, one true contribution story, and one current limitation.

## 11. Mock interview scoring

Each round is worth 10 points:

- Complete request and response flow: 2.
- Accurate implementation and data facts: 2.
- Explanation of design reasons: 2.
- Failure handling, authorization, and transaction boundaries: 2.
- Clear communication and accurate personal responsibilities: 2.

Opening question:

> A user enters a question on the course page and clicks Send. Walk me through what happens, from the React event to PostgreSQL and back to the UI, in 60 to 90 seconds. Then explain why the backend cannot trust the file IDs sent by the browser.

Improve your answer after each round. You do not need to memorize the entire guide before starting. You have mastered a topic when you can explain it without notes and answer follow-up questions.

## 12. Start here: understand the whole AI pipeline

### You do not need to pretend you built every component

Your goal is to understand what goes into each stage, what comes out, why it exists, and how your work connects to it. Implementing every model or knowing every mathematical detail is not the same as understanding the system.

Use this distinction in interviews:

> My main contribution was document ingestion and file-management workflows. My teammates implemented important retrieval and generation components. I understand how those components connect to my work, and I can walk through the complete request flow.

### Two workflows, not one mysterious AI operation

The preparation workflow runs when a file is indexed:

**Document -> parse -> extract text -> create chunks -> generate embeddings -> store chunks and vectors.**

The answering workflow runs when a question arrives:

**Question -> authorized file scope -> query embedding -> hybrid search -> RRF ranking -> context -> Gemini -> citation checks -> stored answer and response.**

The first workflow prepares searchable evidence. The second finds that evidence and generates an answer from it. A broken preparation step can make a correct search algorithm look ineffective.

### RAG in plain English

RAG means **Retrieval-Augmented Generation**:

- Retrieval: find useful stored information.
- Augmented: add that information to the model's input.
- Generation: ask the model to produce an answer.

Think of an open-book explanation: find the relevant pages first, then write the answer with those pages available. This comparison explains the stages; it does not mean the model behaves exactly like a person.

**RAG is not model training.** Your system supplies document content at request time; it does not update Gemini's model weights when a student uploads a PDF.

### Where your contribution matters

If tables disappear during extraction, retrieval cannot find their evidence. If chunks lose page metadata, citations become harder to trace. If replacement leaves old runs active, the model may receive stale evidence. These are important AI-system problems even when the code solving them is ordinary Python, SQL, and API logic.

Suggested reading order: sections 12-16 first, then 18-21. Return to the original OOP and interview sections afterward. The concurrency note in section 17 is an advanced discussion, not the first thing to memorize.

## 13. The basic vocabulary, with concrete meanings

### Document, chunk, token, and metadata

A **document** is the uploaded file. A **chunk** is a smaller piece of extracted content used as a retrieval unit. A **token** is a unit produced by a model's tokenizer; it may be a word, part of a word, punctuation, or another text unit. A token is not necessarily one English word.

**Metadata** describes content: file ID, heading, page range, chunk position, course ID, or the run that produced it. The text answers “what does it say?” Metadata answers “where did it come from?”

Example: a lecture page contains a definition of database indexing. The chunk stores the definition; metadata associates it with lecture.pdf, page 7, its heading, and an ingestion run.

Current `create_chunk` defaults to a 350-token budget and separates content when headings change. The standalone long-text splitter defaults to 500, but the chunker passes its chosen budget into it. Do not confuse a helper's default with the pipeline's actual parameter.

### Ingestion, indexing, and inference

**Ingestion** is the process of bringing a document into the searchable system: parsing, extracting, chunking, embedding, and persistence.

**Indexing** can refer broadly to preparing searchable content, or specifically to a database index structure. Distinguish “the file finished indexing” from “PostgreSQL used an HNSW index for this query.”

**Inference** means running an already-trained model on input to obtain output. Generating embeddings locally and calling Gemini are inference; they are not evidence that you trained those models.

### Query, candidate, rank, score, and top-k

A **query** is a search request or the user's question. A **candidate** is a chunk found by a search stage. A **rank** is its position in a sorted list, starting at 1. A **score** is a number used for ordering or filtering. **Top-k** means retain the first k items after ranking.

An item ranked first has rank 1; its score does not have to be 1. A score of 0.9 is not automatically a 90% probability of correctness.

### Context, prompt, and citation

**Context** is the selected document content supplied to the model. The **prompt** includes instructions, the question, and that context. A **citation** links an answer back to a source and its quoted evidence.

**Grounding** means checking or constraining an answer against supplied evidence. The exact guarantees depend on the implemented check; the word alone does not mean the answer is proven true.

### A short interview answer

> We split documents into chunks, attach source metadata, and generate embeddings. At question time, we retrieve relevant chunks and include them in the model's prompt. The answer then goes through citation checks before it is returned.

## 14. Embeddings and cosine similarity, step by step

### What an embedding is

An embedding model maps text to a numeric vector, such as `[0.12, -0.35, ...]`. The individual numbers are not a readable summary. Their arrangement lets a search system compare inputs in the model's learned representation.

In the inspected configuration, the local model is `jinaai/jina-embeddings-v5-text-small`, and the chunk vector column has 1,024 dimensions. These are code defaults; environment settings can override the model name, and deployed configuration should be checked separately.

`embed_text` creates document embeddings in batches. `embed_query` creates the question embedding. The code uses the document and query prompt names respectively and requests normalized embeddings.

Semantically similar wording may yield nearby vectors. This is useful for “make SQL faster” versus “improve query performance,” but similarity is not proof that a chunk answers the question.

### The cosine formula

For nonzero vectors q and d:

```formula
cosine_similarity(q, d) = dot(q, d) / (length(q) * length(d))
dot(q, d) = sum over i of q_i * d_i
cosine_distance(q, d) = 1 - cosine_similarity(q, d)
```

q is the question vector; d is the document-chunk vector. The dot product multiplies corresponding coordinates and adds them. Length is the square root of the sum of squared coordinates. Cosine compares direction rather than simply comparing vector size.

### A small worked example

Use two dimensions only to make the arithmetic visible; real project vectors have 1,024 coordinates.

```formula
q = [1, 0]
d = [0.8, 0.6]
dot(q, d) = 1 * 0.8 + 0 * 0.6 = 0.8
length(q) = 1; length(d) = sqrt(0.8^2 + 0.6^2) = 1
cosine_similarity = 0.8; cosine_distance = 0.2
```

A second chunk `[0, 1]` has similarity 0 and distance 1 from q. Under cosine distance, the first chunk is closer. Similarity can range from -1 to 1; cosine distance can range from 0 to 2. These are mathematical ranges, not confidence probabilities.

### What pgvector does here

The model computes embeddings; pgvector stores vectors and supports distance-based search. The project's `_vector_similarity_search` orders by ascending cosine distance. Its separate `vector_search` wrapper converts distance into `1 - distance` for the returned score. The hybrid path instead returns an RRF score.

pgvector's `<=>` operator represents cosine distance. Its documentation also distinguishes exact search from approximate indexed search. [pgvector documentation](https://github.com/pgvector/pgvector)

### Follow-up questions

- **Can two models with 1,024 dimensions be mixed?** Equal dimensions do not mean equal vector spaces. Changing the model generally requires regenerating compatible document embeddings and validating retrieval.
- **Why normalize?** Unit-length vectors make comparison consistent with cosine-based retrieval. It does not make all scores positive or make retrieved text correct.
- **Does pgvector call Gemini?** No. Storage/search and answer generation are different stages.

> An embedding is a numeric representation of text. We compare the question embedding with document embeddings using cosine distance. Smaller distance indicates a closer match in the model's representation, but we still need to evaluate whether the retrieved content answers the question.

## 15. Keyword search and hybrid search

### Two different reasons a chunk may be relevant

Vector search is useful when wording differs but meaning is related. Keyword search is useful when the exact terminology matters, such as an acronym, function name, or course concept. Neither method is universally better.

For “What does ACID mean?”, literal term matching can be valuable. For “How do we keep changes consistent when something fails?”, a semantic search may find a transaction explanation even without the word ACID. These are illustrative examples, not recorded retrieval results.

### The actual keyword implementation

Your code uses PostgreSQL full-text search with an English configuration. The chunk model defines a stored `content_tsv` value derived from `to_tsvector('english', content)`. `_full_text_search` creates a query with `plainto_tsquery`, changes its AND separators to OR, filters using `@@`, and sorts by descending `ts_rank`.

PostgreSQL's `tsvector` holds processed lexemes and positions, not neural embeddings. `tsquery` represents search terms and operators. `ts_rank` ranks matches using lexical frequency information. [PostgreSQL text-search documentation](https://www.postgresql.org/docs/16/textsearch-controls.html)

Important distinctions:

- `tsvector` and pgvector's `vector` are different data types with different purposes.
- This implementation uses `ts_rank`; it is not evidence that the project implements BM25.
- Replacing AND with OR allows a match on any surviving query term. It can broaden candidates but also admit less relevant content.
- English normalization is not a complete multilingual search solution. Test the languages in your actual course material.

### Hybrid search in this project

Hybrid search retrieves a vector-ranked list and a keyword-ranked list, then fuses them. It does not simply concatenate two answers, and it does not mean the model uses two LLMs.

The search config defaults to up to 50 candidates from each list. Results are combined by chunk ID. A chunk found in both lists receives a contribution from both rankings. Weighted RRF then determines the combined order.

If each list has 50 candidates, the union has at most 100 distinct chunks; overlap can make it smaller. The final returned count is limited separately.

> Our hybrid search combines vector similarity search with PostgreSQL full-text search. Vector search helps with semantic matches, while keyword search helps with literal terms. We combine their ranked results using Reciprocal Rank Fusion rather than adding their raw scores.

## 16. RRF: the formula and a fully worked ranking

### What the formula selects

RRF means **Reciprocal Rank Fusion**. It ranks retrieved chunks, not complete generated answers. The highest-ranked chunks become evidence for the prompt. Gemini generates an answer afterward; citation checks happen after generation.

The original RRF method combines rankings through reciprocal rank contributions. The project's implementation extends this with explicit vector and keyword weights. [Original RRF paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

### The project's formula

```formula
RRF(chunk) = vector_weight / (rrf_k + vector_rank)
           + keyword_weight / (rrf_k + keyword_rank)
```

Only include a term if the chunk appears in that ranked list. A missing item contributes zero. Ranks start at 1.

- `vector_weight`: importance assigned to the vector list; default 1.0.
- `keyword_weight`: importance assigned to the keyword list; default 1.0.
- `rrf_k`: smoothing constant; default 60.
- `vector_rank` and `keyword_rank`: positions in the respective lists.

`rrf_k` is NOT the requested top-k count. Changing it does not directly change how many chunks are returned. A larger smoothing constant makes differences between nearby ranks less pronounced; the preferred value should be evaluated for the workload.

### Hypothetical rankings

Suppose vector search returns A, B, C, while keyword search returns B, C, D. These letters are teaching labels, not actual database rows or benchmark results.

With both weights 1 and `rrf_k = 60`:

| Chunk | Vector rank | Keyword rank | Raw RRF | Final rank |
|---|---:|---:|---:|---:|
| A | 1 | absent | 0.016393 | 3 |
| B | 2 | 1 | 0.032522 | 1 |
| C | 3 | 2 | 0.032002 | 2 |
| D | absent | 3 | 0.015873 | 4 |

### Calculate B by hand

```formula
RRF(B) = 1 / (60 + 2) + 1 / (60 + 1)
       = 1/62 + 1/61
       = 0.016129 + 0.016393
       = 0.032522 (rounded)
```

A is first in vector search but receives only `1/61`. B receives contributions from both lists and ranks above A. This shows how agreement between retrieval methods can affect fusion. It does not prove B is factually correct or always the best evidence.

### Why not add cosine similarity and ts_rank directly?

Their numbers have different meanings and scales. A raw sum may let one retrieval method dominate for numerical reasons. RRF uses positions, avoiding the need to assume the underlying scores are comparable. The tradeoff is that it discards score gaps: rank 1 barely above rank 2 and rank 1 far above rank 2 are treated through rank positions alone.

### Normalized threshold versus returned raw score

The code computes:

```formula
max_possible = (vector_weight + keyword_weight) / (rrf_k + 1)
normalized = raw_RRF / max_possible
```

With equal default weights, `max_possible = 2/61 = 0.032787` approximately. B's normalized score is approximately 0.991935. A's is 0.5.

The normalized value is used for threshold filtering. The returned `RetrievedChunk.score` remains the raw RRF value. Normalized 0.99 does not mean a 99% chance of an accurate answer. The theoretical maximum assumes the same chunk is first in both lists and sensible positive weights.

The default threshold is 0.0, so there is no positive relevance cutoff by default. Top-k selection alone can still include weak matches. Do not claim a configured confidence threshold rejects irrelevant questions unless you have verified one.

### Fusion versus a reranker

A reranker is a separate stage that evaluates a query with candidate text and reorders candidates. RRF combines existing ranked lists without reading the query and chunk together in that way. The source comments mention a reranker as a possible future direction; the inspected path does not implement one.

> RRF combines rankings, not answer probabilities. Each search method contributes weight divided by a constant plus the chunk's rank. We add those contributions by chunk ID and sort the result. This lets us combine search methods without treating their raw scores as comparable.

## 17. Trace the search code and its limits

### The exact sequence to explain

1. `_scope_file_ids` identifies authorized files through database ownership relationships.
2. An empty authorized set returns early. The bottom-level filter currently treats an empty list as no file filter, so the early return matters.
3. `_retrieve` calls `embed_query` in a worker thread.
4. It calls `hybrid_search` with those file IDs and `SearchConfig(final_limit=request.top_k)`.
5. `_vector_similarity_search` orders cosine distance ascending; `_full_text_search` orders text rank descending.
6. `enumerate(..., start=1)` assigns ranks for fusion.
7. Scores accumulate in a dictionary keyed by chunk UUID, which deduplicates a chunk found in both lists.
8. Candidate scores are sorted descending; a normalized threshold is applied; `final_limit` bounds output.
9. `build_context` performs source selection and assigns prompt markers.

### Four numbers that are easy to confuse

| Parameter | Inspected value | Meaning |
|---|---|---|
| `rrf_k` | 60 | Rank-fusion smoothing constant |
| `vector_limit` / `keyword_limit` | 50 each | Candidate limit for each search method |
| `request.top_k` | Default 5; allowed 1-20 | Requested number of fused results for ordinary questions |
| Context source cap | Normally 8 | Maximum sources passed by normal-question context selection |

`SearchConfig.final_limit` defaults to 20 when used alone, but the ordinary question route overrides it with `request.top_k`. With default top_k 5, at most five sources reach the ordinary prompt. With top_k 20, normal context selection still caps sources at eight. Summary intent follows a different path and does not use this normal cap.

### Database indexes

The chunk model declares HNSW for embedding search and GIN for full-text search. HNSW is a graph-based approximate nearest-neighbor index: it trades some recall for speed and uses memory. GIN is an inverted-index structure useful for matching terms. An index declaration does not prove a query uses it; inspect the query plan with EXPLAIN. [pgvector index documentation](https://github.com/pgvector/pgvector#indexing)

The graph in HNSW is a search index, not evidence that the project has a knowledge graph or GraphRAG implementation.

### An advanced concurrency caveat

The inspected code uses `asyncio.gather` for the two searches and passes the same AsyncSession to both. Describe that as the code's intended concurrent scheduling, not proof of safe database parallelism. SQLAlchemy documents that an AsyncSession should not be shared across concurrent tasks; separate sessions or sequential access should be considered and tested. [SQLAlchemy concurrent-task guidance](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)

This is an implementation concern to understand, not a claim that a particular failure was reproduced in this document. No application code was changed while preparing the PDF.

## 18. From selected chunks to a generated answer

### Context construction

`build_context` receives retrieved chunks and builds numbered blocks with filename, page range, optional heading, and content. Marker `[1]` means the first item in the selected context list, not a permanent database ID.

Example context, invented for teaching:

```text
[1] databases.pdf (p.7) - Indexes
An index can speed up selected queries but adds storage and write overhead.

[2] databases.pdf (p.8) - Query plans
A query plan describes how the database executes a query.
```

Marker `[2]` resolves to the second selected chunk. Reordering changes marker meaning; always resolve against `selected`.

### The prompt has different jobs

Instructions define how to answer; the question defines what to answer; source blocks provide evidence. Model weights do not change.

The instruction requests source-based answers, markers, quotes, and an uncovered field for partial coverage. Validation checks some of these properties afterward.

Putting instructions in a system field is good structure, but not proof against prompt injection. Uploaded text is untrusted content and can contain instructions that try to redirect the model.

### The Gemini call

`generate_answer` calls `generateContent` through `httpx.AsyncClient`. Check deployed settings before claiming a particular model name.

The requested JSON contains answer, grounded, marker/quote citations, and optional uncovered. Returned JSON is parsed and validated with `LlmAnswer`.

The route uses the first returned candidate. It does not use RRF to choose among generated answers.

### Temperature, schema, and streaming

- Temperature influences sampling variability; setting it to zero does not guarantee correctness or perfectly reproducible output.
- A response schema guides output shape. Parsing and validation are still needed because an external response is not automatically trustworthy.
- Valid JSON can contain an incorrect explanation. Format validation and factual validation differ.
- This route returns complete JSON, not token-by-token streaming.
- Storing a conversation does not automatically make its history part of the next prompt. The inspected call receives the current question and document context.

**Spoken answer:** After retrieval, we format chunks as numbered sources. Gemini generates an answer with markers and quotes. We validate the response shape and check the citations before returning it.

## 19. Grounding: what the checks prove and what they do not

### Trust the source mapping, not model-invented IDs

The model supplies a marker and a quote. `_resolve_citations` attaches filename, file ID, course ID, and page information from the selected chunk. This prevents the model from being the authority for database identifiers.

Citation `[1]` is a source marker. A file UUID identifies a resource. A chunk UUID identifies a particular processed fragment. These are different identifiers with different lifetimes.

### The implemented checks

1. `drop_unreferenced` removes citation entries not referred to by the answer when answer markers are present. It does not blindly erase every citation from uncited prose.
2. `drop_unverified` can remove a bad quote when the same marker retains another verified quote. If all quotes for a marker fail, it leaves the failure for the gate to reject.
3. `check_grounding` compares answer markers with citation markers, checks allowed source ranges, rejects repeated identical quotes under a marker, and checks that each quote appears in its mapped source.
4. Quote comparison collapses whitespace and case. It does not generally accept changed words, missing negation, or altered numbers.
5. If `uncovered` is present, it must name something and be consistent with having citations.

### A limitation you must be able to explain

Source: “Caching improves read performance but does not guarantee fresh data.”

Invented answer: “Caching always guarantees fresh data [1].”

If the citation quotes the entire actual source sentence, quote presence can pass even though the answer contradicts it. Checking that the quote exists does not establish that the answer's claim follows from it.

The current checker also does not implement a complete factual-claim detector verifying that every factual sentence has an appropriate citation. Do not turn the prompt's requirement into a claim about what the code proves.

### What happens after checking?

If the report fails, the route replaces the answer with an unverifiable-citations message and clears citations. If it passes, the route still combines citation presence with the model's grounded flag to set `grounded`. The report itself is not an answer-quality percentage.

Refusal (“the material does not cover the question”), verification failure (“citations could not be checked”), and a transport failure are different situations. The current generation exception path uses a refusal fallback; that does not prove the documents truly lack an answer.

### Why save a scope snapshot?

It records the requested scope, retrieved and used chunk IDs, and embedding model for tracing the turn. Current user-facing citations use file/page/quote metadata, while chunk IDs may change during re-indexing. Recording a snapshot helps explain what the request used; it is not a full guarantee that historical file bytes will always remain accessible after replacement.

> Our grounding checks verify source mapping, citation markers, and quoted text. They improve traceability and catch some fabricated citations, but they do not prove every claim is semantically correct. Answer evaluation is still necessary.

## 20. What your teammates built, and how your work connects

This responsibility map follows the inspected commit history. It describes code authorship evidence, not every verbal design discussion or sole authorship. Your author identities remain provisional until confirmed.

### Calvin: retrieval and embedding foundations

The history associates the original embedding service and hybrid/RRF implementation with Calvin Khoo (`5c7b5b8`, `8928473`). His work creates model vectors and selects chunks for the answer pipeline. His history also includes authentication and foundational chat UI/session work, plus later ranking-metric extensions (`94c2ae2`).

Understand his search component by reading `embeddings.py` and `vector_ops.py`. Your extraction and chunking provide its stored input; your evaluation measures its retrieval behavior; your real-API work exposes the result to users.

### Yong Zhou / SussyMouse: generation and verification foundations

The history associates prompt/context assembly, real generation, grounding checks, and retrieval-route wiring with this teammate's identities (`2259565`, `6737eb2`, `6eee72b`, `97ada92`). It also attributes the background execution body, event-loop offloading, UUID serializer, and model-loading lock to that teammate's changes.

Understand this component through `prompt.py`, `llm.py`, `grounding.py`, and `routers/rag.py`. It turns retrieved chunks into evidence for Gemini and validates parts of the returned citation structure. Your summary/context and extraction improvements extend that workflow.

### Your likely contribution: document workflows and integration

For the candidate BaoSheng identities, the evidence supports document ingestion, chunking, processing/status orchestration, resource APIs, replacement/deletion correctness, file-explorer states, real API integration, and the original chunk-size experiment. These are substantive parts of a RAG application even if you did not implement the search model or generation gate.

### Four useful interview sentences

> I mainly worked on preparing and managing the documents that the retrieval system searches.

> My teammate implemented the hybrid-search foundation. I understand the vector and keyword paths and how RRF combines their rankings.

> The generation and grounding components were also team contributions. I integrated document-summary behavior and improved the content supplied to that pipeline.

> One of my correctness changes was deactivating old ingestion runs after replacement, so my teammate's retrieval code would not read stale chunks.

You can explain a component you did not write. Keep “our system does” separate from “I implemented.”

## 21. A complete question walkthrough, including failures

### Successful request

Imagine the user asks: “Why can an index make writes slower?”

1. The frontend submits the question and scope to `/rag/query`.
2. The backend verifies identity and resolves visible file IDs. The frontend's IDs are not trusted as ownership proof.
3. The embedding model produces a query vector.
4. Vector search might find related material phrased as “index-maintenance overhead.” Keyword search might find passages using “index” and “writes.” These are hypothetical possibilities, not measured results.
5. RRF fuses the two chunk rankings. It produces an evidence list, not a finished explanation.
6. Context selection limits and labels the evidence.
7. Gemini writes an explanation and quotes under source markers.
8. Citation checks validate mapping/quotes; accepted output and a scope snapshot are saved.
9. The response gives the conversation ID, answer, citations, and grounded status. The frontend refreshes messages.

### Failure at each stage

| Stage | Possible failure | What to inspect |
|---|---|---|
| Authentication | Missing or expired token | HTTP status and auth dependency |
| Scope | No visible file or user selects another owner's ID | Ownership query and early return |
| Preparation | Empty text or dropped table | Extraction output, chunk content, run status |
| Embedding | Model load, memory, or incompatible vectors | Model settings, device, logs, run version |
| Search | Weak matches or unsuitable text normalization | Candidate lists, filters, scores, evaluation |
| Context | Relevant evidence omitted by cap | Retrieved list versus selected list |
| Generation | Timeout, missing candidate, malformed output | Transport error and validation logs |
| Grounding | Wrong marker or invented quote | Grounding report and mapped source |
| Persistence | Serialization or commit failure | Driver error, rollback, JSONB values |
| UI | Stale cache or wrong active scope | Query keys, mutation handling, active workspace state |

### Whole-document summary is a different request

Summary intent requires exactly one file and checks ownership. It reads active chunks in `chunk_index` order rather than searching for top-k passages, and removes the normal source-count cap. This avoids summarizing only a few retrieved paragraphs, but a long document can still exceed model context or practical cost limits.

The frontend classifier uses rules/regex; do not call it a trained intent model. A future hierarchical summary could summarize sections first, then combine those summaries, with source verification retained.

### Fake mode is not real model inference

`LLM_FAKE_MODE` defaults to true in the inspected settings, although the actual environment can override it. Fake mode uses deterministic source quoting instead of calling Gemini. Ordinary questions can also use placeholder sources when retrieval is empty in fake mode.

This supports UI development and exercises parts of the downstream format/checking path. It does not demonstrate real retrieval success, model quality, or production end-to-end behavior. Verify configuration before describing a demo as a live AI result.

## 22. Evaluation: formulas and claims you can defend

### Hit@k

For each question, ask whether at least one relevant chunk appears in its first k retrieved results.

```formula
Hit@k = questions with at least one relevant top-k result / total questions
```

Example: 16 hits among 20 questions gives 0.8, or 80%. This is a retrieval metric, not answer accuracy.

### Recall@k

Recall measures how many labeled relevant items were retrieved.

```formula
Recall@k for a question = relevant chunks in top-k / all relevant chunks
```

If two of four relevant chunks appear in the top five, recall is 2/4 = 0.5 but Hit@5 is 1. Specify averaging and handling of empty relevant sets.

The current evaluation script labels a fraction of rank-1 successes `recall_at_1`. Be precise: that implementation counts questions whose first result is relevant; it is a top-1 success rate and is not general per-chunk recall when multiple relevant chunks exist.

### Mean Reciprocal Rank

MRR uses the rank of the first relevant result.

```formula
MRR@k = sum of reciprocal first-relevant ranks within k / total questions
No relevant result within k contributes 0.
```

Ranks `[1, 2, missing]` yield `(1 + 1/2 + 0)/3 = 0.5`. MRR rewards earlier hits. MRR evaluates retrieval; RRF combines rankings. They have different jobs.

### Your recorded chunk-size experiment

The original corpus has 20 pages and 20 questions. Both 350-token and 500-token configurations recorded Hit@5 of 20/20. They produced 34 and 20 chunks respectively. The relevance rule required an expected page and an approved evidence phrase.

The result means both met that criterion on that small corpus. It does not establish 100% answer accuracy, superior production performance, or lower cost. A ceiling effect means an easy metric may fail to distinguish configurations.

You authored the candidate original experiment commit `6041da4`; Calvin authored later ranking-metric additions `94c2ae2`. Explain the collaboration accurately.

### A stronger next experiment

Use varied documents, difficult and unanswerable questions, and clear relevance labels. Compare vector-only, keyword-only, and hybrid retrieval. Measure ranking, answers, citations, latency, and memory separately.

> I would evaluate retrieval and generation separately. Hit@5 tells me whether useful evidence appears in the first five results. It does not tell me whether the generated answer is correct or whether its claims are supported.

## 23. Connect technical understanding to intern interview questions

### You are applying as a developer, not claiming to be a model researcher

Show that you can trace requests, understand data, reason about failure, and learn unfamiliar components. The required depth varies by internship; a general software role and a research-focused AI role may emphasize different skills.

### If asked: did you build the AI part?

> I did not implement every AI component. My main work was document ingestion and resource workflows. I also contributed summary integration and retrieval evaluation. I understand how our embedding, hybrid-search, and generation components connect, and I can explain the complete pipeline.

### If asked: why use PostgreSQL with pgvector?

> It lets us manage relational data and document vectors in the same database. That makes it easier to connect retrieval with course ownership, ingestion versions, and transactions. We would still need to evaluate a different architecture for much larger workloads.

### If asked: where do transactions matter?

> They matter when updating related database records, such as file metadata and active ingestion-run state. However, a database transaction does not automatically make a file write or an external model call atomic. We need explicit recovery or compensation for those boundaries.

### If asked: why async and to_thread?

> Async lets the server yield while waiting for I/O. A synchronous parser or model call can still block the event loop, so we move that blocking work to a thread. That helps responsiveness, but it does not guarantee higher CPU throughput or durable task execution.

### If asked: where is OOP used?

> Our API client encapsulates request handling behind methods. Our database models and custom exceptions use inheritance. A future storage interface could allow different storage implementations through the same contract. I would distinguish an existing implementation from a design improvement we have not built yet.

### If asked: what would you improve?

Pick one concern and a verification plan rather than listing every architecture buzzword.

> I would strengthen the retrieval evaluation with harder and more varied questions. I would first establish baseline vector, keyword, and hybrid results, then compare ranking quality and answer evidence. That would tell us whether a reranker or different chunking policy is justified.

## 24. Practical learning exercises and answer keys

These exercises can be done without uploading private documents or calling the model. Practical code-running steps are optional; this guide did not execute live model inference or a new benchmark.

### Exercise 1: explain the two models

Question: Which component converts text into a vector, and which produces an answer?

Answer: the local embedding model converts document/query text into vectors; Gemini generates answer text from the supplied question and context. pgvector stores/searches vectors and is not either model.

### Exercise 2: calculate RRF

Question: Vector rank is 3, keyword rank is absent, both weights are 1, and `rrf_k` is 60. What is the score?

Answer: `1/(60+3) = 1/63 = 0.015873` approximately. The absent list contributes zero. This is a chunk-ranking value, not correctness probability.

### Exercise 3: distinguish the limits

Question: Both search lists allow 50 candidates, `request.top_k` is 5, and the normal context cap is 8. Does Gemini receive 100 sources?

Answer: no. The candidate union is fused and limited to at most five results, so at most five sources reach the ordinary prompt. For top_k 20, normal context selection caps at eight.

### Exercise 4: predict stale retrieval

Question: A PDF is replaced, but its old active run remains active. What could happen?

Answer: retrieval can select old chunks even while the reader opens the new file. Deactivation prevents that path while new indexing is pending. Byte replacement and database updates still have a cross-resource failure boundary.

### Exercise 5: challenge the grounding guarantee

Question: A quote exists in a source. Does this prove the answer's claim follows from it?

Answer: no. Quote membership checks the quoted text and source mapping, not semantic entailment of every claim.

### Exercise 6: inspect your actual code

Read `SearchConfig` and the two loops in `hybrid_search`. Find rank starting at 1, the two weights, dictionary accumulation, threshold normalization, and the returned raw score. Explain each in one sentence without looking at this guide.

Optional Python arithmetic to run locally:

```python
vector = ["A", "B", "C"]
keyword = ["B", "C", "D"]
scores = {}
for ranking in [vector, keyword]:
    for rank, chunk in enumerate(ranking, start=1):
        scores[chunk] = scores.get(chunk, 0) + 1 / (60 + rank)
print(sorted(scores.items(), key=lambda item: item[1], reverse=True))
```

Expected order: B, C, A, D. This demonstrates the formula; it does not test the real database or model.

### Exercise 7: practise ownership wording

Complete this sentence truthfully: “My teammate implemented ____. My contribution was ____, which connects to it by ____.”

Possible answer for the provisional BaoSheng author identity: “My teammate implemented hybrid search. My contribution was document chunking and stale-run invalidation, which determine what content the search can safely retrieve.”

## 25. A manageable study plan and a final terminology check

### Three short sessions before a full mock interview

Session 1, about 30 minutes: read sections 12-14. Explain chunk, token, embedding, and pgvector aloud. You are ready when you can distinguish model output from storage and search.

Session 2, about 30 minutes: read sections 15-17. Calculate one RRF example and distinguish `rrf_k` from `top_k`. You are ready when you can say what is ranked and why raw scores are not simply added.

Session 3, about 30 minutes: read sections 18-21. Explain prompt, generation, citation mapping, and grounding limits. You are ready when you can describe both a successful answer and a failure without claiming a guarantee the code does not provide.

Then practise the contribution stories and common intern questions. You do not need to memorize 25 sections at once. Start with the request flow and three stories you can defend.

### Common mix-ups to eliminate

| Term | What it means here | What it does not mean |
|---|---|---|
| Embedding | Model-produced numeric representation | Generated answer or readable text summary |
| pgvector | PostgreSQL vector storage/search extension | A language model |
| tsvector | PostgreSQL lexical text-search representation | The neural document embedding |
| Hybrid search | Vector plus keyword retrieval | Combining two generated answers |
| RRF | Combining chunk rankings | An answer-correctness formula |
| Reranker | A possible additional candidate-ordering stage | A component proven implemented by a source comment |
| top-k | Number of highest-ranked results retained | RRF smoothing constant |
| Grounded | Application output/check status with limited guarantees | Proof every factual claim is true |
| Hit@5 | At least one relevant chunk among five | Overall answer accuracy |
| Inference | Running a trained model | Training a new foundation model |
| BackgroundTasks | In-process work after a response | A durable queue with restart recovery |
| Conversation history | Stored messages | Proof all previous turns enter the model prompt |

### Confidence based on understanding

Not knowing this material yet is a learning gap, not evidence that your career is over. The useful next step is small: understand one stage, explain it in simple English, and practise one follow-up. Your document and API work gives you concrete entry points into the AI pipeline.

When you are unsure in an interview:

> That component was implemented by my teammate. My understanding is that it **[simple explanation]**. I would check **[specific code or test]** before claiming **[uncertain behavior]**.

This is stronger than guessing confidently. The goal is accurate explanations and clear reasoning, not pretending to know everything.
