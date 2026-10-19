# NTBC presentation speaker scripts

Replace the formal-photo frame with your actual portrait and fill in your programme/university before presenting. Slides 1–12 form the main presentation. Slides 13–17 support deeper technical questions.

## Slide 1: Self introduction

Keywords: Ch’ng Bao Sheng, Student developer, Document workflows and frontend/backend integration, [Programme and university], NTBC technical project presentation

Hi, I’m Bao Sheng. I’m a student interested in building software across the frontend and backend. In NTBC, I worked mainly on document processing, file APIs, and connecting the file browser to real backend data. Today I’ll explain the project and then focus on my contributions. Replace the education placeholder with your actual details.

## Slide 2: NTBC project overview

Keywords: Study assistant for course materials, Lecture notes and slides, Questions and source citations, Three-person team

NTBC helps students ask questions about their own course materials. Students upload notes or slides, ask a question, and receive an answer with citations linking back to the source. Our aim is to make relevant material easier to find. We do not claim that citations guarantee every answer is correct.

## Slide 3: Technology stack

Keywords: React and TypeScript, FastAPI and Python, PostgreSQL with pgvector, Docling, local Jina embeddings, Gemini, Shared UI and Tauri desktop shell

Our frontend uses React and TypeScript. The API uses Python and FastAPI, which fits our document and model libraries. PostgreSQL stores application records and vectors through pgvector. Docling parses documents. A local embedding model supports retrieval, and Gemini generates answers. The web and Tauri desktop shells share UI components.

## Slide 4: System architecture

Keywords: Presentation: shared React UI, Application: FastAPI routes and services, Data: PostgreSQL and local file storage, External generation: Gemini

The presentation layer collects user actions and displays results. The application layer validates requests and runs processing. The database and file storage keep our records and original documents. Gemini is an external service rather than our database. This is a modular application in a monorepo, not a microservice architecture.

## Slide 5: RAG workflows

Keywords: Retrieval-Augmented Generation, Ingestion: parse, chunk, embed, store, Answering: authorize, retrieve, generate, verify, Searchable documents without retraining the LLM

RAG means retrieving source content before generating an answer. There are two workflows. Ingestion prepares documents for search. Answering retrieves relevant passages for the current question and passes them to Gemini. We can process new documents without retraining the language model.

## Slide 6: My contribution

Keywords: Document ingestion and chunking, Course, folder and file APIs, File replacement consistency, Real API integration in the file browser

My main contributions were document ingestion and chunking, resource APIs, and frontend integration. I prepared document content for retrieval and connected user actions to backend operations. My deepest hands-on experience is in these workflows. Other teammates implemented important parts of authentication, retrieval, generation, and grounding.

## Slide 7: Document extraction

Keywords: Docling document items, Body text, headings and page metadata, Tables as Markdown, Bullet preservation, PDF OCR currently disabled

I worked with Docling to extract useful content and preserve source information. I handled text, tables, and bullet-like items so useful evidence would not disappear before retrieval. Page information helps link chunks back to a document. Our current PDF configuration disables OCR, so image-only documents may have no extractable text. Source: apps/api/app/services/ingestion.py.

## Slide 8: Token-aware chunking

Keywords: Embedding model tokenizer, Token count instead of word count, Original-string token offsets, Headings and page provenance, Current 350-token target

The model reads tokens, so I used its tokenizer rather than word counts. For long text, token offsets identify where to cut the original string. This helps preserve the original text. Chunks carry headings and page information. The newest page-boundary rule and headings-in-content change were teammate improvements. The 350-token value is a target, not a proven strict bound for every final chunk. Source: apps/api/app/services/ingestion.py.

## Slide 9: Upload and indexing flow

Keywords: POST /files: store bytes and metadata, Ownership check, POST /files/{id}/ingest: 202 Accepted, Queued, processing, ready, failed, Background task and status polling

Upload and indexing are separate. POST /files stores the original file and metadata after checking ownership. The UI then asks for ingestion. The API records a queued run and returns 202. Background processing parses, chunks, embeds, and stores content. The UI polls for status. I contributed processing and status APIs, while teammates implemented important background execution details. BackgroundTasks is in-process, not a durable queue.

