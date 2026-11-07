# Ch'ng Bao Sheng — NTBC contribution, decisions, and measurable impact

Compiled: 2026-11-07. Working branch: `baosheng-feat-evaluation-harness`.

Purpose: preserve resume-ready evidence, interview stories, technical contributions,
and the decisions Bao Sheng drove in the available conversation. This is a living
evidence ledger, not a claim that every proposal was implemented or independently
authored. Conversation references below quote or paraphrase the supplied chat;
they are not external transcripts with permanent message links. Relative links
point to repository evidence. Local run artifacts are ignored by Git and must be
archived separately if they need to accompany an application.

## 1. Attribution and confidence

- **User-directed, AI-assisted implementation:** Bao Sheng selected priorities,
  described constraints, challenged assumptions, requested changes, and asked for
  validation. The coding assistant wrote substantial code, generated the 50-question
  dataset and first-pass answer reviews, and executed the recorded experiments.
  Do not describe all of that as independently hand-written or independently labelled.
- **Earlier personal contributions:** Bao Sheng described ingestion, file/folder/course
  APIs, chunk-size evaluation, frontend integration, and the stale-ingestion fix as
  personal work. The existing [contribution playbook](../contribution-interview-playbook.en.md)
  provides historical commit references; this document does not repeat its entire
  author-history audit or newly verify every old claim.
- **Team boundaries:** Bao Sheng explicitly identified embedding, retrieval,
  grounding checks, and deployment as areas his teammate worked on. Comparing or
  integrating those components does not make him their original author.
- **No inflated outcomes:** feature counts, test counts, and corpus size describe
  delivered scope or verification, not users served, revenue, saved hours, or
  production reliability. No such business-impact measurement exists here.
- **Current status:** the latest harness, review compiler, and code-block filtering
  changes are local working-tree work at compilation time, not established merged
  production releases. Earlier follow-up commits are listed in section 7.

## 2. Best resume claims, with proof and limits

### A. Strongest measured improvement: extraction evidence retention

Suggested bullet:

> Directed an AI-assisted RAG ingestion investigation and targeted Docling filtering
> fix, increasing retained evidence from 70/73 (95.9%) to 71/73 (97.3%) on a
> 38-page text-transcribed course PDF, with regression checks for code-block formatting.

Measurement:

- Before: 70 of 73 labelled evidence groups survive extraction and remain intact in chunks.
- After: 71 of 73 survive both stages; the page-4 translator evidence is recovered.
- Absolute gain: **1 group / 73 = 1.37 percentage points**, rounded 1.4 pp.
- Missing groups: 3 → 2, a **33.3% reduction in this small observed miss count**.
  Prefer the 70/73 → 71/73 wording; “33% reduction” without the tiny denominator misleads.
- Root cause: Docling classified useful text as `code`, but NTBC's allow-list skipped it.
  The fix keeps `code` items and respects code boundaries during chunking.
- The two remaining misses originate on page 21 in a picture-labelled region without
  extracted text. This filtering change does not recover them.
- **Not measured:** improved downstream retrieval or generated answers after this fix;
  the after-fix run was extraction-only. It also does not establish original-image OCR accuracy.

Evidence:

- [Before checks](../../evaluation/runs/20261107T113258086748Z/checks.json)
- [Raw diagnostic parse](../../evaluation/runs/20261107T113635350705Z/docling_structure_topic1.json)
- [After checks](../../evaluation/runs/20261107T115210823381Z/checks.json)
- [Ingestion implementation](../../apps/api/app/services/ingestion.py)
- [Processing regression tests](../../apps/api/tests/test_processing.py)
- [Chunking regression tests](../../apps/api/tests/test_chunking.py)

### B. Evaluation ownership and experimental design

Suggested bullet:

> Defined and directed an AI-assisted, stage-by-stage RAG evaluation harness covering
> extraction, chunking, PostgreSQL/pgvector persistence, three retrieval methods,
> and answer review across 50 questions and 73 evidence groups.

Scope actually produced:

