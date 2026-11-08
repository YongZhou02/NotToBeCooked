/**
 * The results matrix: one row per question (or per group of questions), one
 * column per measured score, every score on a 0-1 scale.
 *
 * `null` always means "not measured here" and is never averaged in as zero: an
 * unanswerable question has no evidence to retrieve, and a run without
 * generation has no answer to judge.
 */
import { questionSources } from "./questions"
import type { SourceDocument } from "./documents"
import type { Question, QuestionScores } from "../types"

export type MethodId = "hybrid_rrf" | "vector" | "keyword"

export interface MatrixColumn {
  id: string
  group: "Pipeline" | "Retrieval" | "Answer" | "AI judge"
  label: string
  help: string
  value: (scores: QuestionScores, method: MethodId) => number | null
}

const retrieval =
  (metric: string) =>
  (scores: QuestionScores, method: MethodId): number | null =>
    scores.retrieval?.[method]?.[metric] ?? null

const judged =
  (key: "correct" | "supported" | "useful") =>
  (scores: QuestionScores): number | null => {
    const value = scores.judge?.[key]
    return typeof value === "number" ? value / 2 : null
  }

export const COLUMNS: MatrixColumn[] = [
  {
    id: "extraction",
    group: "Pipeline",
    label: "Extracted",
    help: "Share of this question's gold quotes found word for word in the extracted PDF text.",
    value: (s) => s.extraction ?? null,
  },
  {
    id: "chunking",
    group: "Pipeline",
    label: "Chunk intact",
    help: "Share of its gold quotes that sit whole inside one chunk.",
    value: (s) => s.chunking ?? null,
  },
  {
    id: "hit@1",
    group: "Retrieval",
    label: "Hit@1",
    help: "1 if the first result holds any required evidence.",
    value: retrieval("hit@1"),
  },
  {
    id: "hit@5",
    group: "Retrieval",
    label: "Hit@5",
    help: "1 if any of the top five results holds any required evidence.",
    value: retrieval("hit@5"),
  },
  {
    id: "evidence_recall@5",
    group: "Retrieval",
    label: "Recall@5",
    help: "Share of the required evidence groups found in the top five.",
    value: retrieval("evidence_recall@5"),
  },
  {
    id: "complete_evidence@5",
    group: "Retrieval",
    label: "Complete@5",
    help: "1 only if every required evidence group is in the top five.",
    value: retrieval("complete_evidence@5"),
  },
  {
    id: "mrr@5",
    group: "Retrieval",
    label: "MRR@5",
    help: "1 / rank of the first matching result (1, 0.5, 0.33...), 0 if none in the top five.",
    value: retrieval("mrr@5"),
  },
  {
    id: "shown",
    group: "Answer",
    label: "Shown",
    help: "1 if the student saw the answer. 0 if the app's grounding check blocked it or the model call failed.",
    value: (s) =>
      s.answer_state ? (s.answer_state === "shown" ? 1 : 0) : null,
  },
  {
    id: "correct",
    group: "AI judge",
    label: "Correct",
    help: "Judge's correctness grade, 0-2 shown as 0-1. Blocked drafts are graded too.",
    value: judged("correct"),
  },
  {
    id: "supported",
    group: "AI judge",
    label: "Supported",
    help: "Judge's grade for how well the cited passages support the answer, 0-2 shown as 0-1.",
    value: judged("supported"),
  },
  {
    id: "useful",
    group: "AI judge",
    label: "Useful",
    help: "Judge's grade for how useful the answer is to a student, 0-2 shown as 0-1.",
    value: judged("useful"),
  },
]

export type GroupBy =
  | "question"
  | "split"
  | "category"
  | "origin"
  | "source"
  | "answerable"
  | "outcome"

export interface MatrixFilters {
  split: string
  category: string
  origin: string
  source: string
  answerable: string
  outcome: string
}

export const ALL: MatrixFilters = {
  split: "all",
  category: "all",
  origin: "all",
  source: "all",
  answerable: "all",
  outcome: "all",
}

export interface QuestionEntry {
  question: Question
  scores: QuestionScores
  sources: string[]
  outcome: string
}

const OUTCOME_LABEL: Record<string, string> = {
  shown: "Shown",
  blocked: "Blocked",
  failed: "Model call failed",
}

/** Questions the run actually scored, with the tags the filters work on. */
export function entriesForRun(
  questions: readonly Question[],
  runId: string,
  registry: readonly SourceDocument[]
): QuestionEntry[] {
  return questions.flatMap((question) => {
    const scores = question.traces?.[runId]?.scores
    if (!scores?.in_run) return []
    return [
      {
        question,
        scores,
        sources: [
          ...questionSources(registry, {
            evidence_groups: question.evidence_groups ?? [],
            source_document: question.source_document,
          }),
        ],
        outcome: scores.answer_state ?? "not generated",
      },
    ]
  })
}

export function filterEntries(
  entries: readonly QuestionEntry[],
  f: MatrixFilters
): QuestionEntry[] {
  return entries.filter(
    (e) =>
      (f.split === "all" || e.question.split === f.split) &&
      (f.category === "all" || e.question.category === f.category) &&
      (f.origin === "all" || (e.question.origin ?? "synthetic") === f.origin) &&
      (f.source === "all" || e.sources.includes(f.source)) &&
      (f.answerable === "all" ||
        String(e.question.answerable !== false) === f.answerable) &&
      (f.outcome === "all" || e.outcome === f.outcome)
  )
}

/** The values a group-by or filter can take, from the entries themselves. */
export function tagValues(
  entries: readonly QuestionEntry[],
  key: Exclude<GroupBy, "question">
): string[] {
  return [...new Set(entries.flatMap((e) => groupKeys(e, key)))].sort()
}

