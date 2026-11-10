import type {
  DashboardData,
  EvidenceGroup,
  HumanReview,
  Origin,
  Question,
} from "../types"
import { resolveDocument, type SourceDocument } from "./documents"
import type { Persisted } from "./storage"

/** A question with the reviewer's changes laid over the original. */
export interface ResolvedQuestion extends Question {
  origin: Origin
  is_hard_case: boolean
  verified: boolean
  is_edited: boolean
  evidence_groups: EvidenceGroup[]
  required_facts: string[]
  traces: NonNullable<Question["traces"]>
}

const hasOwn = (object: object, key: string) =>
  Object.prototype.hasOwnProperty.call(object, key)

// dashboard_data.json keeps each question's gold evidence inside its per-run
// traces, not at the top level. Gold evidence is the same in every run of a
// dataset, so the first trace is enough.
function evidenceGroupsFromTraces(q: Question): EvidenceGroup[] {
  const trace = Object.values(q.traces ?? {})[0]
  return (trace?.groups ?? []).map((g) => ({
    id: g.id,
    alternatives: g.alternatives ?? [],
  }))
}

/**
 * The original question with the reviewer's changes laid over it. Originals
 * are never rewritten, so an edit that is put back simply stops being an edit.
 */
export function resolveQuestion(
  p: Persisted,
  original: Question,
  defaultOrigin: Origin
): ResolvedQuestion {
  const q: Question = { ...original, ...(p.questionEdits[original.id] ?? {}) }
  const answerEdited = hasOwn(p.answerEdits, q.id)
  return {
    ...q,
    origin: q.origin || defaultOrigin,
    is_hard_case: Boolean(p.reviews[q.id]?.hard_case ?? q.is_hard_case),
    reference_answer: answerEdited
      ? (p.answerEdits[q.id] as string)
      : q.reference_answer,
    is_edited: answerEdited || hasOwn(p.questionEdits, q.id),
    verified: hasOwn(p.verifications, q.id)
      ? Boolean(p.verifications[q.id])
      : Boolean(q.verified),
    evidence_groups: q.evidence_groups ?? evidenceGroupsFromTraces(q),
    required_facts: q.required_facts ?? [],
    traces: q.traces ?? {},
  }
}

export function getAllQuestions(
  p: Persisted,
  data: DashboardData
): ResolvedQuestion[] {
  return [
    ...data.questions.map((q) => resolveQuestion(p, q, "synthetic")),
    ...p.customQuestions.map((q) => resolveQuestion(p, q, "human")),
  ]
}

export function originalQuestion(
  p: Persisted,
  data: DashboardData,
  id: string
): Question | undefined {
  return (
    data.questions.find((q) => q.id === id) ??
    p.customQuestions.find((q) => q.id === id)
  )
}

type EditableField =
  | "question"
  | "category"
  | "split"
  | "required_facts"
  | "evidence_groups"
  | "source_document"
const EDITABLE_FIELDS: EditableField[] = [
  "question",
  "category",
  "split",
  "required_facts",
  "evidence_groups",
  "source_document",
]

export type QuestionValues = Partial<Pick<Question, EditableField>> & {
  reference_answer?: string
}

function originalValue(original: Question, field: EditableField): unknown {
  if (field === "evidence_groups")
    return original.evidence_groups ?? evidenceGroupsFromTraces(original)
  if (field === "required_facts") return original.required_facts ?? []
  return original[field]
}

/** Stores only what differs from the original, for edits and imports alike. */
export function storeQuestionChanges(
  p: Persisted,
  data: DashboardData,
  id: string,
  values: QuestionValues
): Persisted {
  const original = originalQuestion(p, data, id)
  if (!original) return p

  const patch: Record<string, unknown> = {}
  EDITABLE_FIELDS.forEach((field) => {
    if (values[field] === undefined) return
    if (
      JSON.stringify(values[field]) !==
      JSON.stringify(originalValue(original, field))
    ) {
      patch[field] = values[field]
    }
  })

  const questionEdits = { ...p.questionEdits }
  if (Object.keys(patch).length > 0) questionEdits[id] = patch
  else delete questionEdits[id]

  const answerEdits = { ...p.answerEdits }
  if (values.reference_answer !== undefined) {
    if (values.reference_answer !== original.reference_answer)
      answerEdits[id] = values.reference_answer
    else delete answerEdits[id]
  }

  return { ...p, questionEdits, answerEdits }
}

/**
 * A question's sources are the PDFs its evidence points at, plus the document
 * it was written against (a human question may have no gold quote yet).
 */
export function questionSources(
  registry: readonly SourceDocument[],
  q: Pick<ResolvedQuestion, "evidence_groups" | "source_document">
): Set<string> {
  const ids = (q.evidence_groups ?? []).flatMap((g) =>
    (g.alternatives ?? []).map((alt) => alt.document_id)
  )
  if (q.source_document) ids.push(q.source_document)
  const out = new Set<string>()
  ids.forEach((id) => {
    const doc = resolveDocument(registry, id)
    if (doc) out.add(doc.id)
  })
  return out
}

export interface Filters {
  search: string
  split: "all" | "dev" | "test"
  origin: "all" | "human" | "synthetic"
  /** A source document id, or "all". */
  source: string
  verification: "all" | "verified" | "unverified"
  difficulty: "all" | "hard"
}

export const defaultFilters = (): Filters => ({
  search: "",
  split: "all",
  origin: "all",
  source: "all",
  verification: "all",
  difficulty: "all",
})

export function filtersAreDefault(f: Filters): boolean {
  const d = defaultFilters()
  return (Object.keys(d) as (keyof Filters)[]).every((k) => f[k] === d[k])
}