| Item | Recorded scope | Interpretation |
|---|---:|---|
| Corpus | 1 PDF, 38 pages | User-supplied text-transcribed Topic 1, not multiple original-image PDFs |
| Questions | 50 | Assistant-authored; owner review pending |
| Evidence groups | 73 | Alternatives within a group are OR; required groups are AND |
| Splits | 15 dev / 35 provisional test | Related questions across splits; not an independently sealed benchmark |
| Retrieval variants | 3 | Vector-only, PostgreSQL full-text keyword, hybrid + RRF |
| Retrieval records | 150 | 50 questions × 3 methods, not 150 independent questions |
| Timing repetitions | 3 per query/method | Repetitions measure timing variability, not extra quality samples |
| Generated answers | 15 | Hybrid only; 3 per category across 5 categories |
| Answer-review dimensions | 4 | Faithfulness, correctness, completeness, citation support |

The scope includes actual storage consistency checks and rollback of temporary
database fixtures. It does not test the entire deployed application: HTTP/auth,
UI, conversation memory, file replacement, and original-image understanding are outside this run.

Evidence: [methodology](../../evaluation/README.md),
[runner](../../apps/api/scripts/evaluate_pipeline.py),
[golden questions](../../evaluation/golden/questions.json),
[evidence key](../../evaluation/golden/evidence_key.json),
[answer key](../../evaluation/golden/answer_key.json),
[recorded run configuration](../../evaluation/runs/20261107T113258086748Z/config.json).

### C. Traceable, human-auditable evaluation

Suggested bullet:

> Specified an offline evidence-review workflow consolidating 50 questions,
> source passages, extraction/chunk traces, 150 retrieval records, and 15 generated
> answers into one HTML report with visible metric calculations and separate owner ratings.

The compiler checks golden-file hashes and recomputes every saved retrieval metric,
failing on disagreement. All 150 records agreed with recomputation in the local
verification. This proves implementation consistency, **not** correctness of every
gold label or semantic judgement. Owner ratings remain separate and can be exported
as JSON. This work removes the need to navigate scattered artifacts manually;
time saved has not been measured.

Verification at delivery: 9 tests passed across the compiler and metric suites;
browser checks confirmed report loading, question switching, and review controls.
The test count is a snapshot, not a coverage percentage or a production-quality guarantee.

Evidence: [compiler](../../apps/api/scripts/compile_evaluation_review.py),
[report template](../../apps/api/app/evaluation/review_template.html),
[compiler tests](../../apps/api/tests/test_evaluation_review.py),
[metric tests](../../apps/api/tests/test_pipeline_evaluation.py),
[local compiled report](../../evaluation/runs/20261107T113258086748Z/review.html).

### D. Retrieval trade-off — an analysis result, not an implemented retrieval invention

On the **35-question provisional test split**, the baseline produced:

| Method | Hit@1 | Hit@5 | Evidence recall@5 | Complete evidence@5 | MRR@5 | Median DB retrieval |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.829 | 0.971 | 0.948 | 0.914 | 0.887 | 4.4 ms |
| PostgreSQL keyword | 0.829 | 0.971 | 0.962 | 0.943 | 0.880 | 4.1 ms |
| Hybrid + RRF | 0.886 | 0.971 | 0.962 | 0.943 | 0.920 | 18.7 ms |

Interview-safe interpretation: hybrid ranked a relevant passage first on 31/35
questions versus vector's 29/35, but all methods hit some evidence in 34/35 top-five
results. Hybrid's evidence recall tied keyword's and cost more DB retrieval time.
These observations do not establish statistical significance, universal superiority,
or user-visible latency; embedding/generation/HTTP/UI time is excluded.

Possible wording if space permits:

> Compared vector, keyword, and hybrid retrieval on a controlled pilot; identified
> higher hybrid first-hit accuracy alongside equal top-five hit rate and increased
> database latency, rather than assuming a more complex retriever was always better.

Evidence: [baseline findings](../../evaluation/baselines/topic1-pilot-2026-11-07.md),
[summary CSV](../../evaluation/runs/20261107T113258086748Z/summary.csv),
[per-question traces](../../evaluation/runs/20261107T113258086748Z/retrieval.jsonl).