## Slide 10: Resource APIs and ownership

Keywords: Course and folder management, Read, rename, move, delete, replace, JWT identity and resource ownership, Database commit, Cross-course move restriction

I worked on course, folder, and file APIs. A valid login token identifies the caller, but the backend must separately check ownership of each resource. I contributed these checks in resource workflows. File moves currently stay within the course. Changes commit to the database before the UI refreshes. Authentication foundations were teammate work.

## Slide 11: File replacement correctness

Keywords: Problem: new file with old searchable chunks, PUT /files/{id}/content, Deactivate old ingestion runs, Reset indexing state, Re-index replacement content

One correctness issue I addressed was stale retrieval after replacement. Replacing bytes does not automatically replace old embeddings. I deactivated the previously active ingestion runs and reset the file’s indexing state. Search filters active runs, so old chunks are excluded until the replacement is indexed. The tradeoff is temporary unavailability in search. Filesystem changes and database commits are not one atomic transaction. Evidence: commits 02e8647 and 9878edd.

## Slide 12: Frontend integration

Keywords: TanStack Query, Query hooks and mutation hooks, Cache invalidation, Three-second polling while pending, Loading, error and processing states

I helped replace fixture-based explorer data with real API data. Query hooks fetch server records, and mutation hooks perform writes such as upload, rename, and delete. After success, cache invalidation triggers fresh data. While files are uploaded or processing, the file list polls every three seconds. Zustand handles local workspace state, while Query handles server data. Source: useExplorerData.ts and useExplorerMutations.ts.

## Slide 13: Question and answer flow

Keywords: POST /rag/query, Owned-file scope, Query embedding, Vector search and keyword search, RRF, Gemini and citation checks

When Send is clicked, the frontend sends the question and scope to the API. The backend resolves files the caller can access, embeds the question, and combines vector and keyword search using RRF. Selected passages go to Gemini. The backend checks citation markers and quotes, saves messages, and returns JSON. I understand this flow through integration, but teammates wrote important search and generation foundations.

## Slide 14: Team components I can explain

Keywords: JWT: signed login token, Embedding: vector representation of text, Vector search: related meaning, Keyword search: specific terms, RRF: combines ranked results, Grounding: source and quote checks

My teammates built important parts of these components. I can explain their concepts and how they connect to my work, but I did not implement all their internals. Vector search helps when wording differs, keyword search captures specific terms, and RRF combines ranking positions. Citation checks verify traceability and consistency rather than proving every claim true.

## Slide 15: Engineering tradeoffs

Keywords: RAG: changing documents and source references, pgvector: relational data and vectors together, Polling: simple status updates, Local embeddings: CPU and memory cost, Model change: regenerate compatible embeddings

RAG fits frequently changing course documents. pgvector lets us keep resource filters and vectors in PostgreSQL. Polling was simple for our scope but creates more traffic as usage grows. Local embeddings need CPU and memory. If we switch embedding models, we regenerate document embeddings and use the matching model for questions. These are team choices, not all decisions I made alone.

## Slide 16: Retrieval evaluation

Keywords: My controlled 350 vs 500 token experiment, One 20-page PDF and 20 questions, 34 chunks vs 20 chunks, Both Hit@5: 20/20, Small benchmark, ceiling effect

I built a controlled comparison of 350-token and 500-token chunks. Both achieved Hit@5 of 20 out of 20 in the historical small corpus. Hit@5 means at least one relevant result appeared in the top five. It is not 100 percent answer accuracy. The result could not establish a universal winner, and the newest chunker needs evaluation again. Calvin later extended ranking metrics. Source: apps/api/evaluation/chunk_retrieval_results.md.

## Slide 17: Lessons and next improvements

Keywords: Data quality affects AI answers, File, index and UI consistency, Citation checks have limits, Future: durable jobs and version-safe replacement, Wider evaluation and concurrency testing

I learned that building an AI application requires more than calling a model. Useful source data, correct access checks, and consistent file workflows matter. Future improvements include durable ingestion jobs, version checks for replacement races, and broader evaluation. These are proposed improvements rather than completed features. I am happy to discuss the document workflow in more detail.