function groupKeys(
  e: QuestionEntry,
  key: Exclude<GroupBy, "question">
): string[] {
  switch (key) {
    case "split":
      return [e.question.split]
    case "category":
      return [e.question.category]
    case "origin":
      return [e.question.origin ?? "synthetic"]
    case "source":
      return e.sources.length ? e.sources : ["(no evidence)"]
    case "answerable":
      return [e.question.answerable === false ? "unanswerable" : "answerable"]
    case "outcome":
      return [OUTCOME_LABEL[e.outcome] ?? e.outcome]
  }
}

export interface Cell {
  /** Mean of the measured values, or null when none were measured. */
  value: number | null
  measured: number
  total: number
}

export interface MatrixRow {
  key: string
  label: string
  /** Set for question rows: open it in the Visualization tab. */
  questionId?: string
  question?: Question
  count: number
  cells: Record<string, Cell>
}

export function cellFor(
  entries: readonly QuestionEntry[],
  column: MatrixColumn,
  method: MethodId
): Cell {
  const values = entries
    .map((e) => column.value(e.scores, method))
    .filter((v): v is number => typeof v === "number")
  return {
    value: values.length
      ? values.reduce((a, b) => a + b, 0) / values.length
      : null,
    measured: values.length,
    total: entries.length,
  }
}

function row(
  key: string,
  label: string,
  entries: readonly QuestionEntry[],
  method: MethodId,
  extra: Partial<MatrixRow> = {}
): MatrixRow {
  return {
    key,
    label,
    count: entries.length,
    cells: Object.fromEntries(
      COLUMNS.map((c) => [c.id, cellFor(entries, c, method)])
    ),
    ...extra,
  }
}

export function buildRows(
  entries: readonly QuestionEntry[],
  groupBy: GroupBy,
  method: MethodId,
  labelFor: (key: Exclude<GroupBy, "question">, value: string) => string = (
    _,
    v
  ) => v
): MatrixRow[] {
  if (groupBy === "question") {
    return entries.map((e) =>
      row(e.question.id, e.question.question, [e], method, {
        questionId: e.question.id,
        question: e.question,
      })
    )
  }
  // A question with evidence in two PDFs counts in both source groups.
  const groups = new Map<string, QuestionEntry[]>()
  entries.forEach((e) =>
    groupKeys(e, groupBy).forEach((k) => {
      groups.set(k, [...(groups.get(k) ?? []), e])
    })
  )
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, list]) => row(k, labelFor(groupBy, k), list, method))
}

export function summaryRow(
  entries: readonly QuestionEntry[],
  method: MethodId
): MatrixRow {
  return row("__all", "All rows shown", entries, method)
}

export function sortRows(
  rows: MatrixRow[],
  columnId: string | null,
  direction: "asc" | "desc"
): MatrixRow[] {
  if (!columnId) return rows
  const sign = direction === "asc" ? 1 : -1
  // Not-measured cells always sink to the bottom, whichever way it sorts.
  return [...rows].sort((a, b) => {
    const x = a.cells[columnId]?.value
    const y = b.cells[columnId]?.value
    if (x == null && y == null) return 0
    if (x == null) return 1
    if (y == null) return -1
    return (x - y) * sign
  })
}

export function formatScore(value: number | null): string {
  if (value == null) return "–"
  if (value === 0 || value === 1) return String(value)
  return value.toFixed(2)
}

// ---------------------------------------------------------------------------
// Colour: red (0) -> neutral grey (0.5) -> teal (1), interpolated in OKLab so
// the middle stays grey instead of turning muddy brown. The poles pass the
// colour-vision-deficiency checks on the light surface; red-green would not.
// Every cell also prints its number, so colour is never the only signal.

export const SCALE = {
  low: "#c4423a",
  mid: "#f0efec",
  high: "#0b9483",
} as const

type Lab = [number, number, number]

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

const toLinear = (c: number) => {
  const v = c / 255
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
}
const fromLinear = (v: number) => {
  const c = v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055
  return Math.round(Math.min(1, Math.max(0, c)) * 255)
}

function rgbToOklab([r, g, b]: [number, number, number]): Lab {
  const [lr, lg, lb] = [toLinear(r), toLinear(g), toLinear(b)]
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb)
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb)
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

function oklabToRgb([L, A, B]: Lab): [number, number, number] {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3
  return [
    fromLinear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    fromLinear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    fromLinear(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ]
}

const LOW = rgbToOklab(hexToRgb(SCALE.low))
const MID = rgbToOklab(hexToRgb(SCALE.mid))
const HIGH = rgbToOklab(hexToRgb(SCALE.high))

const mix = (a: Lab, b: Lab, t: number): Lab => [
  a[0] + (b[0] - a[0]) * t,
  a[1] + (b[1] - a[1]) * t,
  a[2] + (b[2] - a[2]) * t,
]

function luminance([r, g, b]: [number, number, number]): number {
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b)
}

/** Background and readable text colour for a 0-1 score. */
export function scoreColors(value: number): {
  background: string
  color: string
} {
  const t = Math.min(1, Math.max(0, value))
  const lab = t < 0.5 ? mix(LOW, MID, t / 0.5) : mix(MID, HIGH, (t - 0.5) / 0.5)
  const rgb = oklabToRgb(lab)
  // Pick whichever ink contrasts more with this fill.
  const bg = luminance(rgb)
  const dark = (bg + 0.05) / (luminance([22, 32, 30]) + 0.05)
  const light = 1.05 / (bg + 0.05)
  return {
    background: `rgb(${rgb.join(" ")})`,
    color: dark >= light ? "#16201e" : "#ffffff",
  }
}