## 3. Decision ledger — what Bao Sheng proposed, challenged, or required

The numbering below is this document's conversation index, not a fabricated chat ID.
“Delivered” means artifacts exist locally unless a commit is explicitly given.

| ID | User direction in the available conversation | Skill demonstrated | Result/status and attribution |
|---|---|---|---|
| C01 | Asked for a Seagate-focused story and lessons from the ViTrox interview | Career reflection; audience awareness | Motivated the work; JD and ViTrox details are not independently verified here |
| C02 | Explained ingestion, APIs, evaluation, stale-file bug, and teammate responsibilities | Technical communication; ownership boundaries | Self-reported contribution narrative, supported in part by historical playbook |
| C03 | Said “这个我解释不到” about frontend-to-API integration | Intellectual honesty; identifying knowledge gaps | Do not use that claim in an interview until able to explain an actual request/mutation flow |
| C04 | Asked which owned functions could attract follow-up questions | Preparation; risk identification | Focused discussion on defendable technical decisions rather than feature names |
| C05 | Asked to discuss new NTBC features with substantial AI relevance | Initiative; product thinking | Exploration request, not proof of delivered features |
| C06 | Asked how feedback should work and then requested implementation | Requirements refinement; user-feedback thinking | Feedback work appears in commit `af7e413`; no measured answer-quality improvement from collecting feedback |
| C07 | Challenged grounded-answer proposal as overlapping Yong Zhou's work | Collaboration; scope/attribution awareness | Avoided framing a teammate's existing work as a new personal contribution |
| C08 | Requested broad research and one best recommendation | Prioritisation; information seeking | Research was requested; this ledger does not claim an exhaustive web search was completed |
| C09 | Brought a friend's evaluation-harness advice and asked if it was worthwhile | Openness to feedback; evidence-based thinking | Harness concept was externally suggested, then adopted and refined by Bao Sheng |
| C10 | Asked for deeper evaluation after a previous ceiling effect | Experimental critique | Broadened evaluation beyond any-evidence Hit@5; goal is diagnostic discrimination, not manufacturing a winner |
| C11 | Questioned whether the current setup understands images and diagram relationships | Assumption checking; AI limitations awareness | Text-only/transcribed corpus scope documented; no unsupported vision capability claim |
| C12 | Asked whether testing across three files means one contains the answer | Clarification; retrieval-scope reasoning | Multi-file distractor experiment discussed; current recorded pilot is one file only |
| C13 | Requested chart extraction enablement | Ingestion feature initiative | Chart extraction follow-up commit `f49e3f9`; current benchmark explicitly disables it |
| C14 | Said “plan with me first” before creating the harness | Collaborative planning | Requirements discussed before experimental execution; do not equate this with sole architecture authorship |
| C15 | Supplied/described a text-transcribed PDF retaining diagram/chart relationships and page structure | Corpus preparation; controlled-input design | 38-page input used; transcription fidelity against original diagrams not independently measured |
| C16 | Asked whether Docling/OCR preserves content into chunks and pgvector | Systems thinking; stage-level observability | Harness checks extraction, chunk retention, and database round-trip rather than retrieval alone |
| C17 | Asked why independent evidence labels are needed when citations already exist | Methodological scrutiny | Made the distinction explicit: generated citations are outputs; independent expected evidence is the reference |
| C18 | Explicitly requested correctness, completeness, faithfulness, and citation support on about 15 questions | Quality specification | 15 generated answers and four-dimension rubric; assistant reviews are not independent owner ratings |
| C19 | Required evaluation data in an evaluation folder, with test questions, evidence, and answer key separated | Reproducibility; information architecture | `evaluation/golden/` contains separate files; this separation is directly user-required |
| C20 | Required a new Bao Sheng branch from main, not the old branch; wanted interpretation before implementation | Change control; scope governance | Current branch `baosheng-feat-evaluation-harness`; branch history not re-audited in this document |
| C21 | Asked to clean up/namescope earlier committed files before proceeding | Maintainability; review hygiene | Organised follow-up commits listed below; no claim of eliminating all technical debt |
| C22 | Asked for simple explanations and challenged unclear results | Learning discipline; communication feedback | Required results to be understandable, not merely machine-generated artifacts |
| C23 | Suspected the filter kept headings/paragraphs/lists/tables but dropped arrows | Hypothesis-driven debugging | Diagnosis narrowed to useful `code` being filtered on p4 versus empty `picture` on p21 |
| C24 | Specifically requested fixing the extraction filtering loop | Targeted problem-solving; scope control | Implemented code-label preservation; 70/73 → 71/73 retained anchors |
| C25 | Asked for solutions to the remaining page-21 missing evidence | Persistence; limitation recognition | Still unresolved by filtering alone; no OCR/VLM fallback claimed as delivered |
| C26 | Asked to inspect “every methodology” and see how metrics decide right/wrong | Critical evaluation; auditability | Exact matcher and metric equations exposed, with automatic checks separate from semantic judgements |
| C27 | Proposed a script compiling scattered JSON into one intuitive file | Developer experience; human-in-the-loop design | Offline HTML compiler delivered; all 150 stored retrieval metric records recomputed consistently |
| C28 | Requested this measurable, resume-traceable contribution record | Outcome orientation; evidence communication | This document links decisions to code/results and separates proposals from measured impact |
| C29 | Reported login connectivity, slow indexing, failed indexing, and PDF preview problems with screenshots | Observational bug reporting; persistence | Follow-up reliability commits exist; screenshots alone do not establish root cause or performance gain |
| C30 | Asked how to test file replacement, noticed missing UI, and requested a Replace option first | End-to-end testability; product workflow reasoning | Replacement workflow work in `af7e413`; current evaluation run is not a replacement regression test |
| C31 | Shared a generated statistical summary and asked whether its quality was acceptable | User-centred AI quality review | Quality concern recorded; no formal before/after statistics-answer score established |