export function filterQuestions(
  all: ResolvedQuestion[],
  filters: Filters,
  registry: readonly SourceDocument[]
): ResolvedQuestion[] {
  const query = filters.search.toLowerCase().trim()
  return all.filter((q) => {
    if (filters.split !== "all" && q.split !== filters.split) return false
    if (filters.origin !== "all" && q.origin !== filters.origin) return false
    if (
      filters.source !== "all" &&
      !questionSources(registry, q).has(filters.source)
    )
      return false
    if (filters.difficulty === "hard" && !q.is_hard_case) return false
    if (filters.verification === "verified" && !q.verified) return false
    if (filters.verification === "unverified" && q.verified) return false
    if (query) {
      const hit =
        (q.id || "").toLowerCase().includes(query) ||
        (q.question || "").toLowerCase().includes(query) ||
        (q.reference_answer || "").toLowerCase().includes(query)
      if (!hit) return false
    }
    return true
  })
}

export interface SplitMetrics {
  questions: number
  evidence_groups: number
  golden_quotes: number
  verified: number
  unverified: number
  synthetic: number
  human: number
  categories: Record<string, number>
}

const blankMetrics = (questions = 0): SplitMetrics => ({
  questions,
  evidence_groups: 0,
  golden_quotes: 0,
  verified: 0,
  unverified: 0,
  synthetic: 0,
  human: 0,
  categories: {},
})

export interface AllMetrics {
  dev: SplitMetrics
  test: SplitMetrics
  total: SplitMetrics
}

export function computeSplitMetrics(questions: ResolvedQuestion[]): AllMetrics {
  const summary: AllMetrics = {
    dev: blankMetrics(),
    test: blankMetrics(),
    total: blankMetrics(questions.length),
  }
  questions.forEach((q) => {
    const part = q.split === "dev" ? summary.dev : summary.test
    const groupCount = (q.evidence_groups ?? []).length
    const quoteCount = (q.evidence_groups ?? []).reduce(
      (sum, group) => sum + (group.alternatives ?? []).length,
      0
    )
    for (const target of [part, summary.total]) {
      if (target !== summary.total) target.questions += 1
      target.evidence_groups += groupCount
      target.golden_quotes += quoteCount
      if (q.verified) target.verified += 1
      else target.unverified += 1
      if (q.origin === "human") target.human += 1
      else target.synthetic += 1
      const cat = q.category || "general"
      target.categories[cat] = (target.categories[cat] ?? 0) + 1
    }
  })
  return summary
}

export function newHumanId(): string {
  const stamp = Date.now().toString(36)
  const random = Math.random().toString(36).slice(2, 6)
  return `human-${stamp}-${random}`
}

/** The export file. Same shape as the old dashboard wrote, key for key. */
export function buildExportPayload(
  p: Persisted,
  data: DashboardData,
  selected: ResolvedQuestion[],
  now = new Date()
) {
  return {
    dataset: data.dataset.name,
    exported_at: now.toISOString(),
    metrics_summary: computeSplitMetrics(getAllQuestions(p, data)),
    questions: selected.map((q) => ({
      id: q.id,
      question: q.question,
      reference_answer: q.reference_answer,
      category: q.category,
      split: q.split,
      origin: q.origin,
      is_hard_case: q.is_hard_case,
      verified: q.verified,
      is_edited_by_human: q.is_edited,
      source_document: q.source_document,
      evidence_groups: q.evidence_groups,
      required_facts: q.required_facts,
      human_review: p.reviews[q.id] ?? null,
    })),
  }
}

export function exportFileName(count: number, now = new Date()): string {
  return `ntbc_evaluation_dataset_${now.toISOString().slice(0, 10)}_${count}q.json`
}

type Incoming = Question & {
  human_review?: HumanReview | null
  is_edited_by_human?: boolean
}

export type ImportResult =
  | { ok: true; next: Persisted; count: number }
  | { ok: false; message: string }

/**
 * Brings an exported file in. Questions this browser has never seen are added;
 * ones it already has take the file's wording; verified state and the review
 * are overwritten for each one.
 */
export function applyImport(
  start: Persisted,
  data: DashboardData,
  parsed: unknown
): ImportResult {
  const file = parsed as { questions?: unknown } | null
  if (!file || !Array.isArray(file.questions)) {
    return {
      ok: false,
      message: "Invalid format: expected a JSON file with a 'questions' array.",
    }
  }

  let p = start
  let count = 0
  for (const raw of file.questions as Incoming[]) {
    if (!raw || !raw.id) continue
    count++
    const q: Incoming = { ...raw }

    // Older human ids were a per-browser counter, so a teammate's human-001 is
    // not this browser's human-001 unless the text says so.
    const existing = p.customQuestions.find((cq) => cq.id === q.id)
    const clashes =
      existing &&
      /^human-\d{3}$/.test(q.id) &&
      resolveQuestion(p, existing, "human").question !== q.question
    if (clashes) q.id = newHumanId()

    if (!originalQuestion(p, data, q.id)) {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { human_review, is_edited_by_human, ...stored } = q
      p = { ...p, customQuestions: [...p.customQuestions, stored] }
    } else {
      p = storeQuestionChanges(p, data, q.id, {
        question: q.question,
        category: q.category,
        split: q.split,
        required_facts: q.required_facts,
        evidence_groups: q.evidence_groups,
        source_document: q.source_document,
        reference_answer: q.reference_answer,
      })
    }
    if (q.verified !== undefined) {
      p = {
        ...p,
        verifications: { ...p.verifications, [q.id]: Boolean(q.verified) },
      }
    }
    if (q.human_review) {
      p = { ...p, reviews: { ...p.reviews, [q.id]: q.human_review } }
    }
  }
  return { ok: true, next: p, count }
}
