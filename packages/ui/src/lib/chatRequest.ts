export interface ChatRequestClassification {
  intent: "question" | "document_summary"
  scopesCurrentDocument: boolean
}

const CURRENT_DOCUMENT_PATTERN = /\b(?:this|current|open)\s+(?:file|document)\b/
const WHOLE_DOCUMENT_ACTIONS = new Set([
  "condense",
  "quiz me",
  "simplify",
  "storyboard",
])
const SUMMARY_PATTERN =
  /\b(?:condense|summari[sz]e|overview|explain all(?: the)? concepts?)\b/

export function classifyChatRequest(text: string): ChatRequestClassification {
  const normalized = text.trim().toLowerCase()
  const referencesCurrentDocument = CURRENT_DOCUMENT_PATTERN.test(normalized)
  const isWholeDocumentAction = WHOLE_DOCUMENT_ACTIONS.has(normalized)
  const isDocumentSummary =
    isWholeDocumentAction || SUMMARY_PATTERN.test(normalized)

  return {
    intent: isDocumentSummary ? "document_summary" : "question",
    scopesCurrentDocument: isDocumentSummary || referencesCurrentDocument,
  }
}