## 4. Earlier technical contributions — keep separate from today's measured work

| Contribution described by Bao Sheng | Defensible content | Qualification / evidence |
|---|---|---|
| PDF ingestion | Docling structure-aware extraction, removal of repetitive furniture, page/heading metadata | [Historical ingestion map](../contribution-interview-playbook.en.md); do not imply perfect structure preservation |
| Token-based chunking | Embedding-model tokenizer, nominal 350-token budget, page/section boundaries | Current [ingestion code](../../apps/api/app/services/ingestion.py); implementation evolved collaboratively |
| Resource APIs | CRUD/lifecycle operations for files, folders, and courses | Historical playbook contains commit-level mapping; not all methods necessarily use identical CRUD semantics |
| Original retrieval experiment | Approximately 20-page PDF, 20 questions, 350-vs-500-token comparison, top-five any-evidence check | User-reported; original “20/0” wording should be **20/20 = 100% Hit@5** if original artifact confirms it |
| Ceiling-effect recognition | Perfect any-evidence scores did not distinguish configurations | Explains why richer evidence coverage and answer review were requested; not a failure to be hidden |
| Stale replacement-content bug | Old ingestion runs remained active after file replacement; deactivate them to exclude outdated chunks | Historical commits `02e8647`, `9878edd`; no measured production incident reduction |
| Frontend integration | Reported contribution to frontend/backend integration and later replacement workflow | User explicitly said one integration phrase was hard to explain; review code before using as a primary story |

## 5. Hard skills demonstrated or developed

This is a record of practical engagement, not a claim of expert proficiency in every tool.

