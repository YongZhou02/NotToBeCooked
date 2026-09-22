# NotToBeCooked (NTBC)

A study assistant that answers questions about **your own course material** and shows you
the passage it got each answer from. Upload lecture slides, notes and past papers; ask a
question; get an answer with citations you can click back to the source.

Built by a three-person university project team, July 2026 – December 2026.

> **Status: in development.** Auth, upload, ingestion, retrieval and answering work
> end-to-end against the API. The file-browser UI is still rendering fixture data rather
> than calling the file endpoints — that wiring is tracked as Gantt row r81. See
> [Where the project actually is](#-where-the-project-actually-is).

## 🧠 What it does, and the part that was hard

Answering a question from a document is the easy half. The hard half is **not answering
when the documents do not say.**

```
question ──▶ scope ──▶ embed ──▶ hybrid search ──▶ LLM ──▶ grounding gate ──▶ answer
                 │                     │                         │
      only files the caller     vector + full-text,      every citation checked
      owns; never "all"         fused with weighted      against the chunks that
                                RRF                      were actually retrieved
```

* **Scope is resolved before retrieval, never inside it.** `hybrid_search` filters on the
  file ids it is handed and on nothing else — it has no idea who is asking. Handing it an
  empty list means *no filter*, i.e. every chunk in the database. So the caller resolves
  the scope from the requesting user's own courses in every branch and returns early
  rather than passing an empty list down.
* **The grounding gate can reject the model's answer.** An answer whose citations do not
  support it, or which cites a chunk that was never retrieved, is replaced with a refusal.
  The model may also declare which part of the question the sources did *not* cover, and
  that declaration is itself checked.
* **Ingestion runs are versioned.** Re-indexing a file produces a new `INGESTION_RUN` and
  retires the previous one inside a single statement, guarded by a partial unique index —
  so retrieval never sees two generations of the same file at once.

## 🏗️ Architecture

```
                        ┌───────────────────────────────┐
                        │   packages/ui (@workspace/ui) │
                        │  Single Source of Truth (UI)  │
                        │  - shadcn/ui (Base UI / Vega) │
                        │  - Shared Views & Components  │
                        │  - Tailwind v4 (globals.css)  │
                        └──────────────┬────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
┌───────▼───────────────┐      ┌───────▼───────────────┐      ┌───────▼───────────────┐
│       apps/web        │      │     apps/desktop      │      │       apps/api        │
│   (Vite Web Client)   │      │  (Tauri v2 App Core)  │      │ (Python FastAPI + uv) │
└───────────────────────┘      └───────┬───────────────┘      └───────────────────────┘
                                       │
                     ┌─────────────────┴─────────────────┐
                     │                                   │
         ┌───────────▼───────────┐           ┌───────────▼───────────┐
         │     Desktop Target    │           │     Android Target    │
         │ (Linux/macOS/Windows) │           │   (Tablets & Mobile)  │
         └───────────────────────┘           └───────────────────────┘
```

* **`packages/ui`** — design system, shadcn components, Tailwind styles and shared views.
  One source of truth; the apps are thin shells around it.
* **`packages/contracts`** — the OpenAPI document and the types generated from it, plus
  the typed API client. **Checked, not trusted:** `pnpm verify` regenerates the document
  from the running app and fails the build if the committed copy has drifted.
* **`apps/web`** — Vite + React 19 web client.
* **`apps/desktop`** — Tauri v2, compiled to native desktop binaries or an Android
  `.apk`/`.aab`.
* **`apps/api`** — FastAPI, SQLModel, asyncpg, Alembic, managed with `uv`.

**Data:** PostgreSQL 16 with `pgvector`. Nine entities — `USER`, `COURSE`, `FOLDER`,
`MILESTONE`, `FILE`, `INGESTION_RUN`, `CHUNK`, `CONVERSATION`, `MESSAGE`. The diagram of
record is [`docs/erd/erd.mmd`](docs/erd/erd.mmd), and it is checked against the models on
every build (see `pnpm erd:check`).

**Models:** `jinaai/jina-embeddings-v5-text-small` (1024-dim) for embeddings, run locally;
Gemini for generation. Document parsing is Docling.

## 🚀 Quick start

### 1. Prerequisites

* [Node.js](https://nodejs.org/) >= 20 and [pnpm](https://pnpm.io/) >= 10.33
* [Python](https://www.python.org/) >= 3.11 and [uv](https://docs.astral.sh/uv/)
* Docker (for the PostgreSQL + pgvector container)
* [Rust toolchain](https://www.rust-lang.org/tools/install) — only for Tauri desktop or
  Android builds
* [Android Studio & SDK](https://developer.android.com/studio) — only for Android builds

### 2. Setup

```bash
pnpm install                       # frontend monorepo
cd apps/api && uv sync && cd ../..  # python environment
docker compose -f apps/api/docker-compose.yml up -d db   # postgres + pgvector
cd apps/api && uv run alembic upgrade head && cd ../..    # schema
```

Copy `apps/api/.env.example` to `apps/api/.env` and fill it in. **`.env` is gitignored and
must stay that way** — `alembic.ini`'s `sqlalchemy.url` is deliberately left empty for the
same reason: that file is committed, and a real URL carries the database password.

**VS Code / Pyright:** select `./apps/api/.venv/bin/python` as your interpreter. The root
`.vscode/settings.json` and `apps/api/pyrightconfig.json` are already configured for you.

## 💻 Commands

Run from the repository root.

| Command | Description |
| :--- | :--- |
| `pnpm dev` | Web, Desktop and API concurrently |
| `pnpm dev:web` | Web client (`localhost:5173`) |
| `pnpm dev:api` | FastAPI backend (`localhost:8000`, docs at `/docs`) |
| `pnpm dev:desktop` | Tauri desktop app (`localhost:1420`) |
| `pnpm dev:android` | Android tablet emulator or device |
| `pnpm verify` | **The gate.** Typecheck, lint, build and test every package, then `contracts:check` and `erd:check` |
| `pnpm schema:update` | Regenerate `openapi.json` and the generated client types |

`pnpm verify` is what CI runs, with nothing added — if it passes on your machine it passes
there. Two of its steps are worth knowing about:

* **`contracts:check`** regenerates the OpenAPI document from the app and compares it to
  the committed `packages/contracts/openapi.json`. It exists because that file went stale
  for several hours in September while the build stayed green, leaving the frontend typed
  against a backend that no longer existed. Fix with `pnpm schema:update`.
* **`erd:check`** compares `app/schemas/*.py` against `docs/erd/erd.mmd` and fails if the
  committed comparison is out of date. Fix with
  `cd apps/api && uv run python scripts/erd_diff.py --write`.

## ⚠️ Gotchas

### `shadcn` component management

* ❌ Do not capitalise component names (`shadcn add Card`) — the registry returns 404.
* ❌ Do not run it from the root without a target.
* ✅ Lowercase, and target `packages/ui`:
  ```bash
  pnpm dlx shadcn@latest add card --cwd packages/ui
  ```

### Python packages with `uv`

* ❌ `uv install` is not a subcommand. ❌ No global `pip install` inside `apps/api`.
* ✅ `uv sync` · `uv add <pkg>` · `uv add --dev <pkg>` · `uv run python <script.py>`

### `opencv-python` breaks Docling

If `POST /files/{file_id}/ingest` returns 500 with `module 'cv2' has no attribute
'setNumThreads'` or `libgthread-2.0.so.0: cannot open shared object file`, the GUI build of
opencv has been pulled in behind you. The fix, the cause and a check for it are in
[`apps/api/DEVELOPMENT.md`](apps/api/DEVELOPMENT.md) §6. **Redo it after every `uv sync`.**

### Red squigglies under `from fastapi import FastAPI`

Your IDE is pointing at the global interpreter. Select `apps/api/.venv/bin/python`.

## 📦 Deployment

The backend runs on an **Oracle Cloud Always Free ARM instance** (Ampere A1, 2 OCPU /
12 GB), not on a container platform, and the reasons are written down because they are not
obvious:

* **The API is a systemd _user_ unit, not a system unit.** SELinux is Enforcing on Oracle
  Linux and denies `init_t` so much as reading `.venv/bin/python` under `/home`. A system
  unit fails with `203/EXEC` before it starts. Relabelling would work and would be undone
  by the next `uv sync`.
* **`loginctl enable-linger` is required**, or logging out tears down the user systemd
  instance — API and database container together, with no error, because nothing failed.
* **PostgreSQL binds `127.0.0.1`, never `0.0.0.0`.** The box has a public IP, and container
  runtimes insert their own iptables rules that can bypass firewalld's zones, so a running
  firewall is not the guarantee it looks like.
* **Rootless podman on the box, Docker on developer machines.** The three differences that
  actually cost someone time are in [`apps/api/DEVELOPMENT.md`](apps/api/DEVELOPMENT.md) §9.

Measured on that hardware, 10 September 2026: a 331-second ingest with 329 concurrent
`/health` samples, worst latency **0.19 s**, zero non-200 responses, zero blocked polls —
after moving the CPU-bound ingest and query embedding off the event loop.

## 📚 Documentation

| Where | What |
| :--- | :--- |
| [`apps/api/DEVELOPMENT.md`](apps/api/DEVELOPMENT.md) | Backend architecture, how to add an endpoint, auth, error shapes, deployment differences |
| [`docs/erd/erd.mmd`](docs/erd/erd.mmd) · [`erd.png`](docs/erd/erd.png) | The schema of record |
| [`docs/erd/KNOWN_ISSUES.md`](docs/erd/KNOWN_ISSUES.md) | Every design defect found, with the measurement behind it, what was decided, and what would reopen it |
| [`docs/erd/CODE_VS_ERD.md`](docs/erd/CODE_VS_ERD.md) | Generated comparison of the models against the diagram |

`KNOWN_ISSUES.md` is the one worth reading if you only read one. It is published rather
than kept privately so that the diagram and the team's understanding of it stay the same
document — including the findings that were **declined**, with the condition that would
reopen each.

## 📍 Where the project actually is

Being specific here rather than implying everything works:

* **Works end-to-end:** register and log in, ask a question and get an answer with
  citations checked against the retrieved chunks and refused when they do not support
  it, with conversations kept across sessions. Creating courses and folders, uploading
  and ingesting files work against the API but have no UI yet.
* **Not wired yet:** the file-browser and upload UI are built and mounted but render
  fixture data. The API client covers auth, `/rag/query`, the chat sessions and
  a file's content — nineteen endpoints, all of the file, folder and course
  management, still have no client method.
* **Not started:** the roadmap/milestone feature, and public exposure of the deployment
  (TLS, firewall) — both scheduled for later phases.

## 🧑‍🤝‍🧑 Team

Three members, one shared `dev` branch, feature branches into `dev`, and `dev` into `main`
once per weekly meeting. Decisions are recorded rather than remembered — the meeting
agenda states the options, the recommendation, and what happens if no decision is reached.

## 📄 Licence

MIT — see [`LICENSE`](LICENSE). Copyright is held jointly by the three members
named there; chosen at the meeting of 22 September 2026, with all three agreeing.
Relicensing a future version would need the same three again.
