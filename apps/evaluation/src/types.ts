/** Shapes of evaluation/dashboard/dashboard_data.json and of the saved edits. */

export type Origin = "human" | "synthetic"
export type Split = "dev" | "test" | "stress"
export type Decision = "approve" | "needs_revision" | "reject"

export interface EvidenceAlternative {
  document_id: string
  pdf_page: number
  quote: string
}

export interface EvidenceGroup {
  id?: string
  alternatives: EvidenceAlternative[]
}

export interface TraceGroup extends EvidenceGroup {
  extraction?: {
    exact?: boolean
    fuzzy_score?: number
    fuzzy_pass?: boolean
    matches?: unknown[]
  }
  chunking?: { intact?: boolean; matches?: unknown[] }
  retrieval?: Record<string, { ranks?: number[]; found?: boolean } | undefined>
}

export interface AssistantReview {
  faithfulness?: number | null
  correctness?: number | null
  completeness?: number | null
  citation_support?: number | null
}

/** One question's numbers in one run, built by build_dashboard_data.py. */
export interface QuestionScores {
  /** False when the run did not score this question at all. */
  in_run: boolean
  extraction?: number | null
  chunking?: number | null
  retrieval?: Record<string, Record<string, number> | undefined>
  answer_state?: "shown" | "blocked" | "failed" | null
  grounding_problems?: string[]
  judge?: {
    correct?: number | null
    supported?: number | null
    useful?: number | null
    refused?: boolean | null
    note?: string | null
  } | null
}

export interface RunTrace {
  run_id?: string
  scores?: QuestionScores
  groups?: TraceGroup[]
  context?: {
    chunks: unknown[]
    metrics?: Record<string, number>
  } | null
  citation?: unknown[]
  generation?: { answer?: string; grounded?: boolean } | null
  assistant_review?: AssistantReview | null
}

/** A question as stored in dashboard_data.json, or as a person wrote it. */
export interface Question {
  id: string
  question: string
  reference_answer: string
  category: string
  split: Split
  origin?: Origin
  verified?: boolean
  is_hard_case?: boolean
  source_document?: string
  required_facts?: string[]
  evidence_groups?: EvidenceGroup[]
  label_review?: Record<string, unknown>
  /** False for questions the notes cannot answer (the app should refuse). */
  answerable?: boolean
  author?: string | null
  traces?: Record<string, RunTrace>
}

export interface HumanReview {
  decision?: Decision
  question_clear?: boolean
  answer_correct?: boolean
  evidence_supports?: boolean
  hard_case?: boolean
  notes?: string
  updated_at?: string
}

export interface PhaseScore {
  id: string
  number: number
  label: string
  value: number | null
  metric: string
  status: string
  secondary: string
}

export interface RetrievalMethodScores {
  "evidence_recall@5": number
  "mrr@5": number
  "hit@1": number
  "complete_evidence@5": number
  median_retrieval_ms: number
}

export interface Run {
  id: string
  created_at?: string
  mode: string
  same_source_run_count: number
  questions_evaluated: number
  generation_answers: number
  phases: PhaseScore[]
  retrieval_methods?: Record<string, RetrievalMethodScores>
  generation_model?: string | null
  judge?: { model?: string | null; label?: string | null } | null
}

export interface DatasetDocument {
  id: string
  path: string
  sha256?: string
  pages?: number
  coverage?: string
}

export interface Dataset {
  name: string
  documents: DatasetDocument[]
}

export type ConcernStatus = "measured" | "partly_measured" | "not_measured"
export type ConcernSeverity = "high" | "medium" | "low" | "unknown"

export interface Concern {
  id: string
  title: string
  feels_like: string
  status: ConcernStatus
  severity: ConcernSeverity
  headline: string
  metrics?: { label: string; value: string; note?: string }[]
  examples?: { question_id: string; note?: string }[]
  how_measured?: string
}

export interface Concerns {
  run_id?: string
  items: Concern[]
}

export interface DashboardData {
  dataset: Dataset
  selected_run_id: string
  runs: Run[]
  questions: Question[]
  concerns?: Concerns
}