| Skill | Observable evidence | Interview proof to prepare |
|---|---|---|
| RAG ingestion and document models | Diagnosed label allow-list loss; distinguished `code` from empty `picture` | Explain why changing a filter cannot recover text Docling never emitted |
| Token-aware chunking | Discussed tokenizer/budget and requested formatting-preserving fix | Walk through boundaries, page metadata, and an over-budget input |
| Evaluation design | Requested stage checks, control corpus, separate keys, four answer dimensions | Explain answerable evidence groups, splits, denominators, and pilot limitations |
| Retrieval metrics | Engaged with ceiling effect and requested visible calculations | Calculate Hit@5 vs evidence recall vs complete evidence vs MRR by hand |
| PostgreSQL/pgvector verification | Explicitly asked to trace content into database storage | Distinguish persistence integrity from semantic embedding quality |
| Root-cause analysis | Suspected filtering rather than treating every failure as retrieval | Demonstrate one source → raw item → filtered item → chunk trace |
| Data provenance and reproducibility | Required folders/key separation; requested auditable compiled artifacts | Show hashes, configuration, run IDs, and why results from different runs stay separate |
| API/file lifecycle consistency | Described active-ingestion invalidation and replacement workflow | Explain version visibility, temporary unavailability, and non-atomic filesystem/DB updates |
| Testing and regression prevention | Requested actionable validation; targeted code-block checks added | Explain what unit checks prove and what still needs integration testing |
| Human-in-the-loop evaluation | Requested manual methodology audit and intuitive reporting | Show how owner disagreement is saved without silently rewriting baseline scores |
| Git workflow | Specified branch base and isolation requirements | Show correct branch and relevant diff; do not claim solo delivery of all commits |
| AI-assisted engineering | Iteratively challenged proposals, constrained scope, requested evidence | Explain which code/data the assistant produced and which decisions were yours |

## 6. Soft skills — behaviours, not unsupported adjectives

- **Initiative:** moved from interview preparation to requesting concrete project improvements.
- **Critical thinking:** challenged whether citations prove correctness, whether images
  are actually understood, and whether retrieval-only success hides extraction failures.
- **Learning agility:** repeatedly asked for simpler explanations and requested manual
  inspection rather than accepting metrics without understanding them.
- **Ownership:** required a personal branch based on main, explicit plan interpretation,
  organised evaluation artifacts, and a traceable record of decisions.
- **Collaboration and integrity:** brought a friend's advice, acknowledged teammate
  responsibilities, and objected to duplicate grounded-answer work being presented as his own.
- **Requirements communication:** specified separate answer/evidence keys, approximately
  15 reviewed answers, four quality dimensions, and a single intuitive review artifact.
- **Persistence:** followed failures from UI symptoms through indexing and extraction
  to specific label-handling issues; asked about unresolved misses instead of declaring victory.
- **Outcome orientation:** asked for measurable before/after impact and resume traceability.

None of these behaviours establishes formal people management, team leadership,
stakeholder approval, production adoption, or measured collaboration productivity.
Prefer “drove the evaluation requirements” to “led a team” unless there is other evidence.

## 7. Code and artifact traceability

| Evidence | Location / commit | Status |
|---|---|---|
| Existing authorship audit / interview stories | [English playbook](../contribution-interview-playbook.en.md), [Chinese coaching](../contribution-interview-coaching.zh-CN.md) | Historical audit; date/scope caveats inside |
| Chart extraction / Windows indexing follow-up | `f49e3f9` | Existing local commit; not proof this benchmark tests charts |
| Answer feedback / replacement workflows | `af7e413` | Existing local commit; no measured quality/business uplift |
| PDF preview resize-loop fix | `5563485` | Existing local commit; no quantified rendering improvement |
| Development tooling organisation | `bc206d7` | Existing local commit |
| Pipeline runner / metrics | [runner](../../apps/api/scripts/evaluate_pipeline.py), [scorer](../../apps/api/app/evaluation/metrics.py) | Local working-tree implementation |
| Golden corpus definition | [manifest](../../evaluation/corpus_manifest.json), [golden data](../../evaluation/golden/questions.json) | Assistant-authored labels require owner review |
| Complete baseline | `evaluation/runs/20261107T113258086748Z/` | Local ignored experiment outputs |
| Diagnostic Docling parse | `evaluation/runs/20261107T113635350705Z/` | Diagnostic reparse, not additional benchmark questions |
| Extraction-only after fix | `evaluation/runs/20261107T115210823381Z/` | No new retrieval/generation scores |
| Single-file review compiler | [script](../../apps/api/scripts/compile_evaluation_review.py), [template](../../apps/api/app/evaluation/review_template.html) | Local; does not call models or database |
| Owner-review aggregation | [script](../../apps/api/scripts/summarize_pipeline_reviews.py) | Pending fields are excluded, not treated as successes |

