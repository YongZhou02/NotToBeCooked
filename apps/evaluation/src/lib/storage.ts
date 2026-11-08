import type { HumanReview, Question } from "../types"

// The same keys the old dashboard used, so edits already made in this browser
// carry over.
export const REVIEW_KEY = "ntbc-evaluation-human-reviews-v1"
export const VERIFICATION_KEY = "ntbc-evaluation-answer-verifications-v1"
export const ANSWER_EDITS_KEY = "ntbc-evaluation-answer-edits-v1"
export const CUSTOM_QUESTIONS_KEY = "ntbc-evaluation-custom-questions-v1"
export const QUESTION_EDITS_KEY = "ntbc-evaluation-question-edits-v1"

/** Everything a person has changed, over the original questions. */
export interface Persisted {
  reviews: Record<string, HumanReview>
  verifications: Record<string, boolean>
  answerEdits: Record<string, string>
  customQuestions: Question[]
  /** Per question, only the fields changed from the original. */
  questionEdits: Record<string, Partial<Question>>
}

export const emptyPersisted: Persisted = {
  reviews: {},
  verifications: {},
  answerEdits: {},
  customQuestions: [],
  questionEdits: {},
}

function read<T>(
  key: string,
  fallback: T,
  isValid: (v: unknown) => boolean
): T {
  try {
    const raw = localStorage.getItem(key)
    if (raw == null) return fallback
    const parsed: unknown = JSON.parse(raw)
    return isValid(parsed) ? (parsed as T) : fallback
  } catch {
    return fallback
  }
}

const isRecord = (v: unknown) =>
  typeof v === "object" && v !== null && !Array.isArray(v)

export function loadPersisted(): Persisted {
  return {
    reviews: read(REVIEW_KEY, {}, isRecord),
    verifications: read(VERIFICATION_KEY, {}, isRecord),
    answerEdits: read(ANSWER_EDITS_KEY, {}, isRecord),
    questionEdits: read(QUESTION_EDITS_KEY, {}, isRecord),
    customQuestions: read(CUSTOM_QUESTIONS_KEY, [], Array.isArray),
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private windows and full storage can refuse; the edit still holds in memory.
  }
}

/** Saves only the parts that changed. */
export function persistChanges(before: Persisted, after: Persisted) {
  if (before.reviews !== after.reviews) write(REVIEW_KEY, after.reviews)
  if (before.verifications !== after.verifications)
    write(VERIFICATION_KEY, after.verifications)
  if (before.answerEdits !== after.answerEdits)
    write(ANSWER_EDITS_KEY, after.answerEdits)
  if (before.questionEdits !== after.questionEdits)
    write(QUESTION_EDITS_KEY, after.questionEdits)
  if (before.customQuestions !== after.customQuestions)
    write(CUSTOM_QUESTIONS_KEY, after.customQuestions)
}

export type { HumanReview }
