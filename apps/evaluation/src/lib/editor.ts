import type { DashboardData, EvidenceGroup, Split } from "../types"
import {
  newHumanId,
  storeQuestionChanges,
  type QuestionValues,
  type ResolvedQuestion,
} from "./questions"
import type { Persisted } from "./storage"

export const CATEGORIES = [
  "definition",
  "exact",
  "paraphrase",
  "relationship",
  "multi_evidence",
  "hard_case",
]

/** What the editor holds while a question is being written or changed. */
export interface Draft {
  question: string
  reference_answer: string
  split: Split
  category: string
  is_hard_case: boolean
  verified: boolean
  source_document: string | undefined
  facts_text: string
  evidence_groups: EvidenceGroup[]
}

export interface EditorState {
  mode: "new" | "edit"
  id: string | null
  isHardCase?: boolean
  message: string
  draft: Draft
}

export function draftFromQuestion(q: ResolvedQuestion): EditorState {
  return {
    mode: "edit",
    id: q.id,
    message: "",
    draft: {
      question: q.question,
      reference_answer: q.reference_answer,
      split: q.split,
      category: q.category,
      is_hard_case: q.is_hard_case,
      verified: q.verified,
      source_document: q.source_document,
      facts_text: q.required_facts.join("\n"),
      evidence_groups: structuredClone(q.evidence_groups),
    },
  }
}

export function blankEvidenceGroup(
  docId: string,
  page: number,
  quote = ""
): EvidenceGroup {
  return { alternatives: [{ document_id: docId, pdf_page: page, quote }] }
}

export function blankDraft(
  isHardCase: boolean,
  docId: string,
  page: number,
  quote: string
): EditorState {
  return {
    mode: "new",
    id: null,
    isHardCase,
    message: "",
    draft: {
      question: "",
      reference_answer: "",
      split: "test",
      category: isHardCase ? "hard_case" : "definition",
      is_hard_case: isHardCase,
      verified: true,
      source_document: docId,
      facts_text: "",
      evidence_groups: [blankEvidenceGroup(docId, page, quote)],
    },
  }
}

export type SaveResult =
  | { ok: true; id: string; next: Persisted }
  | { ok: false; message: string }

/** Turns a finished draft into saved changes. Nothing is stored if it is not
 * finished. */
export function saveDraft(
  p: Persisted,
  data: DashboardData,
  editor: EditorState
): SaveResult {
  const { draft } = editor
  const question = draft.question.trim()
  const referenceAnswer = draft.reference_answer.trim()
  if (!question || !referenceAnswer) {
    return {
      ok: false,
      message: question ? "Enter an answer key." : "Enter a question.",
    }
  }

  const id = editor.mode === "edit" && editor.id ? editor.id : newHumanId()

  // Empty quotes are unfinished rows, not evidence.
  const groups = draft.evidence_groups
    .map((group) => ({
      id: group.id,
      alternatives: group.alternatives
        .map((alt) => ({
          document_id: alt.document_id,
          pdf_page: alt.pdf_page,
          quote: alt.quote.trim(),
        }))
        .filter((alt) => alt.quote),
    }))
    .filter((group) => group.alternatives.length > 0)

  const usedIds = new Set(groups.map((group) => group.id))
  let next = 1
  groups.forEach((group) => {
    if (group.id) return
    while (usedIds.has(`${id}-e${next}`)) next++
    group.id = `${id}-e${next}`
    usedIds.add(group.id)
  })

  const firstDocument = groups[0]?.alternatives[0]?.document_id
  const values: QuestionValues = {
    question,
    reference_answer: referenceAnswer,
    split: draft.split,
    category: draft.category,
    required_facts: draft.facts_text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    evidence_groups: groups,
    // Originals are sourced by their evidence alone, so they never gain this field.
    source_document: draft.source_document
      ? firstDocument || draft.source_document
      : undefined,
  }

  let after: Persisted
  if (editor.mode === "new") {
    after = {
      ...p,
      customQuestions: [
        ...p.customQuestions,
        {
          id,
          origin: "human",
          ...values,
          question,
          reference_answer: referenceAnswer,
          split: draft.split,
          category: draft.category,
          is_hard_case: draft.is_hard_case,
          traces: {},
        },
      ],
    }
  } else {
    after = storeQuestionChanges(p, data, id, values)
    after = {
      ...after,
      reviews: {
        ...after.reviews,
        [id]: { ...(after.reviews[id] ?? {}), hard_case: draft.is_hard_case },
      },
    }
  }
  after = {
    ...after,
    verifications: { ...after.verifications, [id]: draft.verified },
  }
  return { ok: true, id, next: after }
}