For durable resume traceability: review these changes, commit selected work after
approval, archive the run configuration/results with the same dataset hashes, and
record the eventual commit SHA here. Do not assume ignored local files travel with Git.

## 8. Proposed ideas versus delivered outcomes

The following came from friends, assistant suggestions, or the pasted technique
list; discussing them is not implementing them and does not establish original invention.

| Idea discussed | Current evidence-based position |
|---|---|
| Evaluation harness | Delivered locally with measured pilot; refined and directed by Bao Sheng |
| User feedback loop | Feedback implementation exists; no demonstrated feedback-driven model improvement |
| Evidence gate / query rewrite / retry | Discussed; do not claim a newly delivered corrective-RAG system from this work |
| Groundedness/confidence/citation verification | Existing teammate/system overlap; separate semantic support from syntactic quote checks |
| Page-level citations | Present in baseline outputs; no new measured citation-quality improvement claimed |
| Self-querying metadata filters | Proposed; no delivered evaluation in this work |
| Trace/cost dashboard | Retrieval traces/report delivered; provider token/cost tracking and production p95 are not established |
| HyDE, multi-query, decomposition, step-back, routing, adaptive RAG, Self-RAG, ReAct-style loops | Candidate techniques discussed, not implemented contributions here |
| Original-image / chart relationship extraction | Enablement discussed/committed; current text-only pilot cannot validate it |
| Vision/OCR fallback for page 21 | Remaining solution space; no delivered successful fix measured |
| Multi-file benchmark | Discussed but not yet measured in this single-PDF pilot |

## 9. Interview story — defendable 60-second version

> My earlier chunk-size experiment reached the same top-five hit rate for both
> configurations, so it did not tell us much about where the system was failing.
> I wanted a more diagnostic evaluation rather than just adding another AI technique.
>
> I drove the requirements for a stage-by-stage harness: separate question, answer,
> and evidence files; checks from extraction through chunks and database storage;
> and manual review of correctness, faithfulness, completeness, and citation support.
> I used an AI coding assistant for substantial implementation and dataset drafting,
> and required the results to be auditable rather than accepting generated scores.
>
> On our 38-page text-transcribed PDF, the evaluation exposed useful content that
> Docling labelled as code but our filter dropped. I asked for a targeted filter fix.
> Evidence retention increased from 70 out of 73 to 71 out of 73. Two misses remained
> in a picture region, so I would not claim we solved image understanding or improved
> downstream answers without another run.
>
> I also requested a single-file review report so I could inspect every judgement
> and calculation. The main lesson was to trace a quality issue to the stage that
> caused it, and distinguish measured improvement from assumptions.

Use “I can demonstrate” only after personally walking through the report and code.
Currently, the record demonstrates the request for owner review, not completion of it.

## 10. Next measurements that would strengthen the resume

These are a backlog, not outcomes to put on the resume today.

1. Personally review and version the gold labels; preserve disagreement reasons.
2. Rerun the full baseline protocol after the filtering fix with frozen labels and
   comparable settings. Report extraction, retrieval, answer quality, and latency separately.
3. Test a separately authored multi-document holdout to reduce ceiling effects and
   related-question leakage. Do not make questions harder solely to force a method to win.
4. Evaluate a page-21 recovery approach against source-grounded relationship checks,
   keeping text transcription and original-image understanding as separate experiments.
5. Record actual workflow time before claiming time saved by the audit report.
6. Add replacement A→B integration evidence before claiming stale-answer prevention
   as a measured end-to-end guarantee.
7. Freeze reviewed artifacts and link a commit/run archive so a resume reader can
   reproduce the claim rather than relying on this conversation.
